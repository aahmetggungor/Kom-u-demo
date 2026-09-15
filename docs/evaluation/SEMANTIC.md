# Local semantic retrieval

2026-09-15: actual BAAI/bge-m3 weights loaded locally with restricted PyTorch loading, no remote code, CPU inference, 512-token dense normalized embeddings. Revision and SHA-256 are recorded in `bge-provenance.json`. Twelve synthetic demo reports were encoded into PostgreSQL; the browser displayed ranked suggestions and opened the selected original report for human comparison.

The six-text authored diagnostic in `bge-diagnostic.json` is deliberately small and does not estimate production precision/recall. Against a Turkish trapped-person report, cosine scores were 0.794 for its English counterpart, 0.695 for Greek, **0.958 for a different building number**, and 0.733 for a negated rescue need. Consequently no semantic threshold alone authorizes merge or dispatch. Location/time evidence is shown separately; building identity remains unverified. Model load took 14.927 seconds and six-text encoding 0.995 seconds on this CPU run; this is not a throughput benchmark.

Retrieval is exact at development scale, limited to five distinct OPEN cases, same tenant/model revision, and report times within 24 hours of source reports. Up to 50 semantic neighbours are rescored and the top five comparisons are returned. The response separates semantic, location-quality/distance, time, address-marker and need-overlap signals and their weighted contributions. Location basis is `BOTH_CONFIRMED`, `REPORTED_OR_MIXED` or `MISSING`; it is never silently upgraded. Conflicting building numbers, distance over 500 m and time outside 24 hours are blockers. Address text markers are evidence, not verified building identity. There is no automatic grouping and no claim that all true duplicates are returned. Missing embeddings are picked up by an explicit batch or local `--watch` worker; stale model revisions are not mixed. PostgreSQL tests cover tenant isolation, revision isolation, time exclusion, identical-vector similarity, signal output and endpoint authorization.

Remaining work: embedding process supervision, independent labelled multilingual pairs, hard negatives from real nearby buildings/landmarks and changing needs, calibrated proposal policy, larger-scale tenant-aware retrieval benchmarks, and deployment-specific resource limits.

## 240-message template stress diagnostic

`duplicate-retrieval-diagnostic.json` selects 80 three-language event groups from the development corpus and removes the explicit `[SYNTHETIC SITE n]` suffix before embedding. It evaluates 240 same-event cross-language pairs against 228 different-event, same-language, same-template hard negatives.

- Semantic recall@1 was 0.0 for TR, EL and EN because identical same-language templates from other events outranked cross-language counterparts.
- Every hard-negative percentile was cosine 1.0. At cosine 0.92, semantic-only precision was 0.1493 and recall 0.1667 on this artificially balanced pair set.
- The combined gate produced zero false proposals and 1.0 precision but only 0.1667 recall. This is not deployable precision evidence: the test supplied exact same-building truth directly from gold labels, while Komşu does not yet extract a reliable building identity.

The corpus was authored during development and repeats templates, so it cannot estimate field duplicate accuracy. It is useful as a counterexample: language/need wording and semantic similarity cannot identify an incident without trustworthy place/entity/time evidence. Automatic merge remains disabled.

## Explainable multi-signal candidate diagnostic — 2026-09-16

The updated diagnostic uses 120 disjoint synthetic event groups: events 0–59 for threshold development and 60–119 as a held-out test. It encodes 360 messages with the same pinned bge-m3 revision. Each positive is a cross-language report from the same synthetic event; each hard negative is a same-language, same-template report from a different event/building. The scorer uses only report fields available at runtime, rather than passing the gold `same_building` label into the gate.

The predeclared selection rule required zero development false candidates, then maximized F1, recall and threshold. It selected 0.85. Held-out results were precision/recall/F1 1.0 and false-merge-candidate rate 0.0 for TR, EL and EN (360 directed positives, 168 hard negatives). Runtime 0.68 produced the same synthetic result and was left unchanged.

This perfect number is not promotion evidence. The generator repeats four templates, puts an explicit synthetic building number in every address and supplies exact fixture coordinates. These signals almost reveal the gold grouping directly. `duplicate-retrieval-diagnostic.json` records `NOT_PROMOTED_SAME_AUTHOR_SYNTHETIC_ADDRESS_MARKERS`. Field promotion still requires independently labelled event pairs, realistic address errors/transliteration, nearby-building negatives, missing/incorrect coordinates and adjudicated false-merge cost. The UI describes a review candidate; only the existing versioned human merge endpoint can combine cases.
