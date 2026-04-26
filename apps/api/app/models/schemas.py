from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OperativeNote(BaseModel):
    title: str = Field(default="Untitled operative note", max_length=200)
    note_text: str = Field(min_length=50)


class ExtractedProcedure(BaseModel):
    id: UUID | None = None
    name: str
    body_site: str | None = None
    approach: str | None = None
    laterality: str | None = None
    evidence: str
    confidence: float = Field(ge=0, le=1)


class CPTCodeCandidate(BaseModel):
    id: UUID | None = None
    procedure_name: str
    code: str
    description: str
    modifiers: list[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(ge=0, le=1)
    supported_by_docs: bool = True


class AuditFinding(BaseModel):
    id: UUID | None = None
    severity: str
    category: str
    message: str
    related_code: str | None = None
    recommendation: str


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
