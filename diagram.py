import os, re, streamlit as st, graphviz
from io import BytesIO
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from atlassian import Confluence
import google.generativeai as genai

# ─── ENV SETUP ─────────────────────────────
load_dotenv()

def init_confluence():
    return Confluence(
        url=os.getenv("CONFLUENCE_BASE_URL"),
        username=os.getenv("CONFLUENCE_USER_EMAIL"),
        password=os.getenv("CONFLUENCE_API_KEY"),
    )

# ─── FALLBACK SAMPLE ───────────────────────
def create_fallback_example():
    fallback_code = '''
# type: start
def start(): pass

# type: io
def collect_application(): pass

# type: preprocessor
def validate_application(): pass

# type: preprocessor
def preprocess_application(): pass

# type: process
def check_credit_score(): pass

# type: decision
def credit_score_ok(): pass
# YES: check_documents
# NO: reject_application

# type: process
def check_documents(): pass

# type: decision
def documents_complete(): pass
# YES: approve_application
# NO: request_missing_docs

# type: io
def request_missing_docs(): pass

# type: end
def reject_application(): pass

# type: predefined
def approve_application(): pass

# type: end
def end(): pass
'''
    with open("flowchart_example_all_symbols.py", "w") as f:
        f.write(fallback_code)
    return fallback_code

# ─── PARSE TYPE TAGS ────────────────────────
def parse_type_tags(code: str):
    lines = []
    nodes = []
    label_map = {}
    code_lines = code.splitlines()

    for i, line in enumerate(code_lines):
        m = re.search(r'# type: (\w+)', line)
        if m:
            typ = m.group(1).lower()
            label = None
            if 'def ' in line:
                label_match = re.search(r'def\s+(\w+)', line)
                if label_match:
                    label = label_match.group(1)
            elif 'class ' in line:
                label_match = re.search(r'class\s+(\w+)', line)
                if label_match:
                    label = label_match.group(1)
            else:
                label_match = re.search(r'(\w+)\s*=.*# type:', line)
                label = label_match.group(1) if label_match else f"Step_{i}"

            if label:
                nodes.append((label, typ, i))
                label_map[label] = typ

    # --- Detect data usage in functions and add edges ---
    # Build a map of data variables
    data_vars = {label for label, typ, _ in nodes if typ == 'data'}
    # For each function, scan its body for # uses: ... comments
    for idx, (label, typ, line_idx) in enumerate(nodes):
        if typ in ('start', 'end', 'data'):
            continue  # skip non-function nodes
        # Find function body: from line_idx+1 to next def/class or end
        body_start = line_idx + 1
        if body_start >= len(code_lines):
            continue
        body_end = len(code_lines)
        for j in range(body_start, len(code_lines)):
            if re.match(r'\s*(def |class )', code_lines[j]):
                body_end = j
                break
        # Scan body for # uses: ...
        for j in range(body_start, body_end):
            uses_match = re.search(r'# uses: ([\w, ]+)', code_lines[j])
            if uses_match:
                used_vars = [v.strip() for v in uses_match.group(1).split(',')]
                for used_var in used_vars:
                    if used_var in data_vars:
                        lines.append(f"{used_var} -> {label} | data")

    i = 0
    while i < len(nodes):
        label, typ, line_idx = nodes[i]
        if typ == 'decision':
            yes_target = no_target = None
            for j in range(line_idx + 1, min(line_idx + 4, len(code_lines))):
                yes_match = re.search(r'#\s*YES:\s*(\w+)', code_lines[j])
                no_match = re.search(r'#\s*NO:\s*(\w+)', code_lines[j])
                if yes_match: yes_target = yes_match.group(1)
                if no_match: no_target = no_match.group(1)

            if yes_target:
                lines.append(f"{label} -> {yes_target} | decision_yes")
            if no_target:
                lines.append(f"{label} -> {no_target} | decision_no")
            if not yes_target and not no_target and i + 1 < len(nodes):
                next_label = nodes[i + 1][0]
                lines.append(f"{label} -> {next_label} | {typ}")
        else:
            if i + 1 < len(nodes):
                next_label = nodes[i + 1][0]
                lines.append(f"{label} -> {next_label} | {typ}")
        i += 1

    return lines, label_map

