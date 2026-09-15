import base64
import math
import struct
import wave
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

from conftest import headers
from fastapi.testclient import TestClient
from komsu.ai import TranscriptionOutput
from komsu.app import create_app
from komsu.audio_scanning import ScanOutcome, ScanVerdict, scan_audio_asset
from komsu.cli import provision
from komsu.config import Settings
from komsu.db import tenant_session
from komsu.models import AudioAsset, AudioTranscript, utcnow
from komsu.transcription_worker import UnavailableTranscriber, process_one_transcription

AUDIO_KEY = base64.b64encode(b"T" * 32).decode()


def wav_bytes():
    output = BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(
            b"".join(
                struct.pack("<h", round(7000 * math.sin(2 * math.pi * 440 * i / 16_000)))
                for i in range(4000)
            )
        )
    return output.getvalue()


class CleanScanner:
    def scan(self, payload):
        return ScanOutcome(ScanVerdict.CLEAN, "NO_THREAT_DETECTED")


class FakeTranscriber:
    def transcribe_bytes(self, payload, language_hint=None):
        assert payload.startswith(b"RIFF")
        return TranscriptionOutput(
            "Synthetic transcript: two people need help",
            language_hint or "und",
            "fake-whisper@1",
            0.25,
            ("HUMAN_TRANSCRIPT_REVIEW_REQUIRED",),
        )


class BrokenTranscriber:
    def transcribe_bytes(self, payload, language_hint=None):
        raise RuntimeError("source audio and vendor details must not persist")


def audio_client(engine):
    return TestClient(
        create_app(
            Settings(
                environment="test",
                requests_per_minute=10000,
                audio_master_key_b64=AUDIO_KEY,
                _env_file=None,
            ),
            engine,
        )
    )


