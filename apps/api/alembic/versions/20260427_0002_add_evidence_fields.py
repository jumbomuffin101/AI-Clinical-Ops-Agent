"""add evidence fields

Revision ID: 20260427_0002
Revises: 20260427_0001
Create Date: 2026-04-27 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260427_0002"
down_revision: Union[str, None] = "20260427_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cpt_candidates", sa.Column("evidence_used", sa.JSON(), nullable=True))
    op.add_column("audit_findings", sa.Column("evidence_used", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_findings", "evidence_used")
    op.drop_column("cpt_candidates", "evidence_used")
