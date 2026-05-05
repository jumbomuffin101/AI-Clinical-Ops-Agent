from app.models.schemas import AuditFinding, CPTCodeCandidate
from app.rag.retriever import KeywordRetriever


class BillingAuditor:
    BUNDLED_CODES = {("47562", "47563")}
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

    def run(self, candidates: list[CPTCodeCandidate]) -> list[AuditFinding]:
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
                        evidence_used=evidence_used,
                    )
                )
            if candidate.code in {"36821", "35371", "35301", "49505", "75710"} and not any(mod in candidate.modifiers for mod in ["LT", "RT"]):
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
                        evidence_used=evidence_used,
                    )
                )

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
                    evidence_used=[],
                )
            )
        return findings