# ─── PARSE STEP-BY-STEP PROCEDURES ──────────
def parse_step_procedure(text: str):
    raw_lines = text.splitlines()
    label_map = {}
    label_to_desc = {}
    edges = []

    step_labels = []
    step_line_indices = {}
    steps = []
    goto_after_step = {}  # step label -> goto target if found on next line

    # Parse all steps (ignore WHILE lines completely)
    idx = 0
    while idx < len(raw_lines):
        line_strip = raw_lines[idx].strip()
        # Ignore WHILE lines (do not add as nodes, do not process)
        if re.match(r'^WHILE .+:$', line_strip, re.IGNORECASE):
            idx += 1
            continue
        m = re.match(r'^STEP\s*(\d+):?\s*(.*)$', line_strip, re.IGNORECASE)
        if m:
            num, desc = m.groups()
            label = f"Step_{num}"
            desc = desc.strip()
            step_labels.append(label)
            step_line_indices[label] = idx
            label_to_desc[label] = desc
            steps.append((label, desc))
            # Assign types dynamically
            desc_lower = desc.lower()
            if "begin" in desc_lower or "start" in desc_lower:
                label_map[label] = "start"
            elif any(word in desc_lower for word in ["end", "finish", "successfully"]):
                label_map[label] = "end"
            elif desc_lower.endswith("?") or "is this" in desc_lower or "is customer" in desc_lower:
                label_map[label] = "decision"
            elif any(w in desc_lower for w in ["database", "store"]):
                label_map[label] = "data"
            elif any(w in desc_lower for w in ["collect", "input", "enter"]):
                label_map[label] = "io"
            elif any(w in desc_lower for w in ["retrieve", "create", "determine", "escalate"]):
                label_map[label] = "process"
            else:
                label_map[label] = "process"
            # Check next line for 'Go to STEP X'
            if idx + 1 < len(raw_lines):
                next_line = raw_lines[idx + 1].strip()
                goto_match = re.match(r'^Go to STEP[_ ]?(\d+)', next_line, re.IGNORECASE)
                if goto_match:
                    goto_after_step[label] = f"Step_{goto_match.group(1)}"
        idx += 1

    # Build edges (explicit gotos and IF/THEN/ELSE logic)
    i = 0
    while i < len(steps):
        label, desc = steps[i]
        idx = step_line_indices[label]
        # Check for 'Go to STEP X' in description or on next line
        desc_lower = desc.lower()
        goto_match = re.search(r'go to\s*step[_ ]?(\d+)', desc_lower, re.IGNORECASE)
        goto_target = None
        if goto_match:
            goto_target = f"Step_{goto_match.group(1)}"
        elif label in goto_after_step:
            goto_target = goto_after_step[label]
        if goto_target:
            edges.append(f"{label} -> {goto_target} | process")
        elif i + 1 < len(steps):
            next_label = steps[i + 1][0]
            current_type = label_map.get(label, "process")
            if current_type == "decision":
                # For decisions, look for YES/NO branches in following lines
                yes_target = no_target = None
                for offset in range(1, 6):
                    if idx + offset >= len(raw_lines):
                        break
                    line2 = raw_lines[idx + offset].strip()
                    yes_match = re.match(r'^(yes|then):\s*go to step[_ ]?(\d+)', line2, re.IGNORECASE)
                    no_match = re.match(r'^(no|else):\s*go to step[_ ]?(\d+)', line2, re.IGNORECASE)
                    if yes_match:
                        yes_target = f"Step_{yes_match.group(2)}"
                    if no_match:
                        no_target = f"Step_{no_match.group(2)}"
                if yes_target:
                    edges.append(f"{label} -> {yes_target} | decision_yes | Yes")
                if no_target:
                    edges.append(f"{label} -> {no_target} | decision_no | No")
            else:
                edges.append(f"{label} -> {next_label} | {current_type}")
        i += 1

    return edges, label_map, label_to_desc

