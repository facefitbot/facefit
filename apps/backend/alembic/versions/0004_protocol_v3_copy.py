"""add protocol v3 slide copy

Revision ID: 0004_protocol_v3_copy
Revises: 0003_protocol_url_alias_fields
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_protocol_v3_copy"
down_revision = "0003_protocol_url_alias_fields"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns("analysis_requests")
    if "protocol_slide_copy" not in existing:
        op.add_column("analysis_requests", sa.Column("protocol_slide_copy", sa.JSON(), nullable=True))


def downgrade() -> None:
    existing = _columns("analysis_requests")
    if "protocol_slide_copy" in existing:
        op.drop_column("analysis_requests", "protocol_slide_copy")
