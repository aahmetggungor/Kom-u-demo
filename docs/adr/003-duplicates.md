# ADR-003: bge-m3 behind local embedding port; safe merge proposals

Context: cross-language duplicate noise versus catastrophic false merge (FUNC-007/008).

Decision: evaluate local bge-m3, 1024 dimensions. Separate report-vector table with model revision. Candidate scoring exposes weighted semantic, location-quality/distance, time, address-marker and need-overlap contributions. Missing place evidence prevents a strong candidate; conflicting building numbers, excessive distance and time are explicit blockers. Address markers never claim verified building identity. No autonomous merge in the initial slice; only the existing versioned, reasoned human action can merge. UUID ingestion dedup is distinct from semantic clustering.

Alternatives: lexical matching fails paraphrases/cross-language; standalone vector DB adds replication/ops. pgvector starts exact tenant-scoped search; partitioned HNSW only after recall benchmark.

Consequences: conservative thresholds create extra review work but avoid hiding distinct incidents. The same-author synthetic 60/60 event split scored perfectly because address numbers and coordinates make it easy; its 0.85 threshold is not promoted. Threshold values remain hypotheses until independently labelled pair evaluation with missing/noisy locations and nearby-building negatives. Model outage skips semantic suggestions; reports still appear. Model weights are pre-provisioned with no runtime downloads. Human merge/split preserves original reports, audit and version checks.