# ─── DETECT CONTENT TYPE ────────────────────
def detect_content_type(text: str):
    """Detect if content is code with type tags or step-by-step procedure"""
    lines = text.splitlines()
    
    # Check for code patterns
    code_indicators = 0
    step_indicators = 0
    
    for line in lines:
        line_lower = line.lower().strip()
        
        # Code indicators
        if re.search(r'# type:', line):
            code_indicators += 5
        if re.search(r'def\s+\w+', line):
            code_indicators += 3
        if re.search(r'class\s+\w+', line):
            code_indicators += 3
        if re.search(r'#', line):
            code_indicators += 2
        if re.search(r'import\s+', line):
            code_indicators += 1
        if re.search(r'from\s+', line):
            code_indicators += 1
        
        # Step procedure indicators
        if re.match(r'^STEP\s+\d+', line, re.IGNORECASE):
            step_indicators += 5
        if re.match(r'^\d+[\.\)]', line):
            step_indicators += 3
        if re.match(r'^[•·]\s+', line):
            step_indicators += 2
        if re.match(r'^[-*]\s+', line):
            step_indicators += 2
        if re.search(r'\?\s*(Yes|No|Y|N)', line, re.IGNORECASE):
            step_indicators += 2
    
    if code_indicators > step_indicators:
        return "code"
    elif step_indicators > 0:
        return "procedure"
    else:
        return "unknown"

# ─── FLOWCHART GENERATOR ───────────────────
def build_flowchart_graph(lines, label_map, label_to_desc=None):
    dot = graphviz.Digraph(format="png", engine="dot", graph_attr={
        "dpi": "300",
        "nodesep": "0.5",
        "ranksep": "0.5",
        "splines": "true",
        "concentrate": "false"
    })

    dot.attr('node', fontname="Segoe UI", fontsize="14", style="filled",
             margin="0.15,0.08", width="0.7", height="0.4", fixedsize="false")
    dot.attr('edge', fontname="Segoe UI", fontsize="12")

    style_map = {
        "start": ("oval", "#a7f3d0"),
        "end": ("oval", "#fca5a5"),
        "process": ("box", "#bfdbfe"),      # Lighter blue for process
        "predefined": ("rect", "#c7d2fe"),
        "decision": ("diamond", "#fde68a"), # Light yellow for decision
        "io": ("parallelogram", "#d8b4fe"),
        "data": ("cylinder", "#bbf7d0"),
        "preprocessor": ("trapezium", "#ddd6fe"),
        "off_page": ("box", "#a5f3fc"),
        "page_connector": ("circle", "#fbcfe8"),
        "comment": ("note", "#f3f4f6")
    }

    added = {}
    edges = []

    for line in lines:
        m = re.match(r'(\w+) -> (\w+) \| (\w+)(?: \| (\w+))?', line)
        if not m:
            continue
        src, dst, edge_type, custom_label = m.groups()
        src_type = label_map.get(src, "process")
        dst_type = label_map.get(dst, "process")
        src_shape, src_color = style_map.get(src_type, ("box", "#ffffff"))
        dst_shape, dst_color = style_map.get(dst_type, ("box", "#ffffff"))

        # Use description as label if available
        src_label = src
        dst_label = dst
        if label_to_desc:
            src_label = label_to_desc.get(src, src)
            dst_label = label_to_desc.get(dst, dst)

        # Dynamically set smaller size for page_connector
        if src not in added:
            if src_type == "page_connector":
                dot.node(src, src_label, shape=src_shape, fillcolor=src_color, width="0.7", height="0.7", fixedsize="true")
            else:
                dot.node(src, src_label, shape=src_shape, fillcolor=src_color)
            added[src] = src_type
        if dst not in added:
            if dst_type == "page_connector":
                dot.node(dst, dst_label, shape=dst_shape, fillcolor=dst_color, width="0.7", height="0.7", fixedsize="true")
            else:
                dot.node(dst, dst_label, shape=dst_shape, fillcolor=dst_color)
            added[dst] = dst_type

        edge_label = ""
        if edge_type == "decision_yes" or edge_type == "decision_no":
            edge_label = custom_label or ("Yes" if edge_type == "decision_yes" else "No")

        edges.append((src, dst, edge_label, edge_type))

    # --- Force data nodes inline in the main vertical flow ---
    data_nodes = {n for n, t in label_map.items() if t == 'data'}
    data_edges = [(src, dst) for src, dst, _, _ in edges if src in data_nodes]
    # --- Dynamically insert dummy 'access' process node for each data usage ---
    access_nodes = []
    rerouted_edges = []
    skip_edges = set()
    for data_node in data_nodes:
        targets = [dst for src, dst in data_edges if src == data_node]
        for target in targets:
            # Find the incoming edge to this target (excluding from data_node)
            incoming = [(src, dst, label, typ) for src, dst, label, typ in edges if dst == target and src != data_node]
            if incoming:
                prev_src, _, prev_label, prev_typ = incoming[0]
                access_node = f"access_{data_node}_for_{target}"
                access_nodes.append((access_node, data_node, target))
                # Add edge from previous node to access node
                rerouted_edges.append((prev_src, access_node, '', 'access'))
                # Add edge from data node to access node
                rerouted_edges.append((data_node, access_node, '', 'data_access'))
                # Add edge from access node to target
                rerouted_edges.append((access_node, target, '', 'access_to_func'))
                # Mark the direct edge from prev_src to target and from data_node to target for skipping
                skip_edges.add((prev_src, target))
                skip_edges.add((data_node, target))
    # Add all other edges as usual
    for src, dst, label, typ in edges:
        if (src, dst) not in skip_edges:
            dot.edge(src, dst, label=label, arrowsize="0.5")
    # Add rerouted access/data edges
    for src, dst, label, typ in rerouted_edges:
        if typ == 'access':
            dot.node(src, f"Access {data_node}", shape='box', fillcolor='#f3f4f6', style='filled', fontname='Segoe UI', fontsize='14')
        dot.edge(src, dst, label=label, arrowsize="0.5")
    return dot

