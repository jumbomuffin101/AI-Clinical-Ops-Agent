from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.agents.report_generator import ReportGenerator
from app.models.schemas import AIStructuredOperativeNote
from app.models.schemas import OperativeNote
from app.parsing.note_parser import OperativeNoteParser
from app.providers.groq import GroqProvider
from app.providers.mock import MockLLMProvider
from app.providers.openrouter import OpenRouterProvider
from app.rag.retriever import KeywordRetriever
from app.services.analysis_service import AnalysisService
from app.db.session import Base


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings
    from app.services.analysis_service import AI_RESPONSE_CACHE

    get_settings.cache_clear()
    AI_RESPONSE_CACHE.clear()
    OpenRouterProvider._cooldown_until_by_model.clear()
    yield
    get_settings.cache_clear()
    AI_RESPONSE_CACHE.clear()
    OpenRouterProvider._cooldown_until_by_model.clear()


class FakeProvider:
    def __init__(self, payload: dict):
        self.payload = payload
        self.called = False
        self.calls = 0

    def complete_json(self, prompt: str) -> dict:
        self.called = True
        self.calls += 1
        return self.payload


class FailingProvider:
    def complete_json(self, prompt: str) -> dict:
        raise RuntimeError("simulated OpenRouter failure")


def _service(monkeypatch, provider_payload: dict | None = None) -> AnalysisService:
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    service = AnalysisService()
    if provider_payload is not None:
        service.llm_provider = FakeProvider(provider_payload)
    return service


def _groq_service(monkeypatch, provider_payload: dict | None = None) -> AnalysisService:
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    get_settings.cache_clear()
    service = AnalysisService()
    if provider_payload is not None:
        service.llm_provider = FakeProvider(provider_payload)
    return service


def _valid_ai_payload() -> dict:
    return {
        "parsed_note_sections": {"Procedure": "Diagnostic colonoscopy.", "Findings": "Scope advanced to the cecum.", "Postoperative diagnosis": "Screening."},
        "detected_procedures": [{"name": "Diagnostic colonoscopy", "evidence": "Procedure section", "confidence": 0.9}],
        "anatomy": "colon",
        "laterality": None,
        "likely_cpt_candidates": [],
        "documentation_gaps": [],
        "audit_concerns": [],
        "confidence_reasoning": ["Clear procedure section."],
        "unsupported_or_unclear_procedure": False,
        "procedure_summary": "Diagnostic colonoscopy documented in free text.",
        "reasoning_summary": "Procedure wording supports endoscopic colon evaluation.",
        "suggested_clarifications": ["Confirm cecal intubation if not documented."],
        "likely_procedure_family": "endoscopy",
        "likely_cpt_category": "diagnostic colonoscopy",
        "probable_operative_intent": "diagnostic evaluation",
    }


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
    assert status == "AI enhancement not configured; rules mode used."


def test_provider_factory_selects_openrouter(monkeypatch):
    from app.config import get_settings
    from app.providers.factory import get_llm_provider

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()

    assert isinstance(get_llm_provider(), OpenRouterProvider)


