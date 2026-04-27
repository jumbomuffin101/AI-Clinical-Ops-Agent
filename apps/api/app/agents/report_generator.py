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
    ) -> dict[str, str | int]:
        if not candidates:
            return {
                "score": 0,
                "status": "High Risk",
                "status_key": "high_risk",
                "explanation": "No CPT candidates were generated.",
            }

        avg_confidence = sum(candidate.confidence for candidate in candidates) / len(candidates)
        score = int(avg_confidence * 100)
        reasons = [f"Average CPT confidence contributes {score} base points."]

        severity_penalties = {"high": 28, "medium": 12, "low": 6, "info": 0}
        category_penalties = {"bundling_conflict": 8, "unsupported_code": 8}
        for finding in findings:
            penalty = severity_penalties.get(finding.severity, 8) + category_penalties.get(finding.category, 0)
            score -= penalty
            if penalty:
                reasons.append(f"{finding.category.replace('_', ' ')} penalty: -{penalty}.")

        unsupported_count = sum(1 for candidate in candidates if not candidate.supported_by_docs or candidate.code == "99999")
        if unsupported_count:
            score -= unsupported_count * 18
            reasons.append(f"Unsupported CPT candidate penalty: -{unsupported_count * 18}.")

        missing_modifier_count = sum(1 for finding in findings if finding.category == "missing_modifier")
        if missing_modifier_count:
            score -= missing_modifier_count * 10
            reasons.append(f"Missing modifier penalty: -{missing_modifier_count * 10}.")

        zero_reimbursement_count = sum(1 for estimate in estimates if estimate.allowed_amount <= 0)
        if zero_reimbursement_count:
            score -= zero_reimbursement_count * 8
            reasons.append(f"Missing fee schedule penalty: -{zero_reimbursement_count * 8}.")
        else:
            score += 5
            reasons.append("All CPT candidates matched the local fee schedule: +5.")

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

        return {
            "score": score,
            "status": status,
            "status_key": status_key,
            "explanation": " ".join(reasons),
        }
