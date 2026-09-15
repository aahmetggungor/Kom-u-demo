# Evaluation limits — 2026-09-14

The 3,000-message corpus repeats four templates across 1,000 synthetic multilingual event groups. Its perfect current need metrics measure template regression only. A Turkish water suffix was added after seeing a miss on this corpus, so this is also a development set, not held-out validation.

The separate 18-message challenge set contains six authored examples per language: negation, implicit water/shelter/food requests, explicit rescue/medical needs and an ended exercise. Current micro precision is 0.60, recall 0.50 and F1 0.545 in each language. Need exact match is 2/6. These matching results follow parallel authored examples, not statistically equivalent language performance. Greek text and all labels need independent native-speaker/domain review.

This small challenge exposes concrete failures: keyword presence overcalls negated injuries/trapped people, while indirect descriptions of thirst, homelessness and hunger are missed. The baseline keeps every report visible and requires human review; these controls do not establish operational safety. Do not use scores to suppress reports or authorize dispatch.

`baseline-results.json` and `challenge-results.json` are reproducible via `scripts/evaluate.py`. Inference latency is local in-process rule execution, excluding HTTP, database, queues, geocoding and human review. Unmeasured location, duplication and time-to-triage fields remain null.

`translation-diagnostic.json` is a six-case authored smoke set over four direct directions and both EN-pivot directions. All numerals were retained in 3/6 cases, a target-language negation marker in 1/4 negation cases, and selected proper names verbatim in 0/6. Transliteration can make verbatim name checking pessimistic, while the negation lexicon can miss semantically valid wording; neither is a BLEU/COMET score. The concrete dropped clauses/numbers still show that these outputs cannot drive rescue decisions. `translation-pipeline-smoke.json` proves route/model provenance and warnings survive the actual pipeline. No bilingual human adequacy review has been performed.

Next validation needs independently labelled, consented/de-identified multilingual incident data, incident-level train/test separation, native-speaker review, confidence calibration, per-class false-negative analysis and an actual end-to-end load benchmark. Keep a locked challenge set before further model tuning.

`whisper-diagnostic.json` reports two clean Windows TTS fixtures, one TR and one EN, with micro WER 0.3793. Synthetic TTS is much easier and less varied than telephone/field audio; it is a plumbing smoke test. No Greek clip, real voice, noise/accent matrix, hallucination measurement or automatic language-detection evaluation exists. The adapter remains disconnected from ingestion.
