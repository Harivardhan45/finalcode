import os
import io
import re
import csv
import json
import time
import traceback
import warnings
import requests
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fpdf import FPDF
from docx import Document
from dotenv import load_dotenv
from atlassian import Confluence
import google.generativeai as genai
from bs4 import BeautifulSoup
from io import BytesIO
import difflib
import base64

# Load environment variables
load_dotenv()

app = FastAPI(title="Confluence AI Assistant API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "https://finalcode-backend.onrender.com",  # Add your Render URL
        "https://finalcode-frontend.onrender.com",  # Add frontend domain
        "*"  # For development, you can allow all origins
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API key from environment
GEMINI_API_KEY = os.getenv("GENAI_API_KEY_1") or os.getenv("GENAI_API_KEY_2")
if not GEMINI_API_KEY:
    raise ValueError("No Gemini API key found in environment variables. Please set GENAI_API_KEY_1 or GENAI_API_KEY_2 in your .env file.")

# Configure Gemini AI
genai.configure(api_key=GEMINI_API_KEY)

# Pydantic models for request/response
class SearchRequest(BaseModel):
    space_key: str
    page_titles: List[str]
    query: str

class VideoRequest(BaseModel):
    video_url: Optional[str] = None
    space_key: str
    page_title: str
    question: Optional[str] = None

class CodeRequest(BaseModel):
    space_key: str
    page_title: str
    instruction: str
    target_language: Optional[str] = None

class ImpactRequest(BaseModel):
    space_key: str
    old_page_title: str
    new_page_title: str
    question: Optional[str] = None
    enable_stack_overflow_check: Optional[bool] = True

class DirectCodeImpactRequest(BaseModel):
    old_code: str
    new_code: str
    question: Optional[str] = None
    enable_stack_overflow_check: Optional[bool] = True

class PushToJiraConfluenceSlackRequest(BaseModel):
    summary: str
    video_title: str

class TestRequest(BaseModel):
    space_key: str
    code_page_title: str
    test_input_page_title: Optional[str] = None
    question: Optional[str] = None

class ImageRequest(BaseModel):
    space_key: str
    page_title: str
    image_url: str

class ImageSummaryRequest(BaseModel):
    space_key: str
    page_title: str
    image_url: Optional[str] = None
    summary: str
    question: str

class ChartRequest(BaseModel):
    space_key: str
    page_title: str
    image_url: Optional[str] = None
    table_html: Optional[str] = None
    excel_url: Optional[str] = None
    chart_type: str
    filename: str
    format: str

class ExportRequest(BaseModel):
    content: str
    format: str
    filename: str

class SaveToConfluenceRequest(BaseModel):
    space_key: Optional[str] = None
    page_title: str
    content: str
    mode: Optional[str] = "append"

class PreviewSaveToConfluenceRequest(BaseModel):
    space_key: Optional[str] = None
    page_title: str
    content: str
    mode: str

class PreviewSaveToConfluenceResponse(BaseModel):
    preview_content: str
    diff: str

class AnalyzeGoalRequest(BaseModel):
    goal: str
    available_pages: list[str]

class AnalyzeGoalResponse(BaseModel):
    tools: list[str]
    pages: list[str]
    reasoning: str

class TableSummaryRequest(BaseModel):
    space_key: str
    page_title: str
    table_html: str

class ExcelSummaryRequest(BaseModel):
    space_key: str
    page_title: str
    excel_url: str

# Helper functions
def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        "]+", flags=re.UNICODE)
    no_emoji = emoji_pattern.sub(r'', text)
    return no_emoji.encode('latin-1', 'ignore').decode('latin-1')

def clean_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n")

def init_confluence():
    try:
        return Confluence(
            url=os.getenv('CONFLUENCE_BASE_URL'),
            username=os.getenv('CONFLUENCE_USER_EMAIL'),
            password=os.getenv('CONFLUENCE_API_KEY'),
            timeout=10
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confluence initialization failed: {str(e)}")

# Export functions
def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, line)
    return io.BytesIO(pdf.output(dest='S').encode('latin1'))

def create_docx(text):
    doc = Document()
    for line in text.split('\n'):
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def create_csv(text):
    output = io.StringIO()
    writer = csv.writer(output)
    for line in text.strip().split('\n'):
        writer.writerow([line])
    return io.BytesIO(output.getvalue().encode())

def create_json(text):
    return io.BytesIO(json.dumps({"response": text}, indent=4).encode())

def create_html(text):
    html = f"<html><body><pre>{text}</pre></body></html>"
    return io.BytesIO(html.encode())

def create_txt(text):
    return io.BytesIO(text.encode())


def extract_timestamps_from_summary(summary):
    timestamps = []
    lines = summary.splitlines()
    collecting = False
    for line in lines:
        if "**Timestamps:**" in line or "Timestamps:" in line:
            collecting = True
            continue
        if collecting:
            if not line.strip() or line.strip().startswith("**"):
                break
            # match lines like "* [00:00-00:05] sentence" or "[00:00-00:05] sentence"
            match = re.match(r"^\*?\s*\[(\d{1,2}:\d{2}-\d{1,2}:\d{2})\]\s*(.*)", line.strip())
            if match:
                timestamp_text = f"[{match.group(1)}] {match.group(2)}"
                timestamps.append(timestamp_text)
            elif line.strip().startswith("*") or line.strip().startswith("-"):
                # fallback for bullet points
                timestamps.append(line.strip().lstrip("* -").strip())
            elif line.strip():
                # fallback for any non-empty line
                timestamps.append(line.strip())
    return timestamps

def auto_detect_space(confluence, space_key: Optional[str] = None) -> str:
    """
    If space_key is provided and valid, return it.
    If not provided, auto-detect:
      - If only one space exists, return its key.
      - If multiple, raise error to specify.
    """
    if space_key:
        return space_key
    spaces = confluence.get_all_spaces(start=0, limit=100)["results"]
    if len(spaces) == 1:
        return spaces[0]["key"]
    raise HTTPException(status_code=400, detail="Multiple spaces found. Please specify a space_key.")

def search_web_google(query, num_results=5):
    import os
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": query,
        "num": num_results
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json().get("items", [])
        if not results:
            return ""
        snippets = []
        for item in results:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            snippets.append(f"{title}\n{snippet}\n{link}")
        return "\n\n".join(snippets)
    except Exception as e:
        return f"❌ Google Search error: {e}"

