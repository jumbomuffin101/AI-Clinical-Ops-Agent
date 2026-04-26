from pathlib import Path

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.providers.mock import MockLLMProvider
from app.rag.retriever import KeywordRetriever


ROOT = Path(__file__).resolve().parents[3]


def test_procedure_extraction_mock_provider():
    extractor = ProcedureExtractor(MockLLMProvider())
    procedures = extractor.run("A left arm AV fistula creation was performed for dialysis access.")
    assert procedures[0].name == "AV fistula creation"
    assert procedures[0].laterality == "left"
    assert procedures[0].confidence > 0.9


def test_cpt_coding_output_structure():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedures = ProcedureExtractor(MockLLMProvider()).run("Laparoscopic cholecystectomy removed the gallbladder.")
    candidates = CPTCoder(retriever).run(procedures)
    assert candidates[0].code == "47562"
    assert candidates[0].supported_by_docs is True


def test_audit_findings_for_missing_laterality_modifier():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedures = ProcedureExtractor(MockLLMProvider()).run("Femoral endarterectomy was performed through an open incision.")
    candidates = CPTCoder(retriever).run(procedures)
    findings = BillingAuditor(retriever).run(candidates)
    assert any(finding.category == "missing_modifier" for finding in findings)


def test_reimbursement_estimation():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedures = ProcedureExtractor(MockLLMProvider()).run("A left arm AV fistula creation was completed.")
    candidates = CPTCoder(retriever).run(procedures)
    estimates = ReimbursementEstimator(ROOT / "data" / "fee_schedule" / "fee_schedule.json").run(candidates)
    assert estimates[0].allowed_amount > 0
