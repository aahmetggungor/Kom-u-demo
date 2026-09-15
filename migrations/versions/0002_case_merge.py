"""Human merge targets; original cases and audit remain.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Application migrations target PostgreSQL; SQLite tests use metadata")
    constraints = sa.inspect(op.get_bind()).get_check_constraints("cases")
    status = next(
        c for c in constraints if "DISPATCHED" in c["sqltext"] and "RESOLVED" in c["sqltext"]
    )
    op.drop_constraint(status["name"], "cases", type_="check")
    op.add_column("cases", sa.Column("merged_into_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_case_merge_target",
        "cases",
        "cases",
        ["tenant_id", "merged_into_id"],
        ["tenant_id", "id"],
    )
    op.create_check_constraint(
        "ck_cases_status", "cases", "status IN ('OPEN','DISPATCHED','RESOLVED','MERGED')"
    )
    op.create_check_constraint(
        "ck_cases_merge_state",
        "cases",
        "(status = 'MERGED' AND merged_into_id IS NOT NULL AND merged_into_id <> id) OR (status <> 'MERGED' AND merged_into_id IS NULL)",
    )


def downgrade():
    count = (
        op.get_bind().execute(sa.text("SELECT count(*) FROM cases WHERE status='MERGED'")).scalar()
    )
    if count:
        raise RuntimeError("Cannot downgrade while merged case history exists")
    op.drop_constraint("ck_cases_merge_state", "cases", type_="check")
    op.drop_constraint("fk_case_merge_target", "cases", type_="foreignkey")
    op.drop_constraint("ck_cases_status", "cases", type_="check")
    op.drop_column("cases", "merged_into_id")
    op.create_check_constraint(
        "cases_status_check", "cases", "status IN ('OPEN','DISPATCHED','RESOLVED')"
    )
