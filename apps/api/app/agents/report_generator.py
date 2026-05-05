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
        readiness = self._claim_readiness(candidates, findings, estimates)
        summary = (
            f"Identified {len(procedures)} procedure(s), generated {len(candidates)} CPT candidate(s), "
            f"estimated ${total:,.2f}, and assigned a {readiness['score']}/100 claim readiness score."
        )
        return summary, {
            "claim_readiness": readiness["status_key"],
            "claim_readiness_score": readiness["score"],
            "claim_readiness_status": readiness["status"],
            "claim_readiness_explanation": readiness["explanation"],
            "claim_readiness_reasons": readiness["reasons"],
            "recommended_action": readiness["recommended_action"],
            "main_issue": readiness["main_issue"],
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

    @staticmethod
    def _claim_readiness(
        candidates: list[CPTCodeCandidate],
        findings: list[AuditFinding],
        estimates: list[ReimbursementEstimate],
    ) -> dict:
        if not candidates:
            return {
                "score": 0,
                "status": "High Risk",
                "status_key": "high_risk",
                "explanation": "Confidence is based on procedure match strength, documentation completeness, guideline support, and audit risk.",
                "reasons": ["No CPT candidates were generated.", "A coder should review the note manually."],
                "recommended_action": "Do not submit until billing conflicts or documentation gaps are resolved.",
                "main_issue": "Unsupported procedure",
            }

        avg_confidence = sum(candidate.confidence for candidate in candidates) / len(candidates)
        score = int(avg_confidence * 100)
        reasons: list[str] = []

        severity_penalties = {"high": 28, "medium": 12, "low": 6, "info": 0}
        category_penalties = {"bundling_conflict": 8, "unsupported_code": 8, "missing_laterality": 10}
        for finding in findings:
            penalty = severity_penalties.get(finding.severity, 8) + category_penalties.get(finding.category, 0)
            score -= penalty

        unsupported_count = sum(1 for candidate in candidates if not candidate.supported_by_docs or candidate.code == "99999")
        if unsupported_count:
            score -= unsupported_count * 18

        missing_laterality_count = sum(1 for finding in findings if finding.category == "missing_laterality")
        if missing_laterality_count:
            score -= missing_laterality_count * 10

        zero_reimbursement_count = sum(1 for estimate in estimates if estimate.allowed_amount <= 0)
        if zero_reimbursement_count:
            score -= zero_reimbursement_count * 8
        else:
            score += 5

        score = max(0, min(100, score))
        if score >= 85:
            status = "Ready"
            status_key = "ready"
        elif score >= 60:
            status = "Needs Review"
            status_key = "needs_review"
        else:
            status = "High Risk"
            status_key = "high_risk"

        categories = {finding.category for finding in findings if finding.severity != "info"}
        if "bundling_conflict" in categories:
            main_issue = "Bundling conflict"
        elif "missing_laterality" in categories:
            main_issue = "Missing laterality"
        elif "low_confidence" in categories:
            main_issue = "Ambiguous documentation"
        elif "unsupported_code" in categories:
            main_issue = "Unsupported procedure"
        else:
            main_issue = "No major issues"

        if status == "Ready":
            recommended_action = "Proceed with standard billing review."
        elif status == "Needs Review":
            recommended_action = "Clarify documentation before submission."
        else:
            recommended_action = "Do not submit until billing conflicts or documentation gaps are resolved."

        if avg_confidence >= 0.85:
            reasons.append("Strong procedure match.")
        else:
            reasons.append("Procedure match needs review.")
        if all(candidate.supported_by_docs for candidate in candidates):
            reasons.append("Supporting guideline found.")
        else:
            reasons.append("Missing supporting guideline for at least one CPT candidate.")
        if missing_laterality_count:
            reasons.append("Documentation missing laterality.")
        elif any(finding.category == "low_confidence" for finding in findings):
            reasons.append("Documentation is ambiguous.")
        else:
            reasons.append("Documentation appears complete for the demo checks.")
        if any(finding.severity == "high" for finding in findings):
            reasons.append("Audit risk high.")
        elif any(finding.severity == "medium" for finding in findings):
            reasons.append("Audit risk medium.")
        else:
            reasons.append("Audit risk low.")

        return {
            "score": score,
            "status": status,
            "status_key": status_key,
            "explanation": "Confidence is based on procedure match strength, documentation completeness, guideline support, and audit risk.",
            "reasons": reasons,
            "recommended_action": recommended_action,
            "main_issue": main_issue,
        }
