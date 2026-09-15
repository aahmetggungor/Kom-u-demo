"""Fail-closed audio scan and release state.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Application migrations target PostgreSQL; SQLite tests use metadata")
    op.add_column(
        "audio_assets", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("audio_assets", sa.Column("scanner_revision", sa.String(160)))
    op.add_column("audio_assets", sa.Column("scan_verdict", sa.String(24)))
    op.add_column("audio_assets", sa.Column("scan_reason_code", sa.String(80)))
    op.add_column("audio_assets", sa.Column("scanned_at", sa.DateTime(timezone=True)))
    op.add_column("audio_assets", sa.Column("decided_by", sa.String(36)))
    op.add_column("audio_assets", sa.Column("decision_reason", sa.String(500)))
    op.add_column("audio_assets", sa.Column("decided_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_audio_assets_decided_by", "audio_assets", "users", ["decided_by"], ["id"]
    )
    op.drop_constraint("audio_assets_state_check", "audio_assets", type_="check")
    op.create_check_constraint(
        "ck_audio_assets_state",
        "audio_assets",
        "state IN ('QUARANTINED','SCAN_PASSED','SCAN_ERROR','RELEASED','REJECTED')",
    )
    op.create_check_constraint("ck_audio_assets_version", "audio_assets", "version >= 1")
    op.create_check_constraint(
        "ck_audio_assets_scan_verdict",
        "audio_assets",
        "scan_verdict IS NULL OR scan_verdict IN ('CLEAN','MALICIOUS','INVALID','ERROR')",
    )
    op.execute(
        "GRANT UPDATE (state, version, scanner_revision, scan_verdict, scan_reason_code, "
        "scanned_at, decided_by, decision_reason, decided_at) ON audio_assets TO komsu_app"
    )


def downgrade():
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM audio_assets WHERE state <> 'QUARANTINED'"))
        .scalar()
    )
    if count:
        raise RuntimeError("Cannot downgrade after an audio scan or human decision")
    op.execute("REVOKE UPDATE ON audio_assets FROM komsu_app")
    op.drop_constraint("ck_audio_assets_scan_verdict", "audio_assets", type_="check")
    op.drop_constraint("ck_audio_assets_version", "audio_assets", type_="check")
    op.drop_constraint("ck_audio_assets_state", "audio_assets", type_="check")
    op.create_check_constraint(
        "audio_assets_state_check",
        "audio_assets",
        "state IN ('QUARANTINED','READY','REJECTED')",
    )
    op.drop_constraint("fk_audio_assets_decided_by", "audio_assets", type_="foreignkey")
    for column in [
        "decided_at",
        "decision_reason",
        "decided_by",
        "scanned_at",
        "scan_reason_code",
        "scan_verdict",
        "scanner_revision",
        "version",
    ]:
        op.drop_column("audio_assets", column)
