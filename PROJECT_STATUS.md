# Project status

Updated: 2026-09-16. Controlled development foundation, not production ready.

## COMPLETED
- Correct three-page product PDF extracted and visually inspected, including architecture figure.
- Traceable PDF and engineering-extension requirement matrix created before implementation.
- Architecture with context/container/component diagrams; threat model; nine ADRs and official-source research notes.
- FastAPI ingestion, source preservation, expiring/revocable hashed opaque sessions, role/tenant boundaries, durable jobs, worker lease recovery and claim fencing, conservative TR/EL/EN rules baseline.
- Human case review and location confirmation; versioned dispatch with team checks and transactional audit/events.
- PostgreSQL/PostGIS/pgvector Docker image built and running; Alembic migrations through 0009 applied; runtime non-superuser RLS and spatial trigger tested.
- 104 Python tests passed in the full suite, including 9 real PostgreSQL tests: concurrent dispatch/merge/audio release (one 200, one 409), split, RLS, append-only audit, semantic/audio/transcript isolation, and reviewed retention. Latest run 2026-09-16.
- React/MapLibre dashboard builds; eleven coordinate/localisation/audio tests pass; npm audit reported zero vulnerabilities at installation.
- Browser login and live event connection verified; 12 synthetic reports displayed. Expired demo token correctly rejected after session interruption and rotated with unchanged scope.
- API and migration Docker images build successfully; Compose API and PostgreSQL are healthy. Restart retained synthetic data.
- Deterministic corpus: 3000 synthetic reports / 1000 TR-EL-EN event groups; 12 report local demo seeded.
- Android project, Gradle wrapper, Compose screens, Room schema/queue, WorkManager, encrypted token storage, tenant-scoped cache/queue and relay protocol code written.
- Android debug APK, lint, six app unit tests, seven relay/crypto tests and six Room instrumentation tests passed on Pixel 7 / Android 14 emulator. Relay custody and report/audio queues survive database reopen; ECDSA/AES-GCM tampering is rejected; Room v1→v2→v3 preserves queued reports and adds tenant-scoped audio custody; interrupted sync claims remain pending through lease expiry.
- Browser human review and synthetic dispatch completed; logout and 390px viewport checked without horizontal overflow. Login bundle reduced to 238 kB raw by deferred MapLibre loading.
- Optional institutional/self-hosted geocoder has timeout, bounded retry/backoff, per-process pacing, tenant-scoped cache, circuit breaker, bounded schema validation and public OSM rejection. A localhost contract server and 12 PII-free TR/EL/EN address/landmark/typo fixtures passed exactly; candidates remain review-only and no live gateway/geocoder is configured.
- GIS import requires admin and validates checksums, WGS84 bounds, layer-kind geometry, 200 features/5,000 positions, Polygon/Multi types, version/licence/source date and staleness; tenant isolation is tested. A verified local MapLibre style manifest fails closed on tampering/public tiles and the browser falls back to the blank coordinate workspace. Migration 0009 is applied. Only synthetic layers/style exist.
- Local HTTP benchmark: 30 reports, 6 clients, all processed; acknowledgement p95 79.783 ms. Small baseline-only burst, not a capacity guarantee.
- pip-audit requirements scan: no known vulnerabilities; Bandit: no medium/high findings in the current Python source. These are bounded scans, not a security certification.
- CI workflow and OpenAPI export written. Challenge evaluation exposes 50% need recall on 18 authored examples; interpretation recorded in docs/evaluation/INTERPRETATION.md.

