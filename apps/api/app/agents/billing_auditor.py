from app.models.schemas import AuditFinding, CPTCodeCandidate, StructuredOperativeNote
from app.rag.retriever import KeywordRetriever


class BillingAuditor:
    BUNDLED_CODES = {("47562", "47563")}
    PROCEDURE_CONCEPT_GROUPS = {
        "appendectomy": ["appendix", "appendectomy", "mesoappendix", "appendicitis"],
        "cholecystectomy": [
            "gallbladder",
            "cholecystectomy",
            "cystic duct",
            "cystic artery",
            "liver bed",
            "gallstones",
            "cholelithiasis",
            "cholecystitis",
        ],
        "hernia": ["hernia", "mesh", "mesh repair", "inguinal ligament"],
        "bowel_resection": ["bowel resection", "small bowel", "ileum", "anastomosis", "colectomy"],
    }
    LATERALITY_SENSITIVE_CODES = {"36821", "35371", "35301", "49505", "75710"}
    LATERALITY_SENSITIVE_FAMILIES = {"vascular_access", "vascular_surgery", "angiography", "hernia", "orthopedics", "breast", "eye"}
    LATERALITY_SENSITIVE_TERMS = {
        "hernia",
        "fistula",
        "extremity",
        "unilateral",
        "femoral",
        "carotid",
        "angiogram",
        "angiography",
        "bypass",
        "kidney",
        "renal",
        "nephrectomy",
        "breast",
        "mastectomy",
        "lumpectomy",
        "eye",
        "cataract",
        "retina",
    }
    NON_LATERALITY_TERMS = {
        "bowel",
        "appendectomy",
        "appendix",
        "laparotomy",
        "cholecystectomy",
        "colectomy",
        "abdominal exploration",
        "exploratory laparotomy",
        "small bowel",
        "gallbladder",
    }
    PROCEDURE_FAMILIES = {
        "AV fistula creation": "vascular_access",
        "Femoral endarterectomy": "vascular_surgery",
        "Carotid endarterectomy": "vascular_surgery",
        "Laparoscopic cholecystectomy": "general_surgery",
        "Laparoscopic cholecystectomy with cholangiography": "general_surgery",
        "Laparoscopic appendectomy": "general_surgery",
        "Appendectomy": "general_surgery",
        "Open inguinal hernia repair": "hernia",
        "Diagnostic colonoscopy": "endoscopy",
        "Lower extremity angiogram": "angiography",
    }
    DETECTED_PROCEDURE_FAMILIES = {
        "AV fistula creation": "vascular",
        "Femoral endarterectomy": "vascular",
        "Carotid endarterectomy": "vascular",
        "Lower extremity angiogram": "vascular",
        "Laparoscopic cholecystectomy": "gallbladder",
        "Laparoscopic cholecystectomy with cholangiography": "gallbladder",
        "Laparoscopic appendectomy": "appendix",
        "Appendectomy": "appendix",
        "Open inguinal hernia repair": "hernia",
        "Exploratory laparotomy": "bowel",
        "Small bowel resection": "bowel",
        "Bowel resection with anastomosis": "bowel",
        "Partial colectomy": "bowel",
        "Diagnostic colonoscopy": "endoscopy",
        "Revision total knee arthroplasty": "orthopedic",
        "Revision total hip arthroplasty": "orthopedic",
        "Lower extremity vascular bypass": "vascular",
    }
    MULTI_PROCEDURE_PHRASES = {
        "combined procedure",
        "performed together",
        "same operation",
        "concurrent procedure",
        "additional procedure",
        "followed by",
    }

    def __init__(self, retriever: KeywordRetriever):
        self.retriever = retriever

    def run(self, candidates: list[CPTCodeCandidate], structured_note: StructuredOperativeNote | None = None) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        codes = {candidate.code for candidate in candidates}

        for candidate in candidates:
            docs = self.retriever.retrieve(
                f"audit {candidate.code} modifiers bundling {candidate.procedure_name}",
                family=self.PROCEDURE_FAMILIES.get(candidate.procedure_name),
            )
            evidence_used = [
                {"source": str(doc["source"]), "snippet": str(doc["snippet"]), "score": int(doc["score"])}
                for doc in docs
            ]
            if candidate.code == "99999" or not candidate.supported_by_docs:
                findings.append(
                    AuditFinding(
                        title="Unsupported procedure",
                        severity="high",
                        category="unsupported_code",
                        related_code=candidate.code,
                        message="Unsupported procedure identified.",
                        explanation=f"{candidate.code} is not supported by the local demo guideline set.",
                        recommendation="Route to certified coder review before billing.",
                        suggested_action="Do not submit this code until a supported code or reference is confirmed.",
                        documentation_improvement="Confirm the correct billable procedure and supporting reference before coding.",
                        why_it_matters="Unsupported codes create denial and compliance risk during billing review.",
                        evidence_used=evidence_used,
                    )
                )
            if candidate.confidence < 0.75:
                findings.append(
                    AuditFinding(
                        title="Low confidence coding",
                        severity="medium",
                        category="low_confidence",
                        related_code=candidate.code,
                        message="Low confidence coding.",
                        explanation=f"The procedure-to-code match confidence is {candidate.confidence:.0%}, which indicates documentation or matching ambiguity.",
                        recommendation="Validate operative details against payer guidance.",
                        suggested_action="Clarify the procedure documentation before final billing review.",
                        documentation_improvement="Clarify the exact procedure performed and whether it was diagnostic or therapeutic.",
                        why_it_matters="Clear procedure intent improves CPT selection, coding confidence, and reimbursement predictability.",
                        evidence_used=evidence_used,
                    )
                )
            if self._requires_laterality(candidate) and not any(mod in candidate.modifiers for mod in ["LT", "RT"]):
                findings.append(
                    AuditFinding(
                        title="Missing laterality",
                        severity="medium",
                        category="missing_laterality",
                        related_code=candidate.code,
                        message="Missing laterality.",
                        explanation="The note does not clearly document left or right side, which may affect modifier selection.",
                        recommendation="Clarify laterality before final billing review.",
                        suggested_action="Clarify laterality before final billing review.",
                        documentation_improvement="Document whether the procedure was performed on the left or right side.",
                        why_it_matters="Billing teams need laterality to select LT or RT modifiers and avoid payer follow-up.",
                        evidence_used=evidence_used,
                    )
                )

        if structured_note:
            missing_section_severity = "medium" if len(structured_note.parsed_sections) >= 2 else "low"
            for section in structured_note.missing_sections:
                findings.append(
                    AuditFinding(
                        title=f"{section} section missing",
                        severity=missing_section_severity,
                        category="missing_note_section",
                        related_code=None,
                        message=f"{section} section missing.",
                        explanation=f"The operative note did not include a clear {section.lower()} section.",
                        recommendation=f"Add {section.lower()} for clearer coding support.",
                        suggested_action=f"Add {section.lower()} for clearer coding support.",
                        documentation_improvement=f"Add a clear {section.lower()} section to the operative note.",
                        why_it_matters="Billing reviewers use note structure to confirm the coded service is supported by the documentation.",
                        evidence_used=[],
                    )
                )

            conflict = self._conflicting_documentation_finding(structured_note)
            if conflict:
                findings.append(conflict)

            multi_family_conflict = self._multi_family_procedure_conflict(candidates, structured_note)
            if multi_family_conflict and not any(finding.category == "procedure_documentation_conflict" for finding in findings):
                findings.append(multi_family_conflict)

        for left, right in self.BUNDLED_CODES:
            if left in codes and right in codes:
                findings.append(
                    AuditFinding(
                        title="Bundling conflict detected",
                        severity="high",
                        category="bundling_conflict",
                        related_code=f"{left},{right}",
                        message="Bundling conflict detected.",
                        explanation="The note produced two cholecystectomy candidates that should not both be submitted for the same operative session.",
                        recommendation="Bill only the supported definitive code for the documented service.",
                        suggested_action="Resolve the code conflict before submission.",
                        documentation_improvement="Review whether both procedures should be billed together or select the single supported definitive code.",
                        why_it_matters="Bundled services may be denied or create billing compliance risk if both codes are submitted.",
                        evidence_used=[],
                    )
                )

        if not findings:
            findings.append(
                AuditFinding(
                    title="No major billing risks found",
                    severity="info",
                    category="clean_claim",
                    related_code=None,
                    message="No major billing risks found.",
                    explanation="The local demo checks did not identify missing modifiers, unsupported codes, bundling conflicts, or low-confidence coding.",
                    recommendation="Proceed with human review for final billing validation.",
                    suggested_action="Proceed with standard billing review.",
                    documentation_improvement="No documentation improvement required from the local demo checks.",
                    why_it_matters="A clean review gives billing teams a clearer path to standard coding validation.",
                    evidence_used=[],
                )
            )
        return findings

    @classmethod
    def _requires_laterality(cls, candidate: CPTCodeCandidate) -> bool:
        procedure_name = candidate.procedure_name.lower()
        description = candidate.description.lower()
        combined = f"{procedure_name} {description}"
        if any(term in combined for term in cls.NON_LATERALITY_TERMS):
            return False
        family = cls.PROCEDURE_FAMILIES.get(candidate.procedure_name)
        return (
            candidate.code in cls.LATERALITY_SENSITIVE_CODES
            or family in cls.LATERALITY_SENSITIVE_FAMILIES
            or any(term in combined for term in cls.LATERALITY_SENSITIVE_TERMS)
        )

    @classmethod
    def _conflicting_documentation_finding(cls, structured_note: StructuredOperativeNote) -> AuditFinding | None:
        sections = {name: text.lower() for name, text in structured_note.parsed_sections.items()}
        if not sections:
            return None

        section_families = {
            "procedure": cls._strongest_section_family(sections.get("Procedure", "")),
            "findings": cls._strongest_section_family(sections.get("Findings", "")),
            "technique": cls._strongest_section_family(sections.get("Technique", "")),
            "postop": cls._strongest_section_family(sections.get("Postoperative diagnosis", "")),
        }
        present_families = {family for family in section_families.values() if family}
        if len(present_families) < 2:
            return None

        procedure_family = section_families["procedure"]
        narrative_families = [section_families["findings"], section_families["technique"]]
        postop_family = section_families["postop"]

        if procedure_family and any(family and family != procedure_family for family in [*narrative_families, postop_family]):
            return cls._conflict_finding()
        if postop_family and any(family and family != postop_family for family in narrative_families):
            return cls._conflict_finding()
        if len(present_families) > 1 and any(narrative_families):
            return cls._conflict_finding()
        return None

    @classmethod
    def _section_concepts(cls, text: str) -> set[str]:
        lowered = text.lower()
        return {
            concept
            for concept, terms in cls.PROCEDURE_CONCEPT_GROUPS.items()
            if any(term in lowered for term in terms)
        }

    @classmethod
    def _strongest_section_family(cls, text: str) -> str | None:
        scores = cls._section_family_scores(text)
        if not scores:
            return None
        return max(scores.items(), key=lambda item: item[1])[0]

    @classmethod
    def _section_family_scores(cls, text: str) -> dict[str, int]:
        lowered = text.lower()
        return {
            concept: sum(1 for term in terms if term in lowered)
            for concept, terms in cls.PROCEDURE_CONCEPT_GROUPS.items()
            if any(term in lowered for term in terms)
        }

    @staticmethod
    def _conflict_finding() -> AuditFinding:
        return AuditFinding(
            title="Procedure documentation conflict",
            severity="high",
            category="procedure_documentation_conflict",
            related_code=None,
            message="Procedure documentation conflict detected.",
            explanation="The documented procedure, findings, technique, or postoperative diagnosis appear to describe different operations.",
            recommendation="Confirm final operative procedure before coding.",
            suggested_action="Confirm final operative procedure before coding.",
            documentation_improvement="Clarify whether the documented procedure, findings, and postoperative diagnosis refer to the same service.",
            why_it_matters="Contradictory operative documentation can lead to incorrect coding and should be resolved before submission.",
            evidence_used=[],
        )

    @classmethod
    def _multi_family_procedure_conflict(
        cls,
        candidates: list[CPTCodeCandidate],
        structured_note: StructuredOperativeNote,
    ) -> AuditFinding | None:
        families = cls._detected_candidate_families(candidates)
        if len(families) < 2:
            return None
        if cls._has_explicit_multi_procedure_intent(structured_note.raw_text, families):
            return None
        return AuditFinding(
            title="Procedure documentation conflict",
            severity="high",
            category="procedure_documentation_conflict",
            related_code=None,
            message="Procedure documentation conflict detected.",
            explanation="Multiple unrelated procedure families were detected without clear documentation that separate procedures were intentionally performed together.",
            recommendation="Clarify performed procedure(s) before billing review.",
            suggested_action="Clarify performed procedure(s) before billing review.",
            documentation_improvement="Review the procedure section, verify findings and operative technique consistency, and confirm the intended billable procedure.",
            why_it_matters="Billing reviewers need clear procedure intent before selecting codes for unrelated surgical services.",
            evidence_used=[],
        )

    @classmethod
    def _detected_candidate_families(cls, candidates: list[CPTCodeCandidate]) -> set[str]:
        families: set[str] = set()
        for candidate in candidates:
            family = cls.DETECTED_PROCEDURE_FAMILIES.get(candidate.procedure_name)
            if family:
                families.add(family)
        return families

    @classmethod
    def _has_explicit_multi_procedure_intent(cls, note_text: str, families: set[str]) -> bool:
        lowered = note_text.lower()
        if any(phrase in lowered for phrase in cls.MULTI_PROCEDURE_PHRASES):
            return True
        family_list = sorted(families)
        for index, left in enumerate(family_list):
            for right in family_list[index + 1 :]:
                if cls._families_linked_by_conjunction(lowered, left, right):
                    return True
        return False

    @classmethod
    def _families_linked_by_conjunction(cls, text: str, left_family: str, right_family: str) -> bool:
        left_terms = cls._terms_for_detected_family(left_family)
        right_terms = cls._terms_for_detected_family(right_family)
        conjunctions = ["and", "then", "also", "followed by"]
        return any(
            cls._terms_linked(text, left_term, right_term, conjunction)
            or cls._terms_linked(text, right_term, left_term, conjunction)
            for left_term in left_terms
            for right_term in right_terms
            for conjunction in conjunctions
        )

    @classmethod
    def _terms_for_detected_family(cls, family: str) -> list[str]:
        if family == "appendix":
            return cls.PROCEDURE_CONCEPT_GROUPS["appendectomy"]
        if family == "gallbladder":
            return cls.PROCEDURE_CONCEPT_GROUPS["cholecystectomy"]
        if family == "hernia":
            return cls.PROCEDURE_CONCEPT_GROUPS["hernia"]
        if family == "bowel":
            return cls.PROCEDURE_CONCEPT_GROUPS["bowel_resection"]
        return [family]

    @staticmethod
    def _terms_linked(text: str, left_term: str, right_term: str, conjunction: str) -> bool:
        left_position = text.find(left_term)
        if left_position == -1:
            return False
        right_position = text.find(right_term, left_position + len(left_term))
        if right_position == -1:
            return False
        between = text[left_position + len(left_term) : right_position]
        return len(between) <= 120 and conjunction in between