# ─── GEMINI FLOWCHART GENERATION ─────────────
def gemini_generate_flowchart_structure(text):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-1.5-flash")  # or "models/gemini-1.5-flash-8b"
    prompt = (
        "You are an expert at extracting flowchart logic from code or pseudocode. "
        "Given the following content, extract a flowchart structure as JSON with nodes (id, label, type) and edges (from, to, label). "
        "Types can be: start, end, process, io, decision, predefined, preprocessor, data, off_page, page_connector, comment. "
        "For decisions, include Yes/No labels on edges. "
        "Content:\n" + text +
        "\nRespond ONLY with a JSON object: {nodes: [...], edges: [...]}"
    )
    response = model.generate_content(prompt)
    print("DEBUG: Gemini response:", response)
    gemini_text = None
    if hasattr(response, "text") and isinstance(response.text, str):
        gemini_text = response.text
    elif hasattr(response, "candidates"):
        try:
            gemini_text = response.candidates[0].content.parts[0].text
        except Exception as e:
            print("DEBUG: Could not extract text from candidates:", e)
    print("DEBUG: gemini_text:", gemini_text, type(gemini_text))
    import json
    import re
    try:
        if not isinstance(gemini_text, str):
            gemini_text_str = str(gemini_text) if gemini_text is not None else ""
        else:
            gemini_text_str = gemini_text
        gemini_text_str = gemini_text_str.strip()
        cleaned = re.sub(r"^```json\s*|```$", "", gemini_text_str, flags=re.MULTILINE)
        print("DEBUG: cleaned Gemini text before JSON parse:\n", cleaned)
        match = re.search(r'\{[\s\S]*\}', cleaned)
    except Exception as e:
        raise ValueError(f"Could not clean Gemini response: {e}\nRaw: {gemini_text}")
    if not match:
        raise ValueError("Gemini did not return a valid JSON structure.")
    try:
        return json.loads(match.group(0))
    except Exception as e:
        raise ValueError(f"Failed to parse Gemini JSON: {e}\nRaw: {cleaned}")

