# Institutional geocoder onboarding

Updated 2026-09-16. No live institution geocoder or credentials have been supplied. The current evidence uses only the localhost synthetic contract server and must not be treated as provider acceptance.

## Information the institution must provide

- Service owner, 24/7 operational contact, incident/escalation path and maintenance windows.
- HTTPS origin dedicated to the institution or its contracted processor. Public `nominatim.openstreetmap.org` and other `*.openstreetmap.org` endpoints are rejected by code.
- Authentication method outside the URL: preferably mTLS or a scoped service token delivered through the deployment secret store. Credentials must never enter Git, report text, query logs or screenshots.
- Network allowlists, DNS names, certificate chain/rotation schedule, egress proxy requirements and development/staging endpoints.
- Nominatim-compatible `/search` contract or an approved mapping: request parameters, response fields, precision taxonomy, maximum response size, status codes, retry guidance and version/provenance identifier.
- Licensed coverage for Türkiye/Greece pilot regions, supported TR/EL/EN transliteration, update frequency, source/licence attribution and restrictions on caching or derived coordinates.
- Rate and burst limits, expected p50/p95/p99 latency, uptime/SLA, outage notifications and disaster-mode capacity.
- Data-processing roles, lawful basis, cross-border transfer decision, retention/deletion periods, access controls, provider log policy, sub-processors and breach notification terms.
- A PII-reviewed, consented/de-identified gold corpus with addresses, neighbourhoods, streets, building numbers, landmarks, common abbreviations/typos, expected candidate identifiers and adjudicated coordinates. Real incident text is not required and must not be sent as a geocoder query.

## Komşu request and safety contract

Komşu sends only the explicit `address_raw` field, requested language, result limit five and no report body, need labels, tenant identifier or user token. The tenant identifier remains only in a local SHA-256 cache key. Responses are capped at 64 KiB and five candidates; coordinates, types and strings are schema-validated. Cache entries expire after one hour and are process-local.

The adapter uses a three-second timeout, at most two retries with bounded backoff, five requests/second per worker by default and a circuit breaker after three failed calls. These defaults must be reconciled with the institutional SLA before deployment. Remote HTTP is rejected. Redirects and environment proxy inheritance are disabled.

Candidates never write case coordinates. Even a high-scoring building result remains `CANDIDATE_REQUIRES_REVIEW`; ambiguous, street or area results remain `AMBIGUOUS_LOCATION`. A coordinator must independently check and submit the existing versioned verification action with a reason before coordinates can affect dispatch.

## Acceptance evidence required before pilot

1. Run the contract suite against staging with synthetic inputs and record provider/version, certificate and timestamps.
2. Run the locked institutional gold set with top-k recall, unresolved fraction, precision-type accuracy and median/p95 distance error separately for TR, EL and EN.
3. Exercise timeout, 429, 5xx, malformed/oversized JSON, slow response, certificate/DNS failure, circuit open/recovery and cache expiry. Confirm the original case stays reviewable without coordinates.
4. Verify that provider, reverse-proxy and telemetry logs contain no report body, tokens or tenant/user identifiers and follow the approved retention plan.
5. Perform rate/load testing within the agreed staging quota and document failover/manual coordination.
6. Obtain service owner, security/privacy, legal and pilot operations sign-off. Store evidence links and expiry/review dates in the deployment record.

## Local contract use

```powershell
python scripts/geocoder_contract_server.py --port 8765
$env:KOMSU_GEOCODER_URL='http://127.0.0.1:8765'
python scripts/evaluate_geocoder_contract.py
```

The fixture is PII-free and synthetic. Its authored typo aliases map directly to known rows, so perfect results only prove request/response plumbing and guardrails.
