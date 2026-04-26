from app.models.schemas import AuditFinding, CPTCodeCandidate, ExtractedProcedure, ReimbursementEstimate


class ReportGenerator:
    def run(
        self,
        procedures: list[ExtractedProcedure],
        candidates: list[CPTCodeCandidate],
        findings: list[AuditFinding],
        estimates: list[ReimbursementEstimate],
    ) -> tuple[str, dict]:
        total = sum(estimate.allowed_amount for estimate in estimates)
        blocking = [finding for finding in findings if finding.severity in {"high", "medium"}]
        summary = (
            f"Identified {len(procedures)} procedure(s), generated {len(candidates)} CPT candidate(s), "
            f"and estimated ${total:,.2f} in allowed reimbursement."
        )
        return summary, {
            "claim_readiness": "needs_review" if blocking else "ready_for_review",
            "total_estimated_reimbursement": total,
            "procedure_count": len(procedures),
            "audit_issue_count": len(blocking),
            "coding_summary": [
                {
                    "procedure": candidate.procedure_name,
                    "code": candidate.code,
                    "modifiers": candidate.modifiers,
                    "confidence": candidate.confidence,
                }
                for candidate in candidates
            ],
        }