# ─── FLOWCHART FROM GEMINI STRUCTURE ───────
def build_flowchart_from_gemini(flowchart):
    dot = graphviz.Digraph(format="png", engine="dot", graph_attr={
        "dpi": "300",
        "nodesep": "0.5",
        "ranksep": "0.5",
        "splines": "true",
        "concentrate": "false"
    })
    style_map = {
        "start": ("oval", "#a7f3d0"),
        "end": ("oval", "#fca5a5"),
        "process": ("box", "#bfdbfe"),
        "predefined": ("rect", "#c7d2fe"),
        "decision": ("diamond", "#fde68a"),
        "io": ("parallelogram", "#d8b4fe"),
        "data": ("cylinder", "#bbf7d0"),
        "preprocessor": ("trapezium", "#ddd6fe"),
        "off_page": ("box", "#a5f3fc"),
        "page_connector": ("circle", "#fbcfe8"),
        "comment": ("note", "#f3f4f6")
    }
    for node in flowchart["nodes"]:
        shape, color = style_map.get(node.get("type", "process"), ("box", "#ffffff"))
        # Dynamically set smaller size for page_connector
        if node.get("type") == "page_connector":
            dot.node(str(node["id"]), node["label"], shape=shape, fillcolor=color, style="filled", fontname="Segoe UI", fontsize="14", width="0.7", height="0.7", fixedsize="true")
        else:
            dot.node(str(node["id"]), node["label"], shape=shape, fillcolor=color, style="filled", fontname="Segoe UI", fontsize="14")
    for edge in flowchart["edges"]:
        label = edge.get("label", "")
        dot.edge(str(edge["from"]), str(edge["to"]), label=label, arrowsize="0.5", fontname="Segoe UI", fontsize="12")
    return dot

# ─── MAIN APP ──────────────────────────────
def run():
    st.set_page_config("AI Flowchart Generator", layout="wide")
    st.title("AI Flowchart Generator")

    conf = init_confluence()

    if not os.path.exists("flowchart_example_all_symbols.py"):
        create_fallback_example()

    try:
        # ✅ Load and fix space keys
        spaces_response = conf.get_all_spaces(limit=100)
        if spaces_response is None:
            st.error("❌ Failed to connect to Confluence. Please check your credentials.")
            return
        all_spaces = spaces_response.get("results", [])
        space_options = {f"{s['name']} ({s['key']})": s['key'] for s in all_spaces}

        if "mfs" not in space_options.values():
            space_options["My Flow Space (mfs)"] = "mfs"

        default_index = list(space_options.values()).index("mfs") if "mfs" in space_options.values() else 0
        selected_label = st.selectbox("🔑 Select Confluence Space", list(space_options.keys()), index=default_index)
        selected_space = space_options[selected_label]

        pages = conf.get_all_pages_from_space(selected_space, limit=100)
        if not pages:
            st.error("No pages found in selected space.")
            return

        title = st.selectbox("📄 Select Page", [p["title"] for p in pages])
        page_id = next(p["id"] for p in pages if p["title"] == title)

        page_data = conf.get_page_by_id(page_id, expand="body.storage")
        code = ""
        if page_data and page_data.get("body", {}).get("storage", {}).get("value"):
            html = page_data["body"]["storage"]["value"]
            code = BeautifulSoup(html, "html.parser").get_text(separator="\n")

        # Debug: Show raw content from Confluence
        with st.expander("🪵 Show raw page content (debug)"):
            st.code(code, language="text")

        if not code or len(code.strip()) < 50:
            st.warning("⚠ Using fallback example.")
            code = open("flowchart_example_all_symbols.py").read()

        with st.spinner("💡 Generating flowchart with Gemini AI..."):
            flowchart = gemini_generate_flowchart_structure(code)
            dot = build_flowchart_from_gemini(flowchart)
            flow_lines = True  # For display logic

        if flow_lines:
            path = dot.render("flowchart", format="png", cleanup=True)
            st.image(open(path, "rb").read(), use_container_width=True)

            st.subheader("📥 Download")
            name = st.text_input("File name", "flowchart")
            if name:
                st.download_button("Download PNG", BytesIO(open(path, "rb").read()), f"{name}.png", "image/png")
        else:
            st.error("❌ No flowchart could be generated. Make sure your code or pseudocode is present.")

    except Exception as e:
        st.error(f"❌ Failed to load or generate flowchart: {e}")

if __name__ == "__main__":
    run()