# ADR-003: bge-m3 behind local embedding port; safe merge proposals

Context: cross-language duplicate noise versus catastrophic false merge (FUNC-007/008).

Decision: evaluate local bge-m3, 1024 dimensions. Separate report-vector table with model revision. Candidate scoring combines semantic/geo/time/entities; missing/conflicting building evidence blocks proposal. No autonomous merge in initial slice. UUID ingestion dedup is distinct from semantic clustering.

Alternatives: lexical matching fails paraphrases/cross-language; standalone vector DB adds replication/ops. pgvector starts exact tenant-scoped search; partitioned HNSW only after recall benchmark.

Consequences: conservative thresholds create extra review work but avoid hiding distinct incidents. Threshold values are hypotheses until labelled pair evaluation. Model outage skips semantic suggestions; reports still appear. Model weights pre-provisioned; no runtime downloads. Human merge/split must preserve provenance, aliases and counters before feature release.
