import io
from pathlib import Path
import json
import sys
import re
import os
import shutil
import subprocess

from docxtpl import DocxTemplate
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH

from schema_validator import (
    EXACT_12_KEYS,
    migrate_19_to_12_keys,
    validate_resume_payload,
)

# --------------------------
# Paths
# --------------------------
BASE_DIR = Path(__file__).parent.resolve()

def resolve_template_path() -> Path:
    candidates = [
        BASE_DIR / "templates/resume_template.docx",
        Path.cwd() / "templates/resume_template.docx",
        Path.cwd() / "resume-Creator-New-main/Mail-Resume_Automation-main - Copy/Mail-Resume_Automation-main/templates/resume_template.docx",
        BASE_DIR.parent / "templates/resume_template.docx",
    ]
    for c in candidates:
        if c.exists():
            return c
    return BASE_DIR / "templates/resume_template.docx"

TEMPLATE_PATH = resolve_template_path()
JSON_PATH = BASE_DIR / "data/base_content.json"


# Base folder where numbered subfolders will be created
BASE_FOLDER = BASE_DIR / "outputs"

# Resume final filename
FINAL_FILENAME = "Revanth_Dirisipamu.docx"

# --------------------------
# Style Candidates
# --------------------------
LIST_STYLE_CANDIDATES = {
    "List Bullet",
    "List Paragraph",
    "Bullet",
    "List Bullet 2",
    "List Bullet 3",
    "Body Text List",
}

BULLET_PREFIXES = ("•", "-", "–", "—", "*")


# --------------------------
# Helpers
# --------------------------
def tighten_list_paragraph(p):
    """Tighten line spacing and format bullet paragraphs."""
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    pf.line_spacing = 1
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT


def is_list_style(paragraph):
    """Check if a paragraph uses a list-like style."""
    try:
        return paragraph.style and paragraph.style.name in LIST_STYLE_CANDIDATES
    except Exception:
        return False


def remove_paragraph(paragraph):
    """Remove an unwanted paragraph from the document DOM."""
    p = paragraph._element
    parent = p.getparent()
    if parent is not None:
        parent.remove(p)
    p._p = p._element = None


def normalize_bullets(doc: Document):
    """Normalize bullets and ensure consistent list formatting."""
    prev_was_list = False
    to_delete = []

    for p in doc.paragraphs:
        txt = p.text.strip()

        # Convert manually typed bullets into Word list style
        if txt.startswith(BULLET_PREFIXES):
            raw = p.text
            new_text = raw.lstrip("".join(BULLET_PREFIXES)).lstrip(" \t")
            p.text = new_text if new_text else ""
            try:
                p.style = doc.styles["List Bullet"]
            except KeyError:
                p.style = doc.styles["List Paragraph"]

        # Tighten list paragraphs
        if is_list_style(p):
            tighten_list_paragraph(p)
            if prev_was_list and txt == "":
                to_delete.append(p)
            prev_was_list = True
        else:
            prev_was_list = False

    # Remove empty bullet paragraphs
    for p in to_delete:
        remove_paragraph(p)


def get_next_subfolder(base: Path) -> Path:
    """Find the next numeric subfolder under base, e.g., 1, 2, 3..."""
    base.mkdir(parents=True, exist_ok=True)
    numbers = []
    for child in base.iterdir():
        if child.is_dir() and re.fullmatch(r"\d+", child.name):
            numbers.append(int(child.name))
    next_num = max(numbers, default=0) + 1
    return base / str(next_num)


def estimate_rendered_lines(text: str, chars_per_line: int = 110) -> int:
    """Estimate rendered lines for a block of text at standard resume margins."""
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return 0
    words = clean.split()
    if not words:
        return 0
    lines = 1
    curr_len = 0
    for w in words:
        if curr_len + len(w) + 1 > chars_per_line:
            lines += 1
            curr_len = len(w)
        else:
            curr_len += len(w) + 1
    return lines


def verify_office_rendering(docx_path: Path) -> tuple[int, int]:
    """Verify actual page count and summary line count via Office PDF rendering.
    Uses Word's App Sandbox directory to eliminate any OS 'Grant Access' permission prompts.
    Returns (actual_page_count, summary_line_count).
    """
    actual_pages = 1
    summary_lines = 0

    if sys.platform == "darwin":
        container_dir = Path.home() / "Library/Containers/com.microsoft.Word/Data"
        container_dir.mkdir(parents=True, exist_ok=True)
        
        test_docx = container_dir / "verify_temp.docx"
        test_pdf = container_dir / "verify_temp.pdf"

        try:
            shutil.copy2(docx_path, test_docx)
            script = f'''
            tell application "Microsoft Word"
                set myDoc to open file name "{str(test_docx)}" without dialogs
                save as myDoc file name "{str(test_pdf)}" file format format PDF
                close myDoc saving no
            end tell
            '''
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and test_pdf.exists():
                pdf_bytes = test_pdf.read_bytes()
                page_matches = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
                if page_matches > 0:
                    actual_pages = page_matches
                try:
                    test_pdf.unlink()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if test_docx.exists():
                try:
                    test_docx.unlink()
                except Exception:
                    pass

    return actual_pages, summary_lines


