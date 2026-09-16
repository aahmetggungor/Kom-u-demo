"""Add tenant-scoped inbound delivery receipts and connector actor lookup.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inbound_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("connector_id", sa.String(64), nullable=False),
        sa.Column("delivery_key", sa.String(64), nullable=False),
        sa.Column("external_key", sa.String(64)),
        sa.Column("body_sha256", sa.String(64), nullable=False),
        sa.Column("report_id", sa.String(36)),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "connector_id", "delivery_key"),
        sa.CheckConstraint("state IN ('ACCEPTED','DEAD_LETTER')"),
        sa.CheckConstraint("(state = 'ACCEPTED') = (report_id IS NOT NULL)"),
    )
    op.create_index("ix_inbound_deliveries_tenant_id", "inbound_deliveries", ["tenant_id"])
    op.create_index(
        "ix_inbound_deliveries_quota",
        "inbound_deliveries",
        ["tenant_id", "connector_id", "received_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("GRANT SELECT, INSERT, DELETE ON inbound_deliveries TO komsu_app")
        op.execute("ALTER TABLE inbound_deliveries ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE inbound_deliveries FORCE ROW LEVEL SECURITY")
        op.execute("""CREATE POLICY tenant_boundary ON inbound_deliveries
            USING (tenant_id = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true))""")
        op.execute("""CREATE FUNCTION authenticate_connector_actor(p_tenant text, p_actor text)
            RETURNS text LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
                SELECT role FROM public.memberships
                WHERE tenant_id = p_tenant AND user_id = p_actor
                  AND role IN ('admin','coordinator','rescue-team')
            $$""")
        op.execute("REVOKE ALL ON FUNCTION authenticate_connector_actor(text,text) FROM PUBLIC")
        op.execute("GRANT EXECUTE ON FUNCTION authenticate_connector_actor(text,text) TO komsu_app")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION authenticate_connector_actor(text,text)")
        op.execute("DROP POLICY tenant_boundary ON inbound_deliveries")
    op.drop_index("ix_inbound_deliveries_quota", table_name="inbound_deliveries")
    op.drop_index("ix_inbound_deliveries_tenant_id", table_name="inbound_deliveries")
    op.drop_table("inbound_deliveries")
