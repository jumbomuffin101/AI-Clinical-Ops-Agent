from pathlib import Path

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.agents.report_generator import ReportGenerator
from app.providers.mock import MockLLMProvider
from app.rag.retriever import KeywordRetriever
from app.services.revision_service import RevisionHistory, compare_reports


ROOT = Path(__file__).resolve().parents[3]


def _run(note_text: str) -> dict:
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedures = ProcedureExtractor(MockLLMProvider()).run(note_text)
    candidates = CPTCoder(retriever).run(procedures)
    findings = BillingAuditor(retriever).run(candidates)
    estimates = ReimbursementEstimator(ROOT / "data" / "fee_schedule" / "fee_schedule.json").run(candidates)
    _, report = ReportGenerator().run(procedures, candidates, findings, estimates)
    return {
        "extracted_procedures": [procedure.model_dump() for procedure in procedures],
        "cpt_candidates": [candidate.model_dump() for candidate in candidates],
        "audit_findings": [finding.model_dump() for finding in findings],
        "reimbursement_estimates": [estimate.model_dump() for estimate in estimates],
        "report": report,
    }


def test_revision_comparison_detects_resolved_issue_and_score_improvement():
    initial = _run("Open inguinal hernia repair with mesh was performed. Laterality is missing from the note.")
    revised = _run("Left open inguinal hernia repair with mesh was performed. The left side was prepped and repaired.")

    comparison = compare_reports(initial, revised)

    assert "Missing laterality" in comparison["resolved_issues"]
    assert comparison["new_readiness_score"] > comparison["previous_readiness_score"]
    assert comparison["new_claim_status"] == "Ready"


def test_revision_comparison_reports_cpt_changes():
    initial = _run("Ambiguous operative documentation without a supported procedure pattern.")
    revised = _run("Laparoscopic cholecystectomy was completed. No cholangiogram was performed.")

    comparison = compare_reports(initial, revised)

    assert comparison["cpt_changes"] == [{"from": "99999", "to": "47562"}]


def test_revision_history_storage_tracks_notes_and_score_changes():
    initial = _run("Open inguinal hernia repair with mesh was performed. Laterality is missing from the note.")
    revised = _run("Right open inguinal hernia repair with mesh was performed. The right side was repaired.")
    history = RevisionHistory()

    item = history.add("initial note", "revised note", initial, revised)

    assert len(history.items) == 1
    assert item["original_note"] == "initial note"
    assert item["revised_note"] == "revised note"
    assert item["comparison"]["readiness_score_delta"] > 0
