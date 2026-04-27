"""initial schema

Revision ID: 20260427_0001
Revises:
Create Date: 2026-04-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260427_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("note_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("total_estimated_reimbursement", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_code", sa.String(length=20), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cpt_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("procedure_name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("modifiers", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supported_by_docs", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "extracted_procedures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("body_site", sa.String(length=120), nullable=True),
        sa.Column("approach", sa.String(length=120), nullable=True),
        sa.Column("laterality", sa.String(length=40), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reimbursement_estimates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("allowed_amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("reimbursement_estimates")
    op.drop_table("extracted_procedures")
    op.drop_table("cpt_candidates")
    op.drop_table("audit_findings")
    op.drop_table("analyses")
    op.drop_table("notes")
