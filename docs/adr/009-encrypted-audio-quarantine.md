# ADR 009 — Encrypted audio quarantine in PostgreSQL

Status: accepted for the controlled development slice, 2026-09-15.

## Context

Voice reports can contain names, health information, exact locations and other
high-risk personal data. The existing Whisper adapter only accepts approved
local paths and cannot safely receive arbitrary network uploads. The product
still needs a durable handoff between an authenticated report and a future
scanning/transcription worker. Retention execution must remove the audio in the
same reviewed operation as its report.

## Decision

Accept one raw WAV attachment per existing report at a dedicated authenticated
endpoint. Read the request through the existing streamed body boundary with a
separate 2 MB ceiling. Before persistence, require `audio/wav` or
`audio/x-wav`, mono 16-bit PCM at 16 kHz, duration from 0.2 to 30 seconds and a
minimum energy gate. Do not accept caller filenames, codecs or container
metadata.

Derive independent encryption and replay-digest keys from a 32-byte managed
root key using HKDF-SHA256. Encrypt each payload with AES-256-GCM, a random
96-bit nonce and associated data containing the tenant, report and asset IDs.
Store ciphertext, nonce, bounded metadata, a key ID and an HMAC-SHA256 content
digest in a tenant-RLS PostgreSQL table. Return metadata only. A replay with the
same keyed digest returns the existing asset; different audio for the same
report returns a conflict.

All new assets remain `QUARANTINED`. There is no public download endpoint and
no automatic transition to Whisper. The reviewed retention transaction deletes
matching audio rows before report redaction. An active legal hold blocks that
transaction as it does for text and embeddings.

## Why PostgreSQL for this slice

A `bytea` row keeps the attachment and retention metadata in one transactional,
tenant-scoped system and makes deletion testable with the existing local backup
flow. The 2 MB/30-second ceiling bounds row size. It avoids claiming an object
store lifecycle that has not been deployed or tested.

Object storage becomes preferable when measured volume, backup growth or
streaming latency justifies it. That move requires encrypted object naming,
write/database reconciliation, lifecycle policies, tenant authorization,
orphan collection, legal holds, restore and deletion evidence.

## Consequences and failure behaviour

- Missing or malformed key configuration disables only the audio endpoint with
  503; text reports remain available.
- Invalid media is rejected before encryption and persistence. This format
  parser and energy gate are not malware scanning.
- AEAD associated data prevents moving ciphertext between reports or tenants.
  HMAC supports idempotency without exposing a reusable plaintext hash.
- Runtime database access can insert/select tenant rows but cannot update or
  delete them. Administrative retention performs deletion.
- Backups contain ciphertext, so loss of the managed key makes restoration
  impossible. Compromise of the database and active key exposes retained audio.
- The current single-key configuration records a key ID but does not implement
  a keyring, rotation/re-encryption or emergency revocation.

## Scan/release extension — 2026-09-15

Migration `0006` adds a fail-closed `AudioScanner` protocol, fixed persisted
verdict codes, scanner revision, optimistic version and explicit human decision.
Only `CLEAN`/`SCAN_PASSED` audio can become `RELEASED`, and the releasing
admin/coordinator must differ from the uploader. Exact decision replay is
idempotent; conflicting races return 409. No HTTP endpoint accepts scanner
verdicts and no raw audio route was added.

Before transcription or pilot, connect a pinned and isolated real scanner to the
protocol, then add the released-audio transcription worker. Key rotation,
backup-key recovery and a restore drill that includes encrypted audio remain.
Obtain legal review and use consented multilingual human/noisy audio; the
existing two OS-TTS fixtures prove plumbing only.
