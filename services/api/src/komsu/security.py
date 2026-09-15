import hashlib
from dataclasses import dataclass
from datetime import UTC

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import AccessToken, Membership, utcnow


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    role: str


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(engine, token: str) -> Principal:
    if not 32 <= len(token) <= 256:
        raise HTTPException(401, "Invalid or expired credentials")
    with Session(engine) as session:
        if engine.dialect.name == "postgresql":
            row = session.execute(
                text("SELECT * FROM authenticate_token(:digest)"), {"digest": token_digest(token)}
            ).first()
            if row:
                return Principal(*row)
        else:
            row = session.execute(
                select(AccessToken, Membership.role)
                .join(
                    Membership,
                    (AccessToken.tenant_id == Membership.tenant_id)
                    & (AccessToken.user_id == Membership.user_id),
                )
                .where(AccessToken.digest == token_digest(token), AccessToken.revoked.is_(False))
            ).first()
            if row and row[0].expires_at.replace(tzinfo=UTC) > utcnow():
                return Principal(row[0].tenant_id, row[0].user_id, row[1])
    raise HTTPException(401, "Invalid or expired credentials")


def require_role(principal: Principal, *roles: str):
    if principal.role not in roles:
        raise HTTPException(403, "Role does not permit this action")
