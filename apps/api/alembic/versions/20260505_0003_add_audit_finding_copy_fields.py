"""add audit finding copy fields

Revision ID: 20260505_0003
Revises: 20260427_0002
Create Date: 2026-05-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260505_0003"
down_revision: Union[str, None] = "20260427_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_findings", sa.Column("title", sa.String(length=120), nullable=True))
    op.add_column("audit_findings", sa.Column("explanation", sa.Text(), nullable=True))
    op.add_column("audit_findings", sa.Column("suggested_action", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_findings", "suggested_action")
    op.drop_column("audit_findings", "explanation")
    op.drop_column("audit_findings", "title")
