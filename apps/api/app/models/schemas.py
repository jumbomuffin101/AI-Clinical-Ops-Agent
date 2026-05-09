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