def search_stack_overflow(query: str, num_results: int = 3) -> List[str]:
    """Search Stack Overflow API for relevant discussions"""
    try:
        import os
        STACK_OVERFLOW_API_KEY = os.getenv("STACK_OVERFLOW_API_KEY")
        
        # Stack Overflow API endpoint
        url = "https://api.stackexchange.com/2.3/search/advanced"
        
        params = {
            "site": "stackoverflow",
            "q": query,
            "sort": "votes",
            "order": "desc",
            "pagesize": num_results,
            "filter": "withbody",
            "key": STACK_OVERFLOW_API_KEY if STACK_OVERFLOW_API_KEY else None
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        links = []
        
        if "items" in data:
            for item in data["items"]:
                question_id = item.get("question_id")
                if question_id:
                    links.append(f"https://stackoverflow.com/questions/{question_id}")
        
        return links[:num_results]
        
    except Exception as e:
        print(f"Stack Overflow API error: {e}")
        # Fallback to mock links if API fails
        return [
            f"https://stackoverflow.com/questions/mock-{query.replace(' ', '-').lower()}-1",
            f"https://stackoverflow.com/questions/mock-{query.replace(' ', '-').lower()}-2"
        ]

def check_stack_overflow_risks(code_content: str) -> List[Dict[str, Any]]:
    """Check for risky patterns and deprecated features using Stack Overflow API"""
    try:
        # Common risky patterns and deprecated features to check for
        risk_patterns = [
            # JavaScript/Web patterns
            {
                "pattern": "eval\\(",
                "risk_level": "high",
                "description": "Use of eval() function is dangerous as it executes arbitrary code",
                "deprecation_warning": "eval() is considered dangerous and should be avoided",
                "alternative_suggestions": [
                    "Use JSON.parse() for parsing JSON data",
                    "Use Function constructor for dynamic code execution",
                    "Implement proper input validation and sanitization"
                ],
                "search_terms": ["javascript eval function security risks", "eval() dangerous code execution"]
            },
            {
                "pattern": "innerHTML\\s*=",
                "risk_level": "medium",
                "description": "Direct innerHTML assignment can lead to XSS attacks",
                "deprecation_warning": "innerHTML assignment without sanitization is risky",
                "alternative_suggestions": [
                    "Use textContent for text-only content",
                    "Use DOMPurify library for HTML sanitization",
                    "Use createElement and appendChild for DOM manipulation"
                ],
                "search_terms": ["innerHTML XSS security", "innerHTML vs textContent security"]
            },
            {
                "pattern": "document\\.write\\(",
                "risk_level": "high",
                "description": "document.write() can cause security issues and poor performance",
                "deprecation_warning": "document.write() is deprecated and should not be used",
                "alternative_suggestions": [
                    "Use DOM manipulation methods like createElement",
                    "Use innerHTML with proper sanitization",
                    "Use modern frameworks like React, Vue, or Angular"
                ],
                "search_terms": ["document.write deprecated", "document.write security issues"]
            },
            {
                "pattern": "setTimeout\\(.*,\\s*0\\)",
                "risk_level": "low",
                "description": "setTimeout with 0 delay can indicate potential race conditions",
                "alternative_suggestions": [
                    "Use Promise.resolve().then() for microtasks",
                    "Use requestAnimationFrame for UI updates",
                    "Consider using async/await patterns"
                ],
                "search_terms": ["setTimeout 0 delay race condition", "setTimeout vs Promise microtask"]
            },
            {
                "pattern": "console\\.log\\(",
                "risk_level": "low",
                "description": "Console.log statements should be removed in production code",
                "alternative_suggestions": [
                    "Use proper logging framework",
                    "Remove console.log statements before production",
                    "Use environment-based logging"
                ],
                "search_terms": ["console.log production code", "remove console.log before deployment"]
            },
            {
                "pattern": "var\\s+",
                "risk_level": "medium",
                "description": "var declarations have function scope and can cause hoisting issues",
                "deprecation_warning": "var is considered outdated in modern JavaScript",
                "alternative_suggestions": [
                    "Use const for values that won't be reassigned",
                    "Use let for values that will be reassigned",
                    "Prefer block scope over function scope"
                ],
                "search_terms": ["javascript var vs let const", "var hoisting issues"]
            },
            {
                "pattern": "\\bfor\\s*\\([^)]*var\\s+",
                "risk_level": "medium",
                "description": "var in for loops can cause closure issues",
                "alternative_suggestions": [
                    "Use let instead of var in for loops",
                    "Use forEach, map, or other array methods",
                    "Use for...of loops for iterables"
                ],
                "search_terms": ["var in for loop closure", "javascript for loop var let difference"]
            },
            # Python-specific patterns
            {
                "pattern": "exec\\(",
                "risk_level": "high",
                "description": "Use of exec() function is dangerous as it executes arbitrary code",
                "deprecation_warning": "exec() is considered dangerous and should be avoided",
                "alternative_suggestions": [
                    "Use ast.literal_eval() for safe evaluation",
                    "Use json.loads() for JSON data",
                    "Implement proper input validation and sanitization"
                ],
                "search_terms": ["python exec function security risks", "exec() dangerous code execution"]
            },
            {
                "pattern": "pickle\\.load\\(",
                "risk_level": "high",
                "description": "pickle.load() can execute arbitrary code and is unsafe for untrusted data",
                "deprecation_warning": "pickle.load() is dangerous for untrusted data",
                "alternative_suggestions": [
                    "Use json.load() for safe data deserialization",
                    "Use ast.literal_eval() for simple data structures",
                    "Implement custom serialization for complex objects"
                ],
                "search_terms": ["python pickle security risks", "pickle.load dangerous"]
            },
            {
                "pattern": "subprocess\\.run.*shell=True",
                "risk_level": "medium",
                "description": "subprocess.run with shell=True can execute arbitrary shell commands",
                "deprecation_warning": "shell=True is dangerous with user input",
                "alternative_suggestions": [
                    "Use subprocess.run with shell=False and list arguments",
                    "Use specific command execution libraries",
                    "Validate and sanitize all command inputs"
                ],
                "search_terms": ["python subprocess shell=True security", "subprocess shell injection"]
            },
            {
                "pattern": "input\\(",
                "risk_level": "medium",
                "description": "input() without validation can lead to injection attacks",
                "alternative_suggestions": [
                    "Validate and sanitize all user input",
                    "Use argparse for command-line arguments",
                    "Implement proper input validation"
                ],
                "search_terms": ["python input() security", "input validation python"]
            },
            {
                "pattern": "print\\(",
                "risk_level": "low",
                "description": "print() statements should be replaced with proper logging in production",
                "alternative_suggestions": [
                    "Use logging module for proper logging",
                    "Remove print statements before production",
                    "Use environment-based logging configuration"
                ],
                "search_terms": ["python print vs logging", "remove print statements production"]
            }
        ]
        
        found_risks = []
        
        for pattern_info in risk_patterns:
            if re.search(pattern_info["pattern"], code_content, re.IGNORECASE):
                # Search Stack Overflow for real discussions
                search_query = pattern_info.get("search_terms", [pattern_info["pattern"].replace('\\', '')])[0]
                stack_overflow_links = search_stack_overflow(search_query, 3)
                
                found_risks.append({
                    "pattern": pattern_info["pattern"].replace('\\', ''),
                    "risk_level": pattern_info["risk_level"],
                    "description": pattern_info["description"],
                    "stack_overflow_links": stack_overflow_links,
                    "alternative_suggestions": pattern_info["alternative_suggestions"],
                    "deprecation_warning": pattern_info.get("deprecation_warning")
                })
        
        return found_risks
        
    except Exception as e:
        print(f"Error in Stack Overflow risk check: {e}")
        return []

def hybrid_rag(prompt, api_key=None):
    import google.generativeai as genai
    if api_key:
        genai.configure(api_key=api_key)
    else:
        # fallback to default
        from os import getenv
        genai.configure(api_key=getenv('GENAI_API_KEY_1'))
    model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
    web_context = search_web_google(prompt)
    if not web_context.strip():
        response = model.generate_content(prompt)
        answer = response.parts[0].text.strip() if response.parts else "⚠️ No answer from Gemini."
        return answer, "llm"
    final_prompt = f"""
Use the following web search results to answer the question accurately.
If relevant, include links as citations.

Web Results:
{web_context}

Question: {prompt}

Answer:
"""
    try:
        response = model.generate_content(final_prompt)
        text = response.parts[0].text.strip() if response.parts else "⚠️ No answer from Gemini."
        if "do not contain" in text.lower():
            response = model.generate_content(prompt)
            answer = response.parts[0].text.strip() if response.parts else "⚠️ No fallback answer from Gemini."
            return answer, "llm"
        return text, "hybrid_rag"
    except Exception as e:
        return f"❌ Gemini error: {e}", "hybrid_rag"

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Confluence AI Assistant API", "status": "running"}

@app.get("/spaces")
async def get_spaces():
    """Get all available Confluence spaces"""
    try:
        confluence = init_confluence()
        
        spaces = confluence.get_all_spaces(start=0, limit=100)["results"]
        space_options = [{"name": s['name'], "key": s['key']} for s in spaces]
        
        return {"spaces": space_options}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pages/{space_key}")
async def get_pages(space_key: Optional[str] = None):
    """Get all pages from a specific space (auto-detect if not provided)"""
    try:
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, space_key)
        
        pages = confluence.get_all_pages_from_space(space=space_key, start=0, limit=100)
        page_titles = [p["title"] for p in pages]
        
        return {"pages": page_titles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def ai_powered_search(request: SearchRequest, req: Request):
    """AI Powered Search functionality"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))
        
        full_context = ""
        selected_pages = []
        
        # Get pages
        pages = confluence.get_all_pages_from_space(space=space_key, start=0, limit=100)
        selected_pages = [p for p in pages if p["title"] in request.page_titles]
        
        if not selected_pages:
            raise HTTPException(status_code=400, detail="No pages found")
        
        # Extract content from selected pages
        for page in selected_pages:
            page_id = page["id"]
            page_data = confluence.get_page_by_id(page_id, expand="body.storage")
            raw_html = page_data["body"]["storage"]["value"]
            text_content = clean_html(raw_html)
            full_context += f"\n\nTitle: {page['title']}\n{text_content}"
        
        # Generate AI response
        prompt = (
            f"Answer the following question using the provided Confluence page content as context.\n"
            f"Context:\n{full_context}\n\n"
            f"Question: {request.query}\n"
            f"Instructions: Begin with the answer based on the context above. Then, if applicable, supplement with general knowledge."
        )
        
        structured_prompt = (
            f"Answer the following question. If the provided context directly answers the question, use it. Otherwise, answer from your own knowledge. "
            f"Return your answer as JSON: {{'answer': <your answer>, 'supported_by_context': true/false, 'can_answer': true/false}}. "
            f"If the answer is not in the context but you can answer from your own knowledge, set 'supported_by_context' to false and 'can_answer' to true. "
            f"If you cannot answer at all, set both to false and return an empty or generic answer.\n"
            f"Context:\n{full_context}\n\n"
            f"Question: {request.query}"
        )
        response = ai_model.generate_content(structured_prompt)
        import json as _json
        source = "llm"
        try:
            result = _json.loads(response.text.strip())
            ai_response = result.get('answer', '').strip()
            supported = result.get('supported_by_context', False)
            can_answer = result.get('can_answer', True)
            if not supported and not can_answer:
                ai_response, source = hybrid_rag(request.query, api_key=api_key)
        except Exception:
            ai_response = response.text.strip()
            supported = None
            can_answer = True
            # Try ast.literal_eval for Python-style dict
            import ast, re
            try:
                result = ast.literal_eval(response.text.strip())
                if isinstance(result, dict):
                    ai_response = result.get('answer', '').strip()
                    supported = result.get('supported_by_context', False)
                    can_answer = result.get('can_answer', True)
                    if not supported and not can_answer:
                        ai_response, source = hybrid_rag(request.query, api_key=api_key)
            except Exception:
                # Regex fallback for supported_by_context: false and can_answer: false
                if re.search(r"supported_by_context['\"]?\s*[:=]\s*false", response.text.strip(), re.IGNORECASE) and re.search(r"can_answer['\"]?\s*[:=]\s*false", response.text.strip(), re.IGNORECASE):
                    ai_response, source = hybrid_rag(request.query, api_key=api_key)
            # If ast.literal_eval succeeded and ai_response is still a dict, extract 'answer'
            if isinstance(ai_response, dict):
                ai_response = ai_response.get('answer', '').strip()
            # If ai_response is still a string that looks like a dict, extract 'answer' value with regex
            elif isinstance(ai_response, str):
                match = re.search(r"['\"]?answer['\"]?\s*:\s*['\"]([^'\"]+)['\"]", ai_response)
                if match:
                    ai_response = match.group(1).strip()
        page_titles = [p["title"] for p in selected_pages]
        final_response = ai_response
        return {
            "response": final_response,
            "pages_analyzed": len(selected_pages),
            "page_titles": page_titles,
            "source": source
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/video-summarizer")
async def video_summarizer(request: VideoRequest, req: Request):
    """Video Summarizer functionality using AssemblyAI and Gemini"""
    import requests
    import tempfile
    import subprocess
    import shutil
    confluence = init_confluence()
    space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))

    # Get page info
    pages = confluence.get_all_pages_from_space(space=space_key, start=0, limit=100)
    selected_page = next((p for p in pages if p["title"] == request.page_title), None)
    if not selected_page:
        raise HTTPException(status_code=400, detail="Page not found")
    page_id = selected_page["id"]

    # Get attachments
    attachments = confluence.get(f"/rest/api/content/{page_id}/child/attachment?limit=50")
    video_attachment = None
    for att in attachments.get("results", []):
        if att["title"].lower().endswith(".mp4"):
            video_attachment = att
            break
    if not video_attachment:
        raise HTTPException(status_code=404, detail="No .mp4 video attachment found on this page.")

    # Download video
    video_url = video_attachment["_links"]["download"]
    full_url = f"{os.getenv('CONFLUENCE_BASE_URL').rstrip('/')}{video_url}"
    video_name = video_attachment["title"].replace(" ", "_")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, video_name)
        audio_path = os.path.join(tmpdir, "audio.mp3")
        # Download video file
        video_data = confluence._session.get(full_url).content
        with open(video_path, "wb") as f:
            f.write(video_data)
        # Extract audio using ffmpeg
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "mp3", audio_path
            ], check=True, capture_output=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ffmpeg audio extraction failed: {e}")
        # Upload audio to AssemblyAI
        assemblyai_api_key = os.getenv('ASSEMBLYAI_API_KEY')
        if not assemblyai_api_key:
            raise HTTPException(status_code=500, detail="AssemblyAI API key not configured. Please set ASSEMBLYAI_API_KEY in your environment variables.")
        headers = {"authorization": assemblyai_api_key}
        with open(audio_path, "rb") as f:
            upload_response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                data=f
            )
        if upload_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to upload audio to AssemblyAI")
        audio_url = upload_response.json()["upload_url"]
        # Submit for transcription
        transcript_request = {
            "audio_url": audio_url,
            "speaker_labels": True,
            "auto_chapters": True,
            "auto_highlights": True,
            "entity_detection": True,
            "sentiment_analysis": True
        }
        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json=transcript_request,
            headers={**headers, "content-type": "application/json"}
        )
        if transcript_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to submit audio for transcription")
        transcript_id = transcript_response.json()["id"]
        # Poll for completion
        while True:
            polling_response = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers
            )
            if polling_response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to get transcription status")
            status = polling_response.json()["status"]
            if status == "completed":
                break
            elif status == "error":
                raise HTTPException(status_code=500, detail="Transcription failed")
            time.sleep(3)
        transcript_data = polling_response.json()
        transcript_text = transcript_data.get("text", "")
        if not transcript_text:
            raise HTTPException(status_code=500, detail="No transcript text returned from AssemblyAI")
        
        # Initialize Gemini AI model for text generation
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        
        # Q&A
        if request.question:
            qa_prompt = (
                f"Based on the following video transcript, answer this question: {request.question}\n\n"
                f"Transcript: {transcript_text[:3000]}\n\n"
                f"Provide a detailed answer based on the video content."
            )
            qa_response = ai_model.generate_content(qa_prompt)
            return {"answer": qa_response.text.strip()}
        
        # Generate quotes
        quote_prompt = (
            "Extract 3-5 powerful or interesting quotes from the transcript.\n"
            "Format each quote on a new line starting with a dash (-).\n"
            f"Transcript:\n{transcript_text[:3000]}"
        )
        quotes_response = ai_model.generate_content(quote_prompt).text.strip()
        # Split quotes into individual items
        quotes = [quote.strip().lstrip("- ").strip() for quote in quotes_response.split('\n') if quote.strip()]
        
        # Generate summary WITHOUT timestamps
        summary_prompt = (
            "detailed paragraph summarizing the video content.\n"
            "Do NOT include any timestamps in the summary.\n"
            f"Transcript:\n{transcript_text[:3000]}"
        )
        summary = ai_model.generate_content(summary_prompt).text.strip()
        
        # Generate timestamps separately
        timestamp_prompt = (
            "Extract 5-7 important moments from the following transcript.\n"
            "Format each moment as: [MM:SS-MM:SS] Description of what happens\n"
            "Example: [00:15-00:30] Speaker introduces the main topic\n"
            "Return only the timestamps, one per line.\n\n"
            f"Transcript:\n{transcript_text[:3000]}"
        )
        timestamps_response = ai_model.generate_content(timestamp_prompt).text.strip()
        # Split timestamps into individual items
        timestamps = [ts.strip() for ts in timestamps_response.split('\n') if ts.strip()]
        
        return {
            "summary": summary,
            "quotes": quotes,
            "timestamps": timestamps,
            "qa": [],
            "page_title": request.page_title,
            "transcript": transcript_text[:1000] + "..." if len(transcript_text) > 1000 else transcript_text,
            "video_url": full_url
        }


@app.post("/code-assistant")
async def code_assistant(request: CodeRequest, req: Request):
    """Code Assistant functionality"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))
        
        # Get page content
        pages = confluence.get_all_pages_from_space(space=space_key, start=0, limit=100)
        selected_page = next((p for p in pages if p["title"] == request.page_title), None)
        
        if not selected_page:
            raise HTTPException(status_code=400, detail="Page not found")
        
        page_id = selected_page["id"]
        page_content = confluence.get_page_by_id(page_id, expand="body.storage")
        context = page_content["body"]["storage"]["value"]
        
        # Extract visible code
        soup = BeautifulSoup(context, "html.parser")
        for tag in soup.find_all(['pre', 'code']):
            code_text = tag.get_text()
            if code_text.strip():
                cleaned_code = code_text
                break
        else:
            cleaned_code = soup.get_text(separator="\n").strip()
        
        # Detect language
        def detect_language_from_content(content: str) -> str:
            if "<?xml" in content:
                return "xml"
            if "<html" in content.lower() or "<!DOCTYPE html>" in content:
                return "html"
            if content.strip().startswith("{") or content.strip().startswith("["):
                return "json"
            if re.search(r"\bclass\s+\w+", content) and "public" in content:
                return "java"
            if "#include" in content:
                return "cpp"
            if "def " in content:
                return "python"
            if "function" in content or "=>" in content:
                return "javascript"
            return "text"
        
        detected_lang = detect_language_from_content(cleaned_code)
        
        # Generate summary
        summary_prompt = (
            f"The following is content (possibly code or structure) from a Confluence page:\n\n{context}\n\n"
            "Summarize in detailed paragraph"
        )
        summary_response = ai_model.generate_content(summary_prompt)
        summary = summary_response.text.strip()
        
        # Modify code if instruction provided
        modified_code = None
        if request.instruction:
            alteration_prompt = (
                f"The following is a piece of code extracted from a Confluence page:\n\n{cleaned_code}\n\n"
                f"Please modify this code according to the following instruction:\n'{request.instruction}'\n\n"
                "Return the modified code only. No explanation or extra text."
            )
            altered_response = ai_model.generate_content(alteration_prompt)
            modified_code = re.sub(r"^```[a-zA-Z]*\n|```$", "", altered_response.text.strip(), flags=re.MULTILINE)
        
        # Convert to another language if requested
        converted_code = None
        if request.target_language and request.target_language != detected_lang:
            input_code = modified_code if modified_code else cleaned_code
            convert_prompt = (
                f"The following is a code structure or data snippet:\n\n{input_code}\n\n"
                f"Convert this into equivalent {request.target_language} code. Only show the converted code."
            )
            lang_response = ai_model.generate_content(convert_prompt)
            converted_code = re.sub(r"^```[a-zA-Z]*\n|```$", "", lang_response.text.strip(), flags=re.MULTILINE)
        
        return {
            "summary": summary,
            "original_code": cleaned_code,
            "detected_language": detected_lang,
            "modified_code": modified_code,
            "converted_code": converted_code,
            "target_language": request.target_language
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/impact-analyzer")
async def impact_analyzer(request: ImpactRequest, req: Request):
    """Impact Analyzer functionality"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))
        
        # Get pages
        pages = confluence.get_all_pages_from_space(space=space_key, start=0, limit=100)
        old_page = next((p for p in pages if p["title"] == request.old_page_title), None)
        new_page = next((p for p in pages if p["title"] == request.new_page_title), None)
        
        if not old_page or not new_page:
            raise HTTPException(status_code=400, detail="One or both pages not found")
        
        # Extract content from pages
        def extract_content(content):
            soup = BeautifulSoup(content, 'html.parser')
            # Try to find code blocks first
            code_blocks = soup.find_all('ac:structured-macro', {'ac:name': 'code'})
            if code_blocks:
                return '\n'.join(
                    block.find('ac:plain-text-body').text
                    for block in code_blocks if block.find('ac:plain-text-body')
                )
            # If no code blocks, extract all text content
            return soup.get_text(separator="\n").strip()
        
        old_raw = confluence.get_page_by_id(old_page["id"], expand="body.storage")["body"]["storage"]["value"]
        new_raw = confluence.get_page_by_id(new_page["id"], expand="body.storage")["body"]["storage"]["value"]
        old_content = extract_content(old_raw)
        new_content = extract_content(new_raw)
        
        if not old_content or not new_content:
            raise HTTPException(status_code=400, detail="No content found in one or both pages")
        
        # Generate diff
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        diff = difflib.unified_diff(old_lines, new_lines, fromfile=request.old_page_title, tofile=request.new_page_title, lineterm='')
        full_diff_text = '\n'.join(diff)
        
        # Calculate metrics
        lines_added = sum(1 for l in full_diff_text.splitlines() if l.startswith('+') and not l.startswith('+++'))
        lines_removed = sum(1 for l in full_diff_text.splitlines() if l.startswith('-') and not l.startswith('---'))
        total_lines = len(old_lines) or 1
        percent_change = round(((lines_added + lines_removed) / total_lines) * 100, 2)
        
        # Generate AI analysis
        def clean_and_truncate_prompt(text, max_chars=10000):
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'[^\x00-\x7F]+', '', text)
            return text[:max_chars]
        
        safe_diff = clean_and_truncate_prompt(full_diff_text)
        
        # Impact analysis
        impact_prompt = f"""Write 2 paragraphs summarizing the overall impact of the following changes between two versions of a document.
        
        Cover only:
        - What was changed
        - Which parts of the content are affected
        - Why this matters
        
        Keep it within 20 sentences.
        
        Changes:
        {safe_diff}"""
        
        impact_response = ai_model.generate_content(impact_prompt)
        impact_text = impact_response.text.strip()
        
        # Recommendations
        rec_prompt = f"""As a senior analyst, write 2 paragraphs suggesting improvements for the following changes.

        Focus on:
        - Content quality
        - Clarity and completeness
        - Any possible enhancements
        
        Limit to 20 sentences.
        
        Changes:
        {safe_diff}"""
        
        rec_response = ai_model.generate_content(rec_prompt)
        rec_text = rec_response.text.strip()
        
        # Risk analysis
        risk_prompt = f"Assess the risk of each change in this document diff with severity tags (Low, Medium, High):\n\n{safe_diff}"
        risk_response = ai_model.generate_content(risk_prompt)
        raw_risk = risk_response.text.strip()
        risk_text = re.sub(
            r'\b(Low|Medium|High)\b',
            lambda m: {
                'Low': '🟢 Low',
                'Medium': '🟡 Medium',
                'High': '🔴 High'
            }[m.group(0)],
            raw_risk
        )
        
        # Generate structured risk factors (new dynamic part)
        risk_factors_prompt = f"""
        Analyze the following code/content diff and extract a structured list of key risk factors introduced by these changes.

        Focus on identifying:
        - Broken or removed validation
        - Modified authentication/authorization checks
        - Logical regressions
        - Removed error handling
        - Performance or scalability risks
        - Security vulnerabilities
        - Stability or maintainability concerns

        Write each risk factor as 1 line. Avoid repeating obvious stats like line count.

        Diff:
        {safe_diff}
        """

        risk_factors_response = ai_model.generate_content(risk_factors_prompt)
        risk_factors = risk_factors_response.text.strip().split("\n")
        risk_factors = [re.sub(r"^[\*\-•\s]+", "", line).strip() for line in risk_factors if line.strip()]



        # Stack Overflow Risk Check
        stack_overflow_risks = []
        if getattr(request, 'enable_stack_overflow_check', True):
            # Check both old and new content for risks
            combined_content = f"{old_content}\n{new_content}"
            stack_overflow_risks = check_stack_overflow_risks(combined_content)

        # Q&A if question provided
        qa_answer = None
        if request.question:
            context = (
                f"Summary: {impact_text[:1000]}\n"
                f"Recommendations: {rec_text[:1000]}\n"
                f"Risks: {risk_text[:1000]}\n"
                f"Changes: +{lines_added}, -{lines_removed}, ~{percent_change}%"
            )
            qa_prompt = f"""You are an expert AI assistant. Based on the report below, answer the user's question clearly.

{context}

Question: {request.question}

Answer:"""
            qa_response = ai_model.generate_content(qa_prompt)
            qa_answer = qa_response.text.strip()
            
        
        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "files_changed": 1,
            "percentage_change": percent_change,
            "impact_analysis": impact_text,
            "recommendations": rec_text,
            "risk_analysis": risk_text,
            "risk_level": "low" if percent_change < 10 else "medium" if percent_change < 30 else "high",
            "risk_score": min(10, max(1, round(percent_change / 10))),
            "risk_factors": risk_factors,
            "answer": qa_answer,
            "diff": full_diff_text,
            "stack_overflow_risks": stack_overflow_risks
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/direct-code-impact-analyzer")
async def direct_code_impact_analyzer(request: DirectCodeImpactRequest, req: Request):
    """Direct Code Impact Analyzer functionality - analyzes code without requiring Confluence pages"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        
        old_content = request.old_code
        new_content = request.new_code
        
        if not old_content or not new_content:
            raise HTTPException(status_code=400, detail="Both old and new code must be provided")
        
        # Generate diff
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        diff = difflib.unified_diff(old_lines, new_lines, fromfile="original_code", tofile="modified_code", lineterm='')
        full_diff_text = '\n'.join(diff)
        
        # Calculate metrics
        lines_added = sum(1 for l in full_diff_text.splitlines() if l.startswith('+') and not l.startswith('+++'))
        lines_removed = sum(1 for l in full_diff_text.splitlines() if l.startswith('-') and not l.startswith('---'))
        total_lines = len(old_lines) or 1
        percent_change = round(((lines_added + lines_removed) / total_lines) * 100, 2)
        
        # Generate AI analysis
        def clean_and_truncate_prompt(text, max_chars=10000):
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'[^\x00-\x7F]+', '', text)
            return text[:max_chars]
        
        safe_diff = clean_and_truncate_prompt(full_diff_text)
        
        # Impact analysis
        impact_prompt = f"""Write 2 paragraphs summarizing the overall impact of the following changes between two versions of code.
        
        Cover only:
        - What was changed
        - Which parts of the code are affected
        - Why this matters
        
        Keep it within 20 sentences.
        
        Changes:
        {safe_diff}"""
        
        impact_response = ai_model.generate_content(impact_prompt)
        impact_text = impact_response.text.strip()
        
        # Recommendations
        rec_prompt = f"""As a senior developer, write 2 paragraphs suggesting improvements for the following code changes.

        Focus on:
        - Code quality
        - Performance and efficiency
        - Best practices
        - Any possible enhancements
        
        Limit to 20 sentences.
        
        Changes:
        {safe_diff}"""
        
        rec_response = ai_model.generate_content(rec_prompt)
        rec_text = rec_response.text.strip()
        
        # Risk analysis
        risk_prompt = f"Assess the risk of each change in this code diff with severity tags (Low, Medium, High):\n\n{safe_diff}"
        risk_response = ai_model.generate_content(risk_prompt)
        raw_risk = risk_response.text.strip()
        risk_text = re.sub(
            r'\b(Low|Medium|High)\b',
            lambda m: {
                'Low': '🟢 Low',
                'Medium': '🟡 Medium',
                'High': '🔴 High'
            }[m.group(0)],
            raw_risk
        )
        
        # Generate structured risk factors
        risk_factors_prompt = f"""
        Analyze the following code changes and extract specific risk factors. Return only a list of risk factors, one per line, starting with "- ":
        
        {safe_diff}
        
        Focus on:
        - Breaking changes
        - Performance impacts
        - Security vulnerabilities
        - Maintainability issues
        - Compatibility problems
        """
        
        risk_factors_response = ai_model.generate_content(risk_factors_prompt)
        risk_factors = [line.strip()[2:] for line in risk_factors_response.text.strip().split('\n') if line.strip().startswith('- ')]
        
        # QA response if question provided
        qa_answer = ""
        if request.question:
            qa_prompt = f"""Answer this specific question about the code changes: "{request.question}"

            Code changes:
            {safe_diff}
            
            Provide a concise, direct answer."""
            qa_response = ai_model.generate_content(qa_prompt)
            qa_answer = qa_response.text.strip()
        
        # Stack Overflow risk check if enabled
        stack_overflow_risks = []
        if getattr(request, 'enable_stack_overflow_check', True):
            combined_content = f"{old_content}\n{new_content}"
            stack_overflow_risks = check_stack_overflow_risks(combined_content)
        
        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "files_changed": 1,
            "percentage_change": percent_change,
            "impact_analysis": impact_text,
            "recommendations": rec_text,
            "risk_analysis": risk_text,
            "risk_level": "low" if percent_change < 10 else "medium" if percent_change < 30 else "high",
            "risk_score": min(10, max(1, round(percent_change / 10))),
            "risk_factors": risk_factors,
            "answer": qa_answer,
            "diff": full_diff_text,
            "stack_overflow_risks": stack_overflow_risks
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/push-to-jira-confluence-slack")
async def push_to_jira_confluence_slack(request: PushToJiraConfluenceSlackRequest, req: Request):
    """Push extracted tasks from video summary to Jira, Confluence, and Slack"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        
        
        CONFLUENCE_USER_EMAIL = os.getenv("CONFLUENCE_USER_EMAIL")
        CONFLUENCE_API_KEY = os.getenv("CONFLUENCE_API_KEY")
        CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
        CONFLUENCE_PAGE_ID = "15073281"  
        CONFLUENCE_SPACE_KEY = "MFS"  
        
        JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
        JIRA_EMAIL = os.getenv("JIRA_EMAIL")
        JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
        JIRA_PROJECT_KEY = "MFS"  
        
        SLACK_TOKEN = os.getenv("SLACK_TOKEN")
        SLACK_CHANNEL = "#new-channel"  
        
        # Extract tasks using Gemini
        prompt = f"""
You are an assistant extracting action items from meeting notes.

Please respond ONLY with a JSON array in this exact format, without any extra text or explanation:
[
  {{
    "task": "Task description",
    "assignee": "Person responsible",
    "due": "YYYY-MM-DD"
  }}
]

Meeting Notes:
{request.summary}
"""
        
        response = ai_model.generate_content(prompt)
        output = response.text.strip()

        if output.startswith("```"):
            output = output.split("```")[1].strip()
            if output.lower().startswith("json"):
                output = "\n".join(output.split("\n")[1:]).strip()

        tasks = json.loads(output)
        
        # Helper functions
        def get_next_version(page_id: str) -> int:
            auth = base64.b64encode(f"{CONFLUENCE_USER_EMAIL}:{CONFLUENCE_API_KEY}".encode()).decode()
            res = requests.get(
                f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}",
                headers={"Authorization": f"Basic {auth}"}
            )
            if res.status_code == 200:
                return res.json()["version"]["number"] + 1
            return 1

        def update_confluence_page(page_id: str, title: str, tasks: list):
            auth = base64.b64encode(f"{CONFLUENCE_USER_EMAIL}:{CONFLUENCE_API_KEY}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json"
            }

            table_html = "<table><tr><th>Task</th><th>Assignee</th><th>Due</th><th>Jira</th></tr>"
            for item in tasks:
                link_html = f"<a href='{item.get('link', '#')}' target='_blank'>View</a>" if "link" in item else "—"
                table_html += f"<tr><td>{item['task']}</td><td>{item['assignee']}</td><td>{item['due']}</td><td>{link_html}</td></tr>"
            table_html += "</table>"

            version = get_next_version(page_id)
            payload = {
                "version": {"number": version},
                "title": title,
                "type": "page",
                "body": {
                    "storage": {
                        "value": table_html,
                        "representation": "storage"
                    }
                }
            }

            response = requests.put(
                f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}",
                headers=headers,
                json=payload
            )
            return response.status_code == 200

        def create_jira_issue(summary: str, description: str, assignee: str) -> str:
            url = f"{JIRA_BASE_URL}/rest/api/3/issue"
            auth = (JIRA_EMAIL, JIRA_API_TOKEN)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            adf_description = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            }

            payload = {
                "fields": {
                    "project": {"key": JIRA_PROJECT_KEY},
                    "summary": summary,
                    "description": adf_description,
                    "issuetype": {"name": "Task"},
                    "assignee": {"emailAddress": assignee}
                }
            }

            response = requests.post(url, headers=headers, auth=auth, json=payload)
            print("🔄 Jira response:", response.status_code, response.text)

            if response.status_code == 201:
                return response.json()["key"]
            else:
                return None

        def send_slack_notification(task: dict, issue_key: str, issue_link: str):
            message = f"""
📝 *New AI Task Created!*
*Task:* {task['task']}
*Assignee:* {task['assignee']}
*Due:* {task['due']}
🔗 *Jira:* <{issue_link}|{issue_key}>
"""

            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "channel": SLACK_CHANNEL,
                    "text": message
                }
            )
            print("📤 Slack response:", response.status_code, response.text)
        
        # Process tasks
        task_links = []
        for task in tasks:
            issue_key = create_jira_issue(
                summary=task["task"],
                description=f"Auto-created from video: {request.video_title}. Due: {task['due']}",
                assignee=task["assignee"]
            )
            if issue_key:
                jira_link = f"{JIRA_BASE_URL}/browse/{issue_key}"
                task_links.append({**task, "link": jira_link})
                send_slack_notification(task, issue_key, jira_link)
            else:
                task_links.append({**task, "link": "❌ Jira issue failed"})

        # Update Confluence
        success = update_confluence_page(
            page_id=CONFLUENCE_PAGE_ID,
            title="Action Tracker – AI Updated",
            tasks=task_links
        )

        return {
            "success": success,
            "tasks_created": len(tasks),
            "jira_issues_created": len([t for t in task_links if "❌" not in t.get("link", "")]),
            "confluence_updated": success,
            "slack_notifications_sent": len([t for t in task_links if "❌" not in t.get("link", "")])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-support")
async def test_support(request: TestRequest, req: Request):
    """Test Support Tool functionality"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        print(f"Test support request: {request}")  # Debug log
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))
        
        # Get code page
        pages = confluence.get_all_pages_from_space(space=space_key, start=0, limit=50)
        code_page = next((p for p in pages if p["title"] == request.code_page_title), None)
        
        if not code_page:
            raise HTTPException(status_code=400, detail="Code page not found")
        
        print(f"Found code page: {code_page['title']}")  # Debug log
        
        code_data = confluence.get_page_by_id(code_page["id"], expand="body.storage")
        code_content = code_data["body"]["storage"]["value"]
        
        print(f"Code content length: {len(code_content)}")  # Debug log
        
        # Generate test strategy
        prompt_strategy = f"""The following is a code snippet:\n\n{code_content[:2000]}\n\nPlease generate a **structured test strategy** for the above code using the following format. 

Make sure each section heading is **clearly labeled** and includes a **percentage estimate** of total testing effort and the total of all percentage values across Unit Test, Integration Test, and End-to-End (E2E) Test must add up to exactly **100%**. Each subpoint should be short (1–2 lines max). Use bullet points for clarity.

---


## Unit Test (xx%)
- **Coverage Areas**:  
  - What functions or UI elements are directly tested?  
- **Edge Cases**:  
  - List 2–3 specific edge conditions or unusual inputs.

## Integration Test (xx%)
- **Integrated Modules**:  
  - What parts of the system work together and need testing as a unit?  
- **Data Flow Validation**:  
  - How does data move between components or layers?

## End-to-End (E2E) Test (xx%)
- **User Scenarios**:  
  - Provide 2–3 user flows that simulate real usage.  
- **System Dependencies**:  
  - What systems, APIs, or services must be operational?

## Test Data Management
- **Data Requirements**:  
  - What test data (e.g., users, tokens, inputs) is needed?  
- **Data Setup & Teardown**:  
  - How is test data created and removed?

## Automation Strategy
- **Frameworks/Tools**:  
  - Recommend tools for each test level.  
- **CI/CD Integration**:  
  - How will tests be included in automated pipelines?

## Risk Areas Identified
- **Complex Logic**:  
  - Highlight any logic that's error-prone or tricky.  
- **Third-Party Dependencies**:  
  - Any reliance on external APIs or libraries?  
- **Security/Critical Flows**:  
  - Mention any data protection or authentication flows.

## Additional Considerations
- **Security**:  
  - Are there vulnerabilities or security-sensitive operations?  
- **Accessibility**:  
  - Are there any compliance or usability needs?  
- **Performance**:  
  - Should speed, responsiveness, or load handling be tested?

---

Please format your response exactly like this structure, using proper markdown headings, short bullet points, and estimated test effort percentages. """

        response_strategy = ai_model.generate_content(prompt_strategy)
        strategy_text = response_strategy.text.strip()
        
        print(f"Strategy generated: {len(strategy_text)} chars")  # Debug log
        
        # Generate cross-platform testing
        prompt_cross_platform = f"""You are a cross-platform UI testing expert. Analyze the following frontend code and generate a detailed cross-platform test strategy using the structure below. Your insights should be **relevant to the code**, not generic. Code:\n\n{code_content[:2000]}\n\nFollow the format strictly and customize values based on the code analysis. Avoid repeating default phrases — provide actual testing considerations derived from the code.

---


## Platform Coverage Assessment

### Web Browsers
- **Chrome**: [Insert expected behavior or issues specific to the code]  
- **Firefox**: [Insert any rendering quirks, compatibility notes, or enhancements]  
- **Safari**: [Highlight any issues with WebKit or mobile Safari]  
- **Edge**: [Mention compatibility or layout differences]  
- **Mobile Browsers**: [Describe responsive behavior, touch issues, or layout breaks]  

### Operating Systems
- **Windows**: [Describe any dependency or rendering issues noticed]  
- **macOS**: [Note differences in rendering, fonts, or interactions]  
- **Linux**: [Mention support in containerized or open environments]  
- **Mobile iOS**: [Identify areas needing testing on Safari iOS or WebView]  
- **Android**: [Highlight performance, scrolling, or viewport concerns]  

### Device Categories
- **Desktop**: [List full UI/feature behavior on large screens]  
- **Tablet**: [Mention any layout shifting, input mode support, or constraints]  
- **Mobile**: [List responsiveness issues or changes in UI behavior]  
- **Accessibility**: [Accessibility tags, ARIA usage, screen reader compatibility]  

## Testing Approach

### Automated Cross-Platform Testing
- **Browser Stack Integration**: [Which browsers/devices to target and why]  
- **Device Farm Testing**: [Recommend real-device scenarios to validate]  
- **Performance Benchmarking**: [How platform differences might affect performance]  

### Manual Testing Strategy
- **User Acceptance Testing**: [Suggest user workflows to validate on each platform]  
- **Accessibility Testing**: [Mention checks like tab order, ARIA roles, color contrast]  
- **Localization Testing**: [If text/UI is dynamic, how to test translations or RTL]  

## Platform-Specific Considerations

### Performance Optimization
- **Mobile**: [Mention any heavy assets, unused JS/CSS, or optimizations needed]  
- **Desktop**: [Advanced UI behaviors or feature flags that only show on desktop]  
- **Tablets**: [Navigation patterns or split-view compatibility]  

### Security Implications
- **iOS**: [Any app/webview permissions or secure storage issues]  
- **Android**: [Issues with file access, permissions, or deep linking]  
- **Web**: [CSP, HTTPS enforcement, token handling or XSS risks]  

---

Respond **exactly** in this format with dynamic insights, no extra text outside the structure. """


        response_cross_platform = ai_model.generate_content(prompt_cross_platform)
        cross_text = response_cross_platform.text.strip()
        
        print(f"Cross-platform generated: {len(cross_text)} chars")  # Debug log
        
        # Sensitivity analysis if test input page provided
        sensitivity_text = None
        if request.test_input_page_title:
            test_input_page = next((p for p in pages if p["title"] == request.test_input_page_title), None)
            if test_input_page:
                test_data = confluence.get_page_by_id(test_input_page["id"], expand="body.storage")
                test_input_content = test_data["body"]["storage"]["value"]
                
                prompt_sensitivity = f"""You are a data privacy expert. Classify sensitive fields (PII, credentials, financial) and provide masking suggestions.Also, don't include comments if any code is present.\n\nData:\n{test_input_content[:2000]}"""



                response_sensitivity = ai_model.generate_content(prompt_sensitivity)
                sensitivity_text = response_sensitivity.text.strip()
                print(f"Sensitivity generated: {len(sensitivity_text)} chars")  # Debug log
        
        # Q&A if question provided
        ai_response = None
        if request.question:
            context = f"📘 Test Strategy:\n{strategy_text}\n🌐 Cross-Platform Testing:\n{cross_text}"
            if sensitivity_text:
                context += f"\n🔒 Sensitivity Analysis:\n{sensitivity_text}"
            
            prompt_chat = f"""Based on the following content:\n{context}\n\nAnswer this user query: "{request.question}" """
            response_chat = ai_model.generate_content(prompt_chat)
            ai_response = response_chat.text.strip()
            print(f"Q&A generated: {len(ai_response)} chars")  # Debug log
        
        result = {
            "test_strategy": strategy_text,
            "cross_platform_testing": cross_text,
            "sensitivity_analysis": sensitivity_text,
            "ai_response": ai_response
        }
        
        print(f"Returning result: {result}")  # Debug log
        return result
        
    except Exception as e:
        print(f"Test support error: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/images/{space_key}/{page_title}")
