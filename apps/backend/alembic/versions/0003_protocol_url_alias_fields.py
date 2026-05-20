"""add protocol url alias fields

Revision ID: 0003_protocol_url_alias_fields
Revises: 0002_protocol_v2_fields
Create Date: 2026-05-19 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_protocol_url_alias_fields"
down_revision = "0002_protocol_v2_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("analysis_requests")}
    if "protocol_image_url" not in existing:
        op.add_column("analysis_requests", sa.Column("protocol_image_url", sa.String(length=1000), nullable=True))
    if "legacy_protocol_image_url" not in existing:
        op.add_column("analysis_requests", sa.Column("legacy_protocol_image_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("analysis_requests")}
    if "legacy_protocol_image_url" in existing:
        op.drop_column("analysis_requests", "legacy_protocol_image_url")
    if "protocol_image_url" in existing:
        op.drop_column("analysis_requests", "protocol_image_url")
