"""Password entry for an isolated synthetic demo; never enable on operational data."""

import hmac
import os
import secrets
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

from .app import create_app
from .security import token_digest


class DemoLogin(BaseModel):
    password: str = Field(min_length=1, max_length=256, repr=False)


def validate_demo_password(password: str):
    # Presentation-only access, explicitly allowing a user-selected short demo PIN.
    # Database credentials and operational session authentication remain separate.
    if not 4 <= len(password) <= 256:
        raise RuntimeError("Demo password must contain 4 to 256 characters")


def create_demo_app(settings=None, engine=None, *, password=None, static_dir=None):
    password = os.environ["KOMSU_DEMO_PASSWORD"] if password is None else password
    validate_demo_password(password)
    app = create_app(settings, engine)
    attempts = deque()
    lock = threading.Lock()

    @app.post("/api/v1/demo/session")
    def demo_session(body: DemoLogin):
        # Global bound also prevents botnets from bypassing a per-IP login limit.
        with lock:
            now = time.monotonic()
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if len(attempts) >= 10:
                raise HTTPException(429, "Try again in one minute")
            attempts.append(now)
        if not hmac.compare_digest(body.password.encode(), password.encode()):
            raise HTTPException(401, "Invalid demo password")
        token = secrets.token_urlsafe(32)
        with app.state.engine.begin() as connection:
            connection.execute(
                text("SELECT issue_demo_session(:digest)"), {"digest": token_digest(token)}
            )
        return {"token": token, "expires_in": 28800}

    directory = Path(static_dir or os.environ.get("KOMSU_WEB_DIST", "/app/web"))
    app.mount("/", StaticFiles(directory=directory, html=True), name="demo-web")
    return app
