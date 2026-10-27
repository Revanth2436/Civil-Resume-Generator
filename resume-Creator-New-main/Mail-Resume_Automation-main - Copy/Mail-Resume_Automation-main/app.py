import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import re
import subprocess
import json
import os
import sys
import urllib.parse
from pathlib import Path

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Data models
class JDEmailRequest(BaseModel):
    jd_text: str

class ResumeRequest(BaseModel):
    json_content: dict

# Constants
BASE_DIR = Path(__file__).parent.resolve()
JSON_PATH = BASE_DIR / "data/base_content.json"
RENDER_SCRIPT = BASE_DIR / "test_render.py"

# Detect environment: local vs cloud
IS_CLOUD = os.environ.get("RENDER", "") == "true" or os.environ.get("IS_CLOUD", "") == "true"

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open(BASE_DIR / "static/index.html", "r", encoding="utf-8") as f:
        return f.read()

US_STATES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
    'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH',
    'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
    'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA',
    'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN',
    'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
}
STATE_CODES = set(US_STATES.values())

def extract_location(jd_text: str) -> str:
    # 1. Match 'Location:' or similar labeled pattern
    match = re.search(
        r'(?:Job\s*Location|Work\s*Location|Position\s*Location|Office\s*Location|Location|Site|City[,\s]+State)\s*[:\-–]\s*([^\n\r]+)',
        jd_text,
        re.IGNORECASE
    )
    if match:
        line = match.group(1).strip()
        line = re.sub(r'\s*[\(\[](?:Hybrid|Onsite|Remote|On-site|Full[-\s]time|Part[-\s]time|Contract)[\)\]]', '', line, flags=re.IGNORECASE)
        line = re.sub(r'\b(?:Hybrid|Onsite|Remote|On-site|in)\s*[-–:,]?\s*', '', line, flags=re.IGNORECASE).strip()
        line = re.sub(r'\s*,?\s*(?:USA|United States)\b', '', line, flags=re.IGNORECASE).strip()

        m_city_st = re.search(r'\b([A-Z][a-zA-Z\s]+?),\s*([A-Za-z]{2}|[A-Za-z\s]+)\b', line)
        if m_city_st:
            c = m_city_st.group(1).strip()
            s = m_city_st.group(2).strip()
            if s.upper() in STATE_CODES:
                return f"{c}, {s.upper()}"
            elif s.lower() in US_STATES:
                return f"{c}, {US_STATES[s.lower()]}"
            elif len(c) < 30 and len(s) < 25:
                return f"{c}, {s}"

        cleaned = line.split(';')[0].split('|')[0].strip()
        if cleaned.lower() in US_STATES:
            return cleaned.title()
        elif cleaned.upper() in STATE_CODES:
            return cleaned.upper()
        elif cleaned and len(cleaned) < 40:
            return cleaned

    state_codes_re = '|'.join(STATE_CODES)
    m_general = re.search(rf'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?),\s*({state_codes_re})\b', jd_text)
    if m_general:
        city = m_general.group(1).strip()
        st = m_general.group(2).strip().upper()
        if city.lower() not in ['must', 'with', 'experience', 'knowledge', 'understanding', 'work']:
            return f"{city}, {st}"

    for state_name, code in US_STATES.items():
        if re.search(rf'\b(?:in|at|around)\s+{state_name}\b', jd_text, re.IGNORECASE):
            return state_name.title()

    return ""

@app.get("/api/get-resume-data")
async def get_resume_data():
    if JSON_PATH.exists():
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.post("/api/draft-email")
async def draft_email(request: JDEmailRequest):
    jd_text = request.jd_text
    
    # 1. Extract Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', jd_text)
    if not email_match:
        recipient = ""
    else:
        recipient = email_match.group(0)

    # 2. Extract Job Title
    title_match = re.search(r"(?:Job Title|Role|Position|Title):\s*(.*)", jd_text, re.IGNORECASE)
    if title_match:
        job_title = title_match.group(1).strip()
    else:
        job_title = "Civil Engineer"

    # 3. Extract Location & auto-update base_content.json
    detected_location = extract_location(jd_text)
    if detected_location:
        try:
            if JSON_PATH.exists():
                with open(JSON_PATH, "r", encoding="utf-8") as f:
                    base_data = json.load(f)
            else:
                base_data = {}
            base_data["LOCATION"] = detected_location
            with open(JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(base_data, f, indent=4)
        except Exception as e:
            print(f"Error auto-updating location in JSON: {e}")

    # 4. Construct Subject and Body
    subject = f"Interested in {job_title}"
    
    body_template = """Hi,
I am Revanth Dirisipamu, a Civil Engineer with 4+ years of hands-on experience in QA/QC, materials engineering, field inspections, and construction quality control across heavy civil infrastructure, highway construction, tunneling, and underground structures. My expertise includes materials testing (soil, concrete, aggregates), inspection and test plans (ITPs), rock bolt pull-out testing, and construction quality monitoring in accordance with ASTM, IS, and EN standards.

I have attached my resume for your review, and I would be glad to discuss how my skills and experience align with your team's needs.

Best Regards,
Revanth Dirisipamu
📧 Dirisipamurevanth@gmail.com
📞 +1(479)-317-0202

----------------------------------------------------------------------------------------------------------------------------
Reference:
{jd}
"""
    body = body_template.format(jd=jd_text)
    
    # 5. Build Gmail compose URL (No CC added)
    base_url = "https://mail.google.com/mail/?view=cm&fs=1"
    params = {
        "to": recipient,
        "su": subject,
        "body": body
    }
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    gmail_url = f"{base_url}&{query_string}"
    
    if IS_CLOUD:
        return {
            "status": "success",
            "message": "Gmail draft URL generated",
            "recipient": recipient,
            "location": detected_location,
            "gmail_url": gmail_url
        }
    else:
        import webbrowser
        try:
            webbrowser.open(gmail_url)
            msg = "Draft opened in Gmail"
            if detected_location:
                msg += f" (Location detected: {detected_location})"
            return {"status": "success", "message": msg, "recipient": recipient, "location": detected_location}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to open browser: {str(e)}")

@app.post("/api/generate-resume")
async def generate_resume(request: ResumeRequest):
    try:
        # 1. Update JSON
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(request.json_content, f, indent=4)
        
        # 2. Run test_render.py
        result = subprocess.run(
            [sys.executable, str(RENDER_SCRIPT)], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        # 3. Find the output path from stdout
        output_line = next((line for line in result.stdout.splitlines() if "[OK] Rendered OK:" in line), None)
        
        if output_line:
            file_path = output_line.split("[OK] Rendered OK:")[1].strip()
            
            if IS_CLOUD:
                # On cloud: return download endpoint
                return {
                    "status": "success",
                    "message": "Resume generated! Click to download.",
                    "path": file_path,
                    "download_url": f"/api/download-resume?path={urllib.parse.quote(file_path)}"
                }
            else:
                # On local: open in file explorer
                if os.name == 'nt':
                    subprocess.run(["explorer", "/select,", str(file_path)])
                else:
                    subprocess.run(["open", "-R", str(file_path)])
                return {"status": "success", "message": "Resume generated and opened in File Explorer", "path": file_path}
        else:
             raise HTTPException(status_code=500, detail="Could not determine output file path from script execution.")

    except subprocess.CalledProcessError as e:
        error_msg = f"Script execution failed.\nStdout: {e.stdout}\nStderr: {e.stderr}"
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download-resume")
async def download_resume(path: str):
    """Serve a generated resume file for download."""
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    # Security: ensure the file is within the outputs directory
    try:
        file_path.resolve().relative_to((BASE_DIR / "outputs").resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
