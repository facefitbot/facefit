"""add optional side-profile photo path

Revision ID: 0012_profile_photo_path
Revises: 0011_remove_after_photo
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_profile_photo_path"
down_revision = "0011_remove_after_photo"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _drop_column(table_name: str, column_name: str) -> None:
    if column_name in _columns(table_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    _add_column(
        "analysis_requests",
        sa.Column("profile_photo_path", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    _drop_column("analysis_requests", "profile_photo_path")
