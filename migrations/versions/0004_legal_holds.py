"""Expiring tenant legal holds.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Application migrations target PostgreSQL; SQLite tests use metadata")
    op.create_table(
        "legal_holds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("expires_at > created_at"),
    )
    op.create_index("ix_legal_holds_tenant_id", "legal_holds", ["tenant_id"])
    op.execute("GRANT SELECT, INSERT, UPDATE ON legal_holds TO komsu_app")
    op.execute("ALTER TABLE legal_holds ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE legal_holds FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_boundary ON legal_holds
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))""")


def downgrade():
    count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM legal_holds WHERE released_at IS NULL AND expires_at > now()"
            )
        )
        .scalar()
    )
    if count:
        raise RuntimeError("Cannot downgrade while an active legal hold exists")
    op.execute("DROP POLICY tenant_boundary ON legal_holds")
    op.drop_index("ix_legal_holds_tenant_id", table_name="legal_holds")
    op.drop_table("legal_holds")
