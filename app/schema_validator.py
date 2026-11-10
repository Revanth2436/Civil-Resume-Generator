from typing import List, Dict, Any, Tuple
import re
from pydantic import BaseModel, Field, field_validator, model_validator


# -------------------------------------------------------------
# EXACT 12-KEY ORDER
# -------------------------------------------------------------
EXACT_12_KEYS = [
    "TITLE",
    "LOCATION",
    "SUMMARY",
    "SOFTWARE_PROFICIENCY",
    "TECHNICAL_EXPERTISE",
    "CERTIFICATIONS",
    "MEIL_ROLE",
    "MEIL_BULLETS",
    "NAVAYUGA_ROLE",
    "NAVAYUGA_BULLETS",
    "GAYATRI_ROLE",
    "GAYATRI_BULLETS",
]

# Legacy 8 technical skill keys for backward compatibility adapter
OBSOLETE_8_SKILL_KEYS = [
    "QA_QC_SKILLS",
    "MATERIALS_TESTING_SKILLS",
    "TUNNELING_SKILLS",
    "GEOTECHNICAL_SKILLS",
    "HIGHWAY_SKILLS",
    "STANDARDS_SKILLS",
    "DOCUMENTATION_SKILLS",
    "COORDINATION_SKILLS",
]


def migrate_19_to_12_keys(data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Explicit migration adapter from legacy 19-key payload to new 12-key schema.
    If obsolete technical keys are detected and TECHNICAL_EXPERTISE is absent or empty,
    merges nonempty skills into TECHNICAL_EXPERTISE, strips obsolete keys, and orders by EXACT_12_KEYS.
    Returns (normalized_12_key_dict, was_migrated).
    """
    if not isinstance(data, dict):
        return data, False

    migrated = False
    new_data = dict(data)

    has_obsolete = any(k in new_data for k in OBSOLETE_8_SKILL_KEYS)
    if has_obsolete:
        migrated = True
        # If TECHNICAL_EXPERTISE is not explicitly supplied or empty, merge legacy skills
        if not new_data.get("TECHNICAL_EXPERTISE"):
            phrases = []
            seen = set()
            for k in OBSOLETE_8_SKILL_KEYS:
                val = new_data.get(k)
                if val and str(val).strip():
                    for item in re.split(r"[,;\n]", str(val)):
                        clean_item = item.strip()
                        if clean_item and clean_item.lower() not in seen:
                            seen.add(clean_item.lower())
                            phrases.append(clean_item)
            new_data["TECHNICAL_EXPERTISE"] = ", ".join(phrases)

        # Remove obsolete 8 skill keys
        for k in OBSOLETE_8_SKILL_KEYS:
            new_data.pop(k, None)

    # Ensure required compatibility defaults
    new_data.setdefault("SOFTWARE_PROFICIENCY", "")
    new_data.setdefault("CERTIFICATIONS", "")
    new_data.setdefault("GAYATRI_ROLE", "Internship")
    new_data.setdefault("GAYATRI_BULLETS", [])

    # Order keys strictly according to EXACT_12_KEYS (preserve missing status for validation)
    ordered = {}
    for k in EXACT_12_KEYS:
        if k in new_data:
            ordered[k] = new_data[k]

    # Copy any other unrecognized keys at the end if present
    for k, v in new_data.items():
        if k not in ordered:
            ordered[k] = v

    return ordered, migrated



def validate_resume_payload(data: Dict[str, Any], strict: bool = False) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """Validate resume JSON against the exact 12-key schema.
    Returns:
        (normalized_data, errors, warnings)
    """
    errors = []
    warnings = []

    if not isinstance(data, dict):
        errors.append("Resume payload must be a JSON object (dictionary).")
        return {}, errors, warnings

    # Check for legacy 19-key schema
    normalized, was_migrated = migrate_19_to_12_keys(data)
    if was_migrated:
        warnings.append(
            "Legacy 19-key payload detected. Automatically normalized to the 12-key schema with TECHNICAL_EXPERTISE."
        )

    # 1. Missing keys check
    missing_keys = [k for k in EXACT_12_KEYS if k not in normalized]
    if missing_keys:
        errors.append(f"Missing required 12-key fields: {', '.join(missing_keys)}")

    # 2. Strict key check (extra or misspelled keys)
    extra_keys = [k for k in normalized.keys() if k not in EXACT_12_KEYS]
    if extra_keys:
        msg = f"Unexpected extra or misspelled keys: {', '.join(extra_keys)}"
        if strict:
            errors.append(msg)
        else:
            warnings.append(msg)

    # 3. Bullets count validation
    meil_b = normalized.get("MEIL_BULLETS", [])
    if not isinstance(meil_b, list):
        errors.append("MEIL_BULLETS must be an array of strings.")
    else:
        clean_meil = [re.sub(r"\s+", " ", str(b)).strip() for b in meil_b if str(b).strip()]
        normalized["MEIL_BULLETS"] = clean_meil
        if len(clean_meil) != 6:
            msg = f"MEIL_BULLETS must contain exactly 6 bullets, found {len(clean_meil)}."
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

    nav_b = normalized.get("NAVAYUGA_BULLETS", [])
    if not isinstance(nav_b, list):
        errors.append("NAVAYUGA_BULLETS must be an array of strings.")
    else:
        clean_nav = [re.sub(r"\s+", " ", str(b)).strip() for b in nav_b if str(b).strip()]
        normalized["NAVAYUGA_BULLETS"] = clean_nav
        if len(clean_nav) != 7:
            msg = f"NAVAYUGA_BULLETS must contain exactly 7 bullets, found {len(clean_nav)}."
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

    # 4. Summary validation
    summary = normalized.get("SUMMARY", "")
    if isinstance(summary, list):
        summary = " ".join(str(s).strip() for s in summary if str(s).strip())
    clean_summary = re.sub(r"[\r\n\t]+", " ", str(summary))
    clean_summary = re.sub(r"\s+", " ", clean_summary).strip()
    normalized["SUMMARY"] = clean_summary

    if not clean_summary:
        errors.append("SUMMARY cannot be empty.")
    else:
        words = len(clean_summary.split())
        est_lines = max(1, (len(clean_summary) + 109) // 110)
        if est_lines > 5 or words > 85:
            warnings.append(
                f"SUMMARY has {words} words (~{est_lines} lines). Recommended target is <= 5 lines for strict 1-page fit."
            )

    # 5. Technical Expertise validation
    tech_exp = normalized.get("TECHNICAL_EXPERTISE", "")
    if isinstance(tech_exp, list):
        tech_exp = ", ".join(str(s).strip() for s in tech_exp if str(s).strip())
    normalized["TECHNICAL_EXPERTISE"] = str(tech_exp).strip()

    # Re-order dict to exact 12-key order
    final_ordered = {}
    for k in EXACT_12_KEYS:
        final_ordered[k] = normalized.get(k, "" if not k.endswith("_BULLETS") else [])

    return final_ordered, errors, warnings


class Resume12KeyPayload(BaseModel):
    TITLE: str
    LOCATION: str
    SUMMARY: str
    SOFTWARE_PROFICIENCY: str = ""
    TECHNICAL_EXPERTISE: str = ""
    CERTIFICATIONS: str = ""
    MEIL_ROLE: str
    MEIL_BULLETS: List[str]
    NAVAYUGA_ROLE: str
    NAVAYUGA_BULLETS: List[str]
    GAYATRI_ROLE: str = "Internship"
    GAYATRI_BULLETS: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_and_migration(cls, data: Any) -> Any:
        if isinstance(data, dict):
            migrated_data, _ = migrate_19_to_12_keys(data)
            return migrated_data
        return data

    @field_validator("MEIL_BULLETS")
    @classmethod
    def validate_meil_bullets(cls, v: List[str]) -> List[str]:
        cleaned = [re.sub(r"\s+", " ", str(b)).strip() for b in v if str(b).strip()]
        if len(cleaned) != 6:
            raise ValueError(f"MEIL_BULLETS must contain exactly 6 bullets, found {len(cleaned)}")
        return cleaned

    @field_validator("NAVAYUGA_BULLETS")
    @classmethod
    def validate_navayuga_bullets(cls, v: List[str]) -> List[str]:
        cleaned = [re.sub(r"\s+", " ", str(b)).strip() for b in v if str(b).strip()]
        if len(cleaned) != 7:
            raise ValueError(f"NAVAYUGA_BULLETS must contain exactly 7 bullets, found {len(cleaned)}")
        return cleaned

    def to_12_key_dict(self) -> Dict[str, Any]:
        """Return dict strictly in the exact 12-key order."""
        d = self.model_dump()
        return {k: d.get(k, "" if not k.endswith("_BULLETS") else []) for k in EXACT_12_KEYS}