async def get_images(space_key: Optional[str] = None, page_title: str = ""):
    """Get all images, tables, and Excel attachments from a specific page"""
    try:
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, space_key)
        
        # Get page content
        pages = confluence.get_all_pages_from_space(space=space_key, start=0, limit=100)
        page = next((p for p in pages if p["title"].strip().lower() == page_title.strip().lower()), None)
        
        if not page:
            raise HTTPException(status_code=404, detail=f"Page '{page_title}' not found")
        
        page_id = page["id"]
        html_content = confluence.get_page_by_id(page_id=page_id, expand="body.export_view")["body"]["export_view"]["value"]
        soup = BeautifulSoup(html_content, "html.parser")
        base_url = os.getenv("CONFLUENCE_BASE_URL")
        
        # Images
        image_urls = list({
            base_url + img["src"] if img["src"].startswith("/") else img["src"]
            for img in soup.find_all("img") if img.get("src")
        })
        
        # Tables (as HTML strings)
        tables = [str(table) for table in soup.find_all("table")]
        
        # Excel attachments
        excels = []
        try:
            attachments = confluence.get_attachments_from_content(page_id=page_id, start=0, limit=100)
            for att in attachments.get("results", []):
                title = att.get("title", "")
                if title.lower().endswith((".xls", ".xlsx")):
                    # Compose download URL
                    download_link = att["_links"].get("download")
                    if download_link:
                        url = base_url.rstrip("/") + download_link
                        excels.append(url)
        except Exception as e:
            # If attachment fetch fails, just skip excels
            pass
        
        return {"images": image_urls, "tables": tables, "excels": excels}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/image-summary")
