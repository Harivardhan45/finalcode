import os
import requests
import re

CONFLUENCE_URL = "https://workwizards.atlassian.net/wiki"
PAGE_ID = "55574568"
USERNAME = os.getenv("CONFLUENCE_USER_EMAIL")
API_TOKEN = os.getenv("CONFLUENCE_API_KEY")

def markdown_to_confluence_storage(text):
    # Convert markdown bold (**text**) to <strong>text</strong>
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\\1</strong>", text)
    # Convert markdown bullets to <ul><li>...</li></ul>
    lines = text.splitlines()
    in_list = False
    new_lines = []
    for line in lines:
        bullet = re.match(r"^\s*[\*\-]\s+(.*)", line)
        if bullet:
            if not in_list:
                new_lines.append("<ul>")
                in_list = True
            new_lines.append(f"<li>{bullet.group(1)}</li>")
        else:
            if in_list:
                new_lines.append("</ul>")
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append("</ul>")
    return "\n".join(new_lines)

def update_confluence_page(hlsd_content):
    # Convert markdown to Confluence storage format
    hlsd_content = markdown_to_confluence_storage(hlsd_content)
    # Get current page version
    url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
    response = requests.get(url, auth=(USERNAME, API_TOKEN))
    data = response.json()
    version = data["version"]["number"] + 1

    # Update page
    update_url = f"{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "id": PAGE_ID,
        "type": "page",
        "title": data["title"],
        "body": {
            "storage": {
                "value": f"<pre>{hlsd_content}</pre>",
                "representation": "storage"
            }
        },
        "version": {"number": version}
    }
    r = requests.put(update_url, json=payload, headers=headers, auth=(USERNAME, API_TOKEN))
    print(r.status_code, r.text)

if __name__ == "__main__":
    with open("hlsd.md", "r", encoding='utf-8') as f:
        hlsd = f.read()
    update_confluence_page(hlsd) 