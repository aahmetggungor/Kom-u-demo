import base64
import math
import struct
import wave
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from conftest import headers
from fastapi.testclient import TestClient
from komsu.app import create_app
from komsu.audio_scanning import ScanOutcome, ScanVerdict, scan_audio_asset
from komsu.audio_storage import (
    AudioConfigurationError,
    AudioIntegrityError,
    AudioRejected,
    decrypt_audio,
    derive_keys,
    validate_pcm_wav,
)
from komsu.cli import provision
from komsu.config import Settings
from komsu.db import tenant_session
from komsu.models import AudioAsset
from sqlalchemy import select

AUDIO_KEY = base64.b64encode(b"K" * 32).decode()


class CleanScanner:
    def scan(self, payload):
        assert payload.startswith(b"RIFF")
        return ScanOutcome(ScanVerdict.CLEAN, "NO_THREAT_DETECTED")


class MaliciousScanner:
    def scan(self, payload):
        return ScanOutcome(ScanVerdict.MALICIOUS, "TEST_SIGNATURE_MATCH")


class BrokenScanner:
    def scan(self, payload):
        raise RuntimeError("sensitive vendor error must not be persisted")


def wav_bytes(frequency=440, seconds=1.0, *, rate=16_000, channels=1):
    output = BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        frames = int(rate * seconds)
        stream.writeframes(
            b"".join(
                struct.pack("<h", round(7000 * math.sin(2 * math.pi * frequency * i / rate)))
                * channels
                for i in range(frames)
            )
        )
    return output.getvalue()


def audio_client(engine):
    settings = Settings(
        environment="test",
        requests_per_minute=10000,
        audio_master_key_b64=AUDIO_KEY,
        _env_file=None,
    )
    return TestClient(create_app(settings, engine))


