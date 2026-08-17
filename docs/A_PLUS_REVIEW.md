# A+ critical review

Review date: 2026-08-17. Verdict: **strong research prototype; not yet publication-grade or application-ready as a claimed ML platform**.

The current implementation is materially more honest than the initial prototype: fabricated scenario numbers are gone, the Apocalypso signal abstains, full eligible-set presence snapshots make disappearance meaningful, source failures fail closed, analysis versions are distinct from listing versions, boilerplate extraction is reduced, O*NET candidates abstain when uncertain, and retrieval/classification baselines have reproducible metrics.

## Scorecard

| Area | Grade | Evidence and judgment |
|---|---:|---|
| Research validity | B− | Unit of analysis and sampling caveats are now explicit. Four selected AI-native employers and a capped operational sample cannot support labor-market prevalence claims. |
| Longitudinal design | B | Append-only source/analysis ledger and full eligible-set daily snapshots now exist. Only one distinct day is observed; repost/entity resolution and deadline history remain incomplete. |
| Extraction/classification | C+ | Boilerplate and obvious short-token errors were corrected, rules are versioned, unsupported labor effect abstains, and a 13-record development benchmark exists. The benchmark is small, single-reviewer, partially title-selected, and no calibrated trained classifier exists. |
| Retrieval/ranking ML | C+ | Working BM25, fixed dense baseline, RRF, interaction reranker, deployed search, and six graded queries. BM25 currently beats fusion on aggregate nDCG; no learned embeddings, cross-encoder, held-out test, or latency benchmark. |
| O*NET normalization | C | Conservative occupation candidates cover 321/750 and abstain otherwise. Mappings are unreviewed; O*NET skill normalization is absent. |
| Licensing/provenance | B− | Metadata/evidence-only export, source links, hashes, manifests, and O*NET attribution are present. Source-by-source terms decisions and legal review of excerpts/training use are missing. |
| Forecasting discipline | B | Unsupported numeric forecasts were removed and the signal is null pending 30 days. No backtested forecast exists—which is preferable to a false one. |
| UX/accessibility | B− | Natural-language hybrid search, explicit error state, skip link, Escape-close, dialog semantics, pressed term state, and safe external links improved the surface. Drawer focus trap/restore, semantic table cells, mobile navigation, and automated accessibility tests remain. |
| Reliability/automation | C+ | Source count gates, build, lint, and data refresh exist. CI does not yet run ML evaluation/regression gates or deploy the direct-upload Cloudflare Pages project after a data commit. No source schema fixture tests or alerting exist. |
| Apocalypso integration | B | Version 2 uses explicit null semantics, history threshold, unit, cohort warning, and coverage context. A validated value and consumer contract test remain. |
| Publication readiness | C+ | Methods, architecture, evaluation standard, limitations, and public machine-readable metrics now exist. Dataset DOI/release, license file, data dictionary/schema, gold set, adjudication, and reproducible environment are still missing. |

## Publication blockers (P0)

1. Expand and independently adjudicate evaluation data. Six retrieval queries and 13 classification observations can only guard regressions; they cannot support CV claims or scientific conclusions.
2. Implement a true learned embedding baseline and cross-encoder candidate, with temporal held-out evaluation. Promote only if they beat BM25 under the evaluation standard.
3. Replace heuristic multi-label rules with a scored hierarchical baseline, calibrated thresholds, explicit abstention, and occupation/source/tail slices.
4. Complete source rights review. Record terms URL, review date, permitted retention, excerpt rule, redistribution, and training permission per source.
5. Accumulate at least 30 stable daily frames before publishing trend signals, and longer before forecasting. Backtest every forecast target.
6. Add O*NET skill normalization and human review of occupation mappings. Current occupation candidates are not validated labels.
7. Make deployment automatic and observable. The scheduled GitHub refresh currently commits data but does not prove that the direct-upload Cloudflare Pages deployment changed.

## High-priority engineering (P1)

- Store HTTP status, ETag/Last-Modified, response hash, latency, and feed schema version in retrieval manifests.
- Add canonical repost clusters using normalized employer/title/location plus content similarity and explicit confidence.
- Introduce JSON Schema for public corpus, snapshots, metrics, and Apocalypso; validate in CI.
- Add hand-built source fixtures for HTML cleaning, compensation units, title relevance, evidence selection, and ontology regressions.
- Run ML evaluation in CI and fail on missing qrels, metric calculation errors, unexplained large regressions, or test-set mutation.
- Measure browser search p50/p95/p99 now; move retrieval to a versioned service before corpus size makes client computation expensive.
- Finish WCAG testing with keyboard focus trapping/restoration, semantic table structure, visible mobile navigation, and axe/Playwright checks.
- Add a data dictionary, repository/content license, citation file, release checksums, and changelog.

## Technical Fellow evidence bar

The defensible CV bullet today is limited: Jobservatory has a provenance-aware 750-record public corpus from six feeds, durable version/analysis lineage, a browser hybrid retrieval baseline, six-query retrieval metrics, and a small multi-label regression set. It is not yet defensible to claim semantic retrieval, cross-encoder reranking, extreme multi-label classification, calibrated predictions, low-latency serving, market trends, or forecasting.

The application-ready bar is reached only when the P0 items are completed and a clean checkout reproduces the held-out metrics and latency report. The most valuable current result is negative but rigorous: on the small development set, BM25 nDCG@10 exceeds the present dense-hash and fusion baselines. That finding gives the next learned retrieval experiment a real hurdle.
