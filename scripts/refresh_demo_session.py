"""Rotate only the existing local demo session; no role or tenant expansion."""

import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from komsu.db import make_engine
from komsu.models import AccessToken, utcnow
from komsu.security import token_digest
from sqlalchemy.orm import Session

load_dotenv()
path = Path(".env.session.json")
identity = json.loads(path.read_text(encoding="utf-8"))
engine = make_engine(os.environ["KOMSU_ADMIN_DATABASE_URL"])
with Session(engine) as session:
    old = session.get(AccessToken, token_digest(identity["token"]))
    if old is None or old.tenant_id != identity["tenant_id"] or old.user_id != identity["user_id"]:
        raise SystemExit("Existing session identity not found; no changes made")
    old.revoked = True
    token = secrets.token_urlsafe(32)
    session.add(
        AccessToken(
            digest=token_digest(token),
            tenant_id=old.tenant_id,
            user_id=old.user_id,
            expires_at=utcnow() + timedelta(hours=8),
        )
    )
    session.commit()
identity["token"] = token
path.write_text(json.dumps(identity, indent=2), encoding="utf-8")
print("Existing local demo session rotated for 8 hours; tenant and role unchanged")
