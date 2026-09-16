"""Bootstrap a dedicated synthetic database, then supervise unprivileged children."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from alembic import command
from alembic.config import Config
from komsu.db import make_engine, tenant_session
from komsu.domain import ingest
from komsu.models import Membership, Organization, Team, User
from komsu.schemas import ReportIn
from komsu.security import Principal
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

TENANT = str(uuid5(NAMESPACE_URL, "komsu/render/synthetic-demo"))
ACTOR = str(uuid5(NAMESPACE_URL, "komsu/render/synthetic-coordinator"))


def bootstrap():
    admin_url = make_url(os.environ["KOMSU_ADMIN_DATABASE_URL"]).set(
        drivername="postgresql+psycopg"
    )
    app_password = os.environ["KOMSU_APP_PASSWORD"]
    if len(app_password) < 24 or len(os.environ["KOMSU_DEMO_PASSWORD"]) < 24:
        raise RuntimeError("Generated credentials must contain at least 24 characters")
    admin = make_engine(admin_url.render_as_string(hide_password=False))
    with admin.begin() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname='komsu_app'")
        ).scalar()
        if not exists:
            cursor = connection.connection.driver_connection.cursor()
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE komsu_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}"
                ).format(sql.Literal(app_password))
            )
        unsafe = connection.execute(
            text(
                "SELECT rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname='komsu_app'"
            )
        ).scalar()
        if unsafe:
            raise RuntimeError("Unsafe application role; refusing to launch")
    os.environ["KOMSU_ADMIN_DATABASE_URL"] = admin_url.render_as_string(hide_password=False)
    command.upgrade(Config("alembic.ini"), "head")
    with Session(admin) as session:
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": TENANT}
        )
        if not session.get(Organization, TENANT):
            session.add(Organization(id=TENANT, name="SYNTHETIC DEMO · NOT FOR EMERGENCY USE"))
            session.flush()
            session.add(User(id=ACTOR, display_name="Synthetic demo coordinator"))
            session.flush()
            session.add(Membership(tenant_id=TENANT, user_id=ACTOR, role="coordinator"))
            session.add(Team(tenant_id=TENANT, name="Synthetic rescue team"))
            session.commit()
    # Only this coordinator may receive sessions; the runtime cannot insert arbitrary tokens.
    with admin.begin() as connection:
        connection.execute(
            text(f"""
        CREATE OR REPLACE FUNCTION issue_demo_session(p_digest text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        BEGIN
          IF p_digest !~ '^[0-9a-f]{{64}}$' THEN RAISE EXCEPTION 'Invalid digest'; END IF;
          DELETE FROM public.access_tokens WHERE tenant_id='{TENANT}' AND expires_at < now();
          INSERT INTO public.access_tokens(digest,tenant_id,user_id,expires_at,revoked)
          VALUES(p_digest,'{TENANT}','{ACTOR}',now()+interval '8 hours',false);
        END $$;
        REVOKE ALL ON FUNCTION issue_demo_session(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION issue_demo_session(text) TO komsu_app;
        """)
        )
    runtime_url = admin_url.set(username="komsu_app", password=app_password)
    runtime = make_engine(runtime_url.render_as_string(hide_password=False))
    principal = Principal(TENANT, ACTOR, "coordinator")
    rows = Path("data/render.synthetic.jsonl").read_text(encoding="utf-8").splitlines()
    for line in rows:
        row = json.loads(line)
        row.pop("gold", None)
        with tenant_session(runtime, TENANT) as session:
            ingest(session, principal, ReportIn.model_validate(row), 10000)
    runtime.dispose()
    admin.dispose()
    return runtime_url.render_as_string(hide_password=False)


def child_environment(runtime_url):
    result = {
        key: value
        for key, value in os.environ.items()
        if key not in {"KOMSU_ADMIN_DATABASE_URL", "KOMSU_APP_PASSWORD"}
    }
    result["KOMSU_DATABASE_URL"] = runtime_url
    result["KOMSU_WORKER_TENANT"] = TENANT
    result["KOMSU_ALLOWED_ORIGINS"] = json.dumps([os.environ["RENDER_EXTERNAL_URL"]])
    result["KOMSU_ENVIRONMENT"] = "development"
    return result


def main():
    try:
        environment = child_environment(bootstrap())
    except Exception:
        # SQLAlchemy errors may contain connection secrets: never print the exception.
        print(
            "Demo bootstrap failed: verify database role/extension permissions and credentials",
            flush=True,
        )
        return 1
    children = []

    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    children.append(
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "komsu.render_demo:create_demo_app",
                "--factory",
                "--host",
                "0.0.0.0",
                "--port",
                os.environ.get("PORT", "10000"),
                "--no-access-log",
            ],
            env=environment,
        )
    )
    worker_environment = dict(environment)
    worker_environment.pop("KOMSU_DEMO_PASSWORD", None)
    children.append(subprocess.Popen(["komsu", "worker"], env=worker_environment))
    while all(child.poll() is None for child in children):
        time.sleep(1)
    stop()
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
    return 1


if __name__ == "__main__":
    sys.exit(main())
