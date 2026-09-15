# Released-audio transcription worker

Migration `0007` creates one tenant-scoped job when a clean audio asset is explicitly released. A rolling upgrade queues assets already in `RELEASED`; `0008` adds the claim index and the keyed source-audio digest used by a successful transcript. Forced RLS remains active. Deleting retained audio cascades to its transcript.

The worker selects only `RELEASED` audio, takes a 120-second fenced lease and commits the claim before decrypting. AES-GCM authentication and WAV bounds are checked in memory. Plain audio, transcript text, report IDs and exception text are not written to completion logs. Success records the machine text, language, exact model revision, duration, source HMAC and warnings. No calibrated confidence is invented: `confidence` remains null and `CONFIDENCE_UNAVAILABLE` is recorded.

Transient adapter failures return a job to `QUEUED` with bounded exponential delay and stop after three attempts. Ciphertext authentication failure and missing approved local model are terminal `AUDIO_INTEGRITY_FAILURE` and `MODEL_UNAVAILABLE` results. These codes do not expose exception details. A failed job never modifies the original report or creates a dispatch decision.

Configure `KOMSU_AUDIO_MASTER_KEY_B64`, `KOMSU_WHISPER_MODEL_DIR` and a tenant, then run:

```powershell
.\.venv\Scripts\komsu.exe transcription-worker --tenant TENANT_UUID
```

Use `--once` for one queue attempt. Model weights are local and are not included in the API container. Running without `KOMSU_WHISPER_MODEL_DIR` deliberately records `MODEL_UNAVAILABLE`; it is not a fallback transcription service.

`GET /api/v1/reports/{id}` and case detail return metadata and transcript state, never audio bytes. Admins and coordinators may submit a versioned correction to `POST /api/v1/reports/{id}/audio/transcript/review`. The original machine text remains unchanged beside the corrected text and reason. Exact retries by the same reviewer are idempotent; stale versions conflict.

The automated evidence covers release gating, malformed/tampered ciphertext, model absence, three-attempt retry, source preservation, correction roles/idempotency, tenant isolation and a real PostgreSQL claim/process/read path. It uses deterministic transcriber doubles. The pinned Whisper diagnostic still contains only two synthetic TR/EN TTS clips; Greek, noisy human rescue audio, scanner-engine isolation and operational process supervision remain pilot gates.
