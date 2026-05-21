import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["ENVIRONMENT"] = "test"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///./test_clinical_ops.db"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import Base, get_db
from app.main import app
from app.services.analysis_service import AnalysisService


SAMPLE_NOTE = (
    "Title: Left AV fistula creation. Procedure: Left upper extremity arteriovenous fistula creation. "
    "Operative note: The cephalic vein and radial artery were dissected and an end-to-side anastomosis "
    "was created for durable dialysis access."
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    test_db_dir = Path(__file__).resolve().parents[1] / ".test_dbs"
    test_db_dir.mkdir(exist_ok=True)
    test_db_path = test_db_dir / f"{uuid.uuid4()}.db"
    engine = create_engine(f"sqlite:///{test_db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    test_db_path.unlink(missing_ok=True)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "timestamp" in response.json()


def test_database_health(client):
    response = client.get("/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_llm_debug_endpoint(client):
    response = client.get("/debug/llm")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["api_key_loaded"] is False
    assert body["provider_configured"] is False
    assert body["provider_available"] is None
    assert "api_key" not in body
    assert "primary_model" in body
    assert "fallback_models" in body
    assert "app_name" in body


def test_debug_llm_does_not_smoke_without_query(client, monkeypatch):
    from app.config import get_settings
    from app.providers.openrouter import OpenRouterProvider

    called = {"value": False}

    def fake_smoke(self):
        called["value"] = True
        return True

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(OpenRouterProvider, "smoke_test", fake_smoke)

    response = client.get("/debug/llm")

    assert response.status_code == 200
    assert called["value"] is False
    assert response.json()["provider_configured"] is True
    assert response.json()["provider_available"] is None


def test_debug_llm_smoke_query_calls_provider(client, monkeypatch):
    from app.config import get_settings
    from app.providers.openrouter import OpenRouterProvider

    called = {"value": False}

    def fake_smoke(self):
        called["value"] = True
        return True

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(OpenRouterProvider, "smoke_test", fake_smoke)

    response = client.get("/debug/llm?smoke=true")

    assert response.status_code == 200
    assert called["value"] is True
    assert response.json()["provider_available"] is True


def test_debug_llm_reports_groq_config(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    get_settings.cache_clear()

    response = client.get("/debug/llm")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "groq"
    assert body["provider_configured"] is True
    assert body["provider_available"] is None
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["ai_enabled"] is True


def test_evaluation_summary_endpoint(client):
    response = client.get("/api/evaluation/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_cases"] >= 5
    assert "cpt_accuracy" in body
    assert "readiness_accuracy" in body
    assert "audit_accuracy" in body
    assert "average_confidence" in body
    assert body["per_case_results"]


def test_submit_note_and_get_analysis(client):
    create_response = client.post("/api/notes", json={"title": "Integration note", "note_text": SAMPLE_NOTE})
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["cpt_candidates"][0]["code"] == "36821"
    assert created["total_estimated_reimbursement"] > 0
    assert created["report"]["analysis_mode"] == "Rules mode"
    assert created["analysis_mode"] == "Rules mode"

    get_response = client.get(f"/api/analyses/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]

    list_response = client.get("/api/analyses")
    assert list_response.status_code == 200
    assert list_response.json()[0]["top_cpt_code"] == "36821"

    export_response = client.get(f"/api/analyses/{created['id']}/export")
    assert export_response.status_code == 200
    assert export_response.json()["claim_readiness"]["score"] is not None
    assert created["report"]["recommended_action"]


def test_missing_laterality_is_not_ready(client):
    note = (
        "Title: Open inguinal hernia repair with missing laterality. Procedure: Open inguinal hernia repair with mesh. "
        "Operative note: The hernia sac was reduced and mesh repair was completed. The note does not clearly document "
        "left or right laterality."
    )
    response = client.post("/api/notes", json={"title": "Missing laterality", "note_text": note})
    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] != "Ready"
    assert body["report"]["main_issue"] == "Missing laterality"
    assert body["report"]["recommended_action"] == "Clarify left or right side before review."
    assert body["cpt_candidates"][0]["modifiers"] == []
    missing_laterality = next(finding for finding in body["audit_findings"] if finding["category"] == "missing_laterality")
    assert missing_laterality["documentation_improvement"] == "Document whether the procedure was performed on the left or right side."
    assert "modifier" in missing_laterality["why_it_matters"]


def test_missing_laterality_is_needs_review_not_high_risk(client):
    note = (
        "Title: Open inguinal hernia repair. Procedure: Open inguinal hernia repair with mesh. "
        "Operative note: The hernia sac was reduced and mesh repair was completed. The note does not document the side."
    )
    response = client.post("/api/notes", json={"title": "Missing hernia side", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "Needs Review"
    assert body["report"]["main_issue"] == "Missing laterality"
    assert body["report"]["recommended_action"] == "Clarify left or right side before review."


def test_sectioned_hernia_missing_laterality_is_needs_review(client):
    note = """Procedure: Open inguinal hernia repair with mesh.

Indication: Synthetic patient with symptomatic inguinal hernia.

Findings: Indirect inguinal hernia.

Technique: Groin incision was made. Hernia sac was reduced and mesh was secured to the inguinal ligament and conjoint tendon.

Complications: None."""
    response = client.post("/api/notes", json={"title": "Sectioned missing hernia side", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "Needs Review"
    assert body["report"]["main_issue"] == "Missing laterality"
    assert body["report"]["recommended_action"] == "Clarify left or right side before review."
    assert body["cpt_candidates"][0]["code"] == "49505"
    assert any(finding["category"] == "missing_laterality" for finding in body["audit_findings"])


def test_appendectomy_ready_without_laterality_finding(client):
    note = (
        "Title: Laparoscopic appendectomy. Procedure: Laparoscopic appendectomy. "
        "Findings: Inflamed appendix without perforation. "
        "Technique: The appendix was divided with a stapler and removed laparoscopically. "
        "Postoperative diagnosis: Acute appendicitis."
    )
    response = client.post("/api/notes", json={"title": "Appendectomy", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "Ready"
    assert body["cpt_candidates"][0]["code"] == "44970"
    assert body["report"]["main_issue"] == "No major issues"
    assert not any(finding["category"] == "missing_laterality" for finding in body["audit_findings"])


def test_sectioned_normal_appendectomy_is_ready(client):
    note = """Procedure: Laparoscopic appendectomy.
Indication: Synthetic patient with acute appendicitis.
Findings: Inflamed appendix without perforation.
Technique: Three ports were placed. The appendix was identified, mesoappendix divided, appendix stapled at the base, removed in a retrieval bag, and port sites were closed.
Complications: None.
Postoperative diagnosis: Acute appendicitis."""
    response = client.post("/api/notes", json={"title": "Sectioned appendectomy", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "Ready"
    assert body["report"]["main_issue"] == "No major issues"
    assert body["cpt_candidates"][0]["code"] == "44970"
    assert not any(finding["category"] == "procedure_documentation_conflict" for finding in body["audit_findings"])


def test_conflicting_appendectomy_cholecystectomy_documentation_is_high_risk(client):
    note = """Procedure: Laparoscopic appendectomy.
Findings: Gallstones with inflamed gallbladder.
Technique: Gallbladder was dissected from the liver bed and removed.
Postoperative diagnosis: Acute appendicitis."""
    response = client.post("/api/notes", json={"title": "Conflicting documentation", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Procedure documentation conflict"
    assert body["report"]["detected_procedure"] == "Conflicting procedure documentation"
    assert body["report"]["coding_recommendation"] == "Coder review needed"
    assert body["report"]["suggested_code"] is None
    assert body["report"]["recommended_action"] == "Confirm final operative procedure before coding."
    conflict = next(finding for finding in body["audit_findings"] if finding["category"] == "procedure_documentation_conflict")
    assert conflict["documentation_improvement"] == "Clarify whether the documented procedure, findings, and postoperative diagnosis refer to the same service."


def test_headerAppendix_techniqueGallbladder_shouldConflict(client):
    note = """Procedure: Laparoscopic appendectomy.
Findings: Gallstones with inflamed gallbladder.
Technique: Gallbladder was dissected from the liver bed and removed.
Postoperative diagnosis: Acute appendicitis."""
    response = client.post("/api/notes", json={"title": "Exact appendectomy contradiction", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Procedure documentation conflict"
    assert body["report"]["detected_procedure"] == "Conflicting procedure documentation"
    assert body["report"]["coding_recommendation"] == "Coder review needed"
    assert body["report"]["suggested_code"] is None


def test_appendectomy_procedure_with_gallbladder_technique_is_high_risk(client):
    note = """Procedure: Laparoscopic appendectomy.
Technique: Gallbladder was dissected from the liver bed and removed.
Postoperative diagnosis: Acute appendicitis."""
    response = client.post("/api/notes", json={"title": "Appendectomy gallbladder conflict", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Procedure documentation conflict"
    assert body["report"]["recommended_action"] == "Confirm final operative procedure before coding."


def test_singleProcedureHeaderDifferentTechnique_shouldConflict(client):
    note = """Procedure: Laparoscopic cholecystectomy.
Technique: The appendix was divided at the base with a stapler and removed in a retrieval bag.
Postoperative diagnosis: Cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Single header conflicting technique", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Procedure documentation conflict"
    assert body["report"]["detected_procedure"] == "Conflicting procedure documentation"


def test_singleProcedureHeaderDifferentTechnique_shouldNotBecomeCombined(client):
    note = """Procedure: Laparoscopic cholecystectomy.
Technique: The appendix was divided at the base with a stapler and removed in a retrieval bag.
Postoperative diagnosis: Cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Single header not combined", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["detected_procedure"] == "Conflicting procedure documentation"
    assert body["report"]["coding_recommendation"] == "Coder review needed"
    assert body["report"]["suggested_code"] is None
    assert body["extracted_procedures"] == []
    assert body["cpt_candidates"] == []


def test_final_guardrails_override_ready_appendectomy_gallbladder_report():
    report = {
        "claim_readiness_status": "Ready",
        "review_status": "Ready",
        "main_issue": "No major issues",
        "detected_procedure": "Laparoscopic appendectomy, possible cholecystectomy",
        "coding_recommendation": "Suggested code 44970",
        "suggested_code": "44970",
    }
    findings = []
    note = """Procedure: Laparoscopic appendectomy.
Technique: Gallbladder was dissected from the liver bed and removed.
Postoperative diagnosis: Acute appendicitis."""

    applied = AnalysisService.apply_final_guardrails(note, report, findings)

    assert applied is True
    assert report["claim_readiness_status"] == "High Risk"
    assert report["main_issue"] == "Procedure documentation conflict"
    assert report["detected_procedure"] == "Conflicting procedure documentation"
    assert report["recommended_next_step"] == "Confirm final operative procedure before coding."
    assert report["coding_recommendation"] == "Coder review needed"
    assert report["suggested_code"] is None
    assert report["plain_english_review"] == (
        "The procedure label and operative details describe different services. "
        "Coding should not proceed until the documentation is reconciled."
    )
    assert any(finding.category == "procedure_documentation_conflict" for finding in findings)


def test_final_guardrails_override_ready_cholecystectomy_appendix_report():
    report = {
        "claim_readiness_status": "Ready",
        "review_status": "Ready",
        "main_issue": "No major issues",
        "detected_procedure": "Laparoscopic cholecystectomy, laparoscopic appendectomy",
        "coding_recommendation": "Suggested code 47562",
        "suggested_code": "47562",
    }
    note = """Procedure: Laparoscopic cholecystectomy.
Technique: The appendix was divided at the base with a stapler and removed in a retrieval bag.
Postoperative diagnosis: Cholelithiasis."""

    applied = AnalysisService.apply_final_guardrails(note, report, [])

    assert applied is True
    assert report["claim_readiness_status"] == "High Risk"
    assert report["main_issue"] == "Procedure documentation conflict"
    assert report["detected_procedure"] == "Conflicting procedure documentation"


def test_final_guardrails_allow_explicit_combined_procedure():
    report = {
        "claim_readiness_status": "Ready",
        "review_status": "Ready",
        "main_issue": "No major issues",
        "detected_procedure": "Laparoscopic appendectomy and laparoscopic cholecystectomy",
        "coding_recommendation": "Coder review completed",
        "suggested_code": "44970",
    }
    note = """Procedure: Laparoscopic appendectomy and laparoscopic cholecystectomy.
Technique: The appendix was divided at the base with a stapler and removed. The cystic duct and cystic artery were clipped and divided, and the gallbladder was removed.
Postoperative diagnosis: Acute appendicitis and cholelithiasis."""

    applied = AnalysisService.apply_final_guardrails(note, report, [])

    assert applied is False
    assert report["claim_readiness_status"] == "Ready"
    assert report["main_issue"] == "No major issues"


def test_unrelated_procedure_families_without_section_conflict_is_not_auto_high_risk(client):
    note = (
        "Laparoscopic cholecystectomy was documented in the note. "
        "Laparoscopic appendectomy was listed elsewhere without explanation."
    )
    response = client.post("/api/notes", json={"title": "Unrelated procedures without intent", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert not any(finding["category"] == "procedure_documentation_conflict" for finding in body["audit_findings"])


def test_explicitCombinedProcedure_shouldPass(client):
    note = """Procedure: Laparoscopic appendectomy and laparoscopic cholecystectomy.
Findings: Inflamed appendix and inflamed gallbladder with gallstones.
Technique: The appendix was divided at the base with a stapler and removed. The cystic duct and cystic artery were clipped and divided, and the gallbladder was removed.
Postoperative diagnosis: Acute appendicitis and cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Combined appendectomy cholecystectomy", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "Ready"
    assert body["report"]["main_issue"] == "No major issues"
    assert not any(finding["category"] == "procedure_documentation_conflict" for finding in body["audit_findings"])


def test_conflicting_cholecystectomy_appendix_documentation_is_high_risk(client):
    note = """Procedure: Laparoscopic cholecystectomy.
Findings: Inflamed appendix in right lower quadrant.
Technique: Appendix divided at base and removed.
Postoperative diagnosis: Cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Reverse conflicting documentation", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Procedure documentation conflict"
    assert body["report"]["detected_procedure"] == "Conflicting procedure documentation"
    assert body["report"]["recommended_action"] == "Confirm final operative procedure before coding."


def test_headerGallbladder_techniqueAppendix_shouldConflict(client):
    note = """Procedure: Laparoscopic cholecystectomy.
Findings: Inflamed appendix in the right lower quadrant.
Technique: The appendix was divided at the base with a stapler and removed in a retrieval bag.
Postoperative diagnosis: Cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Exact cholecystectomy contradiction", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Procedure documentation conflict"
    assert body["report"]["detected_procedure"] == "Conflicting procedure documentation"


def test_cholecystectomy_possible_cholangiogram_remains_high_risk(client):
    note = """Procedure: Laparoscopic cholecystectomy, possible cholangiogram.
Indication: Synthetic patient with symptomatic gallstones.
Findings: Inflamed gallbladder.
Technique: The gallbladder was dissected from the liver bed. The note states that a cholangiogram may have been performed but does not clearly document catheter placement or interpretation.
Postoperative diagnosis: Cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Possible cholangiogram", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Bundling conflict"
    assert any(finding["category"] == "bundling_conflict" for finding in body["audit_findings"])


def test_normal_cholecystectomy_is_ready(client):
    note = """Procedure: Laparoscopic cholecystectomy.
Indication: Synthetic patient with symptomatic cholelithiasis.
Findings: Inflamed gallbladder with gallstones.
Technique: Four ports were placed. The cystic duct and cystic artery were clipped and divided. The gallbladder was dissected from the liver bed and removed.
Complications: None.
Postoperative diagnosis: Cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Normal cholecystectomy", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "Ready"
    assert body["report"]["main_issue"] == "No major issues"
    assert body["cpt_candidates"][0]["code"] == "47562"
    assert not any(finding["category"] == "procedure_documentation_conflict" for finding in body["audit_findings"])


def test_cholecystectomy_procedure_with_appendix_technique_is_high_risk(client):
    note = """Procedure: Laparoscopic cholecystectomy.
Technique: Appendix divided at base and removed.
Postoperative diagnosis: Cholelithiasis."""
    response = client.post("/api/notes", json={"title": "Cholecystectomy appendix conflict", "note_text": note})

    assert response.status_code == 201
    body = response.json()
    assert body["report"]["claim_readiness_status"] == "High Risk"
    assert body["report"]["main_issue"] == "Procedure documentation conflict"
    assert body["report"]["recommended_action"] == "Confirm final operative procedure before coding."


def test_revised_note_workflow_improves_readiness(client):
    initial_note = (
        "Title: Open inguinal hernia repair with missing laterality. Procedure: Open inguinal hernia repair with mesh. "
        "Operative note: The hernia sac was reduced and mesh repair was completed. Laterality is missing from the note."
    )
    revised_note = (
        "Title: Left open inguinal hernia repair. Procedure: Left open inguinal hernia repair with mesh. "
        "Operative note: A left groin incision was made. The hernia sac was reduced and mesh repair was completed on the left side."
    )

    initial_response = client.post("/api/notes", json={"title": "Initial revision note", "note_text": initial_note})
    revised_response = client.post("/api/notes", json={"title": "Revised revision note", "note_text": revised_note})

    assert initial_response.status_code == 201
    assert revised_response.status_code == 201
    initial = initial_response.json()
    revised = revised_response.json()
    assert initial["report"]["claim_readiness_status"] != "Ready"
    assert revised["report"]["claim_readiness_status"] == "Ready"
    assert revised["report"]["claim_readiness_score"] > initial["report"]["claim_readiness_score"]
    assert any(finding["category"] == "missing_laterality" for finding in initial["audit_findings"])
    assert not any(finding["category"] == "missing_laterality" for finding in revised["audit_findings"])


def test_invalid_note_input_returns_readable_error(client):
    response = client.post("/api/notes", json={"title": "Bad note", "note_text": "   "})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed."


@pytest.mark.parametrize(
    "identifier_text",
    [
        "MRN: 123456",
        "DOB: 01/02/1970",
        "123-45-6789",
        "test.patient@example.com",
        "555-123-4567",
        "Patient Name: Jane Smith",
        "Name: Jane Smith",
    ],
)
def test_identifier_containing_note_is_rejected(client, identifier_text):
    note = (
        f"Title: Synthetic procedure note. {identifier_text}. "
        "Procedure: Diagnostic colonoscopy. Operative note: The colonoscope was advanced to the cecum."
    )

    response = client.post("/api/notes", json={"title": "Identifier note", "note_text": note})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Potential patient identifiers detected. Please remove identifiers before analysis."
    assert client.get("/api/analyses").json() == []


def test_identifier_in_note_title_is_rejected(client):
    note = "Procedure: Laparoscopic appendectomy. Operative note: Appendix was removed laparoscopically without complication."

    response = client.post("/api/notes", json={"title": "Patient Name: Jane Smith", "note_text": note})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Potential patient identifiers detected. Please remove identifiers before analysis."
    assert client.get("/api/analyses").json() == []


def test_identifier_rejection_happens_before_analysis_service(client, monkeypatch):
    from app.routes import notes

    called = {"value": False}

    def fail_if_called(*args, **kwargs):
        called["value"] = True
        raise AssertionError("analysis service should not run for identifier-containing input")

    monkeypatch.setattr(notes.service, "create_analysis", fail_if_called)
    note = "MRN: 123456. Procedure: Laparoscopic appendectomy. Operative note: Appendix was removed laparoscopically."

    response = client.post("/api/notes", json={"title": "Identifier note", "note_text": note})

    assert response.status_code == 400
    assert called["value"] is False


def test_missing_analysis_returns_404(client):
    response = client.get("/api/analyses/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Analysis not found"
