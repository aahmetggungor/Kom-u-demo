import argparse
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from .config import Settings
from .db import make_engine
from .models import AccessToken, Membership, Organization, Team, User, uid, utcnow
from .security import token_digest


def provision(engine, name: str, role: str = "admin", tenant_id: str | None = None):
    token = secrets.token_urlsafe(32)
    with Session(engine, expire_on_commit=False) as session:
        if not tenant_id:
            org = Organization(id=uid(), name=name)
            session.add(org)
            session.flush()
            tenant_id = org.id
        user = User(id=uid(), display_name=name)
        session.add(user)
        session.flush()
        session.add(Membership(tenant_id=tenant_id, user_id=user.id, role=role))
        session.flush()
        session.add(
            AccessToken(
                digest=token_digest(token),
                tenant_id=tenant_id,
                user_id=user.id,
                expires_at=utcnow() + timedelta(hours=8),
            )
        )
        session.add(Team(tenant_id=tenant_id, name="Synthetic rescue team"))
        session.commit()
    return {"tenant_id": tenant_id, "user_id": user.id, "role": role, "token": token}


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    provision_parser = sub.add_parser("provision")
    provision_parser.add_argument("--name", default="Synthetic Ege pilot")
    provision_parser.add_argument("--output", default=".env.session.json")
    worker_parser = sub.add_parser("worker")
    worker_parser.add_argument("--tenant", default=os.environ.get("KOMSU_WORKER_TENANT"))
    worker_parser.add_argument("--once", action="store_true")
    retention_parser = sub.add_parser("execute-retention")
    retention_parser.add_argument("--plan", required=True)
    retention_parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.command == "provision":
        destination = Path(args.output)
        if destination.exists():
            raise SystemExit("Credential file exists; preserving it")
        engine = make_engine(os.environ.get("KOMSU_ADMIN_DATABASE_URL", Settings().database_url))
        result = provision(engine, args.name)
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(
            f"Provisioned tenant {result['tenant_id']}; 8-hour token saved to ignored credential file"
        )
    elif args.command == "worker":
        if not args.tenant:
            raise SystemExit("Explicit --tenant or KOMSU_WORKER_TENANT is required")
        from .worker import process_one, run

        engine = make_engine(Settings().database_url)
        if args.once:
            print("processed" if process_one(engine, args.tenant) else "queue empty")
        else:
            run(engine, args.tenant)
    elif args.command == "execute-retention":
        from .retention import execute

        admin_url = os.environ.get("KOMSU_ADMIN_DATABASE_URL")
        if not admin_url:
            raise SystemExit("KOMSU_ADMIN_DATABASE_URL is required")
        counts = execute(make_engine(admin_url), args.plan, args.confirm)
        print(json.dumps({"plan_id": args.plan, "status": "EXECUTED", "counts": counts}))


if __name__ == "__main__":
    main()
