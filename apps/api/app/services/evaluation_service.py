import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.agents.report_generator import ReportGenerator
from app.config import get_settings
from app.providers.mock import MockLLMProvider
from app.rag.retriever import KeywordRetriever


def load_gold_standard(path: Path | None = None) -> list[dict]:
    settings = get_settings()
    gold_path = path or settings.project_root / "data" / "evaluation" / "gold_standard.json"
    return json.loads(gold_path.read_text(encoding="utf-8"))


class EvaluationService:
    def __init__(self) -> None:
        settings = get_settings()
        retriever = KeywordRetriever(settings.reference_docs_path)
        self.notes_path = settings.project_root / "data" / "synthetic_notes"
        self.extractor = ProcedureExtractor(MockLLMProvider())
        self.coder = CPTCoder(retriever)
        self.auditor = BillingAuditor(retriever)
        self.estimator = ReimbursementEstimator(settings.fee_schedule_path)
        self.report_generator = ReportGenerator()

    def run(self) -> dict:
        gold_cases = load_gold_standard()
        per_case_results = [self._evaluate_case(case) for case in gold_cases]
        total_cases = len(per_case_results)

        return {
            "total_cases": total_cases,
            "cpt_accuracy": self._accuracy(per_case_results, "cpt_match"),
            "readiness_accuracy": self._accuracy(per_case_results, "readiness_match"),
            "audit_accuracy": self._accuracy(per_case_results, "audit_match"),
            "average_confidence": round(mean([case["actual_confidence"] for case in per_case_results]) if per_case_results else 0, 3),
            "last_evaluated_at": datetime.now(UTC).isoformat(),
            "per_case_results": per_case_results,
        }

    def _evaluate_case(self, gold_case: dict) -> dict:
        note_text = (self.notes_path / gold_case["note_filename"]).read_text(encoding="utf-8")
        procedures = self.extractor.run(note_text)
        candidates = self.coder.run(procedures)
        findings = self.auditor.run(candidates)
        estimates = self.estimator.run(candidates)
        _, report = self.report_generator.run(procedures, candidates, findings, estimates)

        primary_candidate = candidates[0] if candidates else None
        actual_audit_findings = sorted({finding.category for finding in findings})
        expected_audit_findings = sorted(gold_case["expected_audit_findings"])

        cpt_match = (primary_candidate.code if primary_candidate else None) == gold_case["expected_primary_cpt"]
        readiness_match = report["claim_readiness_status"] == gold_case["expected_claim_status"]
        audit_match = expected_audit_findings == actual_audit_findings
        main_issue_match = report["main_issue"] == gold_case["expected_main_issue"]

        return {
            "note_filename": gold_case["note_filename"],
            "expected_primary_cpt": gold_case["expected_primary_cpt"],
            "actual_primary_cpt": primary_candidate.code if primary_candidate else None,
            "expected_claim_status": gold_case["expected_claim_status"],
            "actual_claim_status": report["claim_readiness_status"],
            "expected_main_issue": gold_case["expected_main_issue"],
            "actual_main_issue": report["main_issue"],
            "expected_audit_findings": expected_audit_findings,
            "actual_audit_findings": actual_audit_findings,
            "actual_confidence": round(primary_candidate.confidence if primary_candidate else 0, 3),
            "claim_readiness_score": report["claim_readiness_score"],
            "cpt_match": cpt_match,
            "readiness_match": readiness_match,
            "audit_match": audit_match,
            "main_issue_match": main_issue_match,
            "passed": cpt_match and readiness_match and audit_match and main_issue_match,
        }

    @staticmethod
    def _accuracy(results: list[dict], key: str) -> float:
        if not results:
            return 0
        return round(sum(1 for result in results if result[key]) / len(results), 3)
