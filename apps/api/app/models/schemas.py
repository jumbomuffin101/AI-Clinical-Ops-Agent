from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

MAX_NOTE_LENGTH = 20000


class OperativeNote(BaseModel):
    title: str = Field(default="Untitled operative note", min_length=1, max_length=200)
    note_text: str = Field(min_length=50, max_length=MAX_NOTE_LENGTH)

    @field_validator("title", "note_text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only.")
        return stripped


class ExtractedProcedure(BaseModel):
    id: UUID | None = None
    name: str
    body_site: str | None = None
    approach: str | None = None
    laterality: str | None = None
    evidence: str
    confidence: float = Field(ge=0, le=1)


class EvidenceSnippet(BaseModel):
    source: str
    snippet: str
    score: int | None = None


class StructuredOperativeNote(BaseModel):
    raw_text: str
    parsed_sections: dict[str, str] = Field(default_factory=dict)
    detected_procedure_name: str | None = None
    detected_anatomy: str | None = None
    detected_laterality: str | None = None
    missing_sections: list[str] = Field(default_factory=list)
    parsing_confidence: float = Field(default=0, ge=0, le=1)
    structure_quality: str = "Poorly structured note"


class AIProcedure(BaseModel):
    name: str
    procedure_family: str | None = None
    anatomy: str | None = None
    laterality: str | None = None
    supporting_text: str = ""
    evidence: str = ""
    confidence: float = Field(ge=0, le=1)


class AICPTCandidate(BaseModel):
    procedure_name: str = ""
    code: str | None = None
    description: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""
    needs_human_review: bool = True


class AIAuditConcern(BaseModel):
    title: str
    severity: str = "medium"
    explanation: str = ""
    suggested_action: str = ""


class AIStructuredOperativeNote(BaseModel):
    parsed_note_sections: dict[str, str] = Field(default_factory=dict)
    detected_procedures: list[AIProcedure] = Field(default_factory=list)
    anatomy: str | None = None
    laterality: str | None = None
    likely_cpt_candidates: list[AICPTCandidate] = Field(default_factory=list)
    cpt_candidates: list[AICPTCandidate] = Field(default_factory=list)
    documentation_gaps: list[str] = Field(default_factory=list)
    audit_concerns: list[AIAuditConcern] = Field(default_factory=list)
    confidence_reasoning: list[str] = Field(default_factory=list)
    unsupported_or_unclear_procedure: bool = False
    procedure_summary: str | None = None
    reasoning_summary: str | None = None
    suggested_clarifications: list[str] = Field(default_factory=list)
    likely_procedure_family: str | None = None
    likely_cpt_category: str | None = None
    probable_operative_intent: str | None = None


class CPTCodeCandidate(BaseModel):
    id: UUID | None = None
    procedure_name: str
    code: str
    description: str
    modifiers: list[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(ge=0, le=1)
    supported_by_docs: bool = True
    evidence_used: list[EvidenceSnippet] = Field(default_factory=list)


class AuditFinding(BaseModel):
    id: UUID | None = None
    title: str | None = None
    severity: str
    category: str
    message: str
    explanation: str | None = None
    related_code: str | None = None
    recommendation: str
    suggested_action: str | None = None
    documentation_improvement: str | None = None
    why_it_matters: str | None = None
    evidence_used: list[EvidenceSnippet] = Field(default_factory=list)


class ReimbursementEstimate(BaseModel):
    id: UUID | None = None
    code: str
    allowed_amount: float
    currency: str = "USD"
    source: str


class AnalysisReport(BaseModel):
    id: UUID
    note_id: UUID
    status: str
    analysis_mode: str | None = None
    structured_note: StructuredOperativeNote | None = None
    extracted_procedures: list[ExtractedProcedure]
    cpt_candidates: list[CPTCodeCandidate]
    audit_findings: list[AuditFinding]
    reimbursement_estimates: list[ReimbursementEstimate]
    total_estimated_reimbursement: float
    summary: str
    report: dict[str, Any]
    created_at: datetime


class AnalysisListItem(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    top_cpt_code: str | None
    total_reimbursement: float
    claim_readiness_status: str
    main_issue: str | None = None