async def image_summary(request: ImageRequest, req: Request):
    """Generate AI summary for an image"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))
        
        # Download image
        auth = (os.getenv('CONFLUENCE_USER_EMAIL'), os.getenv('CONFLUENCE_API_KEY'))
        response = requests.get(request.image_url, auth=auth)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Failed to fetch image")
        
        image_bytes = response.content
        
        # Upload to Gemini
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(image_bytes)
            tmp.flush()
            uploaded = genai.upload_file(
                path=tmp.name,
                mime_type="image/png",
                display_name=f"confluence_image_{request.page_title}.png"
            )
        
        prompt = (
            "You are analyzing a technical image from a documentation page. "
            "If it's a chart or graph, explain what is shown in detail. "
            "If it's code, summarize what the code does. "
            "Avoid mentioning filenames or metadata. Provide an informative analysis in 1 paragraph."
        )
        
        response = ai_model.generate_content([uploaded, prompt])
        summary = response.text.strip()
        
        return {"summary": summary}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/image-qa")
async def image_qa(request: ImageSummaryRequest, req: Request):
    """Generate AI response for a question about an image, table, or excel (uses summary if no image_url)"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))
        # If image_url is provided and non-empty, use image logic
        if getattr(request, 'image_url', None):
            image_url = request.image_url
            if image_url:
                # Download image
                import requests
                auth = (os.getenv('CONFLUENCE_USER_EMAIL'), os.getenv('CONFLUENCE_API_KEY'))
                response = requests.get(image_url, auth=auth)
                if response.status_code != 200:
                    raise HTTPException(status_code=404, detail="Failed to fetch image")
                image_bytes = response.content
                # Upload to Gemini
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                    tmp_img.write(image_bytes)
                    tmp_img.flush()
                    uploaded_img = genai.upload_file(
                        path=tmp_img.name,
                        mime_type="image/png",
                        display_name=f"qa_image_{request.page_title}.png"
                    )
                full_prompt = (
                    "You're analyzing a technical image extracted from documentation. "
                    "Answer the user's question based on the visual content of the image, "
                    "as well as the summary below.\n\n"
                    f"Summary:\n{request.summary}\n\n"
                    f"User Question:\n{request.question}"
                )
                ai_response = ai_model.generate_content([uploaded_img, full_prompt])
                answer = ai_response.text.strip()
                return {"answer": answer}
        # Otherwise, use summary-only logic (for tables/excels)
        text_prompt = (
            "You are analyzing a table, Excel sheet, or text extracted from documentation. "
            "Answer the user's question based on the summary below.\n\n"
            f"Summary:\n{request.summary}\n\n"
            f"User Question:\n{request.question}"
        )
        ai_response = ai_model.generate_content(text_prompt)
        answer = ai_response.text.strip()
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-chart")
async def create_chart(request: ChartRequest, req: Request):
    """Create chart from image, table, or Excel data"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, getattr(request, 'space_key', None))
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns
        from io import StringIO
        import tempfile
        import requests
        import base64
        import io
        # Priority: excel_url > table_html > image_url
        df = None
        if request.excel_url:
            # Download and read Excel file
            auth = (os.getenv('CONFLUENCE_USER_EMAIL'), os.getenv('CONFLUENCE_API_KEY'))
            response = requests.get(request.excel_url, auth=auth)
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Failed to fetch Excel file")
            excel_bytes = response.content
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_xls:
                tmp_xls.write(excel_bytes)
                tmp_xls.flush()
                df = pd.read_excel(tmp_xls.name)
        elif request.table_html:
            # Parse HTML table to DataFrame
            dfs = pd.read_html(request.table_html)
            if not dfs:
                raise HTTPException(status_code=400, detail="No table found in HTML")
            df = dfs[0]
        elif request.image_url:
            # Existing image logic
            auth = (os.getenv('CONFLUENCE_USER_EMAIL'), os.getenv('CONFLUENCE_API_KEY'))
            response = requests.get(request.image_url, auth=auth)
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Failed to fetch image")
            image_bytes = response.content
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
                tmp_img.write(image_bytes)
                tmp_img.flush()
                uploaded_img = genai.upload_file(
                    path=tmp_img.name,
                    mime_type="image/png",
                    display_name=f"chart_image_{request.page_title}.png"
                )
            graph_prompt = (
                "You're looking at a Likert-style bar chart image or table. Extract the full numeric table represented by the chart.\n"
                "Return only the raw CSV table: no markdown, no comments, no code blocks.\n"
                "The first column must be the response category (e.g., Strongly Agree), followed by columns for group counts (e.g., Students, Lecturers, Staff, Total).\n"
                "Ensure all values are numeric and the CSV is properly aligned. Do NOT summarize—just output the table."
            )
            graph_response = ai_model.generate_content([uploaded_img, graph_prompt])
            csv_text = graph_response.text.strip()
            def clean_ai_csv(raw_text):
                lines = raw_text.strip().splitlines()
                clean_lines = [
                    line.strip() for line in lines
                    if ',' in line and not line.strip().startswith("```") and not line.lower().startswith("here")
                ]
                header = clean_lines[0].split(",")
                cleaned_data = [clean_lines[0]]
                for line in clean_lines[1:]:
                    if line.split(",")[0] != header[0]:
                        cleaned_data.append(line)
                return "\n".join(cleaned_data)
            cleaned_csv = clean_ai_csv(csv_text)
            df = pd.read_csv(StringIO(cleaned_csv))
        else:
            raise HTTPException(status_code=400, detail="No data source provided for chart generation")
        # Clean and process DataFrame
        for col in df.columns[1:]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=df.columns[1:], how='all', inplace=True)
        if df.empty:
            raise HTTPException(status_code=400, detail="Failed to extract chart data from provided source")
        # Create chart based on type
        plt.clf()
        if request.chart_type == "Grouped Bar":
            melted = df.melt(id_vars=[df.columns[0]], var_name="Group", value_name="Count")
            plt.figure(figsize=(10, 6))
            sns.barplot(data=melted, x=melted.columns[0], y="Count", hue="Group")
            plt.xticks(rotation=45)
            plt.title("Grouped Bar Chart")
            plt.tight_layout()
        elif request.chart_type == "Stacked Bar":
            df_plot = df.set_index(df.columns[0])
            plt.figure(figsize=(10, 6))
            df_plot.drop(columns="Total", errors="ignore").plot(kind='bar', stacked=True)
            plt.title("Stacked Bar Chart")
            plt.xticks(rotation=45)
            plt.ylabel("Count")
            plt.tight_layout()
        elif request.chart_type == "Line":
            df_plot = df.set_index(df.columns[0])
            plt.figure(figsize=(10, 6))
            df_plot.drop(columns="Total", errors="ignore").plot(marker='o')
            plt.title("Line Chart")
            plt.xticks(rotation=45)
            plt.ylabel("Count")
            plt.tight_layout()
        elif request.chart_type == "Pie":
            plt.figure(figsize=(7, 6))
            label_col = df.columns[0]
            if "Total" in df.columns:
                data = df["Total"]
            else:
                data = df.iloc[:, 1:].sum(axis=1)
            plt.pie(data, labels=df[label_col], autopct="%1.1f%%", startangle=140)
            plt.title("Pie Chart (Total Responses)")
            plt.tight_layout()
        # Save chart to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format=request.format.lower(), bbox_inches="tight")
        buf.seek(0)
        chart_bytes = buf.getvalue()
        # Convert to base64 for response
        chart_base64 = base64.b64encode(chart_bytes).decode()
        return {
            "chart_data": chart_base64,
            "mime_type": f"image/{request.format.lower()}",
            "filename": f"{request.filename}.{request.format.lower()}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export")
async def export_content(request: ExportRequest, req: Request):
    """Export content in various formats"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        if request.format == "pdf":
            buffer = create_pdf(request.content)
            file_data = buffer.getvalue()
            return {"file": base64.b64encode(file_data).decode('utf-8'), "mime": "application/pdf", "filename": f"{request.filename}.pdf"}
        elif request.format == "docx":
            buffer = create_docx(request.content)
            file_data = buffer.getvalue()
            return {"file": base64.b64encode(file_data).decode('utf-8'), "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "filename": f"{request.filename}.docx"}
        elif request.format == "csv":
            buffer = create_csv(request.content)
            file_data = buffer.getvalue()
            return {"file": file_data.decode('utf-8'), "mime": "text/csv", "filename": f"{request.filename}.csv"}
        elif request.format == "json":
            buffer = create_json(request.content)
            file_data = buffer.getvalue()
            return {"file": file_data.decode('utf-8'), "mime": "application/json", "filename": f"{request.filename}.json"}
        elif request.format == "html":
            buffer = create_html(request.content)
            file_data = buffer.getvalue()
            return {"file": file_data.decode('utf-8'), "mime": "text/html", "filename": f"{request.filename}.html"}
        else:  # txt/markdown
            buffer = create_txt(request.content)
            file_data = buffer.getvalue()
            return {"file": file_data.decode('utf-8'), "mime": "text/plain", "filename": f"{request.filename}.txt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save-to-confluence")
async def save_to_confluence(request: SaveToConfluenceRequest, req: Request):
    """
    Update the content of a Confluence page (storage format).
    """
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, request.space_key)
        # Get page by title, expand body.storage
        page = confluence.get_page_by_title(space=space_key, title=request.page_title, expand='body.storage')
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        page_id = page["id"]
        
        # Handle different save modes
        existing_content = page["body"]["storage"]["value"]
        mode = request.mode or "append"
        
        if mode == "append":
            # Append new content to existing content
            updated_body = existing_content + "<hr/>" + request.content
        elif mode == "overwrite":
            # Replace entire content
            updated_body = request.content
        else:
            raise HTTPException(status_code=400, detail="Invalid mode. Use 'append' or 'overwrite'")
        
        # Update page
        confluence.update_page(
            page_id=page_id,
            title=request.page_title,
            body=updated_body,
            representation="storage"
        )
        return {"message": "Page updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/preview-save-to-confluence")
