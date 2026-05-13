import hashlib
import logging
import re
import time
from uuid import UUID

from pydantic import ValidationError

from sqlalchemy.orm import Session

from app.agents.billing_auditor import BillingAuditor
from app.agents.cpt_coder import CPTCoder
from app.agents.procedure_extractor import ProcedureExtractor
from app.agents.reimbursement_estimator import ReimbursementEstimator
from app.agents.report_generator import ReportGenerator
from app.config import get_settings
from app.logging_utils import log_event
from app.models import db as models
from app.models.schemas import (
    AIAuditConcern,
    AIStructuredOperativeNote,
    AnalysisListItem,
    AnalysisReport,
    AuditFinding,
    ExtractedProcedure,
    OperativeNote,
    StructuredOperativeNote,
)
from app.parsing.note_parser import OperativeNoteParser
from app.providers.factory import get_llm_provider
from app.rag.retriever import KeywordRetriever
from app.safety.phi_detector import contains_phi_like_identifier


logger = logging.getLogger(__name__)
AI_CACHE_TTL_SECONDS = 600
AI_RESPONSE_CACHE: dict[str, tuple[float, AIStructuredOperativeNote]] = {}


class AnalysisService:
    def __init__(self) -> None:
        self.settings = get_settings()
        retriever = KeywordRetriever(self.settings.reference_docs_path)
        self.llm_provider = get_llm_provider()
        self.extractor = ProcedureExtractor(self.llm_provider)
        self.parser = OperativeNoteParser()
        self.coder = CPTCoder(retriever)
        self.auditor = BillingAuditor(retriever)
        self.estimator = ReimbursementEstimator(self.settings.fee_schedule_path)
        self.report_generator = ReportGenerator()
        self._known_note_hashes = self._load_known_note_hashes()

    def create_analysis(self, db: Session, payload: OperativeNote) -> AnalysisReport:
        note = models.Note(title=payload.title, note_text=payload.note_text)
        db.add(note)
        db.flush()

        structured_note = self.parser.parse(payload.note_text)
        procedures = self.extractor.run(payload.note_text, structured_note)
        candidates = self.coder.run(procedures)
        findings = self.auditor.run(candidates, structured_note)
        ai_analysis, ai_status = self._maybe_run_ai_analysis(payload.note_text, candidates, findings)
        if ai_analysis:
            structured_note = self._merge_structured_note(structured_note, ai_analysis)
            procedures = self.extractor.run(payload.note_text, structured_note)
            procedures = self._merge_ai_procedures(procedures, ai_analysis, structured_note)
            candidates = self.coder.run(procedures)
            findings = self.auditor.run(candidates, structured_note)
        findings.extend(self._ai_audit_findings(ai_analysis))
        if ai_analysis and ai_analysis.unsupported_or_unclear_procedure and not any(finding.category == "unsupported_code" for finding in findings):
            findings.append(self._unsupported_ai_finding())
        estimates = self.estimator.run(candidates)
        summary, report = self.report_generator.run(procedures, candidates, findings, estimates)
        report["structured_note"] = structured_note.model_dump()
        report["analysis_mode"] = "Hybrid AI mode" if ai_analysis else "Rules mode"
        report["ai_assist_status"] = ai_status

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
            analysis_mode=analysis.report.get("analysis_mode", "Rules mode"),
            structured_note=analysis.report.get("structured_note"),
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
                    "evidence_used": row.evidence_used or [],
                }
                for row in analysis.cpt_candidates
            ],
            audit_findings=[
                {
                    "id": UUID(row.id),
                    "title": row.title,
                    "severity": row.severity,
                    "category": row.category,
                    "message": row.message,
                    "explanation": row.explanation,
                    "related_code": row.related_code,
                    "recommendation": row.recommendation,
                    "suggested_action": row.suggested_action,
                    "documentation_improvement": row.documentation_improvement,
                    "why_it_matters": row.why_it_matters,
                    "evidence_used": row.evidence_used or [],
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

    def _run_ai_analysis(self, note_text: str) -> tuple[AIStructuredOperativeNote | None, str]:
        selected_provider = self.settings.llm_provider.strip().lower()
        if selected_provider != "openrouter":
            log_event(logger, logging.INFO, "llm.fallback.activated", reason="provider_not_openrouter", provider=selected_provider or "mock")
            return None, "Rules mode enabled."
        if not self.settings.openrouter_api_key:
            log_event(logger, logging.WARNING, "llm.fallback.activated", reason="openrouter_api_key_missing", provider=selected_provider)
            return None, "OpenRouter API key not configured; rules fallback used."
        if not self.settings.openrouter_enabled:
            log_event(logger, logging.INFO, "llm.fallback.activated", reason="openrouter_disabled", provider=selected_provider)
            return None, "OpenRouter disabled; rules fallback used."
        if contains_phi_like_identifier(note_text):
            log_event(logger, logging.WARNING, "llm.fallback.activated", reason="phi_like_identifier_detected", provider=selected_provider)
            return None, "Possible identifier detected. Remove identifiers before using Hybrid AI mode."
        cache_key = self._ai_cache_key(note_text)
        cached = AI_RESPONSE_CACHE.get(cache_key)
        now = time.time()
        if cached and cached[0] > now:
            log_event(logger, logging.INFO, "llm.openrouter.cache.hit", model=self.settings.openrouter_model)
            return cached[1], "OpenRouter cached draft analysis validated."
        if cached:
            AI_RESPONSE_CACHE.pop(cache_key, None)
        try:
            log_event(logger, logging.INFO, "llm.openrouter.analysis.attempted", provider=selected_provider)
            raw_output = self.llm_provider.complete_json(self._openrouter_prompt(note_text))
            validated = AIStructuredOperativeNote.model_validate(raw_output)
            AI_RESPONSE_CACHE[cache_key] = (time.time() + AI_CACHE_TTL_SECONDS, validated)
            log_event(logger, logging.INFO, "llm.openrouter.validation.success", procedure_count=len(validated.detected_procedures))
            log_event(logger, logging.INFO, "llm.openrouter.analysis.succeeded", provider=selected_provider)
            return validated, "OpenRouter draft analysis validated."
        except ValidationError as exc:
            log_event(
                logger,
                logging.WARNING,
                "llm.fallback.activated",
                reason="openrouter_schema_validation_failed",
                validation_errors=exc.errors(),
            )
            return None, f"OpenRouter output failed schema validation; rules fallback used. {exc.errors()[0]['msg'] if exc.errors() else ''}".strip()
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "llm.fallback.activated",
                reason="openrouter_request_or_parse_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None, f"OpenRouter unavailable or invalid; rules fallback used. {type(exc).__name__}: {exc}"

    def _maybe_run_ai_analysis(
        self,
        note_text: str,
        candidates: list,
        findings: list[AuditFinding],
    ) -> tuple[AIStructuredOperativeNote | None, str]:
        if self._is_known_deterministic_note(note_text):
            log_event(logger, logging.INFO, "llm.fallback.activated", reason="known_deterministic_example")
            return None, "Known deterministic example; rules mode used."
        if self._rules_need_ai_help(candidates, findings):
            return self._run_ai_analysis(note_text)
        log_event(logger, logging.INFO, "llm.fallback.activated", reason="rules_confident_custom_note")
        return None, "Rules handled the note confidently; OpenRouter not needed."

    @staticmethod
    def _rules_need_ai_help(candidates: list, findings: list[AuditFinding]) -> bool:
        if not candidates:
            return True
        if any(candidate.code == "99999" or candidate.confidence < 0.85 or not candidate.supported_by_docs for candidate in candidates):
            return True
        return any(finding.category in {"unsupported_code", "low_confidence"} for finding in findings)

    def _is_known_deterministic_note(self, note_text: str) -> bool:
        return self._normalized_hash(note_text) in self._known_note_hashes

    def _ai_cache_key(self, note_text: str) -> str:
        return hashlib.sha256(f"{self.settings.openrouter_model}:{self._normalize_text(note_text)}".encode("utf-8")).hexdigest()

    def _load_known_note_hashes(self) -> set[str]:
        notes_path = self.settings.project_root / "data" / "synthetic_notes"
        if not notes_path.exists():
            return set()
        return {self._normalized_hash(path.read_text(encoding="utf-8")) for path in notes_path.glob("*.txt")}

    @classmethod
    def _normalized_hash(cls, text: str) -> str:
        return hashlib.sha256(cls._normalize_text(text).encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()

    @staticmethod
    def _openrouter_prompt(note_text: str) -> str:
        return (
            "Analyze this synthetic operative note for billing review assistance. "
            "Do not assume this is real patient data. Return JSON only with exactly these top-level keys: "
            "parsed_note_sections, detected_procedures, anatomy, laterality, likely_cpt_candidates, "
            "documentation_gaps, audit_concerns, confidence_reasoning, unsupported_or_unclear_procedure. "
            "Use null when anatomy or laterality is unclear. Do not invent CPT codes when documentation is vague. "
            "Mark unsupported_or_unclear_procedure true if the procedure cannot be confidently mapped.\n\n"
            f"OPERATIVE NOTE:\n{note_text}"
        )

    @staticmethod
    def _merge_structured_note(
        deterministic: StructuredOperativeNote,
        ai_analysis: AIStructuredOperativeNote,
    ) -> StructuredOperativeNote:
        sections = {**ai_analysis.parsed_note_sections, **deterministic.parsed_sections}
        missing_sections = [section for section in OperativeNoteParser.CRITICAL_SECTIONS if section not in sections]
        confidence = max(deterministic.parsing_confidence, 0.7 if ai_analysis.parsed_note_sections else deterministic.parsing_confidence)
        return StructuredOperativeNote(
            raw_text=deterministic.raw_text,
            parsed_sections=sections,
            detected_procedure_name=deterministic.detected_procedure_name or (ai_analysis.detected_procedures[0].name if ai_analysis.detected_procedures else None),
            detected_anatomy=deterministic.detected_anatomy or ai_analysis.anatomy,
            detected_laterality=deterministic.detected_laterality,
            missing_sections=missing_sections,
            parsing_confidence=confidence,
            structure_quality=OperativeNoteParser._quality(confidence),
        )

    @staticmethod
    def _merge_ai_procedures(
        procedures: list[ExtractedProcedure],
        ai_analysis: AIStructuredOperativeNote | None,
        structured_note: StructuredOperativeNote,
    ) -> list[ExtractedProcedure]:
        if not ai_analysis or ai_analysis.unsupported_or_unclear_procedure:
            return procedures
        if not procedures or procedures[0].name != "Unclassified operative procedure":
            return procedures

        known_names = set(CPTCoder.CODEBOOK)
        candidates = [procedure for procedure in ai_analysis.detected_procedures if procedure.name in known_names and procedure.confidence >= 0.65]
        if not candidates:
            return procedures

        procedure = max(candidates, key=lambda item: item.confidence)
        return [
            ExtractedProcedure(
                name=procedure.name,
                body_site=procedure.anatomy or structured_note.detected_anatomy,
                approach=None,
                laterality=procedure.laterality or structured_note.detected_laterality,
                evidence=procedure.evidence,
                confidence=min(procedure.confidence, 0.82),
            )
        ]

    @staticmethod
    def _ai_audit_findings(ai_analysis: AIStructuredOperativeNote | None) -> list[AuditFinding]:
        if not ai_analysis:
            return []
        findings: list[AuditFinding] = []
        for concern in ai_analysis.audit_concerns:
            findings.append(
                AuditFinding(
                    title=concern.title,
                    severity=concern.severity if concern.severity in {"high", "medium", "low", "info"} else "medium",
                    category="ai_audit_concern",
                    message=concern.title,
                    explanation=concern.explanation,
                    recommendation=concern.suggested_action,
                    suggested_action=concern.suggested_action,
                    documentation_improvement=concern.suggested_action,
                    why_it_matters="Hybrid AI mode raised this as a draft concern for human billing review.",
                    evidence_used=[],
                )
            )
        for gap in ai_analysis.documentation_gaps:
            findings.append(
                AuditFinding(
                    title="Documentation gap",
                    severity="low",
                    category="ai_documentation_gap",
                    message=gap,
                    explanation=gap,
                    recommendation="Clarify this documentation gap before relying on AI-assisted coding suggestions.",
                    suggested_action="Clarify this documentation gap before relying on AI-assisted coding suggestions.",
                    documentation_improvement=gap,
                    why_it_matters="Clearer documentation improves coding support and reduces review ambiguity.",
                    evidence_used=[],
                )
            )
        return findings

    @staticmethod
    def _unsupported_ai_finding() -> AuditFinding:
        return AuditFinding(
            title="Unsupported or unclear procedure",
            severity="high",
            category="unsupported_code",
            message="Unsupported or unclear procedure.",
            explanation="Hybrid AI mode could not confidently map the note to a supported procedure.",
            recommendation="Clarify the operative procedure and route to coder review.",
            suggested_action="Clarify the operative procedure and route to coder review.",
            documentation_improvement="Document the exact procedure performed, anatomy, approach, and therapeutic intent.",
            why_it_matters="The system should not invent a high-confidence billing code when the documented procedure is unclear.",
            evidence_used=[],
        )

    def list_recent_analyses(self, db: Session, limit: int = 10) -> list[AnalysisListItem]:
        rows = db.query(models.Analysis).join(models.Note).order_by(models.Analysis.created_at.desc()).limit(limit).all()
        items: list[AnalysisListItem] = []
        for analysis in rows:
            top_candidate = analysis.cpt_candidates[0] if analysis.cpt_candidates else None
            items.append(
                AnalysisListItem(
                    id=UUID(analysis.id),
                    title=analysis.note.title or f"Analysis {analysis.id[:8]}",
                    created_at=analysis.created_at,
                    top_cpt_code=top_candidate.code if top_candidate else None,
                    total_reimbursement=analysis.total_estimated_reimbursement,
                    claim_readiness_status=analysis.report.get("claim_readiness_status", analysis.report.get("claim_readiness", "Needs Review")),
                    main_issue=analysis.report.get("main_issue"),
                )
            )
        return items

    def export_analysis(self, db: Session, analysis_id: UUID) -> dict:
        analysis = db.get(models.Analysis, str(analysis_id))
        if analysis is None:
            raise LookupError("Analysis not found")
        report = self.get_analysis(db, analysis_id)
        return {
            "note": {
                "id": analysis.note.id,
                "title": analysis.note.title,
                "created_at": analysis.note.created_at.isoformat(),
                "synthetic_data_only": True,
            },
            "analysis": report.model_dump(mode="json"),
            "claim_readiness": {
                "score": analysis.report.get("claim_readiness_score"),
                "status": analysis.report.get("claim_readiness_status"),
                "explanation": analysis.report.get("claim_readiness_explanation"),
            },
            "final_report": analysis.report,
        }
