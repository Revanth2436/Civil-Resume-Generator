# Civil Resume Generator

A dedicated web application and automation tool for generating tailored Civil Engineering resumes directly from Job Descriptions (JDs), drafting recruiter outreach emails, and formatting documents to industry specifications.

**Author**: Revanth Dirisipamu  
**Contact**: Dirisipamurevanth@gmail.com | +1(479)-317-0202  

---

## Features
- **Job Description Email Drafter**: Automatically extracts recruiter email, job title, and location from pasted JDs, and generates a pre-formatted Gmail draft without manual typing.
- **Dynamic Location Synchronization**: Extracts job location (e.g., Dallas, TX; Ohio; Columbus, OH) from the JD and dynamically adapts the resume header to match.
- **Tailored Civil Engineering Resume Output**: Built on Microsoft Word templates with native bullet styles, justification, and clean Times New Roman formatting.
- **Configurable Sections**:
  - Professional Summary (Dynamic)
  - Skills & Certifications (Dynamic categorized skills with static labels)
  - Experience (Static company names, locations, and dates with dynamic project bullets)
  - Education & Work Authorization (Static)

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r "resume-Creator-New-main/Mail-Resume_Automation-main - Copy/Mail-Resume_Automation-main/requirements.txt"
```

### 2. Run Locally
```bash
cd "resume-Creator-New-main/Mail-Resume_Automation-main - Copy/Mail-Resume_Automation-main"
python app.py
```
Open [http://localhost:8000](http://localhost:8000) in your browser.
