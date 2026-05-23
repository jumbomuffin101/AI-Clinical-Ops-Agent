import logging
import re
from dataclasses import dataclass
from enum import StrEnum

from app.logging_utils import log_event
from app.models.schemas import AuditFinding, CPTCodeCandidate, StructuredOperativeNote


logger = logging.getLogger(__name__)


class ProcedureFamily(StrEnum):
    APPENDECTOMY = "APPENDECTOMY"
    CHOLECYSTECTOMY = "CHOLECYSTECTOMY"
    HERNIA_REPAIR = "HERNIA_REPAIR"
    BOWEL_RESECTION = "BOWEL_RESECTION"
    AV_FISTULA = "AV_FISTULA"
    OTHER = "OTHER"


@dataclass(frozen=True)
class ReviewClassification:
    header_family: ProcedureFamily | None
    technique_family: ProcedureFamily | None
    diagnosis_family: ProcedureFamily | None
    procedure_family: ProcedureFamily | None
    findings_family: ProcedureFamily | None
    postop_family: ProcedureFamily | None
    procedure_header_procedures: set[ProcedureFamily]
    findings_procedures: set[ProcedureFamily]
    technique_procedures: set[ProcedureFamily]
    diagnosis_procedures: set[ProcedureFamily]
    procedure_conflict: bool
    conflict_reason: str | None
    valid_combined_procedure: bool
    explicit_multi_procedure_intent: bool


