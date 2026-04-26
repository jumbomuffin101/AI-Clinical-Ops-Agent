from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.agents.report_generator import ReportGenerator
from app.config import get_settings
from app.models import db as models
from app.models.schemas import AnalysisReport, OperativeNote
from app.providers.factory import get_llm_provider
from app.rag.retriever import KeywordRetriever


class AnalysisService:
    def __init__(self) -> None:
        settings = get_settings()
        retriever = KeywordRetriever(settings.reference_docs_path)
        self.extractor = ProcedureExtractor(get_llm_provider())
        self.coder = CPTCoder(retriever)
        self.auditor = BillingAuditor(retriever)
        self.estimator = ReimbursementEstimator(settings.fee_schedule_path)
        self.report_generator = ReportGenerator()

    def create_analysis(self, db: Session, payload: OperativeNote) -> AnalysisReport:
        note = models.Note(title=payload.title, note_text=payload.note_text)
        db.add(note)
        db.flush()

        procedures = self.extractor.run(payload.note_text)
        candidates = self.coder.run(procedures)
        findings = self.auditor.run(candidates)
        estimates = self.estimator.run(candidates)
        summary, report = self.report_generator.run(procedures, candidates, findings, estimates)

        analysis = models.Analysis(
            note_id=note.id,
            status="completed",
            summary=summary,
            report=report,
            total_estimated_reimbursement=sum(estimate.allowed_amount for estimate in estimates),
        )
        db.add(analysis)
        db.flush()

        for procedure in procedures:
            db.add(models.ExtractedProcedureRecord(analysis_id=analysis.id, **procedure.model_dump(exclude={"id"})))
        for candidate in candidates:
            db.add(models.CPTCandidateRecord(analysis_id=analysis.id, **candidate.model_dump(exclude={"id"})))
        for finding in findings:
            db.add(models.AuditFindingRecord(analysis_id=analysis.id, **finding.model_dump(exclude={"id"})))
        for estimate in estimates:
            db.add(models.ReimbursementEstimateRecord(analysis_id=analysis.id, **estimate.model_dump(exclude={"id"})))

        db.commit()
        db.refresh(analysis)
        return self.get_analysis(db, UUID(analysis.id))

    def get_analysis(self, db: Session, analysis_id: UUID) -> AnalysisReport:
        analysis = db.get(models.Analysis, str(analysis_id))
        if analysis is None:
            raise LookupError("Analysis not found")

        return AnalysisReport(
            id=UUID(analysis.id),
            note_id=UUID(analysis.note_id),
            status=analysis.status,
            extracted_procedures=[
                {
                    "id": UUID(row.id),
                    "name": row.name,
                    "body_site": row.body_site,
                    "approach": row.approach,
                    "laterality": row.laterality,
                    "evidence": row.evidence,
                    "confidence": row.confidence,
                }
                for row in analysis.extracted_procedures
            ],
            cpt_candidates=[
                {
                    "id": UUID(row.id),
                    "procedure_name": row.procedure_name,
                    "code": row.code,
                    "description": row.description,
                    "modifiers": row.modifiers,
                    "rationale": row.rationale,
                    "confidence": row.confidence,
                    "supported_by_docs": row.supported_by_docs,
                }
                for row in analysis.cpt_candidates
            ],
            audit_findings=[
                {
                    "id": UUID(row.id),
                    "severity": row.severity,
                    "category": row.category,
                    "message": row.message,
                    "related_code": row.related_code,
                    "recommendation": row.recommendation,
                }
                for row in analysis.audit_findings
            ],
            reimbursement_estimates=[
                {
                    "id": UUID(row.id),
                    "code": row.code,
                    "allowed_amount": row.allowed_amount,
                    "currency": row.currency,
                    "source": row.source,
                }
                for row in analysis.reimbursement_estimates
            ],
            total_estimated_reimbursement=analysis.total_estimated_reimbursement,
            summary=analysis.summary,
            report=analysis.report,
            created_at=analysis.created_at,
        )
