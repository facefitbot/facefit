"""add personal insight json

Revision ID: 0007_personal_insight_json
Revises: 0006_after_photo_universal_v1
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_personal_insight_json"
down_revision = "0006_after_photo_universal_v1"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns("analysis_requests")
    if "personal_insight_json" not in existing:
        op.add_column("analysis_requests", sa.Column("personal_insight_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    existing = _columns("analysis_requests")
    if "personal_insight_json" in existing:
        op.drop_column("analysis_requests", "personal_insight_json")
