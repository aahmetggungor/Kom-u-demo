# ADR-004: Transactional PostgreSQL jobs and events

Context: acknowledged reports must survive API/worker crashes; laptop setup should remain small.

Decision: report/case/job/audit in one transaction; leased jobs with SKIP LOCKED and claim fencing; bounded retry; case/event result transaction. Tenant row lock serialises event-writing commits to prevent sequence cursor skipping uncommitted lower IDs. First deployment has one worker per tenant; configurable tenant binding uses non-owner role.

Alternatives: Redis-only queue risks dual-write gaps; RabbitMQ/Kafka plus outbox adds operations but is an eventual scale path.

Consequences: at-least-once processing, idempotent application; no exactly-once promise. Tenant lock is a deliberate throughput bottleneck to benchmark. Large tenants later use durable broker offsets/outbox dispatcher and partitioned case locking. DB outage refuses ingress with retry; model failures retain reviewable source. Queue quotas limit one tenant starving resources, gateway shared quota still needed across replicas.
