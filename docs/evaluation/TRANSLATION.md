# Local translation evidence — 2026-09-15

Komşu contains an optional offline Marian adapter for Turkish, Greek and English. It preserves the original report, translates only into a separate annotation, and never feeds translation back into classification, coordinates, duplicate grouping, priority or dispatch. Missing or failed routes degrade to `PARTIAL` or `UNAVAILABLE`.

## Active pack

| Route | Pinned repository | License | Weight format / bytes |
|---|---|---|---|
| TR→EN | `Helsinki-NLP/opus-mt-tr-en@19c654...` | Apache-2.0 | PyTorch / 306,727,185 |
| EN→TR | `Helsinki-NLP/opus-mt-en-trk@f9d8f...` | Apache-2.0 | PyTorch / 305,260,005 |
| EL→EN | `Helsinki-NLP/opus-mt_tiny_ell-eng@beff0d...` | Apache-2.0 | safetensors / 50,743,442 |
| EN→EL | `Helsinki-NLP/opus-mt-en-el@165367...` | Apache-2.0 | PyTorch / 311,727,909 |

The full immutable revisions and SHA-256 values are in `translation-provenance.json`. `download_translation_models.py` fetches only named files from those revisions and verifies each weight. The runtime rechecks the weight digest on first load, uses `local_files_only=True`, `trust_remote_code=False` and a restricted weight loader, limits input to 512 tokens/output to 192 tokens, and keeps at most two routes resident. EN→TR adds the model card's required `>>tur<<` target token. TR↔EL records its English pivot and both revisions.

## Diagnostic result

`python scripts/evaluate_translation.py` ran six authored emergency-like sentences. This is a development smoke set, not independent or native-speaker validation.

| Check | Observed |
|---|---:|
| Every source numeral appears in output | 3 / 6 |
| Verbatim selected name retained | 0 / 6 |
| Target negation marker detected | 1 / 4 negation cases |

The direct TR→EN and EN→TR examples dropped a negative instruction. EL→EN also dropped the clause saying water was unnecessary. Pivot examples wrote number words instead of digits, so some numeral failures may preserve quantity semantically; the coordinator still cannot assume that without reading the source. Exact-name matching also counts transliteration as failure. These caveats do not remove the observed critical omissions.

A larger legacy EL→EN candidate was rejected after producing incoherent English under the pinned runtime; `translation-rejected-model.json` records the exact revision/checksum and bounded excerpt. The active smaller model produced coherent text in the same smoke case but still omitted negation.

## Operational boundary

The web case panel labels AI output and route, flags pivots, displays automatic numeral/negation warnings, and keeps the original immediately above it. Human review remains mandatory. Before a pilot, bilingual disaster-domain reviewers need a locked, consented/de-identified corpus and must measure adequacy, critical-error rate, names, addresses, quantities, negation and instruction polarity separately for all six directions.
