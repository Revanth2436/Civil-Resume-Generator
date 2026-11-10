import unittest
import json
import os
import sys
from pathlib import Path
from docx import Document
from docxtpl import DocxTemplate

# Add parent directory to sys.path so we can import schema_validator and test_render
CURRENT_DIR = Path(__file__).parent.resolve()
APP_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "tests" else CURRENT_DIR
sys.path.insert(0, str(APP_DIR))

from schema_validator import (
    EXACT_12_KEYS,
    OBSOLETE_8_SKILL_KEYS,
    Resume12KeyPayload,
    validate_resume_payload,
    migrate_19_to_12_keys,
)
import test_render


def build_ctx(data):
    ctx = dict(data)
    ctx["ALL_SKILLS_ALIGNS_WITH_JD"] = ctx.get("TECHNICAL_EXPERTISE", "")
    return ctx



def get_sample_12_key_data():
    return {
        "TITLE": "Civil Project Engineer",
        "LOCATION": "Austin, TX",
        "SUMMARY": "Results-driven Civil Engineer with over four years of specialized experience in highway construction, geotechnical field testing, structural inspection, and QA/QC compliance. Proven track record managing materials verification, ITP execution, and site safety on major infrastructure projects. Dedicated to delivering high-quality engineering standards.",
        "SOFTWARE_PROFICIENCY": "",
        "TECHNICAL_EXPERTISE": "Highway Construction, Pavement Engineering, Concrete Testing, Soil Mechanics, ASTM Standards, Quality Assurance",
        "CERTIFICATIONS": "",
        "MEIL_ROLE": "Quality Control Civil Engineer",
        "MEIL_BULLETS": [
            "Conducted comprehensive field inspections for concrete placements and earthwork compaction per ASTM standards.",
            "Prepared and managed Inspection and Test Plans (ITPs) to verify civil work compliance.",
            "Reviewed subcontractor material submittals and coordinated laboratory compressive testing.",
            "Identified site discrepancies and coordinated Non-Conformance Reports (NCRs) with project management.",
            "Managed geotechnical data collection and maintained digital QA/QC verification records.",
            "Collaborated with project managers, surveyors, and field foremen to uphold safety and quality schedules."
        ],
        "NAVAYUGA_ROLE": "Junior Civil Field Engineer",
        "NAVAYUGA_BULLETS": [
            "Monitored subgrade preparation, roadway excavation, and backfill compaction across highway alignments.",
            "Supervised placement of aggregate base courses and asphalt paving operations under stringent tolerances.",
            "Inspected drainage culverts, storm sewer pipes, and retaining structure installations.",
            "Calculated daily earthwork cut-and-fill quantities and cross-referenced with surveyor field reports.",
            "Verified field alignment and elevation benchmarks alongside surveyor crews using total stations.",
            "Documented daily construction activities, equipment hours, weather logs, and workforce counts.",
            "Participated in weekly client progress meetings to present field inspection findings and resolved issues."
        ],
        "GAYATRI_ROLE": "Internship",
        "GAYATRI_BULLETS": []
    }


