# ADR-005: Room as UI truth, immutable report UUIDs

Context: offline reporting must survive process death (FUNC-011, EXT-008).

Decision: Room stores report and queue state before UI success; WorkManager network-constrained durable retry; same UUID and immutable content until server receipt. Conflict retains local content for operator resolution. Task edits use expected server version; never last-write-wins dispatch.

Alternatives: memory queue loses data; network-first form blocks in disasters; timestamp-wins trusts device clock.

Consequences: eventual sync, explicit pending/failed/conflict indicators, startup recovery for stale SYNCING claims. WorkManager is not an immediate execution guarantee. Auth refresh/401 pauses with visible action. App private storage/backup exclusion initially; encryption and managed-device controls remain pilot gates. Scale with bounded batches and jitter.
