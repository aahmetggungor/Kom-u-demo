"""Durable, lease-fenced transcription of explicitly released audio."""

import json
import logging
import time
from datetime import timedelta
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update

from .ai import TranscriptionOutput
from .audio_storage import AudioIntegrityError, decrypt_audio
from .db import tenant_session
from .domain import audit, emit, serialize_tenant
from .models import AudioAsset, AudioTranscript, Case, Report, uid, utcnow
from .schemas import TranscriptReviewIn
from .security import Principal, require_role

logger = logging.getLogger("komsu.transcription_worker")
LANGUAGES = frozenset({"tr", "el", "en", "und"})


class ByteTranscriber(Protocol):
    def transcribe_bytes(
        self, approved_audio: bytes, language_hint: str | None = None
    ) -> TranscriptionOutput: ...


class ModelUnavailableError(RuntimeError):
    """Fixed, content-free signal that no approved local model is configured."""


class UnavailableTranscriber:
    def transcribe_bytes(self, approved_audio: bytes, language_hint: str | None = None):
        raise ModelUnavailableError


def transcript_json(row: AudioTranscript | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "state": row.state,
        "attempts": row.attempts,
        "original_text": row.original_text,
        "language": row.language,
        "model_revision": row.model_revision,
        "duration_seconds": row.duration_seconds,
        "confidence": row.confidence,
        "warnings": row.warnings,
        "error_code": row.error_code,
        "corrected_text": row.corrected_text,
        "corrected_language": row.corrected_language,
        "correction_reason": row.correction_reason,
        "corrected_at": row.corrected_at.isoformat() if row.corrected_at else None,
        "version": row.version,
        "human_review_required": True,
    }


def _validate_output(value) -> TranscriptionOutput:
    if not isinstance(value, TranscriptionOutput):
        raise ValueError("Invalid transcriber response")
    if not value.text.strip() or len(value.text) > 8000:
        raise ValueError("Transcript text is outside bounds")
    if value.language not in LANGUAGES:
        raise ValueError("Transcript language is unsupported")
    if not value.model_revision or len(value.model_revision) > 200:
        raise ValueError("Transcript model revision is outside bounds")
    if not 0.2 <= value.duration_seconds <= 30:
        raise ValueError("Transcript duration is outside bounds")
    if len(value.warnings) > 20 or any(len(item) > 80 for item in value.warnings):
        raise ValueError("Transcript warnings are outside bounds")
    return value


