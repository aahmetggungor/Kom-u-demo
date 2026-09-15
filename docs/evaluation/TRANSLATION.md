# Local translation evidence — 2026-09-16

Komşu contains an optional offline Marian adapter for Turkish, Greek and English. It preserves the original report, translates only into a separate annotation, and never feeds translation back into classification, coordinates, duplicate grouping, priority or dispatch. Missing or failed routes degrade to `PARTIAL` or `UNAVAILABLE`.

## Active pack

| Route | Pinned repository | License | Weight format / bytes |
|---|---|---|---|
| TR→EN | `Helsinki-NLP/opus-mt-tr-en@19c654...` | Apache-2.0 | PyTorch / 306,727,185 |
| EN→TR | `Helsinki-NLP/opus-mt-en-trk@f9d8f...` | Apache-2.0 | PyTorch / 305,260,005 |
| EL→EN | `Helsinki-NLP/opus-mt_tiny_ell-eng@beff0d...` | Apache-2.0 | safetensors / 50,743,442 |
| EN→EL | `Helsinki-NLP/opus-mt-en-el@165367...` | Apache-2.0 | PyTorch / 311,727,909 |

The full immutable revisions and SHA-256 values are in `translation-provenance.json`. `download_translation_models.py` fetches only named files from those revisions and verifies each weight. The runtime rechecks the weight digest on first load, uses `local_files_only=True`, `trust_remote_code=False` and a restricted weight loader, limits input to 512 tokens/output to 192 tokens, and keeps at most two routes resident. EN→TR adds the model card's required `>>tur<<` target token. TR↔EL records its English pivot and both revisions.

## Safety-span candidate

`placeholder-terminology-1` builds a deterministic registry for numerals, constrained address/name forms, negation and a small disaster glossary. An initial experiment passed opaque placeholders through Marian; the models mutated those tokens and degraded the sentence, so that design was rejected. The implemented candidate translates the intact sentence and checks the registry afterward. A missing value is appended as a visible `⟦recovered value⟧` annotation and receives a `PROTECTED_*_RECOVERED` warning. It is never silently blended into model prose. Route, immutable model revisions, pivot, protection version, protected categories and warnings remain in per-target provenance.

This mechanism makes an omitted fact visible but cannot prove that it belongs to the correct clause or that the remaining sentence is adequate. It therefore remains a candidate and does not change the default disabled model configuration.

## Diagnostic result

`python scripts/evaluate_translation.py` ran six authored emergency-like sentences. This is a development smoke set, not independent or native-speaker validation.

| Check | Raw OPUS | Guarded candidate |
|---|---:|---:|
| Every source numeral appears in output | 3 / 6 | 6 / 6 |
| Verbatim selected name retained or visibly recovered | 0 / 6 | 6 / 6 |
| Target negation marker detected or visibly recovered | 1 / 4 | 4 / 4 |
| Expected constrained disaster term present | 6 / 6 | 6 / 6 |

The direct TR→EN and EN→TR examples dropped a negative instruction. EL→EN also dropped the clause saying water was unnecessary. Pivot examples wrote number words instead of digits, so some numeral failures may preserve quantity semantically; the coordinator still cannot assume that without reading the source. Exact-name matching counts transliteration as failure. The candidate makes the source markers visible but has not been rated for adequacy or critical errors, so `promotion_decision` remains `NOT_PROMOTED_PENDING_NATIVE_SPEAKER_REVIEW`.

A larger legacy EL→EN candidate was rejected after producing incoherent English under the pinned runtime; `translation-rejected-model.json` records the exact revision/checksum and bounded excerpt. The active smaller model produced coherent text in the same smoke case but still omitted negation.

## Operational boundary

The web case panel labels AI output and route, flags pivots, displays automatic guardrail/recovery warnings, and keeps the original immediately above it. Human review remains mandatory. Translation cannot feed classification, suppression, grouping, priority or dispatch.

`scripts/export_translation_review.py` creates UTF-8 CSV and JSON under `translation-review-package/`. The supplied cases are synthetic and contain no real incident or personal data. Reviewers score adequacy, meaning, critical errors, quantities, names/addresses, negation and terminology without supplying identity. Each immutable source/output row has a SHA-256 digest. `scripts/import_translation_review.py` rejects altered rows and invalid ratings, then emits aggregate counts/rates without reviewer notes. No completed review exists yet.

Before a pilot, Turkish-, Greek- and English-native disaster-domain reviewers must complete all six directions on a larger locked, independently authored, consented/de-identified corpus. The current six cases do not establish general translation quality.
