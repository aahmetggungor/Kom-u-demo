"""Durable released-audio transcription jobs and human corrections.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Application migrations target PostgreSQL; SQLite tests use metadata")
    op.create_table(
        "audio_transcripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column(
            "audio_asset_id",
            sa.String(36),
            sa.ForeignKey("audio_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("claim_id", sa.String(36)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_text", sa.Text()),
        sa.Column("language", sa.String(8)),
        sa.Column("model_revision", sa.String(200)),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("corrected_text", sa.Text()),
        sa.Column("corrected_language", sa.String(8)),
        sa.Column("corrected_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("correction_reason", sa.String(500)),
        sa.Column("corrected_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "report_id"], ["reports.tenant_id", "reports.id"]),
        sa.UniqueConstraint("tenant_id", "audio_asset_id"),
        sa.CheckConstraint("state IN ('QUEUED','RUNNING','DONE','FAILED')"),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1"),
    )
    op.create_index("ix_audio_transcripts_tenant_id", "audio_transcripts", ["tenant_id"])
    op.execute("GRANT SELECT, INSERT, UPDATE ON audio_transcripts TO komsu_app")
    op.execute("ALTER TABLE audio_transcripts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audio_transcripts FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_boundary ON audio_transcripts
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))""")
    # A rolling upgrade may already contain audio released under revision 0006.
    # Queue those assets once so the worker does not silently skip them.
    op.execute("""
        INSERT INTO audio_transcripts (
            id, tenant_id, audio_asset_id, report_id, state, attempts,
            available_at, warnings, version, created_at, updated_at
        )
        SELECT
            substr(md5(a.tenant_id || ':' || a.id), 1, 8) || '-' ||
            substr(md5(a.tenant_id || ':' || a.id), 9, 4) || '-' ||
            substr(md5(a.tenant_id || ':' || a.id), 13, 4) || '-' ||
            substr(md5(a.tenant_id || ':' || a.id), 17, 4) || '-' ||
            substr(md5(a.tenant_id || ':' || a.id), 21, 12),
            a.tenant_id, a.id, a.report_id, 'QUEUED', 0,
            now(), '[]'::json, 1, now(), now()
        FROM audio_assets a
        WHERE a.state = 'RELEASED'
        ON CONFLICT (tenant_id, audio_asset_id) DO NOTHING
    """)


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM audio_transcripts")).scalar()
    if count:
        raise RuntimeError("Cannot downgrade while audio transcript history exists")
    op.execute("DROP POLICY tenant_boundary ON audio_transcripts")
    op.drop_index("ix_audio_transcripts_tenant_id", table_name="audio_transcripts")
    op.drop_table("audio_transcripts")
