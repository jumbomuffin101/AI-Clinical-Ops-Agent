import re

from pydantic import BaseModel, Field


class SectionConsistencyResult(BaseModel):
    procedure_text: str = ""
    findings_text: str = ""
    technique_text: str = ""
    diagnosis_text: str = ""
    procedure_families: list[str] = Field(default_factory=list)
    findings_families: list[str] = Field(default_factory=list)
    technique_families: list[str] = Field(default_factory=list)
    diagnosis_families: list[str] = Field(default_factory=list)
    explicit_combined: bool = False
    procedure_conflict: bool = False
    conflict_reason: str | None = None

    def review_override(self) -> dict[str, str | None]:
        return {
            "review_status": "High Risk",
            "main_issue": "Procedure documentation conflict",
            "detected_procedure": "Conflicting procedure documentation",
            "recommended_next_step": "Confirm final operative procedure before coding.",
            "coding_recommendation": "Coder review needed",
            "suggested_code": None,
        }

_FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "appendectomy": (
        "appendectomy",
        "appendix",
        "appendicitis",
        "mesoappendix",
        "right lower quadrant",
    ),
    "cholecystectomy": (
        "cholecystectomy",
        "gallbladder",
        "gallstones",
        "cholelithiasis",
        "cholecystitis",
        "cystic duct",
        "cystic artery",
        "liver bed",
    ),
    "hernia": (
        "hernia",
        "inguinal",
        "mesh",
        "inguinal ligament",
        "conjoint tendon",
    ),
    "bowel_resection": (
        "bowel resection",
        "small bowel",
        "ileum",
        "distal ileum",
        "anastomosis",
        "colectomy",
    ),
    "av_fistula": (
        "av fistula",
        "arteriovenous fistula",
        "cephalic vein",
        "radial artery",
        "dialysis access",
    ),
}

_SECTION_LABELS = {
    "procedure": "procedure",
    "findings": "findings",
    "technique": "technique",
    "operative note": "operative_note",
    "postoperative diagnosis": "diagnosis",
    "post-op diagnosis": "diagnosis",
    "postop diagnosis": "diagnosis",
    "complications": "complications",
}

_LABEL_PATTERN = "|".join(re.escape(label) for label in sorted(_SECTION_LABELS, key=len, reverse=True))
_SECTION_PATTERN = re.compile(
    rf"(?im)(?:(?<=^)|(?<=[\n\r])|(?<=[.;]))\s*(?P<label>{_LABEL_PATTERN})\b\s*(?:[:\-])?\s*"
)


def analyze_section_consistency(note_text: str) -> SectionConsistencyResult:
    sections = _extract_sections(note_text)
    procedure_text = _join_sections(sections, {"procedure"})
    findings_text = _join_sections(sections, {"findings"})
    technique_text = _join_sections(sections, {"technique", "operative_note"})
    diagnosis_text = _join_sections(sections, {"diagnosis"})

    procedure_families = _match_families(procedure_text)
    findings_families = _match_families(findings_text)
    technique_families = _match_families(technique_text)
    diagnosis_families = _match_families(diagnosis_text)

    explicit_combined = len(procedure_families) > 1
    procedure_conflict = False
    conflict_reason: str | None = None

    if not explicit_combined and len(procedure_families) == 1:
        procedure_family = procedure_families[0]
        detail_families = technique_families

        if procedure_text.strip() and technique_text.strip() and len(detail_families) == 1 and detail_families[0] != procedure_family:
            procedure_conflict = True
            conflict_reason = (
                f"Procedure section documents {procedure_family} but operative details document {detail_families[0]}."
            )
        elif (
            technique_text.strip()
            and len(findings_families) == 1
            and len(technique_families) == 1
            and findings_families[0] != procedure_family
            and technique_families[0] != procedure_family
        ):
            procedure_conflict = True
            conflict_reason = (
                f"Procedure section documents {procedure_family} but findings and technique support a different service."
            )

    return SectionConsistencyResult(
        procedure_text=procedure_text,
        findings_text=findings_text,
        technique_text=technique_text,
        diagnosis_text=diagnosis_text,
        procedure_families=procedure_families,
        findings_families=findings_families,
        technique_families=technique_families,
        diagnosis_families=diagnosis_families,
        explicit_combined=explicit_combined,
        procedure_conflict=procedure_conflict,
        conflict_reason=conflict_reason,
    )


def extract_section_texts(note_text: str) -> dict[str, str]:
    sections = _extract_sections(note_text)
    return {
        "procedure": _join_sections(sections, {"procedure"}),
        "findings": _join_sections(sections, {"findings"}),
        "technique": _join_sections(sections, {"technique", "operative_note"}),
        "operative_note": _join_sections(sections, {"operative_note"}),
        "postoperative_diagnosis": _join_sections(sections, {"diagnosis"}),
        "complications": _join_sections(sections, {"complications"}),
    }


def matched_families(section_text: str) -> list[str]:
    return _match_families(section_text)


def _extract_sections(note_text: str) -> list[tuple[str, str]]:
    matches = list(_SECTION_PATTERN.finditer(note_text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        raw_label = re.sub(r"\s+", " ", match.group("label").strip().lower())
        canonical = _SECTION_LABELS.get(raw_label)
        if not canonical:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(note_text)
        content = note_text[match.end() : end].strip()
        sections.append((canonical, content))
    return sections


def _join_sections(sections: list[tuple[str, str]], names: set[str]) -> str:
    return "\n".join(text for name, text in sections if name in names and text).strip()


def _match_families(section_text: str) -> list[str]:
    lowered = section_text.lower()
    families = [
        family
        for family, keywords in _FAMILY_KEYWORDS.items()
        if any(_matches_keyword(lowered, keyword) for keyword in keywords)
    ]
    return sorted(families)


def _matches_keyword(text: str, keyword: str) -> bool:
    pattern = rf"\b{re.escape(keyword)}\b"
    return re.search(pattern, text) is not None
