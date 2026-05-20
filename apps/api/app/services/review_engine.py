import logging
from dataclasses import dataclass

from app.logging_utils import log_event
from app.models.schemas import AuditFinding, CPTCodeCandidate, StructuredOperativeNote


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewClassification:
    procedure_family: str | None
    findings_family: str | None
    technique_family: str | None
    postop_family: str | None
    procedure_conflict: bool
    conflict_reason: str | None
    explicit_multi_procedure_intent: bool


class ReviewEngine:
    FAMILY_KEYWORDS = {
        "appendectomy": [
            "appendectomy",
            "appendix",
            "mesoappendix",
            "right lower quadrant",
        ],
        "cholecystectomy": [
            "cholecystectomy",
            "gallbladder",
            "gallstones",
            "cholelithiasis",
            "cystic duct",
            "cystic artery",
            "liver bed",
        ],
        "hernia": [
            "hernia",
            "inguinal",
            "mesh",
            "inguinal ligament",
            "conjoint tendon",
        ],
        "bowel_resection": [
            "bowel resection",
            "small bowel",
            "ileum",
            "distal ileum",
            "anastomosis",
            "colectomy",
        ],
    }
    PROCEDURE_NAME_FAMILIES = {
        "AV fistula creation": "vascular",
        "Femoral endarterectomy": "vascular",
        "Carotid endarterectomy": "vascular",
        "Lower extremity angiogram": "vascular",
        "Lower extremity vascular bypass": "vascular",
        "Laparoscopic cholecystectomy": "cholecystectomy",
        "Laparoscopic cholecystectomy with cholangiography": "cholecystectomy",
        "Laparoscopic appendectomy": "appendectomy",
        "Appendectomy": "appendectomy",
        "Open inguinal hernia repair": "hernia",
        "Exploratory laparotomy": "bowel_resection",
        "Small bowel resection": "bowel_resection",
        "Bowel resection with anastomosis": "bowel_resection",
        "Partial colectomy": "bowel_resection",
        "Diagnostic colonoscopy": "endoscopy",
        "Revision total knee arthroplasty": "orthopedic",
        "Revision total hip arthroplasty": "orthopedic",
    }
    MULTI_PROCEDURE_PHRASES = {
        "combined",
        "concurrent",
        "additional procedure",
        "performed together",
        "same operation",
    }

    @classmethod
    def classify(
        cls,
        structured_note: StructuredOperativeNote,
        candidates: list[CPTCodeCandidate] | None = None,
    ) -> ReviewClassification:
        sections = structured_note.parsed_sections
        procedure_family = cls.strongest_family(sections.get("Procedure", ""))
        findings_family = cls.strongest_family(sections.get("Findings", ""))
        technique_family = cls.strongest_family(sections.get("Technique", ""))
        postop_family = cls.strongest_family(sections.get("Postoperative diagnosis", ""))
        procedure_text = sections.get("Procedure", "") or structured_note.raw_text
        explicit_multi_procedure_intent = cls.has_explicit_multi_procedure_intent(procedure_text)

        procedure_conflict = False
        conflict_reason = None
        narrative_families = [findings_family, technique_family, postop_family]
        if procedure_family and not explicit_multi_procedure_intent:
            procedure_conflict = any(family and family != procedure_family for family in narrative_families)
            conflict_reason = "section_contradiction" if procedure_conflict else None
        if not procedure_conflict and candidates:
            candidate_families = cls.detected_candidate_families(candidates)
            procedure_conflict = len(candidate_families) > 1 and not explicit_multi_procedure_intent
            conflict_reason = "multi_family_without_intent" if procedure_conflict else None

        classification = ReviewClassification(
            procedure_family=procedure_family,
            findings_family=findings_family,
            technique_family=technique_family,
            postop_family=postop_family,
            procedure_conflict=procedure_conflict,
            conflict_reason=conflict_reason,
            explicit_multi_procedure_intent=explicit_multi_procedure_intent,
        )
        log_event(
            logger,
            logging.INFO,
            "review.classification",
            procedure_family=classification.procedure_family,
            findings_family=classification.findings_family,
            technique_family=classification.technique_family,
            postop_family=classification.postop_family,
            procedure_conflict=classification.procedure_conflict,
            conflict_reason=classification.conflict_reason,
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
        recommendation = (
            "Clarify performed procedure(s) before billing review."
            if classification.conflict_reason == "multi_family_without_intent"
            else "Confirm final operative procedure before coding."
        )
        return cls.conflict_finding(recommendation)

    @classmethod
    def strongest_family(cls, text: str) -> str | None:
        scores = cls.family_scores(text)
        if not scores:
            return None
        return max(scores.items(), key=lambda item: item[1])[0]

    @classmethod
    def family_scores(cls, text: str) -> dict[str, int]:
        lowered = text.lower()
        return {
            family: sum(1 for keyword in keywords if keyword in lowered)
            for family, keywords in cls.FAMILY_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        }

    @classmethod
    def detected_candidate_families(cls, candidates: list[CPTCodeCandidate]) -> set[str]:
        return {
            family
            for candidate in candidates
            if (family := cls.PROCEDURE_NAME_FAMILIES.get(candidate.procedure_name))
        }

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
    def _families_linked(cls, text: str, left_family: str, right_family: str) -> bool:
        return any(
            cls._terms_linked(text, left_term, right_term)
            or cls._terms_linked(text, right_term, left_term)
            for left_term in cls.FAMILY_KEYWORDS[left_family]
            for right_term in cls.FAMILY_KEYWORDS[right_family]
        )

    @staticmethod
    def _terms_linked(text: str, left_term: str, right_term: str) -> bool:
        left_position = text.find(left_term)
        if left_position == -1:
            return False
        right_position = text.find(right_term, left_position + len(left_term))
        if right_position == -1:
            return False
        between = text[left_position + len(left_term) : right_position]
        return len(between) <= 120 and any(term in between for term in [" and ", " then ", " also ", " followed by "])

    @staticmethod
    def conflict_finding(recommendation: str) -> AuditFinding:
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
