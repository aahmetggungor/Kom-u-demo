"""Adapters map validated upstream envelopes to a common immutable report contract."""

import hashlib
import hmac
from datetime import datetime
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from .schemas import Coordinates, ReportIn, Source, StrictModel


class UpstreamMessage(StrictModel):
    delivery_id: str = Field(min_length=1, max_length=160)
    external_id: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=8000)
    received_at: datetime
    language: Literal["tr", "el", "en", "und"] = "und"
    original_report_id: UUID | None = None
    address_raw: str | None = Field(default=None, max_length=1000)
    location: Coordinates | None = None
    audio_wav_base64: str | None = Field(default=None, max_length=6_700_000)


class InboundAdapter(Protocol):
    def convert(self, message: UpstreamMessage) -> ReportIn: ...


class ChannelAdapter:
    def __init__(self, connector_id: str, source: Source):
        if not connector_id or len(connector_id) > 120:
            raise ValueError("registered connector ID required")
        self.connector_id, self.source = connector_id, source

    def convert(self, message: UpstreamMessage) -> ReportIn:
        identity = message.original_report_id or uuid5(
            NAMESPACE_URL, f"komsu:{self.connector_id}:{message.external_id}"
        )
        return ReportIn(
            client_id=identity,
            text=message.text,
            source=self.source,
            language=message.language,
            occurred_at=message.received_at,
            address_raw=message.address_raw,
            location=message.location,
        )


def verify_webhook_signature(
    secret: bytes,
    body: bytes,
    timestamp: int,
    signature: str,
    now: int,
    max_body_bytes: int = 32768,
) -> bool:
    """Generic HMAC adapter helper; actual vendor signing formats belong in vendor adapters."""
    if (
        len(secret) < 32
        or len(body) > max_body_bytes
        or abs(now - timestamp) > 300
        or len(signature) != 64
    ):
        return False
    expected = hmac.new(secret, str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
