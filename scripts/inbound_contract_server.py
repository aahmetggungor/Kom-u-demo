"""Local synthetic provider simulator. This is not a live messaging integration."""

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException


def create_app(*, target=None, connector=None, secret=None, transport=None):
    target = target or os.environ.get("KOMSU_CONTRACT_TARGET", "http://127.0.0.1:8000")
    connector = connector or os.environ["KOMSU_CONTRACT_CONNECTOR"]
    secret = secret or os.environ["KOMSU_CONTRACT_SECRET"]
    parsed = urlparse(target)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Contract simulator only targets a local API")
    if (
        len(secret) < 32
        or not connector
        or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in connector)
    ):
        raise ValueError("Valid connector and secret required")
    fixtures = json.loads(Path("data/inbound.synthetic.json").read_text(encoding="utf-8"))
    app = FastAPI(title="Synthetic inbound provider contract simulator")

    @app.post("/deliver/{fixture}")
    def deliver(fixture: str):
        if fixture not in fixtures:
            raise HTTPException(404, "Unknown synthetic fixture")
        body = json.dumps(fixtures[fixture], ensure_ascii=False, separators=(",", ":")).encode()
        timestamp = int(time.time())
        signature = hmac.new(
            secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        try:
            with httpx.Client(
                transport=transport, timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                result = client.post(
                    target.rstrip("/") + f"/api/v1/inbound/{connector}",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Komsu-Timestamp": str(timestamp),
                        "X-Komsu-Signature": signature,
                    },
                )
        except httpx.HTTPError:
            raise HTTPException(503, "Local API unavailable; retry same fixture") from None
        return {"synthetic": True, "upstream_status": result.status_code}

    return app
