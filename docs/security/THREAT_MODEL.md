# Threat model

2026-09-14; EXT-010..014, SEC-001, FUNC-016. Trust boundaries: untrusted public messages → adapters/API; operator browser → API; tenant → database; DB → model/geocoder; encrypted report → untrusted relay peer; backups/telemetry → operators.

| Threat | Control to implement / verify | Residual risk |
|---|---|---|
| IDOR / cross-tenant disclosure | Server-derived tenant, scoped predicates, composite FKs, FORCE RLS; real non-owner tests | Superuser and host compromise bypass app isolation |
| Broken auth / account takeover | Random 256-bit opaque tokens hashed in DB, expiry/revocation, no URL tokens; OIDC+MFA pilot gate | Manual provisioning token theft; device revocation delay offline |
| Function/property auth / mass assignment | Explicit Pydantic input allowlists, roles; caller cannot write tenant/AI/dispatch actor | Policy changes need regression review |
| SQL injection | Parameterised ORM and bound SQL; no caller-controlled identifiers | Migration/admin paths privileged |
| XSS | React text rendering, no HTML insertion; CSP, no localStorage token persistence | Browser extensions / dependency compromise |
| CSRF / session misuse | Bearer auth for mutations, exact CORS/Origin; no ambient auth cookie in foundation | OIDC cookie migration requires CSRF defence |
| SSRF / unsafe provider responses | Provider URL is administrator configuration; no arbitrary fetch from report URLs; bounded response validation and timeout | Approved endpoint compromise; DNS/network egress restrictions needed |
| Upload malware / resource exhaustion | Dedicated voice path enforces streamed 2 MB limit, PCM WAV structure, duration and energy gates, then stores only AES-GCM ciphertext in tenant RLS quarantine; local scanner boundary fails closed and release requires a clean verdict plus a different authorized user | Deterministic doubles prove the boundary, not malware detection; a pinned isolated scanner engine and adversarial corpus remain required |
| Bot / spam / duplicate floods | Request size cap, bounded batches, tenant quotas, rate limit, queue capacity and UUID idempotency | Distributed attacks need gateway protection and moderation |
| Poisoned messages / AI prompt injection | Content only input data; model has no tools/dispatch; provenance and human review | Human anchoring bias; adversarial multilingual text |
| AI false negative | Unknown/low-confidence stays visible in review queue; never hidden as harmless; evaluate per-language recall | Rule baseline misses paraphrases/negation |
| AI false positive | Urgency is suggestion, never an autonomous dispatch; operator can override | Wasted operator attention |
| Wrong location / unsafe merge | No invented coordinates; candidate ambiguity; no semantic auto-merge before evaluation; human override + split history | Same building can have distinct incidents; uncertain GPS |
| Compromised device / relay replay | Origin identity, sealed signed envelopes, bounded TTL/hops/seen store, final server UUID idempotency | Offline revocation; custody ACK is not server delivery |
| Lost writes / conflicting dispatch | Atomic transactions, durable queue, optimistic version checks and idempotency | Network partitions require human reconciliation |
| Secrets / data at rest | Secrets outside repo, encrypted disks/backups; scoped runtime DB role; rotate tokens | Local dev volumes are not application-encrypted; synthetic data only |
| Audit tampering | Critical actions same transaction; append-only audit with actor/action/time/target/version, no text | External tamper-evident archive not yet implemented |
| PII in logs / metrics | No payload/header logging; scrub errors; low-cardinality labels; restricted metrics route | Reverse-proxy/access logs require review |

## Role matrix

| Role | Read cases | Submit | Verify/override | Dispatch | Provision / retention |
|---|---|---|---|---|---|
| observer | yes, tenant | no | no | no | no |
| rescue-team | yes, tenant | yes | no | no | no |
| coordinator | yes, tenant | yes | yes | yes | no |
| admin | yes, tenant | yes | yes | yes | yes |

Foundation CLI provisioning is an administrative host operation, not an unauthenticated HTTP endpoint. Never accept role headers. Initial cross-border cooperation requires explicit organisation design; no automatic cross-tenant sharing.

## Retention and release gates

Emergency-end closure should schedule reviewed purge of text/audio/translations/embeddings, device caches and derived precise locations. Legal holds are specific, approved and expiring. Keep only legally reviewed minimal audit metadata; backup deletion/restore re-purge must be documented. No invented universal statutory day count.

Before pilot: test least-privilege PostgreSQL RLS, audit permissions, token revocation, concurrent dispatch, load/abuse, restore, deletion, dependency/container scans, pentest, verified phrase audio and location corpus, physical offline/relay tests, lawful basis/transfer review. National deployment adds institutional SLA/on-call/certification and government integrations.
