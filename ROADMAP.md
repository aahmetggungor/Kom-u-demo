# Vertical-slice roadmap

1. **Receive and review** (FUNC-003/005/014/016, EXT-001/006/010): authenticated text ingress → durable report/job → baseline suggestions → case list/detail → human review; tenant/idempotency/failure tests.
2. **Locate safely** (FUNC-006/010, EXT-004/005): original address → self-host geocoder candidates → map with uncertainty → human location confirmation; ambiguous and distinct-building gold set.
3. **Reduce duplicate noise** (FUNC-007/008, EXT-003): bge-m3 + geo/time/entities → proposed groups → merge/split review → counts; multilingual adversarial pairs and duplicate precision.
4. **Operate offline** (FUNC-011/012, EXT-008): Compose report → Room queue → authenticated idempotent API → dashboard → status on device; process death/retry/conflict tests, professionally verified phrase/audio pack.
5. **Relay across devices** (FUNC-013, EXT-009): sealed signed envelopes → explicitly enabled transport → A/B/C store-and-forward → ingress dedup → delivery receipts; physical device/OS matrix.
6. **Coordinate a team** (FUNC-009/016, EXT-005/007): team/case assignment, translator provider, authorized human dispatch and override → event/history → mobile cached task; authorization and race tests.
7. **Voice and additional sources** (FUNC-002/004/017): authenticated adapters/quarantined voice → Whisper → original/provenance → review; upload abuse and provider outage tests.
8. **Pilot rehearsal** (FUNC-018/019, NFR-001/002/004, EXT-012..021): reproducible earthquake/flood/fire simulations, per-language evaluation, load/failure/restore drills, retention, field/legal/security acceptance. No throughput guarantee before measurement.
