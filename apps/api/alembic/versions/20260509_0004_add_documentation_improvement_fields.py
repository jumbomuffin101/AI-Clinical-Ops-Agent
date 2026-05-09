"""add documentation improvement fields

Revision ID: 20260509_0004
Revises: 20260505_0003
Create Date: 2026-05-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_0004"
down_revision: str | None = "20260505_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_findings", sa.Column("documentation_improvement", sa.Text(), nullable=True))
    op.add_column("audit_findings", sa.Column("why_it_matters", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_findings", "why_it_matters")
    op.drop_column("audit_findings", "documentation_improvement")
