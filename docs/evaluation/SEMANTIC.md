# Local semantic retrieval

2026-09-15: actual BAAI/bge-m3 weights loaded locally with restricted PyTorch loading, no remote code, CPU inference, 512-token dense normalized embeddings. Revision and SHA-256 are recorded in `bge-provenance.json`. Twelve synthetic demo reports were encoded into PostgreSQL; the browser displayed ranked suggestions and opened the selected original report for human comparison.

The six-text authored diagnostic in `bge-diagnostic.json` is deliberately small and does not estimate production precision/recall. Against a Turkish trapped-person report, cosine scores were 0.794 for its English counterpart, 0.695 for Greek, **0.958 for a different building number**, and 0.733 for a negated rescue need. Consequently no semantic threshold alone authorizes merge or dispatch. Location/time evidence is shown separately; building identity remains unverified. Model load took 14.927 seconds and six-text encoding 0.995 seconds on this CPU run; this is not a throughput benchmark.

Retrieval is exact at development scale, limited to five distinct OPEN cases, same tenant/model revision, and report times within 24 hours of source reports. Scores are cosine similarities, not calibrated probabilities. There is no automatic grouping and no claim that all true duplicates are returned. Missing embeddings are picked up by an explicit batch or local `--watch` worker; stale model revisions are not mixed. PostgreSQL tests cover tenant isolation, revision isolation, time exclusion, identical-vector similarity and endpoint authorization.

Remaining work: embedding process supervision and operational metrics, independent labelled multilingual pairs, hard negatives across nearby buildings and changing needs, calibrated proposal policy, larger-scale tenant-aware retrieval benchmarks, and deployment-specific resource limits.

## 240-message template stress diagnostic

`duplicate-retrieval-diagnostic.json` selects 80 three-language event groups from the development corpus and removes the explicit `[SYNTHETIC SITE n]` suffix before embedding. It evaluates 240 same-event cross-language pairs against 228 different-event, same-language, same-template hard negatives.

- Semantic recall@1 was 0.0 for TR, EL and EN because identical same-language templates from other events outranked cross-language counterparts.
- Every hard-negative percentile was cosine 1.0. At cosine 0.92, semantic-only precision was 0.1493 and recall 0.1667 on this artificially balanced pair set.
- The combined gate produced zero false proposals and 1.0 precision but only 0.1667 recall. This is not deployable precision evidence: the test supplied exact same-building truth directly from gold labels, while Komşu does not yet extract a reliable building identity.

The corpus was authored during development and repeats templates, so it cannot estimate field duplicate accuracy. It is useful as a counterexample: language/need wording and semantic similarity cannot identify an incident without trustworthy place/entity/time evidence. Automatic merge remains disabled.
