from pathlib import Path

import pytest

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.agents.report_generator import ReportGenerator
from app.models.schemas import AIStructuredOperativeNote
from app.parsing.note_parser import OperativeNoteParser
from app.providers.mock import MockLLMProvider
from app.rag.retriever import KeywordRetriever
from app.services.analysis_service import AnalysisService


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeProvider:
    def __init__(self, payload: dict):
        self.payload = payload
        self.called = False

    def complete_json(self, prompt: str) -> dict:
        self.called = True
        return self.payload


def _service(monkeypatch, provider_payload: dict | None = None) -> AnalysisService:
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    service = AnalysisService()
    if provider_payload is not None:
        service.llm_provider = FakeProvider(provider_payload)
    return service


def test_mock_mode_works_without_openrouter_key(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    service = AnalysisService()

    ai_analysis, status = service._run_ai_analysis("Synthetic note text without identifiers.")

    assert ai_analysis is None
    assert status == "Rules mode enabled."


def test_openrouter_without_key_falls_back(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    service = AnalysisService()

    ai_analysis, status = service._run_ai_analysis("Synthetic note text without identifiers.")

    assert ai_analysis is None
    assert "fallback" in status.lower()


def test_malformed_ai_output_falls_back(monkeypatch):
    service = _service(monkeypatch, {"detected_procedures": [{"name": "Bad", "confidence": 2}]})

    ai_analysis, status = service._run_ai_analysis("Synthetic operative note with no identifiers.")

    assert ai_analysis is None
    assert "invalid" in status.lower() or "fallback" in status.lower()


def test_phi_like_input_blocks_llm_call(monkeypatch):
    provider = FakeProvider({"parsed_note_sections": {}})
    service = _service(monkeypatch)
    service.llm_provider = provider

    ai_analysis, status = service._run_ai_analysis("Synthetic note. MRN: 123456. Procedure: Colonoscopy.")

    assert ai_analysis is None
    assert provider.called is False
    assert "identifier" in status.lower()


def test_deterministic_rules_override_ai_ready_status(monkeypatch):
    service = _service(
        monkeypatch,
        {
            "parsed_note_sections": {"Procedure": "Open inguinal hernia repair with mesh."},
            "detected_procedures": [{"name": "Open inguinal hernia repair", "evidence": "Procedure line", "confidence": 0.95}],
            "anatomy": "inguinal region",
            "laterality": "left",
            "likely_cpt_candidates": [],
            "documentation_gaps": [],
            "audit_concerns": [],
            "confidence_reasoning": ["AI draft says ready."],
            "unsupported_or_unclear_procedure": False,
        },
    )
    structured = service.parser.parse("Procedure: Open inguinal hernia repair with mesh. Findings: Hernia repaired.")
    ai_analysis = AIStructuredOperativeNote.model_validate(service.llm_provider.complete_json(""))
    merged = service._merge_structured_note(structured, ai_analysis)
    procedures = service.extractor.run("Procedure: Open inguinal hernia repair with mesh. Findings: Hernia repaired.", merged)
    candidates = service.coder.run(procedures)
    findings = service.auditor.run(candidates, merged)

    assert any(finding.category == "missing_laterality" for finding in findings)


def test_arbitrary_vague_note_returns_needs_review_or_high_risk():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    note = "Synthetic note says an unclear operation happened. Details, anatomy, and intent are vague."
    structured = OperativeNoteParser().parse(note)
    procedures = ProcedureExtractor(MockLLMProvider()).run(note, structured)
    candidates = CPTCoder(retriever).run(procedures)
    findings = BillingAuditor(retriever).run(candidates, structured)
    estimates = ReimbursementEstimator(ROOT / "data" / "fee_schedule" / "fee_schedule.json").run(candidates)
    _, report = ReportGenerator().run(procedures, candidates, findings, estimates)

    assert report["claim_readiness_status"] in {"Needs Review", "High Risk"}
