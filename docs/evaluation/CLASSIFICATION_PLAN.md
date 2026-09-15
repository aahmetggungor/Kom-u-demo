# Need and urgency candidate evaluation plan

Date: 2026-09-15. This plan applies only to authored synthetic data. The existing 3,000-row corpus repeats four templates and is suitable for regression/training plumbing, not field validation. Its `gold.group` keeps all three language variants of one event in the same deterministic train/internal-validation partition. Site markers are stripped before model fitting.

The previously inspected 18-row challenge set is development data. It may be used for rules and threshold selection and must never be reported as held-out performance. `data/classification-holdout.synthetic.jsonl` is a separate 36-row authored check covering explicit and indirect rescue, medical, shelter, water and food needs, negation, ended exercises, ambiguity, multiple needs and numbers. It was frozen before the repeatable evaluation script was written, but its author and implementer are the same; it is still not independent validation. Greek wording and labels require native-speaker review.

Candidates:

1. `rules-0.1`, the deployed baseline.
2. `rules-0.2-candidate`, explicit multilingual patterns with class-specific absence handling, ended-exercise handling, ambiguity/number warnings and mandatory human review.
3. A local scikit-learn character TF-IDF plus class-balanced logistic regression experiment. It trains only on the template corpus, tunes a global decision threshold only on the development challenge and runs without remote inference. A need absent from training is always unavailable rather than fabricated.

Before viewing repeatable results, a candidate is considered technically eligible for a later development-default decision only if the authored holdout has overall need precision and recall at least 0.85, every language has recall at least 0.80, rescue and medical recall are at least 0.90, urgency accuracy is at least 0.85 and there are zero false negatives on numbered rescue/medical examples. Regardless of these synthetic thresholds, the deployed default remains unchanged until an independently labelled, de-identified set receives Turkish and Greek native-speaker/domain review. Every result must keep `human_review_required=true`; classification cannot suppress a report, merge a case or dispatch a team.

Run `python scripts/evaluate_classification.py`. The output records dataset digests, library/config provenance, split counts, selected threshold, per-language and per-need metrics, urgency accuracy and row-level failures without changing runtime configuration.
