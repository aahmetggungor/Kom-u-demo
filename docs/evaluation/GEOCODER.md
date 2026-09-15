# Geocoder contract evidence — 2026-09-16

Komşu includes an optional Nominatim-compatible adapter for an explicitly configured self-hosted or contracted institutional service. It rejects public OpenStreetMap Nominatim origins, credentials in URLs, remote HTTP, redirects, unbounded bodies and invalid candidates. Only `address_raw` and language leave the worker; source messages and tenant/user identifiers do not.

The adapter now has a three-second timeout, two bounded retries, per-process five-request/second pacing, tenant-separated one-hour cache and a three-failure/30-second circuit breaker. Failure returns `GEOCODER_UNAVAILABLE`; the classifier output and original report remain reviewable. No candidate can become a case coordinate without the separate human verification API.

`data/geocoder-gold.synthetic.jsonl` has 12 PII-free TR/EL/EN address, street, neighbourhood, landmark, abbreviation and typo fixtures. `scripts/geocoder_contract_server.py` serves only exact authored fixture aliases on loopback. `scripts/evaluate_geocoder_contract.py` measured top-1 provider ID accuracy 1.0, precision-type accuracy 1.0, median error 0 m and unresolved fraction 0.0 overall and in each language.

These results are contract plumbing, not geocoding quality: each query maps directly to an authored fixture, the coordinates are exact and there is no real ambiguity, municipal index, live authentication, network SLA or field address distribution. No live URL or credential was used. Institutional requirements and pilot acceptance checks are in `docs/operations/GEOCODER_ONBOARDING.md`.
