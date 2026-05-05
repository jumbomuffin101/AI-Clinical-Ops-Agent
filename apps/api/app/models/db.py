import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(200))
    note_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="note", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed")
    summary: Mapped[str] = mapped_column(Text)
    report: Mapped[dict] = mapped_column(JSON)
    total_estimated_reimbursement: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    note: Mapped[Note] = relationship(back_populates="analyses")
    extracted_procedures: Mapped[list["ExtractedProcedureRecord"]] = relationship(cascade="all, delete-orphan")
    cpt_candidates: Mapped[list["CPTCandidateRecord"]] = relationship(cascade="all, delete-orphan")
    audit_findings: Mapped[list["AuditFindingRecord"]] = relationship(cascade="all, delete-orphan")
    reimbursement_estimates: Mapped[list["ReimbursementEstimateRecord"]] = relationship(cascade="all, delete-orphan")


class ExtractedProcedureRecord(Base):
    __tablename__ = "extracted_procedures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200))
    body_site: Mapped[str | None] = mapped_column(String(120))
    approach: Mapped[str | None] = mapped_column(String(120))
    laterality: Mapped[str | None] = mapped_column(String(40))
    evidence: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CPTCandidateRecord(Base):
    __tablename__ = "cpt_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    procedure_name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    modifiers: Mapped[list[str]] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    supported_by_docs: Mapped[bool] = mapped_column(default=True)
    evidence_used: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditFindingRecord(Base):
    __tablename__ = "audit_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    related_code: Mapped[str | None] = mapped_column(String(20))
    recommendation: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    evidence_used: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReimbursementEstimateRecord(Base):
    __tablename__ = "reimbursement_estimates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(20))
    allowed_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
