"""Encrypted quarantined audio attachments.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Application migrations target PostgreSQL; SQLite tests use metadata")
    op.create_table(
        "audio_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("report_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("plaintext_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("encryption_key_id", sa.String(80), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("content_hmac", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "report_id"], ["reports.tenant_id", "reports.id"]),
        sa.UniqueConstraint("tenant_id", "report_id"),
        sa.CheckConstraint("state IN ('QUARANTINED','READY','REJECTED')"),
        sa.CheckConstraint("plaintext_bytes BETWEEN 1 AND 2000000"),
        sa.CheckConstraint("duration_ms BETWEEN 200 AND 30000"),
    )
    op.create_index("ix_audio_assets_tenant_id", "audio_assets", ["tenant_id"])
    op.execute("GRANT SELECT, INSERT ON audio_assets TO komsu_app")
    op.execute("ALTER TABLE audio_assets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audio_assets FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_boundary ON audio_assets
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))""")


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM audio_assets")).scalar()
    if count:
        raise RuntimeError("Cannot downgrade while encrypted audio assets exist")
    op.execute("DROP POLICY tenant_boundary ON audio_assets")
    op.drop_index("ix_audio_assets_tenant_id", table_name="audio_assets")
    op.drop_table("audio_assets")