def process_one_transcription(
    engine,
    tenant_id: str,
    transcriber: ByteTranscriber,
    encoded_master_key: str,
) -> bool:
    started = time.monotonic()
    now = utcnow()
    claim = uid()
    with tenant_session(engine, tenant_id) as session:
        row = session.scalar(
            select(AudioTranscript)
            .join(AudioAsset, AudioAsset.id == AudioTranscript.audio_asset_id)
            .where(
                AudioTranscript.tenant_id == tenant_id,
                AudioAsset.tenant_id == tenant_id,
                AudioAsset.state == "RELEASED",
                or_(
                    and_(AudioTranscript.state == "QUEUED", AudioTranscript.available_at <= now),
                    and_(AudioTranscript.state == "RUNNING", AudioTranscript.lease_until < now),
                ),
            )
            .order_by(AudioTranscript.available_at, AudioTranscript.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return False
        changed = session.execute(
            update(AudioTranscript)
            .where(
                AudioTranscript.id == row.id,
                AudioTranscript.tenant_id == tenant_id,
                or_(AudioTranscript.state == "QUEUED", AudioTranscript.lease_until < now),
            )
            .values(
                state="RUNNING",
                claim_id=claim,
                lease_until=now + timedelta(seconds=120),
                attempts=AudioTranscript.attempts + 1,
                updated_at=now,
            )
            .execution_options(synchronize_session="fetch")
        )
        if changed.rowcount != 1:
            session.rollback()
            return False
        asset = session.scalar(
            select(AudioAsset).where(
                AudioAsset.tenant_id == tenant_id, AudioAsset.id == row.audio_asset_id
            )
        )
        report = session.scalar(
            select(Report).where(Report.tenant_id == tenant_id, Report.id == row.report_id)
        )
        transcript_id = row.id
        language_hint = (
            report.original_language if report.original_language in LANGUAGES - {"und"} else None
        )
        session.commit()

    try:
        audio = decrypt_audio(asset, encoded_master_key)
        result = _validate_output(transcriber.transcribe_bytes(audio, language_hint))
        error_code = None
    except AudioIntegrityError:
        result = None
        error_code = "AUDIO_INTEGRITY_FAILURE"
    except ModelUnavailableError:
        result = None
        error_code = "MODEL_UNAVAILABLE"
    except Exception:
        result = None
        error_code = "TRANSCRIBER_FAILURE"

    with tenant_session(engine, tenant_id) as session:
        serialize_tenant(session, tenant_id)
        row = session.scalar(
            select(AudioTranscript)
            .where(AudioTranscript.tenant_id == tenant_id, AudioTranscript.id == transcript_id)
            .with_for_update()
        )
        if row.claim_id != claim or row.state != "RUNNING":
            return True
        report = session.scalar(
            select(Report).where(Report.tenant_id == tenant_id, Report.id == row.report_id)
        )
        case = session.scalar(
            select(Case).where(Case.tenant_id == tenant_id, Case.id == report.case_id)
        )
        if result is None:
            row.error_code = error_code
            if error_code in {"AUDIO_INTEGRITY_FAILURE", "MODEL_UNAVAILABLE"}:
                row.attempts = 3
            row.state = "FAILED" if row.attempts >= 3 else "QUEUED"
            row.available_at = utcnow() + timedelta(seconds=2**row.attempts)
        else:
            row.state = "DONE"
            row.original_text = result.text.strip()
            row.language = result.language
            row.model_revision = result.model_revision
            row.duration_seconds = result.duration_seconds
            row.confidence = None
            row.source_audio_hmac = asset.content_hmac
            row.warnings = list(dict.fromkeys((*result.warnings, "CONFIDENCE_UNAVAILABLE")))
            row.error_code = None
            row.version += 1
        row.claim_id = None
        row.lease_until = None
        row.updated_at = utcnow()
        actor = Principal(tenant_id, "system:audio-transcriber", "admin")
        audit(
            session,
            actor,
            "report.audio_transcription_processed",
            row.id,
            {"result": row.state, "attempt": row.attempts, "error_code": row.error_code},
        )
        emit(session, case, "report.audio_transcript_updated")
        state, attempts = row.state, row.attempts
        session.commit()
    logger.info(
        json.dumps(
            {
                "event": "transcription_job_completed",
                "result": state,
                "attempt": attempts,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
            }
        )
    )
    return True


def review_transcript(
    session, actor: Principal, report_id: str, request: TranscriptReviewIn
) -> tuple[AudioTranscript, bool]:
    require_role(actor, "admin", "coordinator")
    serialize_tenant(session, actor.tenant_id)
    row = session.scalar(
        select(AudioTranscript).where(
            AudioTranscript.tenant_id == actor.tenant_id, AudioTranscript.report_id == report_id
        )
    )
    if row is None:
        raise HTTPException(404, "Transcript not found")
    if (
        row.corrected_by == actor.user_id
        and row.corrected_text == request.corrected_text
        and row.corrected_language == request.language
        and row.correction_reason == request.reason
    ):
        return row, True
    if row.state != "DONE":
        raise HTTPException(409, "Only completed transcripts can be reviewed")
    if row.version != request.expected_version:
        raise HTTPException(409, "Transcript version changed; reload before reviewing")
    row.corrected_text = request.corrected_text
    row.corrected_language = request.language
    row.corrected_by = actor.user_id
    row.correction_reason = request.reason
    row.corrected_at = utcnow()
    row.version += 1
    row.updated_at = utcnow()
    report = session.scalar(
        select(Report).where(Report.tenant_id == actor.tenant_id, Report.id == report_id)
    )
    case = session.scalar(
        select(Case).where(Case.tenant_id == actor.tenant_id, Case.id == report.case_id)
    )
    audit(
        session,
        actor,
        "report.audio_transcript_reviewed",
        row.id,
        {"language": request.language, "version": row.version, "reason": request.reason},
    )
    emit(session, case, "report.audio_transcript_reviewed")
    session.commit()
    return row, False


def run(engine, tenant_id: str, transcriber: ByteTranscriber, encoded_master_key: str):
    while True:
        if not process_one_transcription(engine, tenant_id, transcriber, encoded_master_key):
            time.sleep(1)
