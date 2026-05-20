"""add after photo universal v1 fields

Revision ID: 0006_after_photo_universal_v1
Revises: 0005_face_protocol_final_v1
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_after_photo_universal_v1"
down_revision = "0005_face_protocol_final_v1"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns("analysis_requests")
    if "after_photo_variant_paths" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_variant_paths", sa.JSON(), nullable=True))
    if "after_photo_final_path" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_final_path", sa.String(length=1000), nullable=True))
    if "after_photo_quality_results" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_quality_results", sa.JSON(), nullable=True))
    if "after_photo_used_intensity" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_used_intensity", sa.String(length=32), nullable=True))
    if "after_photo_retry_count" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_retry_count", sa.Integer(), nullable=True, server_default="0"))


def downgrade() -> None:
    existing = _columns("analysis_requests")
    for column in (
        "after_photo_retry_count",
        "after_photo_used_intensity",
        "after_photo_quality_results",
        "after_photo_final_path",
        "after_photo_variant_paths",
    ):
        if column in existing:
            op.drop_column("analysis_requests", column)
