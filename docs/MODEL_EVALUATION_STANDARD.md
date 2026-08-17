# Model evaluation standard

No model or retrieval change is promoted on screenshots or selected examples.

## Required evaluation record

Every run records corpus snapshot/hash, query and annotation set version, split, model/index versions, parameters, random seeds, hardware, latency workload, and source code revision. Results include per-query or per-label outputs, not only averages.

Retrieval promotion reports Recall@5/10/50, MRR, nDCG@10, zero-result rate, source and occupation slices, and p50/p95/p99 service latency. A candidate must beat BM25 on held-out nDCG and Recall without an unacceptable latency or source-concentration regression.

Multi-label promotion reports micro and macro precision/recall/F1, exact match, label coverage, tail-label recall, reliability/calibration error, abstention rate, and employer/occupation/geography slices. Thresholds are tuned only on development data.

Candidate matching additionally requires evidence faithfulness, false-positive qualification rate, missing-skill accuracy, and counterfactual tests for names, schools, location, employment gaps, age proxies, disability proxies, and other protected or sensitive attributes. The ranker produces the match; an LLM may summarize only cited CV and listing passages afterward.

## Release gates

- Frozen, independently adjudicated held-out test set.
- No test-set tuning.
- Reproducible run from a clean checkout.
- Data and model cards updated.
- Error analysis for the worst queries and tail labels.
- Load test and cost report for the intended traffic profile.
- Shadow or offline evaluation before A/B exposure.
- Defined rollback trigger and prior model/index retained.

The current baseline does not pass these production gates. Its purpose is to make the gap measurable.

## Independent temporal protocol

The frozen `independent-temporal-evaluation-2026-07` protocol uses only source
publication timestamps. Its 2026-07-01 cutoff yields 616 training-side and 269
holdout records from the 2,701-record immutable corpus. Records without a source
publication time are excluded, nine posting families crossing the cutoff are
quarantined, and the measured family overlap is zero.

The protocol generates separate shuffled packages for two reviewer slots: 400
retrieval query-document pairs across 20 preregistered strata and 200
classification records. Employer/source identity, URLs, observation IDs, target
labels, retrieval ranks, and model scores are hidden. Package hashes bind every
submission to its exact tasks. Reviewers must be distinct and affirm independent
work; a distinct adjudicator must resolve every disagreement. Promotion remains
blocked unless weighted retrieval Cohen's kappa and binary classification
Cohen's kappa are each at least 0.60, mean classification label-set Jaccard is
at least 0.65, both tasks clear preregistered positive/negative-support floors,
and adjudication coverage is 100%. These support floors prevent vacuous high
agreement from all-zero judgments.

The machine-readable state is
`/api/ml/independent-evaluation-readiness.json`. It distinguishes the valid
source-publication split from a longitudinal observation-history holdout, which
does not yet exist.