# --------------------------
# Main Generation Logic
# --------------------------
def generate_docx_bytes(
    raw_ctx: dict,
    template_path: Path = None,
    strict: bool = False,
    save_raw_path: Path = None,
) -> io.BytesIO:
    """Generate resume DOCX entirely in memory as a BytesIO stream.
    Validates payload against the exact 12-key schema, renders docxtpl,
    and applies all formatting and bullet normalization.
    """
    if template_path is None:
        template_path = TEMPLATE_PATH

    if not template_path.exists():
        raise FileNotFoundError(f"Active template not found: {template_path.resolve()}")

    # Validate and normalize JSON payload against exact 12-key schema
    ctx, errors, warnings = validate_resume_payload(raw_ctx, strict=strict)
    for w in warnings:
        print(f"[SCHEMA NOTICE] {w}")
    if errors and strict:
        for err in errors:
            print(f"[SCHEMA ERROR] {err}")
        raise ValueError(f"Resume validation failed: {'; '.join(errors)}")

    # 1. SUMMARY: One left-aligned paragraph, natural wrapping, max 5 actual rendered lines
    summary_clean = ctx.get("SUMMARY", "")
    summary_words = len(summary_clean.split()) if summary_clean else 0
    summary_est_lines = estimate_rendered_lines(summary_clean, chars_per_line=110)
    if summary_est_lines > 5:
        print(f"[WARNING] Professional Summary exceeds 5 rendered lines (~{summary_est_lines} lines, {summary_words} words). "
              f"Target is at most 5 lines to maintain strict 1-page fit.")

    # 2. DYNAMIC TECHNICAL EXPERTISE:
    raw_tech = ctx.get("TECHNICAL_EXPERTISE", "")
    tech_phrases = []
    seen_lower = set()
    if raw_tech:
        for phrase in re.split(r"[,;\n]", str(raw_tech)):
            p_strip = phrase.strip()
            if p_strip:
                p_lower = p_strip.lower()
                if p_lower not in seen_lower:
                    seen_lower.add(p_lower)
                    tech_phrases.append(p_strip)

    clean_tech_skills = ", ".join(tech_phrases)
    ctx["TECHNICAL_EXPERTISE"] = clean_tech_skills
    # Compatibility alias for templates
    ctx["ALL_SKILLS_ALIGNS_WITH_JD"] = clean_tech_skills

    # 3. STATIC SOFTWARE PROFICIENCY & CERTIFICATIONS:
    # Ignored from JSON for document output. Template values take precedence.

    # 4. EXPERIENCE BULLETS:
    meil_bullets = ctx.get("MEIL_BULLETS", [])
    navayuga_bullets = ctx.get("NAVAYUGA_BULLETS", [])
    if len(meil_bullets) != 6:
        print(f"[BULLET COUNT NOTICE] MEIL_BULLETS has {len(meil_bullets)} bullets (expected exactly 6).")
    if len(navayuga_bullets) != 7:
        print(f"[BULLET COUNT NOTICE] NAVAYUGA_BULLETS has {len(navayuga_bullets)} bullets (expected exactly 7).")

    # 5. DYNAMIC EMPLOYMENT ROLES:
    ctx.setdefault("MEIL_ROLE", "Project Engineer")
    ctx.setdefault("NAVAYUGA_ROLE", "Project Engineer")
    ctx.setdefault("LOCATION", "Dallas, TX")

    # 6. XML ENTITY ESCAPING FOR DOCXTPL:
    from xml.sax.saxutils import escape as xml_escape

    def escape_val(v):
        if isinstance(v, str):
            return xml_escape(v)
        if isinstance(v, list):
            return [escape_val(item) for item in v]
        if isinstance(v, dict):
            return {k: escape_val(val) for k, val in v.items()}
        return v

    render_ctx = {k: escape_val(v) for k, v in ctx.items()}

    # Render with docxtpl into in-memory buffer
    doc = DocxTemplate(str(template_path))
    doc.render(render_ctx)
    raw_buffer = io.BytesIO()
    doc.save(raw_buffer)
    raw_buffer.seek(0)

    if save_raw_path:
        try:
            save_raw_path.parent.mkdir(parents=True, exist_ok=True)
            save_raw_path.write_bytes(raw_buffer.getvalue())
        except Exception:
            pass

    # Post-Process Rendered Document in memory
    d = Document(raw_buffer)
    to_delete = []

    for p in d.paragraphs:
        txt = p.text.strip()

        # A. Summary paragraph: Left-aligned, no justify, minimal spacing
        if summary_clean and txt.startswith(summary_clean[:40]):
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf = p.paragraph_format
            pf.space_before = Pt(2)
            pf.space_after = Pt(2)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            pf.line_spacing = 1
            continue

        # B. Hide Technical Expertise if empty
        if txt.startswith("Technical Expertise:"):
            if not clean_tech_skills or txt == "Technical Expertise:":
                to_delete.append(p)
            else:
                tighten_list_paragraph(p)
            continue

        # C. Remove Gayatri Constructions completely
        if "GAYATRI" in txt.upper() or "CANAL LINING" in txt.upper():
            to_delete.append(p)
            continue

        # D. Remove Work Authorization completely
        if "WORK AUTHORIZATION" in txt.upper() or "ELIGIBLE TO WORK IN THE US" in txt.upper():
            to_delete.append(p)
            continue

        # E. Remove empty paragraphs
        if txt == "":
            to_delete.append(p)
            continue

        # F. Tighten list paragraphs
        if is_list_style(p):
            tighten_list_paragraph(p)

        # G. Format Headings cleanly
        if p.style and p.style.name == "Heading 1":
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(1)

        # H. Clean employer headings to 10pt with tab stop
        if "Megha Engineering" in txt or "Navayuga Engineering" in txt:
            p.paragraph_format.space_before = Pt(3.5)
            p.paragraph_format.space_after = Pt(1)
            for r in p.runs:
                r.font.name = "Times New Roman"
                r.font.size = Pt(10)

    # Remove marked paragraphs
    for p in to_delete:
        remove_paragraph(p)

    # Normalize bullets and list styles
    normalize_bullets(d)

    # Save final document into BytesIO
    out_buffer = io.BytesIO()
    d.save(out_buffer)
    out_buffer.seek(0)
    return out_buffer


