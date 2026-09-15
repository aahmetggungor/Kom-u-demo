"""Versioned, licensed and freshness-aware GIS layer metadata.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("map_layers", sa.Column("dataset_version", sa.String(120), nullable=True))
    op.add_column("map_layers", sa.Column("license_name", sa.String(160), nullable=True))
    op.add_column("map_layers", sa.Column("content_sha256", sa.String(64), nullable=True))
    op.add_column(
        "map_layers", sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("map_layers", sa.Column("stale_after_days", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE map_layers SET dataset_version='legacy', license_name='UNREVIEWED', content_sha256=repeat('0',64), source_updated_at=updated_at, stale_after_days=30"
    )
    for column in (
        "dataset_version",
        "license_name",
        "content_sha256",
        "source_updated_at",
        "stale_after_days",
    ):
        op.alter_column("map_layers", column, nullable=False)
    op.create_check_constraint(
        "ck_map_layers_stale_days", "map_layers", "stale_after_days BETWEEN 1 AND 3650"
    )
    op.create_check_constraint(
        "ck_map_layers_sha256", "map_layers", "content_sha256 ~ '^[0-9a-f]{64}$'"
    )


def downgrade():
    op.drop_constraint("ck_map_layers_sha256", "map_layers", type_="check")
    op.drop_constraint("ck_map_layers_stale_days", "map_layers", type_="check")
    for column in (
        "stale_after_days",
        "source_updated_at",
        "content_sha256",
        "license_name",
        "dataset_version",
    ):
        op.drop_column("map_layers", column)