- Human merge/split preserves original reports and requires versions/reason, clears stale review/coordinates, records audit/events; migration 0002 applied. Browser merge/split and Android snapshot replacement verified.
- Embedding worker polls missing vectors and retains its loaded model; partial-batch failure recovery and original-report retention tested in PostgreSQL.
- Model environment audit: pip 26.2.1 and setuptools 83.0.0; no known issues in auditable packages. The official CPU PyTorch `+cpu` wheel and local Komşu package are outside PyPI matching and were skipped.
- Actual pinned local bge-m3 CPU inference encoded 12 demo reports; tenant-scoped same-revision pgvector suggestions shown in browser with original target report preview. No automatic merge.
- Six-text authored bge diagnostic: different-building cosine 0.958 exceeded same-event English 0.794 / Greek 0.695. Confirms scores cannot establish event identity; no field accuracy claimed.
- 240-message bge template stress diagnostic removed synthetic site markers: recall@1 was 0.0 in every language and different-event same-template cosine was 1.0. Semantic-only threshold 0.92 yielded precision 0.1493/recall 0.1667 on balanced development pairs. The oracle building-identity gate removed false proposals but is not a production capability.
- Runtime duplicate candidates now combine bounded semantic, location-quality/distance, time, address-marker and need-overlap contributions. Conflicting building numbers, excessive distance and time are explicit blockers; the browser shows every contribution and never merges automatically. A new 60-event development / 60-event held-out synthetic split scored 1.0 precision/recall with zero false candidates in each language at 0.85, but was not promoted because repeated templates, exact fixture coordinates and exposed synthetic building numbers make the result unrealistically easy.
- Four pinned Apache-2.0 OPUS-MT routes run locally with checksum verification, immutable provenance, bounded two-model cache and explicit EN pivots. On the same six-case authored diagnostic, raw output retained all numerals in 3/6, negation in 1/4 and names verbatim in 0/6. The guarded candidate retained these observable markers in 6/6, 4/4 and 6/6 by visibly appending recovered safety spans and recording warnings; it remains unpromoted pending bilingual adequacy/critical-error review. A tamper-evident PII-free CSV/JSON review package and aggregate-only importer are included.
- Pinned local Whisper-tiny safetensors adapter enforces approved-root mono PCM, 30-second/2-MB bounds, checksum and pre-model silence rejection. Two disclosed TR/EN OS-TTS clips produced micro WER 0.3793; no Greek/human/noisy audio result and no ingestion connection is claimed.
- Optional loopback worker metrics expose fixed result counts, analysis/job/queue-wait histograms and queue depth/oldest age without content or tenant/report labels. Structured completion logs contain fixed status/attempt/duration only.
- Dashboard chrome, filters, case detail, human review, regrouping, semantic warnings and map controls can be switched between Turkish, Greek and English. The preference contains no case data or credential and is stored locally; message language remains independent.
- Authenticated raw-WAV attachment endpoint enforces MIME, 2 MB, 16 kHz/16-bit/mono, 0.2–30 second and speech-energy bounds before storing. HKDF-separated AES-GCM encryption and keyed replay digest protect one quarantined attachment per report; plaintext/ciphertext never appears in API responses. Tenant RLS, role checks, replay/conflict, tamper failure and retention deletion are tested.
- Local `AudioScanner` boundary revalidates decrypted WAV in memory and persists fixed clean/malicious/invalid/error codes without exception text. Scan failures remain closed; only clean scan-passed audio can be released, by a different admin/coordinator from the uploader. Versioned decision replay, conflicting PostgreSQL release races, audit/events and tenant isolation are tested. No real malware engine is configured.
- Released audio creates one durable, tenant-scoped transcription job. The lease-fenced worker decrypts only after claim, calls the local byte-based Whisper adapter, stores source HMAC provenance/model/language/warnings, and records fixed terminal integrity/model-unavailable states without content in logs. Machine text remains separate from versioned admin/coordinator corrections and is visible in the three-language case panel; raw audio is never downloadable. Tests cover release gating, retry, missing model, tampering, correction permissions/idempotency and real PostgreSQL RLS.
- Android requests microphone access at the point of use and records at most 30 seconds as 16 kHz mono 16-bit PCM WAV, with visible timer, stop, cancel, rerecord and remove controls. Silence/format/size are rejected before private-file/Room persistence. WorkManager uploads the report first and then its audio with fenced tenant-scoped retry; 200 replay is accepted, while auth/conflict/validation remain explicit. The development web form can record/downsample or validate a local WAV and retries the same report/audio IDs. No audio is logged or sent to analytics.
- Need classification failures are now split by language, class, negation, implicit wording, multiple needs, ambiguity and numbers. Deployed `rules-0.1` scored precision 0.571, recall 0.267 and urgency accuracy 0.389 on a new 36-row authored holdout. A guarded rules candidate scored 1.0 on this same-author synthetic set; a local scikit-learn char-TFIDF/logistic candidate scored precision 0.50, recall 0.333 and urgency accuracy 0.389. Runtime remains `rules-0.1` because none of this is independent/native-speaker field validation. Every candidate requires human review and cannot dispatch.

