"""Reviewed retention plans and correct spatial deletion.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Application migrations target PostgreSQL; SQLite tests use metadata")
    op.create_table(
        "retention_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("result_counts", sa.JSON(), nullable=False),
        sa.CheckConstraint("status IN ('SCHEDULED','APPROVED','EXECUTED','CANCELLED')"),
        sa.CheckConstraint("execute_after >= cutoff_at"),
        sa.CheckConstraint("approved_by IS NULL OR approved_by <> requested_by"),
    )
    op.create_index("ix_retention_plans_tenant_id", "retention_plans", ["tenant_id"])
    op.execute("GRANT SELECT, INSERT, UPDATE ON retention_plans TO komsu_app")
    op.execute("GRANT DELETE ON case_locations TO komsu_app")
    op.execute("ALTER TABLE retention_plans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE retention_plans FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_boundary ON retention_plans
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))""")
    # Clearing coordinates must also clear the geography index row.
    op.execute("""CREATE OR REPLACE FUNCTION sync_case_location() RETURNS trigger
        LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
        BEGIN
          IF NEW.lat IS NOT NULL AND NEW.lon IS NOT NULL THEN
            INSERT INTO case_locations(tenant_id, case_id, position, confidence, provenance)
              VALUES(NEW.tenant_id, NEW.id,
                ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat),4326)::geography,
                CASE WHEN NEW.location_status = 'CONFIRMED' THEN 1.0 ELSE 0.0 END,
                NEW.location_status)
              ON CONFLICT(tenant_id, case_id) DO UPDATE SET
                position=EXCLUDED.position, confidence=EXCLUDED.confidence,
                provenance=EXCLUDED.provenance;
          ELSE
            DELETE FROM case_locations WHERE tenant_id=NEW.tenant_id AND case_id=NEW.id;
          END IF;
          RETURN NEW;
        END $$""")


def downgrade():
    count = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM retention_plans WHERE status IN ('APPROVED','EXECUTED')")
        )
        .scalar()
    )
    if count:
        raise RuntimeError("Cannot downgrade approved or executed retention history")
    op.execute("DROP POLICY tenant_boundary ON retention_plans")
    op.execute("REVOKE DELETE ON case_locations FROM komsu_app")
    op.drop_index("ix_retention_plans_tenant_id", table_name="retention_plans")
    op.drop_table("retention_plans")
    op.execute("""CREATE OR REPLACE FUNCTION sync_case_location() RETURNS trigger
        LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
        BEGIN
          IF NEW.lat IS NOT NULL AND NEW.lon IS NOT NULL THEN
            INSERT INTO case_locations(tenant_id, case_id, position, confidence, provenance)
              VALUES(NEW.tenant_id, NEW.id,
                ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat),4326)::geography,
                CASE WHEN NEW.location_status = 'CONFIRMED' THEN 1.0 ELSE 0.0 END,
                NEW.location_status)
              ON CONFLICT(tenant_id, case_id) DO UPDATE SET
                position=EXCLUDED.position, confidence=EXCLUDED.confidence,
                provenance=EXCLUDED.provenance;
          END IF;
          RETURN NEW;
        END $$""")