def test_groq_provider_initialization(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    get_settings.cache_clear()

    provider = GroqProvider()

    assert provider.model == "llama-3.3-70b-versatile"
    assert provider.api_key_configured is True


def test_provider_factory_selects_groq(monkeypatch):
    from app.config import get_settings
    from app.providers.factory import get_llm_provider

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()

    assert isinstance(get_llm_provider(), GroqProvider)


def test_malformed_ai_output_falls_back(monkeypatch):
    service = _service(monkeypatch, {"detected_procedures": [{"name": "Bad", "confidence": 2}]})

    ai_analysis, status = service._run_ai_analysis("Synthetic operative note with no identifiers.")

    assert ai_analysis is None
    assert status == "AI enhancement temporarily unavailable. Core billing review completed successfully."


def test_failing_openrouter_keeps_rules_mode(monkeypatch):
    service = _service(monkeypatch)
    service.llm_provider = FailingProvider()

    ai_analysis, status = service._run_ai_analysis("Synthetic operative note with no identifiers.")

    assert ai_analysis is None
    assert status == "AI enhancement temporarily unavailable. Core billing review completed successfully."


def test_successful_groq_analysis(monkeypatch):
    service = _groq_service(monkeypatch, _valid_ai_payload())

    ai_analysis, status = service._run_ai_analysis("Procedure: Diagnostic colonoscopy. Findings: Scope advanced to the cecum.")

    assert ai_analysis is not None
    assert status == "Groq enhancement validated."


def test_malformed_groq_output_falls_back(monkeypatch):
    service = _groq_service(monkeypatch, {"detected_procedures": [{"name": "Bad", "confidence": 2}]})

    ai_analysis, status = service._run_ai_analysis("Synthetic operative note with no identifiers.")

    assert ai_analysis is None
    assert status == "AI enhancement temporarily unavailable. Core billing review completed successfully."


def test_groq_string_detected_procedures_get_normalized(monkeypatch):
    payload = _valid_ai_payload()
    payload["detected_procedures"] = ["diagnostic colonoscopy"]
    service = _groq_service(monkeypatch, payload)

    ai_analysis, status = service._run_ai_analysis("Custom vague colon procedure note.")

    assert ai_analysis is not None
    assert status == "Groq enhancement validated."
    assert ai_analysis.detected_procedures[0].name == "diagnostic colonoscopy"
    assert ai_analysis.detected_procedures[0].procedure_family == "unknown"
    assert ai_analysis.detected_procedures[0].confidence == 0.65


def test_groq_string_audit_concerns_get_normalized(monkeypatch):
    payload = _valid_ai_payload()
    payload["audit_concerns"] = ["Missing procedure detail"]
    service = _groq_service(monkeypatch, payload)

    ai_analysis, _ = service._run_ai_analysis("Custom vague colon procedure note.")

    assert ai_analysis is not None
    assert ai_analysis.audit_concerns[0].title == "Documentation concern"
    assert ai_analysis.audit_concerns[0].explanation == "Missing procedure detail"
    assert ai_analysis.audit_concerns[0].severity == "medium"


def test_groq_confidence_reasoning_string_gets_wrapped(monkeypatch):
    payload = _valid_ai_payload()
    payload["confidence_reasoning"] = "Procedure is partially supported."
    service = _groq_service(monkeypatch, payload)

    ai_analysis, _ = service._run_ai_analysis("Custom vague colon procedure note.")

    assert ai_analysis is not None
    assert ai_analysis.confidence_reasoning == ["Procedure is partially supported."]


def test_groq_string_cpt_candidates_get_normalized(monkeypatch):
    payload = _valid_ai_payload()
    payload["cpt_candidates"] = ["45378"]
    payload["likely_cpt_candidates"] = []
    service = _groq_service(monkeypatch, payload)

    ai_analysis, _ = service._run_ai_analysis("Custom vague colon procedure note.")

    assert ai_analysis is not None
    assert ai_analysis.cpt_candidates[0].code == "45378"
    assert ai_analysis.cpt_candidates[0].confidence == 0.35
    assert ai_analysis.cpt_candidates[0].needs_human_review is True


def test_non_json_like_groq_output_falls_back(monkeypatch):
    service = _groq_service(monkeypatch)
    service.llm_provider = FakeProvider("not a dict")

    ai_analysis, status = service._run_ai_analysis("Custom vague colon procedure note.")

    assert ai_analysis is None
    assert status == "AI enhancement temporarily unavailable. Core billing review completed successfully."


def test_exact_groq_loose_shape_normalizes_and_validates(monkeypatch):
    payload = {
        "detected_procedures": [
            "Exploratory laparotomy",
            "Small bowel resection",
            "Stapled primary anastomosis",
        ],
        "likely_cpt_candidates": None,
        "audit_concerns": [
            "Potential for incomplete coding due to lack of specific details",
        ],
        "confidence_reasoning": "The note provides a clear description of the procedure and findings, but lacks specific details on the extent of resection and laterality",
    }
    service = _groq_service(monkeypatch, payload)

    ai_analysis, status = service._run_ai_analysis("Custom synthetic exploratory laparotomy note with small bowel resection.")

    assert ai_analysis is not None
    assert status == "Groq enhancement validated."
    assert [procedure.name for procedure in ai_analysis.detected_procedures] == [
        "Exploratory laparotomy",
        "Small bowel resection",
        "Stapled primary anastomosis",
    ]
    assert ai_analysis.likely_cpt_candidates == []
    assert ai_analysis.audit_concerns[0].title == "Documentation concern"
    assert ai_analysis.audit_concerns[0].suggested_action == "Review the operative note for missing coding-support details."
    assert ai_analysis.confidence_reasoning == [
        "The note provides a clear description of the procedure and findings, but lacks specific details on the extent of resection and laterality"
    ]
    assert ai_analysis.procedure_summary == "AI identified: Exploratory laparotomy, Small bowel resection, Stapled primary anastomosis"


def test_exact_groq_loose_shape_produces_hybrid_mode_and_summary(monkeypatch, tmp_path):
    payload = {
        "detected_procedures": [
            "Exploratory laparotomy",
            "Small bowel resection",
            "Stapled primary anastomosis",
        ],
        "likely_cpt_candidates": None,
        "audit_concerns": [
            "Potential for incomplete coding due to lack of specific details",
        ],
        "confidence_reasoning": "The note provides a clear description of the procedure and findings, but lacks specific details on the extent of resection and laterality",
    }
    service = _groq_service(monkeypatch, payload)
    engine = create_engine(f"sqlite:///{tmp_path / 'loose_groq.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        report = service.create_analysis(
            db,
            OperativeNote(
                title="Exploratory laparotomy",
                note_text="Custom synthetic note: exploratory laparotomy with small bowel resection and stapled primary anastomosis was performed.",
            ),
        )

    engine.dispose()
    assert report.analysis_mode == "Hybrid AI mode"
    assert report.report["analysis_mode"] == "Hybrid AI mode"
    assert report.report["ai_procedure_summary"] == "AI identified: Exploratory laparotomy, Small bowel resection, Stapled primary anastomosis"


def test_groq_unavailable_falls_back(monkeypatch):
    service = _groq_service(monkeypatch)
    service.llm_provider = FailingProvider()

    ai_analysis, status = service._run_ai_analysis("Synthetic operative note with no identifiers.")

    assert ai_analysis is None
    assert status == "AI enhancement temporarily unavailable. Core billing review completed successfully."


def test_create_analysis_returns_hybrid_mode_when_openrouter_validates(monkeypatch, tmp_path):
    service = _groq_service(monkeypatch, _valid_ai_payload())
    engine = create_engine(f"sqlite:///{tmp_path / 'hybrid.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        report = service.create_analysis(
            db,
            OperativeNote(
                title="Hybrid mode test",
                note_text="Custom synthetic note: endoscopic colon evaluation was performed, but the note is vague and does not document cecal intubation.",
            ),
        )

    engine.dispose()
    assert report.analysis_mode == "Hybrid AI mode"
    assert report.report["analysis_mode"] == "Hybrid AI mode"
    assert report.report["ai_provider"] == "groq"
    assert report.report["ai_model"] == "llama-3.3-70b-versatile"


def test_known_example_skips_openrouter(monkeypatch, tmp_path):
    service = _groq_service(monkeypatch, _valid_ai_payload())
    fake_provider = service.llm_provider
    note_text = (ROOT / "data" / "synthetic_notes" / "diagnostic_colonoscopy.txt").read_text(encoding="utf-8")
    engine = create_engine(f"sqlite:///{tmp_path / 'known.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        report = service.create_analysis(db, OperativeNote(title="Known note", note_text=note_text))

    engine.dispose()
    assert fake_provider.calls == 0
    assert report.analysis_mode == "Rules mode"


def test_low_confidence_custom_note_triggers_openrouter(monkeypatch, tmp_path):
    service = _groq_service(monkeypatch, _valid_ai_payload())
    fake_provider = service.llm_provider
    note_text = "Custom synthetic note: colonoscopy was started, but endpoint documentation is absent and details are incomplete."
    engine = create_engine(f"sqlite:///{tmp_path / 'custom.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        service.create_analysis(db, OperativeNote(title="Custom note", note_text=note_text))

    engine.dispose()
    assert fake_provider.calls == 1


def test_unsupported_procedure_invokes_groq(monkeypatch, tmp_path):
    service = _groq_service(monkeypatch, _valid_ai_payload())
    fake_provider = service.llm_provider
    note_text = "Custom synthetic operative note: a rare unsupported procedure was performed with unclear anatomy and intent."
    engine = create_engine(f"sqlite:///{tmp_path / 'unsupported.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        service.create_analysis(db, OperativeNote(title="Unsupported note", note_text=note_text))

    engine.dispose()
    assert fake_provider.calls == 1


def test_cached_note_does_not_call_openrouter_twice(monkeypatch):
    from app.services.analysis_service import AI_RESPONSE_CACHE

    AI_RESPONSE_CACHE.clear()
    service = _groq_service(monkeypatch, _valid_ai_payload())
    fake_provider = service.llm_provider
    note = "Custom synthetic unclear operative note with unsupported details."

    first, _ = service._run_ai_analysis(note)
    second, _ = service._run_ai_analysis(note)

    assert first is not None
    assert second is not None
    assert fake_provider.calls == 1


def test_429_cooldown_prevents_immediate_repeat(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "rate-limited-model")
    get_settings.cache_clear()
    OpenRouterProvider._cooldown_until_by_model.clear()
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        request = httpx.Request("POST", OpenRouterProvider.endpoint)
        return httpx.Response(429, headers={"Retry-After": "120"}, request=request, text="rate limited")

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenRouterProvider()

    with pytest.raises(httpx.HTTPStatusError):
        provider.complete_json("Return JSON.")
    with pytest.raises(RuntimeError):
        provider.complete_json("Return JSON.")

    assert calls["count"] == 1
    OpenRouterProvider._cooldown_until_by_model.clear()


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