def create_report(client, actor):
    response = client.post(
        "/api/v1/reports",
        headers=headers(actor),
        json={
            "client_id": str(uuid4()),
            "text": "Synthetic voice attachment transcript pending",
            "language": "en",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 202
    return response.json()


def test_wav_validation_and_key_configuration():
    assert validate_pcm_wav(wav_bytes(seconds=0.25)) == 250
    with pytest.raises(AudioRejected, match="mono"):
        validate_pcm_wav(wav_bytes(channels=2))
    with pytest.raises(AudioRejected, match="energy"):
        silent = BytesIO()
        with wave.open(silent, "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16_000)
            stream.writeframes(b"\0\0" * 16_000)
        validate_pcm_wav(silent.getvalue())
    with pytest.raises(AudioConfigurationError, match="32 bytes"):
        derive_keys(base64.b64encode(b"short").decode())


def test_encrypted_audio_upload_is_idempotent_and_never_returned_as_ciphertext(setup):
    engine, _, admin, _, _, _ = setup
    payload = wav_bytes()
    with audio_client(engine) as client:
        report = create_report(client, admin)
        route = f"/api/v1/reports/{report['report_id']}/audio"
        first = client.post(
            route, headers={**headers(admin), "Content-Type": "audio/wav"}, content=payload
        )
        assert first.status_code == 201
        assert first.json()["state"] == "QUARANTINED"
        assert first.json()["human_review_required"] is True
        replay = client.post(
            route, headers={**headers(admin), "Content-Type": "audio/x-wav"}, content=payload
        )
        assert replay.status_code == 200 and replay.json()["replayed"] is True
        conflict = client.post(
            route, headers={**headers(admin), "Content-Type": "audio/wav"}, content=wav_bytes(550)
        )
        assert conflict.status_code == 409
        detail = client.get(f"/api/v1/reports/{report['report_id']}", headers=headers(admin)).json()
        assert detail["audio"]["id"] == first.json()["id"]
        assert "ciphertext" not in detail["audio"] and "content_hmac" not in detail["audio"]
    with tenant_session(engine, admin["tenant_id"]) as session:
        asset = session.scalar(
            select(AudioAsset).where(AudioAsset.report_id == report["report_id"])
        )
        assert payload not in bytes(asset.ciphertext)
        assert decrypt_audio(asset, AUDIO_KEY) == payload


def test_audio_upload_rejects_wrong_type_scope_and_invalid_data(setup):
    engine, _, admin, other, observer, _ = setup
    with audio_client(engine) as client:
        report = create_report(client, admin)
        route = f"/api/v1/reports/{report['report_id']}/audio"
        assert (
            client.post(
                route, headers={**headers(admin), "Content-Type": "audio/mpeg"}, content=b"x"
            ).status_code
            == 415
        )
        assert (
            client.post(
                route, headers={**headers(admin), "Content-Type": "audio/wav"}, content=b"not wav"
            ).status_code
            == 422
        )
        assert (
            client.post(
                route,
                headers={**headers(observer), "Content-Type": "audio/wav"},
                content=wav_bytes(),
            ).status_code
            == 403
        )
        assert (
            client.post(
                route, headers={**headers(other), "Content-Type": "audio/wav"}, content=wav_bytes()
            ).status_code
            == 404
        )


def test_audio_ciphertext_and_context_tampering_fail_closed():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from komsu.audio_storage import _aad, content_hmac

    payload = wav_bytes(seconds=0.25)
    encryption_key, mac_key = derive_keys(AUDIO_KEY)
    nonce = b"N" * 12
    asset = SimpleNamespace(
        id="asset",
        tenant_id="tenant",
        report_id="report",
        nonce=nonce,
        ciphertext=AESGCM(encryption_key).encrypt(
            nonce, payload, _aad("tenant", "report", "asset")
        ),
        content_hmac=content_hmac(payload, mac_key),
    )
    assert decrypt_audio(asset, AUDIO_KEY) == payload
    asset.report_id = "different-report"
    with pytest.raises(AudioIntegrityError, match="authentication"):
        decrypt_audio(asset, AUDIO_KEY)


def test_clean_scan_requires_a_distinct_authorized_human_to_release(setup):
    engine, _, admin, _, observer, rescue = setup
    coordinator = provision(engine, "Coordinator", "coordinator", admin["tenant_id"])
    with audio_client(engine) as client:
        report = create_report(client, rescue)
        uploaded = client.post(
            f"/api/v1/reports/{report['report_id']}/audio",
            headers={**headers(rescue), "Content-Type": "audio/wav"},
            content=wav_bytes(),
        ).json()
        decision = f"/api/v1/reports/{report['report_id']}/audio/decision"
        assert (
            client.post(
                decision,
                headers=headers(admin),
                json={"expected_version": 1, "decision": "RELEASE", "reason": "reviewed"},
            ).status_code
            == 409
        )
        with tenant_session(engine, admin["tenant_id"]) as session:
            scanned, replayed = scan_audio_asset(
                session,
                admin["tenant_id"],
                uploaded["id"],
                CleanScanner(),
                "test-scanner-v1",
                AUDIO_KEY,
            )
            assert (scanned.state, scanned.version, replayed) == ("SCAN_PASSED", 2, False)
        with tenant_session(engine, admin["tenant_id"]) as session:
            scanned, replayed = scan_audio_asset(
                session,
                admin["tenant_id"],
                uploaded["id"],
                CleanScanner(),
                "test-scanner-v1",
                AUDIO_KEY,
            )
            assert scanned.state == "SCAN_PASSED" and replayed is True

        assert (
            client.post(
                decision,
                headers=headers(observer),
                json={"expected_version": 2, "decision": "RELEASE", "reason": "reviewed"},
            ).status_code
            == 403
        )
        released = client.post(
            decision,
            headers=headers(coordinator),
            json={
                "expected_version": 2,
                "decision": "RELEASE",
                "reason": "Clean scan and source reviewed",
            },
        )
        assert released.status_code == 200
        assert released.json()["state"] == "RELEASED"
        assert released.json()["version"] == 3
        assert "ciphertext" not in released.json()
        replay = client.post(
            decision,
            headers=headers(coordinator),
            json={
                "expected_version": 2,
                "decision": "RELEASE",
                "reason": "Clean scan and source reviewed",
            },
        )
        assert replay.status_code == 200 and replay.json()["replayed"] is True


def test_uploader_cannot_release_their_own_clean_audio(setup):
    engine, _, admin, _, _, _ = setup
    with audio_client(engine) as client:
        report = create_report(client, admin)
        uploaded = client.post(
            f"/api/v1/reports/{report['report_id']}/audio",
            headers={**headers(admin), "Content-Type": "audio/wav"},
            content=wav_bytes(),
        ).json()
        with tenant_session(engine, admin["tenant_id"]) as session:
            scan_audio_asset(
                session,
                admin["tenant_id"],
                uploaded["id"],
                CleanScanner(),
                "test-scanner-v1",
                AUDIO_KEY,
            )
        response = client.post(
            f"/api/v1/reports/{report['report_id']}/audio/decision",
            headers=headers(admin),
            json={"expected_version": 2, "decision": "RELEASE", "reason": "self release"},
        )
        assert response.status_code == 409


@pytest.mark.parametrize(
    ("scanner", "expected_state", "expected_verdict", "reason_code"),
    [
        (MaliciousScanner(), "REJECTED", "MALICIOUS", "TEST_SIGNATURE_MATCH"),
        (BrokenScanner(), "SCAN_ERROR", "ERROR", "SCANNER_FAILURE"),
    ],
)
def test_scan_verdicts_fail_closed(setup, scanner, expected_state, expected_verdict, reason_code):
    engine, _, admin, _, _, rescue = setup
    with audio_client(engine) as client:
        report = create_report(client, rescue)
        uploaded = client.post(
            f"/api/v1/reports/{report['report_id']}/audio",
            headers={**headers(rescue), "Content-Type": "audio/wav"},
            content=wav_bytes(),
        ).json()
    with tenant_session(engine, admin["tenant_id"]) as session:
        asset, _ = scan_audio_asset(
            session,
            admin["tenant_id"],
            uploaded["id"],
            scanner,
            "test-scanner-v1",
            AUDIO_KEY,
        )
        assert (asset.state, asset.scan_verdict, asset.scan_reason_code) == (
            expected_state,
            expected_verdict,
            reason_code,
        )


def test_tampered_ciphertext_is_never_passed_or_released(setup):
    engine, _, admin, _, _, rescue = setup
    with audio_client(engine) as client:
        report = create_report(client, rescue)
        uploaded = client.post(
            f"/api/v1/reports/{report['report_id']}/audio",
            headers={**headers(rescue), "Content-Type": "audio/wav"},
            content=wav_bytes(),
        ).json()
        with tenant_session(engine, admin["tenant_id"]) as session:
            asset = session.get(AudioAsset, uploaded["id"])
            asset.ciphertext = bytes(asset.ciphertext[:-1]) + bytes([asset.ciphertext[-1] ^ 1])
            session.commit()
        with tenant_session(engine, admin["tenant_id"]) as session:
            scanned, _ = scan_audio_asset(
                session,
                admin["tenant_id"],
                uploaded["id"],
                CleanScanner(),
                "test-scanner-v1",
                AUDIO_KEY,
            )
            assert scanned.state == "SCAN_ERROR"
            assert scanned.scan_reason_code == "INTEGRITY_OR_FORMAT_ERROR"
        release = client.post(
            f"/api/v1/reports/{report['report_id']}/audio/decision",
            headers=headers(admin),
            json={"expected_version": 2, "decision": "RELEASE", "reason": "must fail closed"},
        )
        assert release.status_code == 409
