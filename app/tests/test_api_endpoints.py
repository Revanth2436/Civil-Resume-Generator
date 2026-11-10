import unittest
import asyncio
import io
import os
import sys
from pathlib import Path
from docx import Document
from fastapi import HTTPException

# Set up paths
TESTS_DIR = Path(__file__).parent.resolve()
APP_DIR = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as fastapi_app
from app import JDEmailRequest, ResumeRequest
from test_migration_12key import get_sample_12_key_data

class TestFastAPIEndpoints(unittest.TestCase):

    def test_root_serves_html(self):
        res = asyncio.run(fastapi_app.read_root())
        self.assertIn("JD Resume Builder", res)
        self.assertIn("Job Description & Email Draft", res)

    def test_static_files_exist(self):
        static_dir = fastapi_app.STATIC_DIR
        self.assertTrue((static_dir / "index.html").exists())
        self.assertTrue((static_dir / "style.css").exists())
        self.assertTrue((static_dir / "script.js").exists())

    def test_get_resume_data(self):
        data = asyncio.run(fastapi_app.get_resume_data())
        self.assertIsInstance(data, dict)
        self.assertIn("TITLE", data)
        self.assertIn("SUMMARY", data)

    def test_draft_email_endpoint(self):
        req = JDEmailRequest(
            jd_text="Company: ABC Infrastructure\nPosition: Civil QA/QC Engineer\nLocation: Austin, TX\nContact: hiring@abcinfra.com\nSeeking engineer with ASTM experience."
        )
        old_is_cloud = fastapi_app.IS_CLOUD
        fastapi_app.IS_CLOUD = True
        try:
            data = asyncio.run(fastapi_app.draft_email(req))
            self.assertEqual(data.get("status"), "success")
            self.assertEqual(data.get("recipient"), "hiring@abcinfra.com")
            self.assertEqual(data.get("location"), "Austin, TX")
            self.assertIn("mail.google.com", data.get("gmail_url", ""))
        finally:
            fastapi_app.IS_CLOUD = old_is_cloud

    def test_generate_resume_invalid_payload_returns_400(self):
        req = ResumeRequest(json_content={"TITLE": "Engineer"})
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(fastapi_app.generate_resume(req))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Schema validation error", ctx.exception.detail)

    def test_generate_resume_cloud_mode_returns_docx_bytes(self):
        old_is_cloud = fastapi_app.IS_CLOUD
        fastapi_app.IS_CLOUD = True
        try:
            valid_payload = get_sample_12_key_data()
            req = ResumeRequest(json_content=valid_payload)
            response = asyncio.run(fastapi_app.generate_resume(req))

            # Verify response is a streaming Response with binary DOCX
            self.assertEqual(response.media_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            self.assertIn('attachment; filename="Revanth_Dirisipamu.docx"', response.headers.get("Content-Disposition", ""))

            # Verify the returned bytes form a valid, non-corrupted DOCX
            docx_bytes = io.BytesIO(response.body)
            doc = Document(docx_bytes)
            full_text = "\n".join(p.text for p in doc.paragraphs)

            # Confirm all 6 MEIL bullets appear
            for b in valid_payload["MEIL_BULLETS"]:
                self.assertIn(b, full_text)

            # Confirm all 7 Navayuga bullets appear
            for b in valid_payload["NAVAYUGA_BULLETS"]:
                self.assertIn(b, full_text)

            # Confirm dynamic Technical Expertise appears
            self.assertIn(valid_payload["TECHNICAL_EXPERTISE"], full_text)

            # Confirm static Software Proficiency & Certifications remain unchanged
            self.assertIn("AutoCAD, Civil 3D, Bluebeam, Microsoft Office", full_text)
            self.assertIn("OSHA 30-Hour Construction Safety, Bluebeam", full_text)

            # Confirm Gayatri experience is omitted
            self.assertNotIn("Gayatri Projects", full_text)
            self.assertNotIn("GAYATRI", full_text)

            # Confirm no unresolved Jinja placeholders remain
            self.assertNotIn("{{", full_text)
            self.assertNotIn("}}", full_text)
            self.assertNotIn("{%", full_text)
            self.assertNotIn("%}", full_text)

        finally:
            fastapi_app.IS_CLOUD = old_is_cloud

if __name__ == "__main__":
    unittest.main(verbosity=2)
