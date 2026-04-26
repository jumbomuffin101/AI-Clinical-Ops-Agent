from app.models.schemas import AuditFinding, CPTCodeCandidate
from app.rag.retriever import KeywordRetriever


class BillingAuditor:
    BUNDLED_CODES = {("47562", "47563")}

    def __init__(self, retriever: KeywordRetriever):
        self.retriever = retriever

    def run(self, candidates: list[CPTCodeCandidate]) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        codes = {candidate.code for candidate in candidates}

        for candidate in candidates:
            self.retriever.retrieve(f"audit {candidate.code} modifiers bundling")
            if candidate.code == "99999" or not candidate.supported_by_docs:
                findings.append(
                    AuditFinding(
                        severity="high",
                        category="unsupported_code",
                        related_code=candidate.code,
                        message=f"{candidate.code} is not supported by the local reference docs.",
                        recommendation="Route to certified coder review before billing.",
                    )
                )
            if candidate.confidence < 0.75:
                findings.append(
                    AuditFinding(
                        severity="medium",
                        category="low_confidence",
                        related_code=candidate.code,
                        message=f"Coding confidence is {candidate.confidence:.0%}.",
                        recommendation="Validate operative details against payer guidance.",
                    )
                )
            if candidate.code in {"36821", "35371"} and not any(mod in candidate.modifiers for mod in ["LT", "RT"]):
                findings.append(
                    AuditFinding(
                        severity="medium",
                        category="missing_modifier",
                        related_code=candidate.code,
                        message="Laterality-sensitive vascular procedure is missing LT/RT modifier.",
                        recommendation="Confirm side from operative note and append LT or RT when required.",
                    )
                )

        for left, right in self.BUNDLED_CODES:
            if left in codes and right in codes:
                findings.append(
                    AuditFinding(
                        severity="high",
                        category="bundling_conflict",
                        related_code=f"{left},{right}",
                        message="Potential mutually exclusive laparoscopic cholecystectomy code pair detected.",
                        recommendation="Bill only the supported definitive code for the documented service.",
                    )
                )

        if not findings:
            findings.append(
                AuditFinding(
                    severity="info",
                    category="clean_claim",
                    related_code=None,
                    message="No deterministic audit issues were detected.",
                    recommendation="Proceed with human review for final billing validation.",
                )
            )
        return findings
