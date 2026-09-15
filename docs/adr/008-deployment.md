# ADR-008: Local Compose first, staged pilot gates

Context: single-laptop core and institutional ownership, no unearned production claim.

Decision: Compose PostgreSQL image with PostGIS+pgvector, migration job, scoped runtime API/worker, optional monitoring. Bind local ports to loopback. Generate secrets locally; never commit them. Dependency locks, CI scans and container checks before release.

Alternatives: Kubernetes immediately increases operational burden; bare scripts obscure reproducibility. Production orchestration selected only after institution capacity/HA review.

Consequences: Compose single host is not HA. Stage in isolated synthetic-data environment; before pilot validate TLS, encrypted storage/backup, restore, OTLP redaction, legal retention, OIDC/MFA and on-call. Scale API/model workers independently; PostgreSQL HA is an explicit infrastructure project, not achieved by restart policies.
