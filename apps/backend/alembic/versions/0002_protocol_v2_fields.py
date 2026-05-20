"""add protocol v2 fields

Revision ID: 0002_protocol_v2_fields
Revises: 0001_initial_schema
Create Date: 2026-05-19 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_protocol_v2_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("analysis_requests")}
    if "protocol_version" not in existing:
        op.add_column("analysis_requests", sa.Column("protocol_version", sa.String(length=32), nullable=True))
    if "protocol_slide_paths" not in existing:
        op.add_column("analysis_requests", sa.Column("protocol_slide_paths", sa.JSON(), nullable=True))
    if "legacy_protocol_image_path" not in existing:
        op.add_column("analysis_requests", sa.Column("legacy_protocol_image_path", sa.String(length=1000), nullable=True))
    op.execute("UPDATE analysis_requests SET legacy_protocol_image_path = protocol_image_path WHERE protocol_image_path IS NOT NULL")


def downgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("analysis_requests")}
    if "legacy_protocol_image_path" in existing:
        op.drop_column("analysis_requests", "legacy_protocol_image_path")
    if "protocol_slide_paths" in existing:
        op.drop_column("analysis_requests", "protocol_slide_paths")
    if "protocol_version" in existing:
        op.drop_column("analysis_requests", "protocol_version")