class TestResume12KeySchema(unittest.TestCase):

    def test_canonical_key_order_and_presence(self):
        """Test that the 12 keys exist in the exact required order."""
        data = get_sample_12_key_data()
        self.assertEqual(list(data.keys()), EXACT_12_KEYS)

        normalized, errors, warnings = validate_resume_payload(data, strict=True)
        self.assertEqual(errors, [])
        self.assertEqual(list(normalized.keys()), EXACT_12_KEYS)

    def test_missing_required_keys(self):
        """Test that missing required keys generate validation errors."""
        bad_data = get_sample_12_key_data()
        del bad_data["TECHNICAL_EXPERTISE"]
        del bad_data["SUMMARY"]

        normalized, errors, warnings = validate_resume_payload(bad_data, strict=False)
        self.assertTrue(any("TECHNICAL_EXPERTISE" in e for e in errors))
        self.assertTrue(any("SUMMARY" in e for e in errors))

    def test_wrong_key_names(self):
        """Test that misspelled key names generate validation errors or warnings."""
        bad_data = get_sample_12_key_data()
        bad_data["TECH_EXPERTISE"] = bad_data.pop("TECHNICAL_EXPERTISE")

        normalized, errors, warnings = validate_resume_payload(bad_data, strict=True)
        # Should flag missing TECHNICAL_EXPERTISE and unexpected TECH_EXPERTISE
        self.assertTrue(any("TECHNICAL_EXPERTISE" in e for e in errors))
        self.assertTrue(any("TECH_EXPERTISE" in e for e in errors))

    def test_extra_unexpected_keys(self):
        """Test that extra keys are detected and rejected in strict mode."""
        bad_data = get_sample_12_key_data()
        bad_data["UNKNOWN_EXTRA_KEY"] = "Extra Value"

        _, errors, warnings = validate_resume_payload(bad_data, strict=True)
        self.assertTrue(any("UNKNOWN_EXTRA_KEY" in e for e in errors))

    def test_wrong_array_lengths(self):
        """Test that MEIL != 6 bullets or NAVAYUGA != 7 bullets generates errors in strict mode."""
        # MEIL with 5 bullets
        bad_meil = get_sample_12_key_data()
        bad_meil["MEIL_BULLETS"] = bad_meil["MEIL_BULLETS"][:5]
        _, errors, warnings = validate_resume_payload(bad_meil, strict=True)
        self.assertTrue(any("MEIL_BULLETS" in e and "exactly 6" in e for e in errors))

        # NAVAYUGA with 8 bullets
        bad_nav = get_sample_12_key_data()
        bad_nav["NAVAYUGA_BULLETS"].append("Extra 8th bullet item.")
        _, errors, warnings = validate_resume_payload(bad_nav, strict=True)
        self.assertTrue(any("NAVAYUGA_BULLETS" in e and "exactly 7" in e for e in errors))

    def test_pydantic_model_validation(self):
        """Test Pydantic Resume12KeyPayload validation and serialization."""
        data = get_sample_12_key_data()
        model = Resume12KeyPayload(**data)
        ordered_dict = model.to_12_key_dict()
        self.assertEqual(list(ordered_dict.keys()), EXACT_12_KEYS)

        # Ensure bullet validation error in Pydantic model
        with self.assertRaises(ValueError):
            bad_data = get_sample_12_key_data()
            bad_data["MEIL_BULLETS"] = ["Only one bullet"]
            Resume12KeyPayload(**bad_data)

    def test_legacy_19_key_migration_adapter(self):
        """Test that obsolete 8 skill keys are merged into TECHNICAL_EXPERTISE and stripped."""
        legacy_data = {
            "TITLE": "Civil Project Engineer",
            "LOCATION": "Austin, TX",
            "SUMMARY": "Test summary for 19-key migration test.",
            "SOFTWARE_PROFICIENCY": "",
            "QA_QC_SKILLS": "Field Quality Control, Inspection Checklists",
            "MATERIALS_TESTING_SKILLS": "Concrete Slump, Soil Compaction",
            "TUNNELING_SKILLS": "NATM, Rock Bolt Pull-Out",
            "GEOTECHNICAL_SKILLS": "Subgrade Preparation",
            "HIGHWAY_SKILLS": "Asphalt Paving",
            "STANDARDS_SKILLS": "ASTM, IS Standards",
            "DOCUMENTATION_SKILLS": "Daily Reports",
            "COORDINATION_SKILLS": "Contractor Meetings",
            "CERTIFICATIONS": "",
            "MEIL_ROLE": "Quality Control Civil Engineer",
            "MEIL_BULLETS": [f"Bullet {i+1}" for i in range(6)],
            "NAVAYUGA_ROLE": "Junior Civil Field Engineer",
            "NAVAYUGA_BULLETS": [f"Bullet {i+1}" for i in range(7)],
            "GAYATRI_ROLE": "Internship",
            "GAYATRI_BULLETS": []
        }

        normalized, was_migrated = migrate_19_to_12_keys(legacy_data)
        self.assertTrue(was_migrated)
        self.assertEqual(list(normalized.keys()), EXACT_12_KEYS)
        self.assertNotIn("QA_QC_SKILLS", normalized)
        self.assertNotIn("MATERIALS_TESTING_SKILLS", normalized)
        self.assertIn("Field Quality Control", normalized["TECHNICAL_EXPERTISE"])
        self.assertIn("NATM", normalized["TECHNICAL_EXPERTISE"])
        self.assertIn("Asphalt Paving", normalized["TECHNICAL_EXPERTISE"])

    def test_empty_static_fields_preserves_template_text(self):
        """Test that SOFTWARE_PROFICIENCY='' and CERTIFICATIONS='' do NOT overwrite static template text."""
        data = get_sample_12_key_data()
        data["SOFTWARE_PROFICIENCY"] = ""
        data["CERTIFICATIONS"] = ""
        data["TECHNICAL_EXPERTISE"] = "Geotechnical Engineering, Soil Compaction"

        template_path = APP_DIR / "templates/resume_template.docx"
        out_doc_path = APP_DIR / "outputs/test_static_preservation.docx"

        # Render docx
        doc = DocxTemplate(str(template_path))
        ctx = build_ctx(data)
        doc.render(ctx)
        doc.save(str(out_doc_path))

        # Inspect resulting document
        rendered_doc = Document(str(out_doc_path))
        full_text = "\n".join(p.text for p in rendered_doc.paragraphs)

        # Verify static values exist untouched in active template
        self.assertIn("AutoCAD, Civil 3D, Bluebeam, Microsoft Office", full_text)
        self.assertIn("OSHA 30-Hour Construction Safety, Bluebeam", full_text)

        # Verify dynamic expertise is present
        self.assertIn("Geotechnical Engineering, Soil Compaction", full_text)

        # Clean up
        if out_doc_path.exists():
            out_doc_path.unlink()

    def test_empty_technical_expertise_row_hidden(self):
        """Test that empty TECHNICAL_EXPERTISE hides the row completely."""
        data = get_sample_12_key_data()
        data["TECHNICAL_EXPERTISE"] = ""

        # Test through render_resume pipeline
        temp_json = APP_DIR / "outputs/temp_test_empty.json"
        with temp_json.open("w", encoding="utf-8") as f:
            json.dump(data, f)

        out_docx = test_render.render_resume(json_input_path=temp_json)
        self.assertTrue(out_docx.exists())

        rendered_doc = Document(str(out_docx))
        full_text = "\n".join(p.text for p in rendered_doc.paragraphs)

        # Ensure no orphan "Technical Expertise:" paragraph exists with empty text
        for p in rendered_doc.paragraphs:
            if "Technical Expertise:" in p.text:
                self.assertTrue(len(p.text.replace("Technical Expertise:", "").strip()) > 0)

        # Clean up
        if temp_json.exists():
            temp_json.unlink()
        if out_docx.exists():
            out_docx.unlink()

    def test_special_characters_escaping(self):
        """Test that XML special characters (&, <, >, quotes, em-dashes) render cleanly without corruption."""
        data = get_sample_12_key_data()
        data["LOCATION"] = "Austin, TX & San Antonio, TX"
        data["SUMMARY"] = "Civil engineer handling \"heavy civil\" & deep foundations; <grade > tolerances — proven quality."
        data["TECHNICAL_EXPERTISE"] = "Testing & Verification <ASTM C39 & C136>, PQC & Asphalt Mixes — High Precision"
        data["MEIL_BULLETS"][0] = "Conducted & supervised ASTM <C39> compressive tests on concrete & grouts."

        temp_json = APP_DIR / "outputs/temp_test_special_chars.json"
        with temp_json.open("w", encoding="utf-8") as f:
            json.dump(data, f)

        out_docx = test_render.render_resume(json_input_path=temp_json)
        self.assertTrue(out_docx.exists())

        rendered_doc = Document(str(out_docx))
        full_text = "\n".join(p.text for p in rendered_doc.paragraphs)
        self.assertIn("Civil engineer handling \"heavy civil\" & deep foundations; <grade > tolerances — proven quality.", full_text)
        self.assertIn("Testing & Verification <ASTM C39 & C136>", full_text)
        self.assertIn("Conducted & supervised ASTM <C39> compressive tests on concrete & grouts.", full_text)

        # Clean up
        if temp_json.exists():
            temp_json.unlink()
        if out_docx.exists():
            out_docx.unlink()


    def test_end_to_end_docx_generation(self):
        """Test end-to-end rendering produces a valid DOCX file containing all 13 bullets."""
        data = get_sample_12_key_data()
        temp_json = APP_DIR / "outputs/temp_test_e2e.json"
        with temp_json.open("w", encoding="utf-8") as f:
            json.dump(data, f)

        out_docx = test_render.render_resume(json_input_path=temp_json)
        self.assertTrue(out_docx.exists())
        self.assertGreater(out_docx.stat().st_size, 10000)

        rendered_doc = Document(str(out_docx))
        full_text = "\n".join(p.text for p in rendered_doc.paragraphs)

        # Verify all 6 MEIL bullets are rendered
        for b in data["MEIL_BULLETS"]:
            self.assertIn(b, full_text)

        # Verify all 7 NAVAYUGA bullets are rendered
        for b in data["NAVAYUGA_BULLETS"]:
            self.assertIn(b, full_text)

        # Verify Gayatri is NOT rendered
        self.assertNotIn("Gayatri Projects", full_text)
        self.assertNotIn("GAYATRI", full_text)

        # Clean up
        if temp_json.exists():
            temp_json.unlink()
        if out_docx.exists():
            out_docx.unlink()

    def test_generate_docx_bytes_in_memory(self):
        """Test in-memory DOCX generation without any disk writes."""
        data = get_sample_12_key_data()
        template_path = APP_DIR / "templates/resume_template.docx"
        buf = test_render.generate_docx_bytes(data, template_path=template_path, strict=True)
        self.assertIsNotNone(buf)
        val = buf.getvalue()
        self.assertGreater(len(val), 10000)

        # Verify Document parses the buffer correctly
        rendered_doc = Document(buf)
        full_text = "\n".join(p.text for p in rendered_doc.paragraphs)

        # Verify all 6 MEIL and 7 Navayuga bullets appear
        for b in data["MEIL_BULLETS"]:
            self.assertIn(b, full_text)
        for b in data["NAVAYUGA_BULLETS"]:
            self.assertIn(b, full_text)

        # Verify static values remain unchanged
        self.assertIn("AutoCAD, Civil 3D, Bluebeam, Microsoft Office", full_text)
        self.assertIn("OSHA 30-Hour Construction Safety, Bluebeam", full_text)

        # Verify Technical Expertise appears
        self.assertIn(data["TECHNICAL_EXPERTISE"], full_text)

        # Verify Gayatri is excluded
        self.assertNotIn("Gayatri", full_text)
        self.assertNotIn("GAYATRI", full_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

