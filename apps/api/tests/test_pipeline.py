from pathlib import Path

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.agents.report_generator import ReportGenerator
from app.models.schemas import CPTCodeCandidate, ExtractedProcedure, ReimbursementEstimate
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
    assert any(finding.category == "missing_laterality" for finding in findings)


def test_missing_laterality_does_not_assign_modifier():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedures = ProcedureExtractor(MockLLMProvider()).run(
        "Open inguinal hernia repair with mesh was performed. The note does not clearly document left or right laterality."
    )
    candidates = CPTCoder(retriever).run(procedures)
    findings = BillingAuditor(retriever).run(candidates)
    assert candidates[0].code == "49505"
    assert candidates[0].modifiers == []
    missing_laterality = next(finding for finding in findings if finding.title == "Missing laterality")
    assert missing_laterality.documentation_improvement == "Document whether the procedure was performed on the left or right side."
    assert "laterality" in (missing_laterality.why_it_matters or "")


def test_laterality_findings_only_apply_to_sided_procedures():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    coder = CPTCoder(retriever)
    auditor = BillingAuditor(retriever)
    non_sided_procedures = [
        ExtractedProcedure(
            name="Laparoscopic appendectomy",
            body_site="appendix",
            approach="laparoscopic",
            laterality=None,
            evidence="Appendix removed laparoscopically.",
            confidence=0.9,
        ),
        ExtractedProcedure(
            name="Small bowel resection",
            body_site="small bowel",
            approach="open",
            laterality=None,
            evidence="Small bowel resection with anastomosis.",
            confidence=0.82,
        ),
        ExtractedProcedure(
            name="Laparoscopic cholecystectomy",
            body_site="gallbladder",
            approach="laparoscopic",
            laterality=None,
            evidence="Gallbladder removed laparoscopically.",
            confidence=0.95,
        ),
    ]

    for procedure in non_sided_procedures:
        findings = auditor.run(coder.run([procedure]))
        assert not any(finding.category == "missing_laterality" for finding in findings)


def test_hernia_missing_laterality_is_needs_review_not_high_risk():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedure = ExtractedProcedure(
        name="Open inguinal hernia repair",
        body_site="inguinal region",
        approach="open",
        laterality=None,
        evidence="Open inguinal hernia repair with mesh.",
        confidence=0.88,
    )
    candidates = CPTCoder(retriever).run([procedure])
    findings = BillingAuditor(retriever).run(candidates)
    estimates = [ReimbursementEstimate(code=candidates[0].code, allowed_amount=1200, source="test")]
    _, report = ReportGenerator().run([procedure], candidates, findings, estimates)

    assert any(finding.category == "missing_laterality" for finding in findings)
    assert report["claim_readiness_status"] == "Needs Review"
    assert report["main_issue"] == "Missing laterality"


def test_cholecystectomy_bundling_conflict_is_high_risk():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedures = ProcedureExtractor(MockLLMProvider()).run(
        "Laparoscopic cholecystectomy with cholangiogram was documented, and both cholecystectomy services were selected."
    )
    candidates = CPTCoder(retriever).run(procedures)
    findings = BillingAuditor(retriever).run(candidates)
    estimates = [ReimbursementEstimate(code=candidate.code, allowed_amount=1000, source="test") for candidate in candidates]
    _, report = ReportGenerator().run(procedures, candidates, findings, estimates)

    assert any(finding.category == "bundling_conflict" for finding in findings)
    assert report["claim_readiness_status"] == "High Risk"


def test_vague_unsupported_procedure_needs_review_without_conflict():
    procedure = ExtractedProcedure(
        name="Unclassified operative procedure",
        body_site=None,
        approach=None,
        laterality=None,
        evidence="No supported procedure pattern matched.",
        confidence=0.35,
    )
    candidate = CPTCodeCandidate(
        procedure_name=procedure.name,
        code="99999",
        description="Unsupported procedure in local codebook",
        modifiers=[],
        rationale="No matching reference snippet found in the local demo guidelines.",
        confidence=0.25,
        supported_by_docs=False,
    )
    findings = BillingAuditor(KeywordRetriever(ROOT / "data" / "reference_docs")).run([candidate])
    estimates = [ReimbursementEstimate(code="99999", allowed_amount=0, source="test")]
    _, report = ReportGenerator().run([procedure], [candidate], findings, estimates)

    assert any(finding.category == "unsupported_code" for finding in findings)
    assert report["claim_readiness_status"] == "Needs Review"
    assert report["main_issue"] == "Insufficient procedure detail"


def test_complex_gi_unsupported_case_requires_coder_review_not_high_risk():
    procedure = ExtractedProcedure(
        name="Exploratory laparotomy with small bowel resection",
        body_site="small bowel",
        approach="open",
        laterality=None,
        evidence="Exploratory laparotomy with small bowel resection and stapled anastomosis.",
        confidence=0.68,
    )
    candidate = CPTCodeCandidate(
        procedure_name=procedure.name,
        code="99999",
        description="Complex GI surgery identified - additional coding review recommended",
        modifiers=[],
        rationale="Operative intent is understandable, but final CPT specificity requires coder review.",
        confidence=0.45,
        supported_by_docs=False,
    )
    findings = BillingAuditor(KeywordRetriever(ROOT / "data" / "reference_docs")).run([candidate])
    estimates = [ReimbursementEstimate(code="99999", allowed_amount=0, source="test")]
    _, report = ReportGenerator().run([procedure], [candidate], findings, estimates)

    assert report["claim_readiness_status"] == "Needs Review"
    assert report["main_issue"] == "Complex procedure requires coder review"
    assert not any(finding.category == "missing_laterality" for finding in findings)


def test_retrieval_filters_irrelevant_evidence_by_family():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    hernia_docs = retriever.retrieve("open inguinal hernia repair mesh", family="hernia")
    assert hernia_docs
    assert all("hernia" in str(doc["source"]) for doc in hernia_docs)


def test_reimbursement_estimation():
    retriever = KeywordRetriever(ROOT / "data" / "reference_docs")
    procedures = ProcedureExtractor(MockLLMProvider()).run("A left arm AV fistula creation was completed.")
    candidates = CPTCoder(retriever).run(procedures)
    estimates = ReimbursementEstimator(ROOT / "data" / "fee_schedule" / "fee_schedule.json").run(candidates)
    assert estimates[0].allowed_amount > 0
