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


SAMPLE_NOTE = (
    "Title: Left AV fistula creation. Procedure: Left upper extremity arteriovenous fistula creation. "
    "Operative note: The cephalic vein and radial artery were dissected and an end-to-side anastomosis "
    "was created for durable dialysis access."
)


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


def test_submit_note_and_get_analysis(client):
    create_response = client.post("/api/notes", json={"title": "Integration note", "note_text": SAMPLE_NOTE})
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["cpt_candidates"][0]["code"] == "36821"
    assert created["total_estimated_reimbursement"] > 0

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
    assert body["report"]["recommended_action"] == "Clarify documentation before submission."
    assert body["cpt_candidates"][0]["modifiers"] == []
    assert any(finding["category"] == "missing_laterality" for finding in body["audit_findings"])


def test_invalid_note_input_returns_readable_error(client):
    response = client.post("/api/notes", json={"title": "Bad note", "note_text": "   "})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed."


def test_missing_analysis_returns_404(client):
    response = client.get("/api/analyses/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Analysis not found"
