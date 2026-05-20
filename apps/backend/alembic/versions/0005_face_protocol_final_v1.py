"""add face protocol final v1 fields

Revision ID: 0005_face_protocol_final_v1
Revises: 0004_protocol_v3_copy
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_face_protocol_final_v1"
down_revision = "0004_protocol_v3_copy"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns("analysis_requests")
    if "face_protocol_version" not in existing:
        op.add_column("analysis_requests", sa.Column("face_protocol_version", sa.String(length=32), nullable=True))
    if "face_protocol_image_path" not in existing:
        op.add_column("analysis_requests", sa.Column("face_protocol_image_path", sa.String(length=1000), nullable=True))
    if "protocol_copy_json" not in existing:
        op.add_column("analysis_requests", sa.Column("protocol_copy_json", sa.JSON(), nullable=True))
    if "after_photo_status" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_status", sa.String(length=64), nullable=True))
    if "after_photo_plan" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_plan", sa.JSON(), nullable=True))
    if "after_photo_variants" not in existing:
        op.add_column("analysis_requests", sa.Column("after_photo_variants", sa.JSON(), nullable=True))


def downgrade() -> None:
    existing = _columns("analysis_requests")
    for column in (
        "after_photo_variants",
        "after_photo_plan",
        "after_photo_status",
        "protocol_copy_json",
        "face_protocol_image_path",
        "face_protocol_version",
    ):
        if column in existing:
            op.drop_column("analysis_requests", column)
