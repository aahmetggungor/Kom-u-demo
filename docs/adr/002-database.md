# ADR-002: PostgreSQL, PostGIS, tenant RLS

Context: relational dispatch, spatial queries and strong tenant isolation (FUNC-015, EXT-007).

Decision: PostgreSQL with PostGIS geography/GiST, composite tenant foreign keys; non-owner runtime role, transaction-local RLS. Alembic snapshots schema. SQLite supports fast unit tests only, not PostgreSQL parity claims.

Alternatives: document database complicates transactional dispatch; separate geographic database duplicates consistency logic.

Consequences: one authority and backup path; DB is a shared failure domain. Use pool limits, query timeouts, read replicas only for stale-tolerant analytics, tested failover/PITR for pilot. Runtime must not be superuser/BYPASSRLS; auth bootstrap uses narrow SECURITY DEFINER function with fixed search_path and revoked public execution. RLS is defence in depth, not protection from a fully compromised app database credential that can set arbitrary context.