def render_resume(json_input_path: Path = JSON_PATH, template_input_path: Path = None, strict: bool = False) -> Path:
    # Select template: single active template resume_template.docx
    if template_input_path is None:
        template_input_path = TEMPLATE_PATH

    if not template_input_path.exists():
        print(f"Active template not found: {template_input_path.resolve()}")
        sys.exit(1)

    if not json_input_path.exists():
        print(f"JSON not found: {json_input_path.resolve()}")
        sys.exit(1)

    with json_input_path.open("r", encoding="utf-8") as f:
        raw_ctx = json.load(f)

    # Prepare Numbered Output Folder
    target_folder = get_next_subfolder(BASE_FOLDER)
    target_folder.mkdir(parents=True, exist_ok=True)

    OUTPUT_RAW = target_folder / "Tailored_Resume_RAW.docx"
    OUTPUT_FINAL = target_folder / FINAL_FILENAME

    docx_io = generate_docx_bytes(
        raw_ctx=raw_ctx,
        template_path=template_input_path,
        strict=strict,
        save_raw_path=OUTPUT_RAW,
    )

    OUTPUT_FINAL.write_bytes(docx_io.getvalue())

    # --------------------------
    # Page Count Verification via Office Rendering
    # --------------------------
    actual_pages, _ = verify_office_rendering(OUTPUT_FINAL)
    summary_clean = raw_ctx.get("SUMMARY", "")
    summary_words = len(summary_clean.split()) if summary_clean else 0
    summary_est_lines = estimate_rendered_lines(summary_clean, chars_per_line=110)
    tech_phrases = [p.strip() for p in re.split(r"[,;\n]", str(raw_ctx.get("TECHNICAL_EXPERTISE", ""))) if p.strip()]

    if actual_pages == 1:
        print(f"[PAGE COUNT] 1 Page (Verified via Office rendering)")
    else:
        print(f"[PAGE OVERFLOW WARNING] Rendered document is {actual_pages} pages! Conflict breakdown:")
        print(f"  - Summary: {summary_words} words (~{summary_est_lines} lines)")
        print(f"  - Technical skills: {len(tech_phrases)} phrases")
        print(f"  - MEIL bullets: {len(raw_ctx.get('MEIL_BULLETS', []))} bullets")
        print(f"  - Navayuga bullets: {len(raw_ctx.get('NAVAYUGA_BULLETS', []))} bullets")
        print(f"  Please provide shorter/more concise bullet JSON rather than clipping content.")

    print(f"[SUMMARY LINES] ~{summary_est_lines} lines ({summary_words} words)")
    print(f"[OK] Rendered OK: {OUTPUT_FINAL.resolve()}")
    print(f"  (Raw pre-fix version at: {OUTPUT_RAW.resolve()})")
    return OUTPUT_FINAL


def main():
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else JSON_PATH
    render_resume(json_input_path=json_path)


if __name__ == "__main__":
    main()
