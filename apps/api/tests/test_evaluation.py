import json
import subprocess
import sys
from pathlib import Path

from app.services.evaluation_service import EvaluationService, load_gold_standard

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]


def test_gold_standard_parsing():
    cases = load_gold_standard(ROOT / "data" / "evaluation" / "gold_standard.json")
    assert cases
    assert {"note_filename", "expected_primary_cpt", "expected_claim_status", "expected_main_issue", "expected_audit_findings"} <= set(cases[0])


def test_evaluation_service_output_shape():
    summary = EvaluationService().run()
    assert summary["total_cases"] == len(summary["per_case_results"])
    assert 0 <= summary["cpt_accuracy"] <= 1
    assert 0 <= summary["readiness_accuracy"] <= 1
    assert 0 <= summary["audit_accuracy"] <= 1
    assert {"expected_primary_cpt", "actual_primary_cpt", "passed"} <= set(summary["per_case_results"][0])


def test_evaluation_script_output_shape():
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_pipeline.py"],
        cwd=API_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)
    assert summary["total_cases"] >= 5
    assert summary["per_case_results"]
