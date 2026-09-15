# Audio scanning and release boundary

Audio enters PostgreSQL only as tenant-scoped AES-GCM ciphertext in `QUARANTINED` state. Migration `0006` adds the fail-closed scan and human-decision state machine:

```text
QUARANTINED -- clean scan --> SCAN_PASSED -- distinct coordinator/admin --> RELEASED
      |                              |
      +-- scanner failure --> SCAN_ERROR
      +-- malicious/invalid -> REJECTED <-- human rejection
```

`AudioScanner` is a local protocol for a dedicated, privileged worker process. `scan_audio_asset` decrypts authenticated ciphertext only in memory, revalidates the bounded PCM WAV, calls the scanner and persists only a fixed verdict/reason code, scanner revision and time. Exceptions and invalid scanner responses become `SCAN_ERROR`; exception text and audio bytes are not logged or stored as scan metadata. Repeating the same scanner revision is idempotent.

No HTTP endpoint accepts scanner verdicts, and no production malware engine is bundled. Tests use deterministic scanner doubles to prove the boundary and transitions. A pilot deployment must select, pin, license and isolate a real scanner/decoder, then run the same interface in a separately constrained process. Until that happens, audio remains quarantined.

An admin or coordinator may call `POST /api/v1/reports/{report_id}/audio/decision` with `expected_version`, `decision` and a bounded reason. Release is allowed only after a `CLEAN` scan and must be performed by a different user from the uploader. Rejection is permitted while quarantined, scan-passed or scan-error. Decisions are versioned, audited and idempotent for an exact replay; a conflicting race returns `409`.

The API exposes metadata only. It has no raw-audio/ciphertext download route. `RELEASED` means eligible for the next transcription worker; it does not mean a transcript exists or that the audio is safe for arbitrary playback.
