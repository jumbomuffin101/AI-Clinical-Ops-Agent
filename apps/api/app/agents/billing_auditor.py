from app.models.schemas import AuditFinding, CPTCodeCandidate, StructuredOperativeNote
from app.rag.retriever import KeywordRetriever


class BillingAuditor:
    BUNDLED_CODES = {("47562", "47563")}
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

    @staticmethod
    def _conflicting_documentation_finding(structured_note: StructuredOperativeNote) -> AuditFinding | None:
        sections = {name: text.lower() for name, text in structured_note.parsed_sections.items()}
        if not sections:
            return None

        procedure_family = BillingAuditor._section_family(sections.get("Procedure", ""))
        technique_family = BillingAuditor._section_family(sections.get("Technique", ""))
        findings_family = BillingAuditor._section_family(sections.get("Findings", ""))
        diagnosis_family = BillingAuditor._section_family(sections.get("Postoperative diagnosis", ""))
        narrative_family = technique_family or findings_family

        if procedure_family and narrative_family and procedure_family != narrative_family:
            return BillingAuditor._conflict_finding()
        if diagnosis_family and narrative_family and diagnosis_family != narrative_family:
            return BillingAuditor._conflict_finding()
        return None

    @staticmethod
    def _section_family(text: str) -> str | None:
        if any(term in text for term in ["appendectomy", "appendix", "appendicitis"]):
            return "appendectomy"
        if any(term in text for term in ["cholecystectomy", "gallbladder", "gallstones", "cystic duct", "liver bed"]):
            return "cholecystectomy"
        if any(term in text for term in ["bowel", "ileum", "colectomy", "anastomosis", "laparotomy"]):
            return "gi_surgery"
        return None

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