- Container scanning completed; vendor-fixed OS issues patched and pip removed from final runtime images. PostgreSQL 17.11 retained all 12 demo reports; the full Python suite passes after the upgrade. Remaining OS/gosu findings are recorded in docs/security/CONTAINER_SCAN.md, not suppressed.
- Migrations 0003/0004 add tenant-scoped retention plans and expiring legal holds; 0005 adds encrypted audio quarantine, 0006 scan/release state, 0007/0008 durable transcript jobs/provenance, and 0009 versioned/licensed GIS metadata. Destructive execution requires a distinct approver, due time and exact plan-ID confirmation; active holds block it. Transcript rows cascade with retained audio deletion. Synthetic PostgreSQL coverage verifies redaction, audio/spatial/embedding cleanup, cancellation and cross-tenant isolation.
- A 192,131-byte logical backup was restored to a separate local database and migrated from 0002 to 0004; runtime auth, RLS, 12 demo reports/embeddings and semantic retrieval passed. This is same-host restore evidence, not HA/offsite DR.

- Prompt 9 complete: tenant-bound SMS/messaging/social/phone inbound contract, HMAC/timestamp checks, durable replay receipts, hashed dead letters, atomic report/audio/receipt writes and PostgreSQL-serialized quotas. Local synthetic provider simulator covers delivery replay and API outage. Live providers are not connected.
- Prompt 9 verification: 108 non-PostgreSQL tests and 11 PostgreSQL tests passed; concurrent quotas and injected receipt crashes leave no orphan reports/audio. OpenAPI and inbound operations guide updated.
- Protected synthetic Render demo deployed at https://komsu-demo.onrender.com; web/Android use the same API. GitHub Actions produces the demo APK. Free database expiration and disabled heavy models remain presentation limitations.

## IN PROGRESS
- Prompt 10 in progress: server-advertised demo session expiry, credential invalidation with retained offline tenant/queue, renewed login, restored API address and readable queue/retry controls implemented. Android APK/build/lint, 7 app unit tests and 7 Pixel 7 Android 14 emulator tests passed. Versioned phrase/audio-package import and accessibility rehearsal remain.

## NEXT
- Complete Prompt 10 Android offline/stabilization, then Prompt 11 device transport, Prompt 12 load/failure resilience and Prompt 13 centralized monitoring. Live geocoder/GIS/provider integration awaits the listed external inputs.

## BLOCKERS
- No hard infrastructure blocker currently. Docker Desktop was started; Windows localhost/IPv6 connection issue avoided using 127.0.0.1 and explicit connection timeout.
- Recorded rescue audio, native-speaker translation validation data, municipal GIS and physical A/B/C relay devices not supplied. No corresponding production claim.

## RISKS
- Remaining high/critical container findings need vendor updates or reachability review before pilot; local scan is not a clean security result.
- No real-world labelled corpus, validated rescue translations/audio, municipal GIS data or physical relay device test yet.
- AI error and wrong location can harm rescue; no autonomous dispatch permitted.

## TECHNICAL DEBT
- Semantic suggestions and human merge/split UI work locally; embeddings support bounded batch and a continuous local polling worker. Translation is optional and disabled by default because raw models omit critical facts and the guarded output lacks bilingual adequacy review. Transcription attachment and human correction work, but the worker needs separately installed model weights/process supervision and there is no real scanner process. Geocoder adapter is optional and fixture-tested; no external provider is active.
- Web UI has TR/EL/EN controls; rescue wording still requires native-speaker review. Messages retain their original language. Map has an explicit unconfigured-package notice and verified style fallback. Admin GIS import and layer toggles support bounded Point/MultiPoint, LineString/MultiLineString and Polygon/MultiPolygon data with version, licence, checksum, provenance and freshness; only synthetic layers are validated.
- FastAPI test client dependency emits two deprecation warnings; tests still pass. Deferred MapLibre chunk remains about 1.02 MB raw. Android has dependency/deprecation warnings; lint has no errors.
- Relay policy, authenticated encryption/signature primitives and persistent Room custody are implemented and emulator-tested. No organization key distribution, actual radio transport or physical A→B→C validation is claimed.
- Per-process in-memory request quota is development-only; shared gateway quotas, OIDC/MFA, offsite restore/HA, backup and device-cache re-purge, legal approval and OTLP exporter are pilot gates.
- The recorded restore drill ends at migration 0004; a fresh backup/restore drill including 0005–0009 encrypted audio/transcript and GIS metadata state remains required.
- Demo credentials expire after eight hours; ignored .env.session.json stores the local token. No source-control secrets.