async def preview_save_to_confluence(request: PreviewSaveToConfluenceRequest, req: Request):
    """
    Preview the content that would be saved to a Confluence page.
    """
    try:
        confluence = init_confluence()
        space_key = auto_detect_space(confluence, request.space_key)
        # Get page by title, expand body.storage
        page = confluence.get_page_by_title(space=space_key, title=request.page_title, expand='body.storage')
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        
        # Handle different save modes for preview
        existing_content = page["body"]["storage"]["value"]
        
        if request.mode == "append":
            # Preview append mode
            preview_content = existing_content + "<hr/>" + request.content
            diff = f"<div style='color: green;'>+ {request.content}</div>"
        elif request.mode == "overwrite":
            # Preview overwrite mode
            preview_content = request.content
            diff = f"<div style='color: red;'>- {existing_content}</div><div style='color: green;'>+ {request.content}</div>"
        else:
            raise HTTPException(status_code=400, detail="Invalid mode. Use 'append' or 'overwrite'")
        
        return {
            "preview_content": preview_content,
            "diff": diff
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-goal", response_model=AnalyzeGoalResponse)
async def analyze_goal(request: AnalyzeGoalRequest, req: Request):
    """Analyze a user goal and return which tools and pages to use, using Gemini."""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        prompt = (
            "You are an expert AI agent orchestrator. "
            "Given the following user goal and a list of available Confluence page titles, decide which of these tools should be used to accomplish it: "
            "AI Powered Search, Impact Analyzer, Code Assistant, Video Summarizer, Test Support Tool, Image Insights, Chart Builder. "
            "Also, select the most relevant page titles from the provided list that should be used to achieve the goal. "
            "Return a JSON object with three fields: 'tools' (a list of tool names to use, using these exact keys: 'ai_powered_search', 'impact_analyzer', 'code_assistant', 'video_summarizer', 'test_support', 'image_insights', 'chart_builder'), 'pages' (a list of relevant page titles from the provided list), and 'reasoning' (a short explanation of your choices). "
            "Return ONLY valid JSON, no extra text or explanation. Output your answer as a JSON object in a single code block. "
            f"Available pages: {request.available_pages}\n"
            f"User goal: '{request.goal}'"
        )
        response = ai_model.generate_content(prompt)
        # Try to parse the response as JSON
        try:
            # Remove code block markers if present
            raw = response.text.strip()
            if raw.startswith('```json'):
                raw = raw[7:]
            if raw.startswith('```'):
                raw = raw[3:]
            if raw.endswith('```'):
                raw = raw[:-3]
            result = json.loads(raw)
            tools = result.get('tools', [])
            # Patch: handle dict for tools
            if isinstance(tools, dict):
                tools = [k for k, v in tools.items() if v is True or v == 1 or (isinstance(v, str) and v.lower() == 'true')]
            elif not isinstance(tools, list):
                raise ValueError(f"Gemini returned tools in an unexpected format: {tools}")
            pages = result.get('pages', [])
            reasoning = result.get('reasoning', '')
        except Exception as e:
            print(f"[analyze-goal] Failed to parse Gemini response as JSON. Raw response:\n{response.text}")
            tools = []
            pages = []
            reasoning = response.text.strip()
        if not tools or not pages:
            raise HTTPException(status_code=400, detail=f"Gemini did not return valid tools/pages. Raw output:\n{response.text}")
        return {"tools": tools, "pages": pages, "reasoning": reasoning}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/table-summary")
async def table_summary(request: TableSummaryRequest, req: Request):
    """Generate AI summary for a table (HTML)"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        import pandas as pd
        from io import StringIO
        # Parse HTML table to DataFrame
        dfs = pd.read_html(request.table_html)
        if not dfs:
            raise HTTPException(status_code=400, detail="No table found in HTML")
        df = dfs[0]
        csv_text = df.to_csv(index=False)
        prompt = (
            "You are analyzing a table extracted from a Confluence page. "
            "Summarize the following table in detail. "
            "Focus on key trends, outliers, and important data points. "
            "Do not mention file names or metadata.\n\n"
            f"CSV Table:\n{csv_text}"
        )
        response = ai_model.generate_content(prompt)
        summary = response.text.strip()
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/excel-summary")
async def excel_summary(request: ExcelSummaryRequest, req: Request):
    """Generate AI summary for an Excel file"""
    try:
        api_key = get_actual_api_key_from_identifier(req.headers.get('x-api-key'))
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("models/gemini-1.5-flash-8b-latest")
        import pandas as pd
        import tempfile
        import requests
        # Download and read Excel file
        auth = (os.getenv('CONFLUENCE_USER_EMAIL'), os.getenv('CONFLUENCE_API_KEY'))
        response = requests.get(request.excel_url, auth=auth)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Failed to fetch Excel file")
        excel_bytes = response.content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_xls:
            tmp_xls.write(excel_bytes)
            tmp_xls.flush()
            df = pd.read_excel(tmp_xls.name)
        csv_text = df.to_csv(index=False)
        prompt = (
            "You are analyzing an Excel sheet extracted from a Confluence page. "
            "Summarize the following table in detail. "
            "Focus on key trends, outliers, and important data points. "
            "Do not mention file names or metadata.\n\n"
            f"CSV Table:\n{csv_text}"
        )
        response = ai_model.generate_content(prompt)
        summary = response.text.strip()
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def send_to_google_chat(summary: str) -> bool:
    """
    Sends the summary to Google Chat using the webhook URL from env var.
    Returns True if successful, False otherwise.
    """
    webhook_url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("GOOGLE_CHAT_WEBHOOK_URL not set in environment variables.")
    payload = {"text": f"AI Summary:\n{summary}"}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            print(f"Google Chat webhook error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"Exception sending to Google Chat: {e}")
        return False

@app.post("/send-to-google-chat")
async def send_to_google_chat_endpoint(payload: dict = Body(...)):
    """
    Endpoint to send a summary to Google Chat.
    Expects JSON: { "summary": "..." }
    """
    summary = payload.get("summary")
    if not summary:
        raise HTTPException(status_code=400, detail="Missing 'summary' in request body.")
    try:
        success = send_to_google_chat(summary)
        if success:
            return {"status": "success", "message": "Summary sent to Google Chat."}
        else:
            return {"status": "failure", "message": "Failed to send summary to Google Chat."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending to Google Chat: {str(e)}")

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify backend is working"""
    return {"message": "Backend is working", "status": "ok"}

def get_actual_api_key_from_identifier(identifier: str) -> str:
    if identifier and identifier.startswith('GENAI_API_KEY_'):
        key = os.getenv(identifier)
        print(f"Using API key identifier: {identifier}, value: {key}")  # This will appear in Render logs
        if key:
            return key
    fallback = os.getenv('GENAI_API_KEY_1')
    print(f"Falling back to GENAI_API_KEY_1, value: {fallback}")
    return fallback

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
