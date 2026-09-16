"""Tenant-bound, vendor-neutral inbound channel contract helpers."""

import base64
import binascii
import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .adapters import UpstreamMessage
from .config import ChannelConnectorSettings
from .models import InboundDelivery, Membership
from .security import Principal


class InboundRejected(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@contextmanager
def inbound_transaction(engine, tenant_id):
    """Keep report, audio, quota and receipt atomic across internal Session commits."""
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.begin()
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant, 0))"),
                {"tenant": tenant_id},
            )
        else:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield connection
        except HTTPException as exc:
            if exc.status_code == 422:
                connection.commit()  # Persist only the rejected delivery receipt.
            else:
                connection.rollback()
            raise
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()


def keyed_identifier(secret: bytes, namespace: str, value: str) -> str:
    return hmac.new(secret, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def parse_message(body: bytes) -> UpstreamMessage:
    try:
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise ValueError
        return UpstreamMessage.model_validate(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError, TypeError):
        raise InboundRejected("MALFORMED_PAYLOAD") from None


def fallback_delivery_key(secret: bytes, body: bytes) -> str:
    try:
        raw = json.loads(body)
        value = raw.get("delivery_id") if isinstance(raw, dict) else None
        if isinstance(value, str) and 1 <= len(value) <= 160:
            return keyed_identifier(secret, "delivery", value)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        pass
    return keyed_identifier(secret, "malformed-body", body_sha256(body))


def decode_phone_audio(message: UpstreamMessage, source: str, max_bytes: int) -> bytes | None:
    if message.audio_wav_base64 is None:
        return None
    if source != "phone":
        raise InboundRejected("AUDIO_NOT_ALLOWED_FOR_CHANNEL")
    try:
        value = base64.b64decode(message.audio_wav_base64, validate=True)
    except (ValueError, binascii.Error):
        raise InboundRejected("INVALID_AUDIO_ENCODING") from None
    if not value or len(value) > max_bytes:
        raise InboundRejected("INVALID_AUDIO_SIZE")
    return value


def connector_principal(engine, connector: ChannelConnectorSettings) -> Principal | None:
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            role = connection.execute(
                text("SELECT authenticate_connector_actor(:tenant, :actor)"),
                {"tenant": connector.tenant_id, "actor": connector.actor_id},
            ).scalar()
    else:
        with Session(engine) as session:
            role = session.scalar(
                select(Membership.role).where(
                    Membership.tenant_id == connector.tenant_id,
                    Membership.user_id == connector.actor_id,
                )
            )
    if role not in {"admin", "coordinator", "rescue-team"}:
        return None
    return Principal(connector.tenant_id, connector.actor_id, role)


def existing_delivery(session, connector: ChannelConnectorSettings, delivery_key: str):
    return session.scalar(
        select(InboundDelivery).where(
            InboundDelivery.tenant_id == connector.tenant_id,
            InboundDelivery.connector_id == connector.connector_id,
            InboundDelivery.delivery_key == delivery_key,
        )
    )


def quota_exceeded(session, connector: ChannelConnectorSettings) -> bool:
    count = session.scalar(
        select(func.count())
        .select_from(InboundDelivery)
        .where(
            InboundDelivery.tenant_id == connector.tenant_id,
            InboundDelivery.connector_id == connector.connector_id,
            InboundDelivery.received_at >= datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    return count >= connector.requests_per_minute


def record_delivery(
    session,
    connector: ChannelConnectorSettings,
    delivery_key: str,
    external_key: str | None,
    body_hash: str,
    state: str,
    *,
    report_id: str | None = None,
    error_code: str | None = None,
) -> InboundDelivery:
    row = InboundDelivery(
        tenant_id=connector.tenant_id,
        connector_id=connector.connector_id,
        delivery_key=delivery_key,
        external_key=external_key,
        body_sha256=body_hash,
        report_id=report_id,
        state=state,
        error_code=error_code,
    )
    session.add(row)
    try:
        session.commit()
        return row
    except IntegrityError:
        session.rollback()
        existing = existing_delivery(session, connector, delivery_key)
        if existing is None:
            raise
        return existing
