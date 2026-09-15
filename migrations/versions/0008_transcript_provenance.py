"""Add immutable source provenance and a transcription claim index.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Application migrations target PostgreSQL; SQLite tests use metadata")
    op.add_column("audio_transcripts", sa.Column("source_audio_hmac", sa.String(64)))
    op.create_index(
        "ix_audio_transcripts_claim",
        "audio_transcripts",
        ["tenant_id", "state", "available_at"],
    )
    op.execute("""
        UPDATE audio_transcripts AS transcript
        SET source_audio_hmac = asset.content_hmac
        FROM audio_assets AS asset
        WHERE transcript.audio_asset_id = asset.id
          AND transcript.tenant_id = asset.tenant_id
          AND transcript.state = 'DONE'
          AND transcript.source_audio_hmac IS NULL
    """)


def downgrade():
    op.drop_index("ix_audio_transcripts_claim", table_name="audio_transcripts")
    op.drop_column("audio_transcripts", "source_audio_hmac")
