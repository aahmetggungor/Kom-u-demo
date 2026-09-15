"""Bounded encrypted storage for quarantined voice attachments."""

import base64
import hmac
import math
import sys
import wave
from array import array
from io import BytesIO
from os import urandom

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .domain import audit, emit, serialize_tenant
from .models import AudioAsset, Case, Report, uid
from .security import require_role

ALLOWED_CONTENT_TYPES = frozenset({"audio/wav", "audio/x-wav"})


class AudioRejected(ValueError):
    pass


class AudioConfigurationError(ValueError):
    pass


class AudioIntegrityError(ValueError):
    pass


def derive_keys(encoded_master_key: str) -> tuple[bytes, bytes]:
    try:
        master = base64.b64decode(encoded_master_key, validate=True)
    except (ValueError, TypeError) as exc:
        raise AudioConfigurationError("Audio key is not valid base64") from exc
    if len(master) != 32:
        raise AudioConfigurationError("Audio key must decode to exactly 32 bytes")
    material = HKDF(
        algorithm=hashes.SHA256(), length=64, salt=None, info=b"komsu-audio-storage-v1"
    ).derive(master)
    return material[:32], material[32:]


def validate_pcm_wav(payload: bytes, max_bytes: int = 2_000_000) -> int:
    if not payload or len(payload) > max_bytes:
        raise AudioRejected("Audio size is outside the configured bound")
    try:
        with wave.open(BytesIO(payload), "rb") as stream:
            if (
                stream.getnchannels() != 1
                or stream.getsampwidth() != 2
                or stream.getframerate() != 16_000
                or stream.getcomptype() != "NONE"
            ):
                raise AudioRejected("WAV must be mono 16-bit PCM at 16 kHz")
            frames = stream.getnframes()
            duration_ms = round(frames * 1000 / 16_000)
            if not 200 <= duration_ms <= 30_000:
                raise AudioRejected("Audio duration is outside 0.2..30 seconds")
            raw = stream.readframes(frames)
    except (EOFError, wave.Error) as exc:
        raise AudioRejected("Malformed WAV") from exc
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise AudioRejected("Audio contains no samples")
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768.0
    peak = max(abs(sample) for sample in samples) / 32768.0
    if rms < 0.003 or peak < 0.01:
        raise AudioRejected("Audio energy is below the conservative speech gate")
    return duration_ms


def _aad(tenant_id: str, report_id: str, asset_id: str) -> bytes:
    return f"komsu-audio-v1:{tenant_id}:{report_id}:{asset_id}".encode()


def content_hmac(payload: bytes, mac_key: bytes) -> str:
    return hmac.digest(mac_key, payload, "sha256").hex()


def audio_json(asset: AudioAsset, replayed: bool = False) -> dict:
    return {
        "id": asset.id,
        "report_id": asset.report_id,
        "state": asset.state,
        "content_type": asset.content_type,
        "plaintext_bytes": asset.plaintext_bytes,
        "duration_ms": asset.duration_ms,
        "encryption_key_id": asset.encryption_key_id,
        "version": asset.version,
        "scanner_revision": asset.scanner_revision,
        "scan_verdict": asset.scan_verdict,
        "scan_reason_code": asset.scan_reason_code,
        "scanned_at": asset.scanned_at.isoformat() if asset.scanned_at else None,
        "decision_reason": asset.decision_reason,
        "decided_at": asset.decided_at.isoformat() if asset.decided_at else None,
        "created_at": asset.created_at.isoformat(),
        "replayed": replayed,
        "human_review_required": True,
    }


def store_audio(
    session,
    actor,
    report: Report,
    payload: bytes,
    encoded_master_key: str,
    key_id: str,
    max_bytes: int,
) -> tuple[AudioAsset, bool]:
    require_role(actor, "admin", "coordinator", "rescue-team")
    serialize_tenant(session, actor.tenant_id)
    duration_ms = validate_pcm_wav(payload, max_bytes)
    encryption_key, mac_key = derive_keys(encoded_master_key)
    digest = content_hmac(payload, mac_key)
    existing = session.scalar(
        select(AudioAsset).where(
            AudioAsset.tenant_id == actor.tenant_id, AudioAsset.report_id == report.id
        )
    )
    if existing:
        if not hmac.compare_digest(existing.content_hmac, digest):
            raise HTTPException(409, "Report already has a different audio attachment")
        return existing, True
    asset_id, nonce = uid(), urandom(12)
    ciphertext = AESGCM(encryption_key).encrypt(
        nonce, payload, _aad(actor.tenant_id, report.id, asset_id)
    )
    asset = AudioAsset(
        id=asset_id,
        tenant_id=actor.tenant_id,
        report_id=report.id,
        created_by=actor.user_id,
        state="QUARANTINED",
        content_type="audio/wav",
        plaintext_bytes=len(payload),
        duration_ms=duration_ms,
        encryption_key_id=key_id,
        nonce=nonce,
        ciphertext=ciphertext,
        content_hmac=digest,
    )
    session.add(asset)
    case = session.scalar(
        select(Case).where(Case.tenant_id == actor.tenant_id, Case.id == report.case_id)
    )
    audit(
        session,
        actor,
        "report.audio_quarantined",
        report.id,
        {"asset_id": asset.id, "bytes": len(payload), "duration_ms": duration_ms, "key_id": key_id},
    )
    emit(session, case, "report.audio_quarantined")
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        serialize_tenant(session, actor.tenant_id)
        existing = session.scalar(
            select(AudioAsset).where(
                AudioAsset.tenant_id == actor.tenant_id, AudioAsset.report_id == report.id
            )
        )
        if existing and hmac.compare_digest(existing.content_hmac, digest):
            return existing, True
        raise HTTPException(409, "Concurrent audio attachment conflict") from None
    return asset, False


def decrypt_audio(asset: AudioAsset, encoded_master_key: str) -> bytes:
    encryption_key, mac_key = derive_keys(encoded_master_key)
    try:
        payload = AESGCM(encryption_key).decrypt(
            bytes(asset.nonce),
            bytes(asset.ciphertext),
            _aad(asset.tenant_id, asset.report_id, asset.id),
        )
    except InvalidTag as exc:
        raise AudioIntegrityError("Audio authentication failed") from exc
    expected = content_hmac(payload, mac_key)
    if not hmac.compare_digest(expected, asset.content_hmac):
        raise AudioIntegrityError("Audio content digest failed")
    return payload
