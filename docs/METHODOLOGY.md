# Methodology and corpus coverage contract

## What the corpus represents

The current corpus is a capped, source-stratified set of direct or strongly AI-applied listings from 53 selected employer career feeds across Greenhouse, Lever, and Ashby. Thirty-seven declared sectors include frontier-model and safety research, AI cloud and data platforms, defense robotics, autonomous vehicles, enterprise software and search, AI agents, healthcare and biotech, fintech, industrial IoT, legal technology, agriculture, energy, manufacturing, professional services, travel, mobility, commerce, design, education, consumer platforms, and media and interactive entertainment. It is global, employer-concentrated, and not representative of the US or global labor market. “Comprehensive” means all rule-eligible listings within the versioned source registry, subject to a published 5,000-observation cap; it is not a synonym for the whole labor market or a high row count.

The public coverage assessment makes expansion falsifiable. Its current targets are at least 50 employers and 25 sectors, no employer above 15% of published observations, at least 65% compensation coverage, and presence across 15 required sectors. The employer and sector-count targets now pass. The current status remains `expanding`: the largest employer contributes 18.55%, compensation coverage is 62.6%, and public-sector sources remain an explicit gap.

The unit of analysis is a listing observation at a retrieval time. Listing versions and analysis versions are separate. A source text can remain unchanged while the ontology or extraction method changes.

## Inclusion and sampling

A listing is eligible as `direct` when versioned rules find an AI term in its title, or as `applied` when at least two AI method terms occur in the role-focused description. The collector excludes weaker `contextual` matches and trims common employer, compensation, privacy, and equal-opportunity boilerplate before classification. If eligible records exceed the publication cap, allocation is proportional to eligible source volume with a minimum source floor. Retrieval manifests publish fetched, eligible, and selected counts.

This is a deterministic operational sample, not a probability sample. Employer comparisons must use within-source rates or explicitly reweighted cohorts. Raw counts must never be described as market share.

## Provenance and rights

The public export retains metadata, hashes, derived fields, and short evidence excerpts linked to the source. Full descriptions are processed transiently and are not republished. Public API availability does not itself establish a license to republish, redistribute, or train on content. Each source needs a recorded terms/licensing review before expansion, and excerpt retention should receive legal review.

O*NET occupation candidates cite the [O*NET Database](https://www.onetcenter.org/database.html), record taxonomy version 30.3, and remain explicitly inferred and unreviewed. Exact record-level software mappings require both listing evidence and an O*NET occupation-linked workplace example. Separately published essential and transferable skill profiles are inherited occupational context, not listing-stated requirements. The compact derived ontology pins official file hashes and carries the required CC BY 4.0 attribution and modification notice.

## Labels

Source facts include employer, source title, location string, source timestamps, URL, and explicitly parsed compensation. Rule-derived fields include direct-role relevance, seniority, domain, skill labels, system layers, AI relationship, maturity, human role, and O*NET occupation.

Every rule-derived field must expose method and ontology versions. Unsupported labor effects abstain as `unclassified`; the system does not assign augmentation by default. A short source span supports a rule match, but a span is not proof that the normalized label is correct.

## Longitudinal analysis

The append-only version ledger preserves new source or analysis versions. Daily presence snapshots cover the full eligible set, so disappearance is not inferred from movement across the 5,000-record publication cap. Same-day refreshes replace that day's aggregate frame.

Entity resolution uses two stable, versioned metadata keys. A posting family matches normalized employer and title and may span locations; an exact-variant group additionally matches normalized location. Family and exact-variant confidence values describe the strength of that metadata rule, not the probability of a shared requisition. Every group remains `unreviewed`, and the public record explicitly states that a match does not prove a repost. Exact-variant groups can prevent obvious train/evaluation leakage while human adjudication and content-similarity validation remain pending.

Trend publication requires at least 30 distinct daily frames, a stable source cohort, per-source denominators, and sensitivity analysis for feed outages and cohort changes. Term counts from one date are frequencies, not emergence. A removed listing is “no longer observed,” not “filled” or “eliminated.”

## Evaluation

Retrieval reports Recall@5, Recall@10, MRR, and nDCG@10 over committed graded judgments. Classification reports micro/macro F1, precision, recall, exact match, tail-label recall, and prediction coverage. The existing labeled sets are small, single-reviewer development fixtures. A separate frozen 2,701-record corpus now supports an unlabeled independent protocol with 20 query strata, 400 retrieval pairs per reviewer, and 200 hierarchical classification records per reviewer. The 2026-07-01 source-publication cutoff leaves 616 training candidates and 269 holdout candidates after nine crossing posting families are quarantined; measured posting-family leakage is zero. This is valid publication-time separation within one retrieved corpus, not longitudinal observation-history evidence. It cannot support promotion until two distinct reviewers finish both blind packages, a distinct adjudicator resolves every disagreement, and the agreement thresholds pass.

The versioned hierarchical candidate uses title/location TF-IDF, per-label logistic regression, held-partition Platt calibration, explicit threshold-band abstention, and deterministic parent consistency. Its metrics measure weak-rule agreement only, so its promotion gate rejects it. Annotation guidelines, hashed blind packages, temporal and posting-family separation, two-reviewer validation, agreement statistics, fail-closed adjudication, and gated gold finalization are implemented. Real independent annotations and sufficient adjudicated tail-label support remain outstanding.

## Forecasting and Apocalypso

No numeric forecast is currently published. Previous hard-coded scenario percentages were removed because they were not model outputs. Apocalypso emits a null signal with `insufficient_history` until the minimum history and cohort requirements are met. Future forecasts must specify target, horizon, baseline, backtest, uncertainty interval, and failure threshold.