def create_audio(client, engine, uploader, approver, *, release=True):
    report = client.post(
        "/api/v1/reports",
        headers=headers(uploader),
        json={
            "client_id": str(uuid4()),
            "text": "Original source text remains immutable",
            "language": "en",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    ).json()
    uploaded = client.post(
        f"/api/v1/reports/{report['report_id']}/audio",
        headers={**headers(uploader), "Content-Type": "audio/wav"},
        content=wav_bytes(),
    ).json()
    with tenant_session(engine, uploader["tenant_id"]) as session:
        scan_audio_asset(
            session,
            uploader["tenant_id"],
            uploaded["id"],
            CleanScanner(),
            "test-scanner-v1",
            AUDIO_KEY,
        )
    if release:
        response = client.post(
            f"/api/v1/reports/{report['report_id']}/audio/decision",
            headers=headers(approver),
            json={
                "expected_version": 2,
                "decision": "RELEASE",
                "reason": "Clean fixture reviewed",
            },
        )
        assert response.status_code == 200, response.text
    return report, uploaded


def test_worker_processes_only_released_audio_and_preserves_source(setup):
    engine, _, admin, other, observer, rescue = setup
    approver = provision(engine, "Transcript coordinator", "coordinator", admin["tenant_id"])
    with audio_client(engine) as client:
        pending_report, _ = create_audio(client, engine, rescue, approver, release=False)
        assert (
            process_one_transcription(engine, admin["tenant_id"], FakeTranscriber(), AUDIO_KEY)
            is False
        )
        report, _ = create_audio(client, engine, rescue, approver)
        assert process_one_transcription(engine, admin["tenant_id"], FakeTranscriber(), AUDIO_KEY)
        assert (
            process_one_transcription(engine, admin["tenant_id"], FakeTranscriber(), AUDIO_KEY)
            is False
        )
        detail = client.get(f"/api/v1/reports/{report['report_id']}", headers=headers(admin))
        assert detail.status_code == 200
        body = detail.json()
        assert body["original_text"] == "Original source text remains immutable"
        assert body["transcript"]["state"] == "DONE"
        assert body["transcript"]["original_text"].startswith("Synthetic transcript")
        assert body["transcript"]["confidence"] is None
        assert "CONFIDENCE_UNAVAILABLE" in body["transcript"]["warnings"]
        with tenant_session(engine, admin["tenant_id"]) as session:
            transcript = (
                session.query(AudioTranscript).filter_by(report_id=report["report_id"]).one()
            )
            asset = session.query(AudioAsset).filter_by(report_id=report["report_id"]).one()
            assert transcript.source_audio_hmac == asset.content_hmac
        review_path = f"/api/v1/reports/{report['report_id']}/audio/transcript/review"
        review = {
            "expected_version": 2,
            "corrected_text": "Two people need medical help",
            "language": "en",
            "reason": "Coordinator listened and corrected wording",
        }
        assert client.post(review_path, headers=headers(observer), json=review).status_code == 403
        assert client.post(review_path, headers=headers(other), json=review).status_code == 404
        corrected = client.post(review_path, headers=headers(approver), json=review)
        assert corrected.status_code == 200
        assert corrected.json()["original_text"].startswith("Synthetic transcript")
        assert corrected.json()["corrected_text"] == review["corrected_text"]
        assert corrected.json()["version"] == 3
        replay = client.post(review_path, headers=headers(approver), json=review)
        assert replay.status_code == 200 and replay.json()["replayed"] is True
        assert (
            client.get(
                f"/api/v1/reports/{pending_report['report_id']}", headers=headers(admin)
            ).json()["transcript"]
            is None
        )


def test_transcriber_failures_retry_three_times_with_fixed_error(setup):
    engine, _, admin, _, _, rescue = setup
    approver = provision(engine, "Transcript coordinator", "coordinator", admin["tenant_id"])
    with audio_client(engine) as client:
        report, _ = create_audio(client, engine, rescue, approver)
        for attempt in range(1, 4):
            assert process_one_transcription(
                engine, admin["tenant_id"], BrokenTranscriber(), AUDIO_KEY
            )
            with tenant_session(engine, admin["tenant_id"]) as session:
                row = session.query(AudioTranscript).filter_by(report_id=report["report_id"]).one()
                assert row.error_code == "TRANSCRIBER_FAILURE"
                assert "source audio" not in str(row.error_code)
                if attempt < 3:
                    row.available_at = utcnow()
                    session.commit()
        detail = client.get(f"/api/v1/reports/{report['report_id']}", headers=headers(admin)).json()
        assert detail["transcript"]["state"] == "FAILED"
        assert detail["transcript"]["attempts"] == 3


def test_integrity_failure_is_terminal_and_fail_closed(setup):
    engine, _, admin, _, _, rescue = setup
    approver = provision(engine, "Transcript coordinator", "coordinator", admin["tenant_id"])
    with audio_client(engine) as client:
        report, uploaded = create_audio(client, engine, rescue, approver)
        with tenant_session(engine, admin["tenant_id"]) as session:
            asset = session.get(AudioAsset, uploaded["id"])
            asset.ciphertext = bytes(asset.ciphertext[:-1]) + bytes([asset.ciphertext[-1] ^ 1])
            session.commit()
        assert process_one_transcription(engine, admin["tenant_id"], FakeTranscriber(), AUDIO_KEY)
        detail = client.get(f"/api/v1/reports/{report['report_id']}", headers=headers(admin)).json()
        assert detail["transcript"]["state"] == "FAILED"
        assert detail["transcript"]["attempts"] == 3
        assert detail["transcript"]["error_code"] == "AUDIO_INTEGRITY_FAILURE"
        assert detail["transcript"]["original_text"] is None


def test_missing_local_model_records_explicit_unavailable_result(setup):
    engine, _, admin, _, _, rescue = setup
    approver = provision(engine, "Transcript coordinator", "coordinator", admin["tenant_id"])
    with audio_client(engine) as client:
        report, _ = create_audio(client, engine, rescue, approver)
        assert process_one_transcription(
            engine, admin["tenant_id"], UnavailableTranscriber(), AUDIO_KEY
        )
        detail = client.get(f"/api/v1/reports/{report['report_id']}", headers=headers(admin)).json()
        assert detail["transcript"]["state"] == "FAILED"
        assert detail["transcript"]["attempts"] == 3
        assert detail["transcript"]["error_code"] == "MODEL_UNAVAILABLE"
        assert detail["transcript"]["original_text"] is None
