# Project status

Updated: 2026-09-15. Controlled development foundation, not production ready.

## COMPLETED
- Correct three-page product PDF extracted and visually inspected, including architecture figure.
- Traceable PDF and engineering-extension requirement matrix created before implementation.
- Architecture with context/container/component diagrams; threat model; nine ADRs and official-source research notes.
- FastAPI ingestion, source preservation, expiring/revocable hashed opaque sessions, role/tenant boundaries, durable jobs, worker lease recovery and claim fencing, conservative TR/EL/EN rules baseline.
- Human case review and location confirmation; versioned dispatch with team checks and transactional audit/events.
- PostgreSQL/PostGIS/pgvector Docker image built and running; Alembic migrations through 0005 applied; runtime non-superuser RLS and spatial trigger tested.
- 78 Python tests passed in the full suite, including 8 real PostgreSQL tests: concurrent dispatch and merge (one 200, one 409), split, RLS, append-only audit, semantic/audio isolation, and reviewed retention. Latest run 2026-09-15.
- React/MapLibre dashboard builds; six coordinate/localisation tests pass; npm audit reported zero vulnerabilities at installation.
- Browser login and live event connection verified; 12 synthetic reports displayed. Expired demo token correctly rejected after session interruption and rotated with unchanged scope.
- API and migration Docker images build successfully; Compose API and PostgreSQL are healthy. Restart retained synthetic data.
- Deterministic corpus: 3000 synthetic reports / 1000 TR-EL-EN event groups; 12 report local demo seeded.
- Android project, Gradle wrapper, Compose screens, Room schema/queue, WorkManager, encrypted token storage, tenant-scoped cache/queue and relay protocol code written.
- Android debug APK, lint, four app unit tests, seven relay/crypto tests and four Room instrumentation tests passed on Pixel 7 / Android 14 emulator. Relay custody survives database reopen; ECDSA/AES-GCM tampering is rejected; Room v1→v2 preserves queued reports; interrupted sync claims remain pending through lease expiry.
- Browser human review and synthetic dispatch completed; logout and 390px viewport checked without horizontal overflow. Login bundle reduced to 238 kB raw by deferred MapLibre loading.
- Optional self-hosted geocoder candidate adapter and review-only candidate UI, channel normalization/HMAC helpers and validated pipeline implemented with fixture tests; no live gateway/geocoder configured.
- GIS import requires admin and validates bounds/types/feature limits; tenant isolation tested. Production web build visually verified with 12 case points and synthetic hospital/road layers. Fixed MapLibre CSS sizing and bundled the v6 worker with Vite ?worker&url.
- Local HTTP benchmark: 30 reports, 6 clients, all processed; acknowledgement p95 79.783 ms. Small baseline-only burst, not a capacity guarantee.
- pip-audit requirements scan: no known vulnerabilities; Bandit: no medium/high findings in the current Python source. These are bounded scans, not a security certification.
- CI workflow and OpenAPI export written. Challenge evaluation exposes 50% need recall on 18 authored examples; interpretation recorded in docs/evaluation/INTERPRETATION.md.

- Human merge/split preserves original reports and requires versions/reason, clears stale review/coordinates, records audit/events; migration 0002 applied. Browser merge/split and Android snapshot replacement verified.
- Embedding worker polls missing vectors and retains its loaded model; partial-batch failure recovery and original-report retention tested in PostgreSQL.
- Model environment audit: pip 26.2.1 and setuptools 83.0.0; no known issues in auditable packages. The official CPU PyTorch `+cpu` wheel and local Komşu package are outside PyPI matching and were skipped.
- Actual pinned local bge-m3 CPU inference encoded 12 demo reports; tenant-scoped same-revision pgvector suggestions shown in browser with original target report preview. No automatic merge.
- Six-text authored bge diagnostic: different-building cosine 0.958 exceeded same-event English 0.794 / Greek 0.695. Confirms scores cannot establish event identity; no field accuracy claimed.
- 240-message bge template stress diagnostic removed synthetic site markers: recall@1 was 0.0 in every language and different-event same-template cosine was 1.0. Semantic-only threshold 0.92 yielded precision 0.1493/recall 0.1667 on balanced development pairs. The oracle building-identity gate removed false proposals but is not a production capability.
- Four pinned Apache-2.0 OPUS-MT routes run locally with checksum verification, immutable provenance, bounded two-model cache and explicit EN pivots. Six-case diagnostics retained all numerals in 3/6, a negation marker in 1/4 and selected names verbatim in 0/6; translations remain review-only annotations. One incoherent legacy EL→EN model was rejected and recorded.
- Pinned local Whisper-tiny safetensors adapter enforces approved-root mono PCM, 30-second/2-MB bounds, checksum and pre-model silence rejection. Two disclosed TR/EN OS-TTS clips produced micro WER 0.3793; no Greek/human/noisy audio result and no ingestion connection is claimed.
- Optional loopback worker metrics expose fixed result counts, analysis/job/queue-wait histograms and queue depth/oldest age without content or tenant/report labels. Structured completion logs contain fixed status/attempt/duration only.
- Dashboard chrome, filters, case detail, human review, regrouping, semantic warnings and map controls can be switched between Turkish, Greek and English. The preference contains no case data or credential and is stored locally; message language remains independent.
- Authenticated raw-WAV attachment endpoint enforces MIME, 2 MB, 16 kHz/16-bit/mono, 0.2–30 second and speech-energy bounds before storing. HKDF-separated AES-GCM encryption and keyed replay digest protect one quarantined attachment per report; plaintext/ciphertext never appears in API responses. Tenant RLS, role checks, replay/conflict, tamper failure and retention deletion are tested.

