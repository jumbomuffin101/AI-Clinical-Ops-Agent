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
    AIProcedure,
    AIStructuredOperativeNote,
    AnalysisListItem,
    AnalysisReport,
    AuditFinding,
    CPTCodeCandidate,
    ExtractedProcedure,
    OperativeNote,
    StructuredOperativeNote,
)
from app.parsing.note_parser import OperativeNoteParser
from app.providers.factory import get_llm_provider
from app.rag.retriever import KeywordRetriever
from app.safety.phi_detector import contains_phi_like_identifier
from app.services.review_engine import ProcedureFamily, ReviewClassification, ReviewEngine


logger = logging.getLogger(__name__)
AI_CACHE_TTL_SECONDS = 600
AI_RESPONSE_CACHE: dict[str, tuple[float, AIStructuredOperativeNote]] = {}
PHI_REJECTION_MESSAGE = "Potential patient identifiers detected. Please remove identifiers before analysis."


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
        if contains_phi_like_identifier(f"{payload.title}\n{payload.note_text}"):
            log_event(logger, logging.WARNING, "analysis.rejected", reason="phi_like_identifier_detected")
            raise ValueError(PHI_REJECTION_MESSAGE)

        note = models.Note(title=payload.title, note_text=payload.note_text)
        db.add(note)
        db.flush()

        structured_note = self.parser.parse(payload.note_text)
        procedures = self.extractor.run(payload.note_text, structured_note)
        candidates = self.coder.run(procedures)
        findings = self.auditor.run(candidates, structured_note)
        classification = self._apply_deterministic_guardrails(structured_note, candidates, findings)
        ai_analysis, ai_status = self._maybe_run_ai_analysis(payload.note_text, candidates, findings)
        if ai_analysis:
            structured_note = self._merge_structured_note(structured_note, ai_analysis)
            procedures = self.extractor.run(payload.note_text, structured_note)
            procedures = self._merge_ai_procedures(procedures, ai_analysis, structured_note)
            candidates = self.coder.run(procedures)
            findings = self.auditor.run(candidates, structured_note)
            classification = self._apply_deterministic_guardrails(structured_note, candidates, findings)
        findings.extend(self._ai_audit_findings(ai_analysis, candidates))
        classification = self._apply_deterministic_guardrails(structured_note, candidates, findings)
        if ai_analysis and ai_analysis.unsupported_or_unclear_procedure and not any(finding.category == "unsupported_code" for finding in findings):
            findings.append(self._unsupported_ai_finding())
        estimates = self.estimator.run(candidates)
        summary, report = self.report_generator.run(procedures, candidates, findings, estimates)
        self._apply_review_priority(report, findings)
        self._log_review_classification(classification, report)
        report["structured_note"] = structured_note.model_dump()
        report["analysis_mode"] = "Hybrid AI mode" if ai_analysis else "Rules mode"
        report["ai_assist_status"] = ai_status
        report["ai_provider"] = self.settings.llm_provider.strip().lower() if ai_analysis else None
        report["ai_model"] = self._provider_model(self.settings.llm_provider.strip().lower()) if ai_analysis else None
        report["ai_procedure_summary"] = ai_analysis.procedure_summary if ai_analysis else None
        report["ai_reasoning_summary"] = ai_analysis.reasoning_summary if ai_analysis else None
        report["ai_documentation_gaps"] = ai_analysis.documentation_gaps if ai_analysis else []
        report["ai_suggested_clarifications"] = ai_analysis.suggested_clarifications if ai_analysis else []
        report["ai_confidence_reasoning"] = ai_analysis.confidence_reasoning if ai_analysis else []
        report["ai_likely_procedure_family"] = self._infer_ai_procedure_family(ai_analysis) if ai_analysis else None
        report["ai_likely_cpt_category"] = ai_analysis.likely_cpt_category if ai_analysis else None
        report["ai_probable_operative_intent"] = ai_analysis.probable_operative_intent if ai_analysis else None
        report["ai_supporting_texts"] = self._ai_supporting_texts(ai_analysis)
        report["ai_cpt_rationales"] = self._ai_cpt_rationales(ai_analysis) or self._validated_cpt_rationales(ai_analysis, candidates)
        self._force_raw_section_procedure_conflict(structured_note, findings, report)
        self._log_raw_section_review(structured_note, report)

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

    @staticmethod
    def _apply_deterministic_guardrails(
        structured_note: StructuredOperativeNote,
        candidates: list[CPTCodeCandidate],
        findings: list[AuditFinding],
    ) -> ReviewClassification:
        classification = ReviewEngine.classify(structured_note, candidates)
        if classification.procedure_conflict and not any(finding.category == "procedure_documentation_conflict" for finding in findings):
            findings.append(ReviewEngine.conflict_finding())
        return classification

    @staticmethod
    def _log_review_classification(classification: ReviewClassification, report: dict) -> None:
        log_event(
            logger,
            logging.INFO,
            "review.finalized",
            procedure_family=classification.procedure_family,
            findings_family=classification.findings_family,
            technique_family=classification.technique_family,
            postop_family=classification.postop_family,
            procedure_conflict=classification.procedure_conflict,
            final_review_status=report.get("claim_readiness_status"),
            final_main_issue=report.get("main_issue"),
        )

    @staticmethod
    def _apply_review_priority(report: dict, findings: list[AuditFinding]) -> None:
        categories = {finding.category for finding in findings if finding.severity != "info"}
        if {"procedure_documentation_conflict", "conflicting_documentation", "conflicting_procedures"} & categories:
            conflict = next(
                (
                    finding
                    for finding in findings
                    if finding.category in {"procedure_documentation_conflict", "conflicting_documentation", "conflicting_procedures"}
                ),
                None,
            )
            report["claim_readiness_status"] = "High Risk"
            report["claim_readiness"] = "high_risk"
            report["main_issue"] = "Procedure documentation conflict"
            report["recommended_action"] = conflict.recommendation if conflict else "Confirm final operative procedure before coding"
            report["detected_procedure"] = "Conflicting procedure documentation"
            report["coding_recommendation"] = "Coder review needed"
            report["suggested_code"] = None
            return
        if "bundling_conflict" in categories:
            report["claim_readiness_status"] = "High Risk"
            report["claim_readiness"] = "high_risk"
            report["main_issue"] = "Bundling conflict"
            return
        if {"mutually_exclusive_procedures", "unsupported_cpt_combination", "compliance_risk", "severe_ambiguity"} & categories:
            report["claim_readiness_status"] = "High Risk"
            report["claim_readiness"] = "high_risk"
            return
        if "missing_laterality" in categories:
            report["claim_readiness_status"] = "Needs Review"
            report["claim_readiness"] = "needs_review"
            report["main_issue"] = "Missing laterality"
            report["recommended_action"] = "Clarify left or right side before review."

    @classmethod
    def _force_raw_section_procedure_conflict(
        cls,
        structured_note: StructuredOperativeNote,
        findings: list[AuditFinding],
        report: dict,
    ) -> None:
        classification = ReviewEngine.classify(structured_note)
        if not classification.procedure_conflict:
            return

        if not any(finding.category == "procedure_documentation_conflict" for finding in findings):
            findings.append(ReviewEngine.conflict_finding())
        report["claim_readiness_status"] = "High Risk"
        report["claim_readiness"] = "high_risk"
        report["main_issue"] = "Procedure documentation conflict"
        report["detected_procedure"] = "Conflicting procedure documentation"
        report["recommended_action"] = "Confirm final operative procedure before coding"
        report["coding_recommendation"] = "Coder review needed"
        report["suggested_code"] = None
        report["plain_english_review"] = (
            "The procedure label and operative details describe different services. "
            "Coding should not proceed until the documentation is reconciled."
        )

    @staticmethod
    def classify_section_family(section_text: str) -> ProcedureFamily | None:
        return ReviewEngine.classify_section_family(section_text)

    @classmethod
    def _log_raw_section_review(cls, structured_note: StructuredOperativeNote, report: dict) -> None:
        classification = ReviewEngine.classify(structured_note)
        log_event(
            logger,
            logging.INFO,
            "review.raw_section_finalized",
            procedure_family=classification.procedure_family,
            findings_family=classification.findings_family,
            technique_family=classification.technique_family,
            postop_family=classification.postop_family,
            procedure_header_procedures=AnalysisService._family_values(classification.procedure_header_procedures),
            findings_procedures=AnalysisService._family_values(classification.findings_procedures),
            technique_procedures=AnalysisService._family_values(classification.technique_procedures),
            diagnosis_procedures=AnalysisService._family_values(classification.diagnosis_procedures),
            procedure_conflict=classification.procedure_conflict,
            final_review_status=report.get("claim_readiness_status"),
            final_main_issue=report.get("main_issue"),
        )

    @staticmethod
    def _family_values(families: set[ProcedureFamily]) -> list[str]:
        return sorted(family.value for family in families)

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
        if selected_provider not in {"groq", "openrouter"}:
            log_event(logger, logging.INFO, "llm.fallback.activated", reason="provider_not_hybrid", provider=selected_provider or "mock")
            return None, "Rules mode enabled."
        if not self._provider_enabled(selected_provider):
            log_event(logger, logging.INFO, "llm.fallback.activated", reason="provider_disabled", provider=selected_provider)
            return None, "AI enhancement disabled; rules mode used."
        if not self._provider_api_key_loaded(selected_provider):
            log_event(logger, logging.WARNING, "llm.fallback.activated", reason="provider_api_key_missing", provider=selected_provider)
            return None, "AI enhancement not configured; rules mode used."
        if contains_phi_like_identifier(note_text):
            log_event(logger, logging.WARNING, "llm.fallback.activated", reason="phi_like_identifier_detected", provider=selected_provider)
            return None, "Possible identifier detected. Remove identifiers before using Hybrid AI mode."
        cache_key = self._ai_cache_key(note_text)
        cached = AI_RESPONSE_CACHE.get(cache_key)
        now = time.time()
        if cached and cached[0] > now:
            log_event(logger, logging.INFO, "llm.cache.hit", provider=selected_provider, model=self._provider_model(selected_provider))
            return cached[1], "Cached AI enhancement used."
        if cached:
            AI_RESPONSE_CACHE.pop(cache_key, None)
        try:
            log_event(logger, logging.INFO, "llm.analysis.attempted", provider=selected_provider, model=self._provider_model(selected_provider))
            raw_output = self.llm_provider.complete_json(self._ai_prompt(note_text))
            normalized_output, normalization_applied = self._normalize_ai_output(raw_output)
            log_event(
                logger,
                logging.INFO,
                "llm.response.shape",
                provider=selected_provider,
                keys=sorted(raw_output.keys()) if isinstance(raw_output, dict) else [],
                detected_procedures_type=type(raw_output.get("detected_procedures")).__name__ if isinstance(raw_output, dict) else type(raw_output).__name__,
                audit_concerns_type=type(raw_output.get("audit_concerns")).__name__ if isinstance(raw_output, dict) else type(raw_output).__name__,
                confidence_reasoning_type=type(raw_output.get("confidence_reasoning")).__name__ if isinstance(raw_output, dict) else type(raw_output).__name__,
            )
            log_event(logger, logging.INFO, "llm.response.normalized", provider=selected_provider, normalization_applied=normalization_applied)
            log_event(
                logger,
                logging.INFO,
                "llm.output.normalized",
                provider=selected_provider,
                normalization_applied=normalization_applied,
                original_field_types=self._field_types(raw_output),
                normalized_field_counts=self._field_counts(normalized_output),
            )
            validated = AIStructuredOperativeNote.model_validate(normalized_output)
            AI_RESPONSE_CACHE[cache_key] = (time.time() + AI_CACHE_TTL_SECONDS, validated)
            log_event(logger, logging.INFO, "llm.validation.success", provider=selected_provider, procedure_count=len(validated.detected_procedures))
            log_event(logger, logging.INFO, "llm.analysis.succeeded", provider=selected_provider)
            return validated, f"{self._provider_display_name(selected_provider)} enhancement validated."
        except ValidationError as exc:
            log_event(
                logger,
                logging.WARNING,
                "llm.fallback.activated",
                reason="provider_schema_validation_failed",
                provider=selected_provider,
                validation_errors=exc.errors(),
            )
            return None, "AI enhancement temporarily unavailable. Core billing review completed successfully."
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "llm.fallback.activated",
                reason="provider_request_or_parse_failed",
                provider=selected_provider,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None, "AI enhancement temporarily unavailable. Core billing review completed successfully."

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
        return None, "Rules handled the note confidently; AI provider not needed."

    @staticmethod
    def _rules_need_ai_help(candidates: list, findings: list[AuditFinding]) -> bool:
        if not candidates:
            return True
        if any(candidate.code == "99999" or candidate.confidence < 0.85 or not candidate.supported_by_docs for candidate in candidates):
            return True
        return any(finding.category in {"unsupported_code", "low_confidence", "missing_note_section"} for finding in findings)

    def _is_known_deterministic_note(self, note_text: str) -> bool:
        return self._normalized_hash(note_text) in self._known_note_hashes

    def _ai_cache_key(self, note_text: str) -> str:
        model = self._provider_model(self.settings.llm_provider.strip().lower())
        return hashlib.sha256(f"{model}:{self._normalize_text(note_text)}".encode("utf-8")).hexdigest()

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
    def _ai_prompt(note_text: str) -> str:
        return (
            "Analyze this synthetic operative note for billing review assistance. Return JSON only. "
            "Use this exact shape and no markdown:\n"
            "{\n"
            '  "parsed_note_sections": {"procedure": "", "indication": "", "findings": "", "technique": "", "complications": ""},\n'
            '  "detected_procedures": [{"name": "", "procedure_family": "", "anatomy": "", "laterality": null, "confidence": 0.0, "supporting_text": ""}],\n'
            '  "cpt_candidates": [{"code": "", "description": "", "confidence": 0.0, "rationale": "", "needs_human_review": true}],\n'
            '  "documentation_gaps": [""],\n'
            '  "audit_concerns": [{"title": "", "severity": "low|medium|high", "explanation": "", "suggested_action": ""}],\n'
            '  "confidence_reasoning": [""],\n'
            '  "unsupported_or_unclear_procedure": false,\n'
            '  "procedure_summary": "",\n'
            '  "reasoning_summary": "",\n'
            '  "suggested_clarifications": [""],\n'
            '  "likely_procedure_family": "",\n'
            '  "likely_cpt_category": "",\n'
            '  "probable_operative_intent": ""\n'
            "}\n"
            "Use null for unknown laterality. Do not invent high-confidence CPT codes when documentation is vague. "
            "Map bowel resection, colectomy, enterotomy, anastomosis, and laparotomy into the GI surgery family. "
            "For unsupported or complex procedures, describe likely operative intent and clarification needs instead of forcing billing certainty. "
            "Treat output as draft review support, not authoritative billing advice.\n\n"
            f"OPERATIVE NOTE:\n{note_text}"
        )

    @staticmethod
    def _normalize_ai_output(raw_output: object) -> tuple[dict, bool]:
        if not isinstance(raw_output, dict) or not raw_output:
            raise ValueError("AI response was empty or not a JSON object.")

        normalized = dict(raw_output)
        applied = False
        aliases = {
            "procedures": "detected_procedures",
            "concerns": "audit_concerns",
        }
        for alias, canonical in aliases.items():
            if canonical not in normalized and alias in normalized:
                normalized[canonical] = normalized[alias]
                applied = True
        defaults = {
            "parsed_note_sections": {},
            "detected_procedures": [],
            "cpt_candidates": [],
            "likely_cpt_candidates": [],
            "documentation_gaps": [],
            "audit_concerns": [],
            "confidence_reasoning": [],
            "unsupported_or_unclear_procedure": False,
            "suggested_clarifications": [],
        }
        for key, value in defaults.items():
            if key not in normalized or normalized[key] is None:
                normalized[key] = value
                applied = True

        for key in ["confidence_reasoning", "documentation_gaps", "suggested_clarifications"]:
            if isinstance(normalized.get(key), str):
                normalized[key] = [normalized[key]]
                applied = True

        procedures = normalized.get("detected_procedures")
        if isinstance(procedures, str):
            procedures = [procedures]
            applied = True
        if isinstance(procedures, list):
            normalized_procedures = []
            for item in procedures:
                if isinstance(item, str):
                    normalized_procedures.append(
                        {
                            "name": item,
                            "procedure_family": "unknown",
                            "anatomy": None,
                            "laterality": None,
                            "confidence": 0.65,
                            "supporting_text": item,
                            "evidence": item,
                        }
                    )
                    applied = True
                elif isinstance(item, dict):
                    procedure = dict(item)
                    procedure.setdefault("name", "Unclear procedure")
                    procedure.setdefault("procedure_family", "unknown")
                    procedure.setdefault("anatomy", None)
                    procedure.setdefault("laterality", None)
                    procedure.setdefault("confidence", 0.5)
                    procedure.setdefault("supporting_text", procedure.get("evidence", ""))
                    procedure.setdefault("evidence", procedure.get("supporting_text", ""))
                    normalized_procedures.append(procedure)
                else:
                    applied = True
            normalized["detected_procedures"] = normalized_procedures

        concerns = normalized.get("audit_concerns")
        if isinstance(concerns, str):
            concerns = [concerns]
            applied = True
        if isinstance(concerns, list):
            normalized_concerns = []
            for item in concerns:
                if isinstance(item, str):
                    normalized_concerns.append(
                        {
                            "title": "Documentation concern",
                            "severity": "medium",
                            "explanation": item,
                            "suggested_action": "Review the operative note for missing coding-support details.",
                        }
                    )
                    applied = True
                elif isinstance(item, dict):
                    concern = dict(item)
                    concern.setdefault("title", "AI audit concern")
                    concern.setdefault("severity", "medium")
                    concern.setdefault("explanation", "")
                    concern.setdefault("suggested_action", "Review before final billing.")
                    normalized_concerns.append(concern)
                else:
                    applied = True
            normalized["audit_concerns"] = normalized_concerns

        for candidate_key in ["cpt_candidates", "likely_cpt_candidates"]:
            candidates = normalized.get(candidate_key)
            if isinstance(candidates, str):
                candidates = [candidates]
                applied = True
            if isinstance(candidates, list):
                normalized_candidates = []
                for item in candidates:
                    if isinstance(item, str):
                        normalized_candidates.append(
                            {
                                "procedure_name": "",
                                "code": item,
                                "description": "",
                                "confidence": 0.35,
                                "rationale": "AI returned an unstructured CPT candidate; human review required.",
                                "needs_human_review": True,
                            }
                        )
                        applied = True
                    elif isinstance(item, dict):
                        candidate = dict(item)
                        candidate.setdefault("procedure_name", "")
                        candidate.setdefault("code", None)
                        candidate.setdefault("description", "")
                        candidate.setdefault("confidence", 0.5)
                        candidate.setdefault("rationale", "")
                        candidate.setdefault("needs_human_review", True)
                        normalized_candidates.append(candidate)
                    else:
                        applied = True
                normalized[candidate_key] = normalized_candidates

        if not normalized.get("likely_cpt_candidates") and normalized.get("cpt_candidates"):
            normalized["likely_cpt_candidates"] = normalized["cpt_candidates"]
            applied = True

        if "unsupported_or_unclear_procedure" not in raw_output:
            normalized["unsupported_or_unclear_procedure"] = not bool(normalized.get("detected_procedures"))
            applied = True

        if not normalized.get("procedure_summary") and normalized.get("detected_procedures"):
            names = [item.get("name", "") for item in normalized["detected_procedures"] if isinstance(item, dict) and item.get("name")]
            if names:
                normalized["procedure_summary"] = "AI identified: " + ", ".join(names)
                applied = True
        if not normalized.get("reasoning_summary") and normalized.get("confidence_reasoning"):
            normalized["reasoning_summary"] = " ".join(str(item) for item in normalized["confidence_reasoning"])
            applied = True

        return normalized, applied

    @staticmethod
    def _field_types(raw_output: object) -> dict[str, str]:
        if not isinstance(raw_output, dict):
            return {"root": type(raw_output).__name__}
        keys = [
            "parsed_note_sections",
            "detected_procedures",
            "procedures",
            "likely_cpt_candidates",
            "cpt_candidates",
            "audit_concerns",
            "concerns",
            "confidence_reasoning",
            "documentation_gaps",
        ]
        return {key: type(raw_output.get(key)).__name__ for key in keys if key in raw_output}

    @staticmethod
    def _field_counts(normalized_output: dict) -> dict[str, int]:
        keys = [
            "parsed_note_sections",
            "detected_procedures",
            "likely_cpt_candidates",
            "cpt_candidates",
            "audit_concerns",
            "confidence_reasoning",
            "documentation_gaps",
        ]
        counts: dict[str, int] = {}
        for key in keys:
            value = normalized_output.get(key)
            if isinstance(value, (list, dict)):
                counts[key] = len(value)
        return counts

    def _provider_enabled(self, provider: str) -> bool:
        if provider == "groq":
            return self.settings.groq_enabled
        if provider == "openrouter":
            return self.settings.openrouter_enabled
        return False

    def _provider_api_key_loaded(self, provider: str) -> bool:
        if provider == "groq":
            return bool(self.settings.groq_api_key)
        if provider == "openrouter":
            return bool(self.settings.openrouter_api_key)
        return False

    def _provider_model(self, provider: str) -> str:
        if provider == "groq":
            return self.settings.groq_model
        if provider == "openrouter":
            return self.settings.openrouter_model
        return "rules"

    @staticmethod
    def _provider_display_name(provider: str) -> str:
        if provider == "groq":
            return "Groq"
        if provider == "openrouter":
            return "OpenRouter"
        return "Rules"

    @staticmethod
    def _merge_structured_note(
        deterministic: StructuredOperativeNote,
        ai_analysis: AIStructuredOperativeNote,
    ) -> StructuredOperativeNote:
        sections = {**ai_analysis.parsed_note_sections, **deterministic.parsed_sections}
        missing_sections = [section for section in OperativeNoteParser.CRITICAL_SECTIONS if section not in sections]
        confidence = max(deterministic.parsing_confidence, 0.7 if ai_analysis.parsed_note_sections else deterministic.parsing_confidence)
        ai_procedure_anatomy = next((procedure.anatomy for procedure in ai_analysis.detected_procedures if procedure.anatomy), None)
        return StructuredOperativeNote(
            raw_text=deterministic.raw_text,
            parsed_sections=sections,
            detected_procedure_name=deterministic.detected_procedure_name or (ai_analysis.detected_procedures[0].name if ai_analysis.detected_procedures else None),
            detected_anatomy=deterministic.detected_anatomy or ai_analysis.anatomy or ai_procedure_anatomy,
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
        if not ai_analysis:
            return procedures
        if not procedures or procedures[0].name != "Unclassified operative procedure":
            return procedures

        mapped = [
            AnalysisService._ai_procedure_to_extracted(procedure, ai_analysis, structured_note)
            for procedure in ai_analysis.detected_procedures
        ]
        candidates = [procedure for procedure in mapped if procedure is not None]
        if not candidates and ai_analysis.unsupported_or_unclear_procedure:
            return procedures

        return candidates or procedures

    @staticmethod
    def _ai_procedure_to_extracted(
        procedure: AIProcedure,
        ai_analysis: AIStructuredOperativeNote,
        structured_note: StructuredOperativeNote,
    ) -> ExtractedProcedure | None:
        mapped_name = AnalysisService._map_ai_procedure_name(procedure, ai_analysis)
        if not mapped_name:
            return None
        confidence = AnalysisService._ai_cpt_mapping_confidence(procedure, mapped_name)
        evidence = procedure.supporting_text or procedure.evidence or f"AI identified {procedure.name} for human coding review."
        return ExtractedProcedure(
            name=mapped_name,
            body_site=procedure.anatomy or structured_note.detected_anatomy or AnalysisService._default_body_site(mapped_name),
            approach=AnalysisService._default_approach(mapped_name),
            laterality=procedure.laterality or structured_note.detected_laterality,
            evidence=evidence,
            confidence=confidence,
        )

    @staticmethod
    def _map_ai_procedure_name(procedure: AIProcedure, ai_analysis: AIStructuredOperativeNote) -> str | None:
        text = " ".join(
            item
            for item in [
                procedure.name,
                procedure.procedure_family or "",
                procedure.anatomy or "",
                procedure.supporting_text,
                procedure.evidence,
                ai_analysis.likely_procedure_family or "",
                ai_analysis.likely_cpt_category or "",
                ai_analysis.probable_operative_intent or "",
            ]
            if item
        ).lower()
        if procedure.name in CPTCoder.CODEBOOK:
            return procedure.name
        if any(term in text for term in ["small bowel resection", "enterectomy", "small intestine resection"]):
            return "Small bowel resection"
        if "bowel resection" in text and "anastom" in text:
            return "Bowel resection with anastomosis"
        if any(term in text for term in ["colectomy", "colon resection", "colonic resection"]):
            return "Partial colectomy"
        if any(term in text for term in ["exploratory laparotomy", "laparotomy", "celiotomy"]):
            return "Exploratory laparotomy"
        if "appendectomy" in text or "appendix" in text:
            return "Laparoscopic appendectomy" if "laparoscopic" in text else "Appendectomy"
        if "cholecystectomy" in text or "gallbladder" in text:
            return "Laparoscopic cholecystectomy with cholangiography" if "cholangiogram" in text or "cholangiography" in text else "Laparoscopic cholecystectomy"
        if "inguinal hernia" in text:
            return "Open inguinal hernia repair"
        if any(term in text for term in ["revision total knee", "knee arthroplasty revision", "revision knee arthroplasty"]):
            return "Revision total knee arthroplasty"
        if any(term in text for term in ["revision total hip", "hip arthroplasty revision", "revision hip arthroplasty"]):
            return "Revision total hip arthroplasty"
        if any(term in text for term in ["vascular bypass", "femoral popliteal bypass", "fem-pop bypass", "lower extremity bypass"]):
            return "Lower extremity vascular bypass"
        return None

    @staticmethod
    def _ai_cpt_mapping_confidence(procedure: AIProcedure, mapped_name: str) -> float:
        raw_name = procedure.name.strip().lower()
        exact = raw_name == mapped_name.lower()
        if exact and procedure.confidence >= 0.85:
            return min(procedure.confidence, 0.88)
        if mapped_name in {"Small bowel resection", "Bowel resection with anastomosis", "Partial colectomy"}:
            return min(max(procedure.confidence, 0.72), 0.78)
        if mapped_name == "Exploratory laparotomy":
            return min(max(procedure.confidence, 0.68), 0.76)
        return min(max(procedure.confidence, 0.7), 0.82)

    @staticmethod
    def _default_body_site(mapped_name: str) -> str | None:
        if mapped_name in {"Exploratory laparotomy", "Small bowel resection", "Bowel resection with anastomosis", "Partial colectomy"}:
            return "abdomen"
        if mapped_name in {"Revision total knee arthroplasty", "Revision total hip arthroplasty"}:
            return "joint"
        if mapped_name == "Lower extremity vascular bypass":
            return "lower extremity arteries"
        return None

    @staticmethod
    def _default_approach(mapped_name: str) -> str | None:
        if mapped_name in {"Exploratory laparotomy", "Small bowel resection", "Bowel resection with anastomosis", "Partial colectomy"}:
            return "open"
        if mapped_name == "Laparoscopic cholecystectomy":
            return "laparoscopic"
        return None

    @staticmethod
    def _ai_supporting_texts(ai_analysis: AIStructuredOperativeNote | None) -> list[str]:
        if not ai_analysis:
            return []
        texts: list[str] = []
        for procedure in ai_analysis.detected_procedures:
            text = procedure.supporting_text or procedure.evidence
            if text and text not in texts:
                texts.append(text)
        return texts[:5]

    @staticmethod
    def _ai_cpt_rationales(ai_analysis: AIStructuredOperativeNote | None) -> list[str]:
        if not ai_analysis:
            return []
        rationales: list[str] = []
        for candidate in [*ai_analysis.likely_cpt_candidates, *ai_analysis.cpt_candidates]:
            label = candidate.code or candidate.description or candidate.procedure_name or "Uncoded CPT suggestion"
            rationale = candidate.rationale or "AI suggested this as a draft candidate for human coding review."
            item = f"{label}: {rationale}"
            if item not in rationales:
                rationales.append(item)
        return rationales[:5]

    @staticmethod
    def _validated_cpt_rationales(ai_analysis: AIStructuredOperativeNote | None, candidates: list) -> list[str]:
        if not ai_analysis:
            return []
        rationales: list[str] = []
        for candidate in candidates:
            if candidate.code == "99999":
                continue
            rationales.append(f"{candidate.code}: {candidate.rationale}")
        return rationales[:5]

    @staticmethod
    def _infer_ai_procedure_family(ai_analysis: AIStructuredOperativeNote | None) -> str | None:
        if not ai_analysis:
            return None
        text = " ".join(
            [
                ai_analysis.likely_procedure_family or "",
                ai_analysis.likely_cpt_category or "",
                ai_analysis.probable_operative_intent or "",
                ai_analysis.procedure_summary or "",
                " ".join(procedure.name for procedure in ai_analysis.detected_procedures),
                " ".join((procedure.supporting_text or procedure.evidence) for procedure in ai_analysis.detected_procedures),
            ]
        ).lower()
        if any(term in text for term in ["bowel resection", "small bowel", "colectomy", "enterotomy", "anastomosis", "laparotomy", "enterectomy"]):
            return "GI surgery"
        if any(term in text for term in ["vascular bypass", "femoral bypass", "popliteal bypass"]):
            return "vascular surgery"
        if any(term in text for term in ["revision total knee", "revision total hip", "arthroplasty revision"]):
            return "orthopedic revision"
        return ai_analysis.likely_procedure_family

    @staticmethod
    def _ai_audit_findings(ai_analysis: AIStructuredOperativeNote | None, candidates: list[CPTCodeCandidate]) -> list[AuditFinding]:
        if not ai_analysis:
            return []
        findings: list[AuditFinding] = []
        laterality_relevant = AnalysisService._laterality_relevant_for_ai(ai_analysis, candidates)
        for concern in ai_analysis.audit_concerns:
            concern_text = f"{concern.title} {concern.explanation} {concern.suggested_action}"
            if AnalysisService._is_laterality_text(concern_text) and not laterality_relevant:
                continue
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
            if AnalysisService._is_laterality_text(gap) and not laterality_relevant:
                continue
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
    def _is_laterality_text(text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in ["laterality", "left", "right", "side", "sided"])

    @staticmethod
    def _laterality_relevant_for_ai(ai_analysis: AIStructuredOperativeNote, candidates: list[CPTCodeCandidate]) -> bool:
        if any(BillingAuditor._requires_laterality(candidate) for candidate in candidates):
            return True
        text = " ".join(
            [
                ai_analysis.likely_procedure_family or "",
                ai_analysis.procedure_summary or "",
                " ".join(procedure.name for procedure in ai_analysis.detected_procedures),
                " ".join((procedure.anatomy or "") for procedure in ai_analysis.detected_procedures),
            ]
        ).lower()
        if any(term in text for term in ["bowel", "appendectomy", "appendix", "cholecystectomy", "gallbladder", "colectomy", "laparotomy", "abdominal exploration"]):
            return False
        return any(term in text for term in ["hernia", "fistula", "extremity", "breast", "kidney", "renal", "eye", "orthopedic", "unilateral"])

    @staticmethod
    def _unsupported_ai_finding() -> AuditFinding:
        return AuditFinding(
            title="Complex procedure requires coder review",
            severity="medium",
            category="unsupported_code",
            message="Complex procedure requires coder review.",
            explanation="Hybrid AI mode identified the operative intent, but the local demo CPT library does not contain enough specificity for final code selection.",
            recommendation="Confirm bowel resection extent, anastomosis details, additional procedures, and final CPT selection.",
            suggested_action="Confirm bowel resection extent, anastomosis details, additional procedures, and final CPT selection.",
            documentation_improvement="Confirm bowel resection extent, anastomosis details, additional procedures, and final CPT selection required.",
            why_it_matters="Complex GI procedures often require coder confirmation because CPT selection depends on operative extent and separately supported services.",
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
