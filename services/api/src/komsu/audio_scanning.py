"""Fail-closed scanning and human release for encrypted audio attachments.

The scanner protocol is intentionally local to a privileged worker boundary. The
API never accepts a caller-supplied verdict and never returns audio bytes.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select

from .audio_storage import AudioIntegrityError, AudioRejected, decrypt_audio, validate_pcm_wav
from .domain import audit, emit, serialize_tenant
from .models import AudioAsset, AudioTranscript, Case, Report, utcnow
from .schemas import AudioDecisionIn
from .security import Principal, require_role

SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,79}$")


class ScanVerdict(StrEnum):
    CLEAN = "CLEAN"
    MALICIOUS = "MALICIOUS"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ScanOutcome:
    verdict: ScanVerdict
    reason_code: str


class AudioScanner(Protocol):
    """Implemented by an isolated scanner; plaintext must remain process-local."""

    def scan(self, payload: bytes) -> ScanOutcome: ...


def _asset_context(session, tenant_id: str, *, asset_id: str | None = None, report_id=None):
    query = select(AudioAsset).where(AudioAsset.tenant_id == tenant_id)
    if asset_id is not None:
        query = query.where(AudioAsset.id == asset_id)
    if report_id is not None:
        query = query.where(AudioAsset.report_id == report_id)
    asset = session.scalar(query)
    if asset is None:
        raise HTTPException(404, "Audio attachment not found")
    report = session.scalar(
        select(Report).where(Report.tenant_id == tenant_id, Report.id == asset.report_id)
    )
    case = session.scalar(
        select(Case).where(Case.tenant_id == tenant_id, Case.id == report.case_id)
    )
    return asset, case


def _scanner_actor(tenant_id: str, scanner_revision: str) -> Principal:
    return Principal(tenant_id, f"system:audio-scanner:{scanner_revision}"[:80], "admin")


def scan_audio_asset(
    session,
    tenant_id: str,
    asset_id: str,
    scanner: AudioScanner,
    scanner_revision: str,
    encoded_master_key: str,
) -> tuple[AudioAsset, bool]:
    """Scan one asset synchronously inside a dedicated worker transaction.

    Scanner failures become a persisted SCAN_ERROR. Nothing is released here.
    """
    if not scanner_revision.strip() or len(scanner_revision) > 160:
        raise ValueError("scanner_revision must be 1..160 characters")
    serialize_tenant(session, tenant_id)
    asset, case = _asset_context(session, tenant_id, asset_id=asset_id)
    if asset.scanned_at and asset.scanner_revision == scanner_revision:
        return asset, True
    if asset.state not in {"QUARANTINED", "SCAN_ERROR"}:
        raise HTTPException(409, f"Audio in {asset.state} cannot be scanned")

    verdict = "ERROR"
    reason_code = "SCANNER_FAILURE"
    try:
        payload = decrypt_audio(asset, encoded_master_key)
        validate_pcm_wav(payload, max_bytes=asset.plaintext_bytes)
        outcome = scanner.scan(payload)
        if not isinstance(outcome, ScanOutcome) or not SAFE_CODE.fullmatch(outcome.reason_code):
            reason_code = "SCANNER_PROTOCOL_ERROR"
        else:
            verdict = outcome.verdict.value
            reason_code = outcome.reason_code
    except (AudioIntegrityError, AudioRejected):
        reason_code = "INTEGRITY_OR_FORMAT_ERROR"
    except Exception:  # Scanner implementations are untrusted; fail closed and persist only a code.
        reason_code = "SCANNER_FAILURE"

    asset.scanner_revision = scanner_revision
    asset.scan_verdict = verdict
    asset.scan_reason_code = reason_code
    asset.scanned_at = utcnow()
    asset.version += 1
    if verdict == ScanVerdict.CLEAN:
        asset.state = "SCAN_PASSED"
    elif verdict in {ScanVerdict.MALICIOUS, ScanVerdict.INVALID}:
        asset.state = "REJECTED"
    else:
        asset.state = "SCAN_ERROR"

    actor = _scanner_actor(tenant_id, scanner_revision)
    audit(
        session,
        actor,
        "report.audio_scanned",
        asset.id,
        {
            "scanner_revision": scanner_revision,
            "verdict": asset.scan_verdict,
            "reason_code": asset.scan_reason_code,
            "version": asset.version,
        },
    )
    emit(session, case, f"report.audio_{asset.state.lower()}")
    session.commit()
    return asset, False


def decide_audio(
    session, actor: Principal, report_id: str, request: AudioDecisionIn
) -> tuple[AudioAsset, bool]:
    """Apply a versioned human release/reject decision with separation of duty."""
    require_role(actor, "admin", "coordinator")
    serialize_tenant(session, actor.tenant_id)
    asset, case = _asset_context(session, actor.tenant_id, report_id=report_id)
    target_state = "RELEASED" if request.decision == "RELEASE" else "REJECTED"
    if (
        asset.state == target_state
        and asset.decided_by == actor.user_id
        and asset.decision_reason == request.reason
    ):
        return asset, True
    if asset.version != request.expected_version:
        raise HTTPException(409, "Audio version changed; reload before deciding")
    if request.decision == "RELEASE":
        if asset.state != "SCAN_PASSED" or asset.scan_verdict != "CLEAN":
            raise HTTPException(409, "Only clean scan-passed audio can be released")
        if asset.created_by == actor.user_id:
            raise HTTPException(409, "Audio release requires a different authorized user")
    elif asset.state not in {"QUARANTINED", "SCAN_PASSED", "SCAN_ERROR"}:
        raise HTTPException(409, f"Audio in {asset.state} cannot be rejected")

    asset.state = target_state
    asset.decided_by = actor.user_id
    asset.decision_reason = request.reason
    asset.decided_at = utcnow()
    asset.version += 1
    if target_state == "RELEASED":
        session.add(
            AudioTranscript(
                tenant_id=actor.tenant_id,
                audio_asset_id=asset.id,
                report_id=asset.report_id,
                state="QUEUED",
            )
        )
    audit(
        session,
        actor,
        f"report.audio_{target_state.lower()}",
        asset.id,
        {"reason": request.reason, "version": asset.version},
    )
    emit(session, case, f"report.audio_{target_state.lower()}")
    session.commit()
    return asset, False