- Container scanning completed; vendor-fixed OS issues patched and pip removed from final runtime images. PostgreSQL 17.11 retained all 12 demo reports; the full Python suite passes after the upgrade. Remaining OS/gosu findings are recorded in docs/security/CONTAINER_SCAN.md, not suppressed.
- Migrations 0003/0004 add tenant-scoped retention plans and expiring legal holds; 0005 adds encrypted audio quarantine. Destructive execution requires a distinct approver, due time and exact plan-ID confirmation; active holds block it. Synthetic PostgreSQL coverage verifies redaction, audio/spatial/embedding cleanup, cancellation and cross-tenant isolation.
- A 192,131-byte logical backup was restored to a separate local database and migrated from 0002 to 0004; runtime auth, RLS, 12 demo reports/embeddings and semantic retrieval passed. This is same-host restore evidence, not HA/offsite DR.

## IN PROGRESS
- Quarantined-audio release/transcription workflow and operational validation. Model evaluation remains deliberately gated by real multilingual and field data.

## NEXT
- Quarantine scanning and explicit release into transcription; Greek/noisy human transcription validation; live geocoder/municipal data integration; central monitoring; relay key distribution/radio implementation and physical-device validation.

## BLOCKERS
- No hard infrastructure blocker currently. Docker Desktop was started; Windows localhost/IPv6 connection issue avoided using 127.0.0.1 and explicit connection timeout.
- Recorded rescue audio, native-speaker translation validation data, municipal GIS and physical A/B/C relay devices not supplied. No corresponding production claim.

## RISKS
- Remaining high/critical container findings need vendor updates or reachability review before pilot; local scan is not a clean security result.
- No real-world labelled corpus, validated rescue translations/audio, municipal GIS data or physical relay device test yet.
- AI error and wrong location can harm rescue; no autonomous dispatch permitted.

## TECHNICAL DEBT
- Semantic suggestions and human merge/split UI work locally; embeddings support bounded batch and a continuous local polling worker. Translation is optional and disabled by default because diagnostics show critical omissions. Transcription has a bounded local adapter and encrypted quarantine ingestion, but no scanner/release worker or automated transcript attachment. Geocoder adapter is optional and fixture-tested; no external provider is active.
- Web UI has TR/EL/EN controls; rescue wording still requires native-speaker review. Messages retain their original language. Map has point overlay and an explicit unconfigured-base-map notice. Admin GIS import and layer toggles support bounded Point/LineString data with provenance; four synthetic layers loaded.
- FastAPI test client dependency emits two deprecation warnings; tests still pass. Deferred MapLibre chunk remains about 1.02 MB raw. Android has dependency/deprecation warnings; lint has no errors.
- Relay policy, authenticated encryption/signature primitives and persistent Room custody are implemented and emulator-tested. No organization key distribution, actual radio transport or physical A→B→C validation is claimed.
- Per-process in-memory request quota is development-only; shared gateway quotas, OIDC/MFA, offsite restore/HA, backup and device-cache re-purge, legal approval and OTLP exporter are pilot gates.
- The recorded restore drill ends at migration 0004; a fresh backup/restore drill including 0005 encrypted audio remains required.
- Demo credentials expire after eight hours; ignored .env.session.json stores the local token. No source-control secrets.
