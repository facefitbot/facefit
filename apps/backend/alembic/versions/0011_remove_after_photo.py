"""remove after photo production fields

Revision ID: 0011_remove_after_photo
Revises: 0010_admin_operations
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_remove_after_photo"
down_revision = "0010_admin_operations"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _drop_column(table_name: str, column_name: str) -> None:
    if column_name in _columns(table_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    for column_name in [
        "after_photo_retry_count",
        "after_photo_used_intensity",
        "after_photo_quality_results",
        "after_photo_final_path",
        "after_photo_variant_paths",
        "after_photo_variants",
        "after_photo_plan",
        "after_photo_status",
        "after_photo_path",
    ]:
        _drop_column("analysis_requests", column_name)
    _drop_column("bot_settings", "after_photo_enabled")


def downgrade() -> None:
    columns = _columns("analysis_requests")
    if "after_photo_path" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_path", sa.String(length=1000), nullable=True))
    if "after_photo_status" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_status", sa.String(length=64), nullable=True))
    if "after_photo_plan" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_plan", sa.JSON(), nullable=True))
    if "after_photo_variants" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_variants", sa.JSON(), nullable=True))
    if "after_photo_variant_paths" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_variant_paths", sa.JSON(), nullable=True))
    if "after_photo_final_path" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_final_path", sa.String(length=1000), nullable=True))
    if "after_photo_quality_results" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_quality_results", sa.JSON(), nullable=True))
    if "after_photo_used_intensity" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_used_intensity", sa.String(length=32), nullable=True))
    if "after_photo_retry_count" not in columns:
        op.add_column("analysis_requests", sa.Column("after_photo_retry_count", sa.Integer(), nullable=True, server_default="0"))
    if "after_photo_enabled" not in _columns("bot_settings"):
        op.add_column("bot_settings", sa.Column("after_photo_enabled", sa.Boolean(), nullable=True, server_default=sa.text("false")))
