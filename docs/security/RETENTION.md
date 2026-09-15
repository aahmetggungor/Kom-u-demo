# Retention execution and legal holds

Migrations `0003`, `0004` and `0005` implement a tenant-scoped, reviewed development workflow. The system does not invent a statutory retention period: an administrator supplies a past cutoff and a future execution time using an approved reason code. A second administrator must approve the plan. The requester cannot self-approve. A scheduled or approved plan can be cancelled without deleting data.

An administrator may register an expiring legal hold with a bounded reason code. An active, unreleased hold blocks execution for the entire tenant. Holds can be released explicitly; expired and released holds remain as metadata. The current schema is tenant-wide because the development model has no first-class emergency/incident container. Case- or incident-specific holds require that model before pilot use.

Execution is deliberately unavailable through the browser/API. From an administrative environment, after reviewing the plan preview and active holds:

```powershell
komsu execute-retention --plan PLAN_UUID --confirm PLAN_UUID
```

The exact plan UUID must be repeated. The command requires `KOMSU_ADMIN_DATABASE_URL`, locks the plan, confirms `APPROVED` status, checks the execution time and rejects any active legal hold. It then deletes matching encrypted audio assets and report embeddings; redacts source report text, language, raw address, report coordinates, analysis and payload digest; clears derived case coordinates, region, needs and AI confidence; deletes the matching PostGIS index row; redacts free-text review reasons; and deletes map layers last updated by the cutoff. Counts are stored on the executed plan. Tenant IDs, entity IDs, timestamps, bounded reason codes, statuses, dispatch metadata and the non-PII audit trail remain for review.

The PostgreSQL test uses synthetic data to prove distinct approval, wrong-confirmation rejection, active-hold blocking, hold release, encrypted-audio deletion, report/derivative redaction, spatial row deletion, cancellation and cross-tenant isolation. It does not prove legal sufficiency. Before a real pilot, counsel must approve the inventory, lawful basis, period per data class, legal-hold authority, audit metadata, backups, client caches and cross-border behavior.

Known gaps: backup copies are not automatically re-purged, Android cache purge receipts are absent, audio key rotation and quarantined-to-transcription approval are not implemented, and no remote backup lifecycle exists. The local restore exercise in `docs/evaluation/local-restore.json` demonstrates restore plus forward migration only; it is not disaster recovery or high availability validation.