class ReviewEngine:
    FAMILY_KEYWORDS = {
        ProcedureFamily.APPENDECTOMY: [
            "appendectomy",
            "appendix",
            "mesoappendix",
            "right lower quadrant",
        ],
        ProcedureFamily.CHOLECYSTECTOMY: [
            "cholecystectomy",
            "gallbladder",
            "gallstones",
            "cholelithiasis",
            "cystic duct",
            "cystic artery",
            "liver bed",
        ],
        ProcedureFamily.HERNIA_REPAIR: [
            "hernia",
            "inguinal",
            "mesh",
            "inguinal ligament",
            "conjoint tendon",
        ],
        ProcedureFamily.BOWEL_RESECTION: [
            "bowel",
            "bowel resection",
            "small bowel",
            "ileum",
            "distal ileum",
            "anastomosis",
            "colectomy",
        ],
        ProcedureFamily.AV_FISTULA: [
            "av fistula",
            "arteriovenous fistula",
            "cephalic vein",
            "radial artery",
            "dialysis access",
        ],
    }
    PROCEDURE_NAME_FAMILIES = {
        "AV fistula creation": ProcedureFamily.AV_FISTULA,
        "Laparoscopic cholecystectomy": ProcedureFamily.CHOLECYSTECTOMY,
        "Laparoscopic cholecystectomy with cholangiography": ProcedureFamily.CHOLECYSTECTOMY,
        "Laparoscopic appendectomy": ProcedureFamily.APPENDECTOMY,
        "Appendectomy": ProcedureFamily.APPENDECTOMY,
        "Open inguinal hernia repair": ProcedureFamily.HERNIA_REPAIR,
        "Exploratory laparotomy": ProcedureFamily.BOWEL_RESECTION,
        "Small bowel resection": ProcedureFamily.BOWEL_RESECTION,
        "Bowel resection with anastomosis": ProcedureFamily.BOWEL_RESECTION,
        "Partial colectomy": ProcedureFamily.BOWEL_RESECTION,
    }
    MULTI_PROCEDURE_PHRASES = {
        "combined",
        "concurrent",
        "additional procedure",
        "performed together",
        "same operation",
        " with ",
    }
    SECTION_CONFIDENCE = {
        "technique": 4,
        "procedure_header": 3,
        "postop_diagnosis": 2,
        "findings": 1,
    }
    RAW_SECTION_NAMES = {
        "procedure": "procedure",
        "findings": "findings",
        "technique": "technique",
        "postoperative diagnosis": "postoperative_diagnosis",
    }
    RAW_SECTION_PATTERN = re.compile(
        r"\b(Procedure|Findings|Technique|Postoperative diagnosis)\s*:\s*",
        flags=re.IGNORECASE,
    )
    DETERMINISTIC_CONFLICT_FAMILIES = {
        ProcedureFamily.APPENDECTOMY,
        ProcedureFamily.CHOLECYSTECTOMY,
        ProcedureFamily.HERNIA_REPAIR,
        ProcedureFamily.BOWEL_RESECTION,
    }
    DEBUG_FAMILY_LABELS = {
        ProcedureFamily.APPENDECTOMY: "appendectomy",
        ProcedureFamily.CHOLECYSTECTOMY: "cholecystectomy",
        ProcedureFamily.HERNIA_REPAIR: "hernia",
        ProcedureFamily.BOWEL_RESECTION: "bowel",
    }

    @classmethod
    def validate_section_consistency(cls, note_text: str) -> dict:
        debug = cls.debug_section_analysis(note_text)
        has_conflict = debug["conflict_detected"]
        log_event(
            logger,
            logging.INFO,
            "section_consistency.validation",
            procedure_families=debug["procedure_families"],
            findings_families=debug["findings_families"],
            technique_families=debug["technique_families"],
            diagnosis_families=debug["diagnosis_families"],
            explicit_combined=debug["explicit_combined"],
            has_conflict=has_conflict,
        )
        if not has_conflict:
            return {
                "has_conflict": False,
                "review_status": None,
                "main_issue": None,
                "detected_procedure": None,
                "recommended_next_step": None,
                "coding_recommendation": None,
                "suggested_code": None,
            }
        return {
            "has_conflict": True,
            "review_status": "High Risk",
            "main_issue": "Procedure documentation conflict",
            "detected_procedure": "Conflicting procedure documentation",
            "recommended_next_step": "Confirm final operative procedure before coding.",
            "coding_recommendation": "Coder review needed",
            "suggested_code": None,
        }

    @classmethod
    def debug_section_analysis(cls, note_text: str) -> dict:
        sections = cls.extract_raw_sections(note_text)
        procedure_families = cls.deterministic_section_families(sections.get("procedure", ""))
        findings_families = cls.deterministic_section_families(sections.get("findings", ""))
        technique_families = cls.deterministic_section_families(sections.get("technique", ""))
        postop_families = cls.deterministic_section_families(sections.get("postoperative_diagnosis", ""))
        if "appendicitis" in sections.get("postoperative_diagnosis", "").lower():
            postop_families.add(ProcedureFamily.APPENDECTOMY)
        explicit_combined = len(procedure_families) > 1
        has_conflict = (
            not explicit_combined
            and len(procedure_families) == 1
            and len(technique_families) == 1
            and next(iter(procedure_families)) != next(iter(technique_families))
        )
        return {
            "procedure_text": sections.get("procedure", ""),
            "technique_text": sections.get("technique", ""),
            "findings_text": sections.get("findings", ""),
            "diagnosis_text": sections.get("postoperative_diagnosis", ""),
            "procedure_families": cls._debug_family_values(procedure_families),
            "technique_families": cls._debug_family_values(technique_families),
            "findings_families": cls._debug_family_values(findings_families),
            "diagnosis_families": cls._debug_family_values(postop_families),
            "explicit_combined": explicit_combined,
            "conflict_detected": has_conflict,
        }

    @classmethod
    def extract_raw_sections(cls, note_text: str) -> dict[str, str]:
        matches = list(cls.RAW_SECTION_PATTERN.finditer(note_text))
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            raw_label = re.sub(r"\s+", " ", match.group(1).strip().lower())
            label = cls.RAW_SECTION_NAMES.get(raw_label)
            if not label:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(note_text)
            sections[label] = note_text[match.end() : end].strip()
        return sections

    @classmethod
    def deterministic_section_family(cls, section_text: str) -> ProcedureFamily | None:
        families = cls.deterministic_section_families(section_text)
        if len(families) != 1:
            return None
        return next(iter(families))

    @classmethod
    def deterministic_section_families(cls, section_text: str) -> set[ProcedureFamily]:
        lowered = section_text.lower()
        return {
            family
            for family in cls.DETERMINISTIC_CONFLICT_FAMILIES
            if any(keyword in lowered for keyword in cls.FAMILY_KEYWORDS[family])
        }

    @classmethod
    def classify(
        cls,
        structured_note: StructuredOperativeNote,
        candidates: list[CPTCodeCandidate] | None = None,
    ) -> ReviewClassification:
        sections = structured_note.parsed_sections
        header_family = cls.normalize_procedure_family(sections.get("Procedure", ""))
        technique_family = cls.normalize_procedure_family(sections.get("Technique", ""))
        diagnosis_family = cls.normalize_procedure_family(sections.get("Postoperative diagnosis", ""))
        procedure_family = header_family
        findings_family = cls.strongest_family(sections.get("Findings", ""))
        postop_family = diagnosis_family
        procedure_header_procedures = cls.extract_section_procedures(sections.get("Procedure", ""))
        findings_procedures = cls.extract_section_procedures(sections.get("Findings", ""))
        technique_procedures = cls.extract_section_procedures(sections.get("Technique", ""))
        diagnosis_procedures = cls.extract_section_procedures(sections.get("Postoperative diagnosis", ""))
        procedure_text = sections.get("Procedure", "") or structured_note.raw_text
        explicit_multi_procedure_intent = cls.has_explicit_multi_procedure_intent(procedure_text)
        valid_combined_procedure = cls.is_valid_combined_procedure(procedure_header_procedures)

        header_technique_conflict = bool(header_family and technique_family and header_family != technique_family)
        diagnosis_technique_conflict = False
        procedure_conflict = False if valid_combined_procedure else header_technique_conflict
        conflict_reason = None
        if procedure_conflict and header_technique_conflict:
            procedure_conflict = True
            conflict_reason = "procedure_header_technique_mismatch"
        elif procedure_conflict and diagnosis_technique_conflict:
            conflict_reason = "diagnosis_technique_mismatch"

        classification = ReviewClassification(
            header_family=header_family,
            technique_family=technique_family,
            diagnosis_family=diagnosis_family,
            procedure_family=procedure_family,
            findings_family=findings_family,
            postop_family=postop_family,
            procedure_header_procedures=procedure_header_procedures,
            findings_procedures=findings_procedures,
            technique_procedures=technique_procedures,
            diagnosis_procedures=diagnosis_procedures,
            procedure_conflict=procedure_conflict,
            conflict_reason=conflict_reason,
            valid_combined_procedure=valid_combined_procedure,
            explicit_multi_procedure_intent=explicit_multi_procedure_intent,
        )
        log_event(
            logger,
            logging.INFO,
            "review.classification",
            header_family=classification.header_family,
            procedure_family=classification.procedure_family,
            findings_family=classification.findings_family,
            technique_family=classification.technique_family,
            diagnosis_family=classification.diagnosis_family,
            postop_family=classification.postop_family,
            procedure_header_procedures=cls._sorted_family_values(classification.procedure_header_procedures),
            findings_procedures=cls._sorted_family_values(classification.findings_procedures),
            technique_procedures=cls._sorted_family_values(classification.technique_procedures),
            diagnosis_procedures=cls._sorted_family_values(classification.diagnosis_procedures),
            procedure_conflict=classification.procedure_conflict,
            conflict_reason=classification.conflict_reason,
            valid_combined_procedure=classification.valid_combined_procedure,
        )
        return classification

    @classmethod
    def procedure_conflict_finding(
        cls,
        structured_note: StructuredOperativeNote,
        candidates: list[CPTCodeCandidate] | None = None,
    ) -> AuditFinding | None:
        classification = cls.classify(structured_note, candidates)
        if not classification.procedure_conflict:
            return None
        return cls.conflict_finding("Confirm final operative procedure before coding.")

    @classmethod
    def strongest_family(cls, text: str) -> ProcedureFamily | None:
        scores = cls.family_scores(text)
        if not scores:
            return None
        return max(scores.items(), key=lambda item: item[1])[0]

    @classmethod
    def family_scores(cls, text: str) -> dict[ProcedureFamily, int]:
        lowered = text.lower()
        return {
            family: sum(1 for keyword in keywords if keyword in lowered)
            for family, keywords in cls.FAMILY_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        }

    @classmethod
    def detected_candidate_families(cls, candidates: list[CPTCodeCandidate]) -> set[ProcedureFamily]:
        return {
            family
            for candidate in candidates
            if (family := cls.PROCEDURE_NAME_FAMILIES.get(candidate.procedure_name))
        }

    @classmethod
    def classify_section_family(cls, section_text: str) -> ProcedureFamily | None:
        return cls.strongest_family(section_text)

    @classmethod
    def normalize_procedure_family(cls, text: str) -> ProcedureFamily | None:
        return cls.strongest_family(text)

    @classmethod
    def extract_section_procedures(cls, section_text: str) -> set[ProcedureFamily]:
        lowered = section_text.lower()
        return {
            family
            for family, keywords in cls.FAMILY_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        }

    @staticmethod
    def is_valid_combined_procedure(procedure_header_procedures: set[ProcedureFamily]) -> bool:
        return len(procedure_header_procedures) > 1

    @classmethod
    def has_explicit_multi_procedure_intent(cls, procedure_text: str) -> bool:
        lowered = procedure_text.lower()
        if any(phrase in lowered for phrase in cls.MULTI_PROCEDURE_PHRASES):
            return True
        families = [
            family
            for family in cls.FAMILY_KEYWORDS
            if family in cls.family_scores(lowered)
        ]
        if len(families) < 2:
            return False
        return any(
            cls._families_linked(lowered, families[left_index], families[right_index])
            for left_index in range(len(families))
            for right_index in range(left_index + 1, len(families))
        )

    @classmethod
    def _families_linked(cls, text: str, left_family: ProcedureFamily, right_family: ProcedureFamily) -> bool:
        return any(
            cls._terms_linked(text, left_term, right_term)
            or cls._terms_linked(text, right_term, left_term)
            for left_term in cls.FAMILY_KEYWORDS[left_family]
            for right_term in cls.FAMILY_KEYWORDS[right_family]
        )

    @staticmethod
    def _sorted_family_values(families: set[ProcedureFamily]) -> list[str]:
        return sorted(family.value for family in families)

    @classmethod
    def _debug_family_values(cls, families: set[ProcedureFamily]) -> list[str]:
        return sorted(cls.DEBUG_FAMILY_LABELS.get(family, family.value.lower()) for family in families)

    @staticmethod
    def _terms_linked(text: str, left_term: str, right_term: str) -> bool:
        left_position = text.find(left_term)
        if left_position == -1:
            return False
        right_position = text.find(right_term, left_position + len(left_term))
        if right_position == -1:
            return False
        between = text[left_position + len(left_term) : right_position]
        return len(between) <= 120 and any(term in between for term in [" and ", " with ", " then ", " also ", " followed by "])

    @staticmethod
    def conflict_finding(recommendation: str = "Confirm final operative procedure before coding.") -> AuditFinding:
        return AuditFinding(
            title="Procedure documentation conflict",
            severity="high",
            category="procedure_documentation_conflict",
            related_code=None,
            message="Procedure documentation conflict detected.",
            explanation="The procedure label and operative details describe different services.",
            recommendation=recommendation,
            suggested_action=recommendation,
            documentation_improvement="Clarify whether the documented procedure, findings, and postoperative diagnosis refer to the same service.",
            why_it_matters="Coding should not proceed until contradictory operative documentation is reconciled.",
            evidence_used=[],
        )
