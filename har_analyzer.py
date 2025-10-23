from flask import Flask, render_template, request
import json
from typing import Optional
from pydantic import BaseModel
from call_gemini import Gemini
import re

# Original har analyzing functions, index and analyze html files created by Rahul Ranjan https://medium.com/@rahul.fiem/har-analyzer-766ff60c9478. Accessed on 10/16/25
# call_gemini.py, ai_review.html, modifications to original har analyzing function and graphical modifications created by Dereck Goolsby-Bearsong https://github.com/dkbearsong 

app = Flask(__name__)

class PB_builder(BaseModel):
    slowest_requests: list[str]
    large_transfers: list[str]
    redirect_chains: list[str]

class Output_Builder(BaseModel):
    load_failures: list[str]
    redirects: list[str]
    performance_bottlenecks: PB_builder
    overall_slowness: str
    security_concerns: list[str]
    cdn_issues: list[str]
    suggests: str

def format_ai_paragraph(paragraph):
    # Split on numbered points (1. 2. 3. etc.)
    points = re.split(r'\d+\.\s+', paragraph)
    # Remove empty strings from the list
    points = [point.strip() for point in points if point.strip()]
    
    # Convert each point to HTML with bold formatting
    list_items = []
    for point in points:
        # Replace **text** with <strong>text</strong>
        formatted_point = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', point)
        list_items.append(f'<li>{formatted_point}</li>')
    
    # Wrap in ordered list
    return f'<ol>{"".join(list_items)}</ol>'

def parse_har(file_path):
    with open(file_path, 'r') as f:
        har = json.load(f)

    # Typical HAR schema: { "log": { "entries": [...] } }
    entries = har.get('log', {}).get('entries', [])
    entries_data = []
    total_time = 0.0
    status_code_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    for entry in entries:
        request = entry.get('request', {})
        response = entry.get('response', {})
        timings = entry.get('timings', {})

        # Prefer entry-level time if present, fallback to wait
        time_taken = float(entry.get('time', timings.get('wait', 0) or 0))

        status = int(response.get('status', 0) or 0)
        status_category = status // 100
        if status_category in status_code_counts:
            status_code_counts[status_category] += 1

        total_time += time_taken

        entries_data.append({
            "method": request.get('method', 'GET'),
            "url": request.get('url', 'N/A'),
            "status": status,
            "content_type": (response.get('content') or {}).get('mimeType', 'N/A'),
            "time": time_taken,
            # Not truly source IP; included as a placeholder from headers if present
            "source_ip": (request.get('headers') or [{}])[0].get('value', 'N/A'),
            "error_message": response.get('statusText') if status >= 400 else None,
            "payload": (request.get('postData') or {}).get('text', 'N/A'),
            "response_size": (response.get('content') or {}).get('size', 0) or 0,
            "timings": {
                "dns": float(timings.get('dns', 0) or 0),
                "connect": float(timings.get('connect', 0) or 0),
                "send": float(timings.get('send', 0) or 0),
                "wait": float(timings.get('wait', 0) or 0),
                "receive": float(timings.get('receive', 0) or 0),
            }
        })

    summary = {
        "total_requests": len(entries_data),
        "total_time": total_time,
        "average_time": (total_time / len(entries_data)) if entries_data else 0,
        "status_code_counts": status_code_counts,
        "success_count": status_code_counts.get(2, 0),
        "failure_count": status_code_counts.get(4, 0) + status_code_counts.get(5, 0),
    }

    return entries_data, summary

# Route for HAR file analysis
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_file():
    if 'har_file' not in request.files:
        return "No HAR file uploaded", 400
    
    har_file = request.files['har_file']
    file_path = "/tmp/harfile.har"
    har_file.save(file_path)
    
    entries_data, summary = parse_har(file_path)
    
    # Render results in a simple HTML table in the browser
    return render_template('analyze.html', summary=summary, entries_data=entries_data)

@app.route('/ai_review', methods=['POST'])
def ai_review():
    if 'har_file' not in request.files:
        return "No HAR file uploaded", 400
    
    har_file = request.files['har_file']
    file_path = "/tmp/harfile.har"
    har_file.save(file_path)
    user_actions: Optional[str] = request.form.get('user_actions', '')
    
    entries_data, summary = parse_har(file_path)

    # formulate data for AI review
    system_message = f"""
    Analyze the user's data pulled from a har file to identify potential errors, performance bottlenecks, and other notable problems. The user action recorded was: { user_actions }.

    Please provide a summary report focusing on:
    1.  **Load failures and errors:** Highlight any requests with a status code outside the 200–399 range (e.g., 404 Not Found, 500 Internal Server Error, 403 Forbidden). For any errors, explain the likely cause and impact.
    2.  **Redirects**: Highlight any redirects where followup requests were followed with a 400 to 500 code
    3.  **Performance bottlenecks:**
        *   Identify the slowest-loading requests, particularly those with long "Waiting" (TTFB) or "Blocked" times.
        *   Point out any exceptionally large file transfers (e.g., large images, JavaScript bundles).
        *   Flag any excessive or unexpected redirect chains.
    4.  **Overall slowness:** Provide an assessment of the overall page load performance. Consider the number of requests and the total time taken. 
    5.  **Security considerations:** Note any requests made over unencrypted HTTP instead of HTTPS.
    6.  **CDN issues:** Identify any links coming from a CDN that may have resulted in error codes or long load times. Provide details about these entries.
    7.  **Suggestions for improvement:** Based on the findings, provide specific, actionable recommendations (e.g., compress resources, optimize server response, investigate third-party scripts).

    """
    gemini_obj = Gemini(system_message)
    ai_payload = {
        "summary": summary,
        "entries": entries_data,
    }
    ai_prompt = json.dumps(ai_payload)
    response_data = gemini_obj.call_gemini_JSON(
        model="gemini-2.5-flash",
        prompt=ai_prompt,
        scheme=Output_Builder
    )  
    response_data["suggests"] = format_ai_paragraph(response_data["suggests"])
    
    # Render results in a simple HTML table in the browser
    return render_template('ai_review.html', response=response_data, summary=summary, entries_data=entries_data)


if __name__ == '__main__':
    app.run(debug=True, port=8000)