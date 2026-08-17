# A+ critical review

Review date: 2026-08-17. Verdict: **strong research prototype; not yet publication-grade or application-ready as a claimed ML platform**.

The current implementation is materially more honest than the initial prototype: fabricated scenario numbers are gone, the Apocalypso signal abstains, full eligible-set presence snapshots make disappearance meaningful, source failures fail closed, analysis versions are distinct from listing versions, boilerplate extraction is reduced, O*NET candidates abstain when uncertain, and retrieval/classification baselines have reproducible metrics.

## Scorecard

| Area | Grade | Evidence and judgment |
|---|---:|---|
| Research validity | B | Unit of analysis, declared source universe, ATS/sector coverage, and concentration diagnostics are explicit. Nineteen selected employers remain a curated cohort that cannot support labor-market prevalence claims. |
| Longitudinal design | B | Append-only source/analysis ledger and full eligible-set daily snapshots now exist. Only one distinct day is observed; repost/entity resolution and deadline history remain incomplete. |
| Extraction/classification | B− | A frozen 1,709-record weak-label snapshot now trains a versioned five-family hierarchical logistic baseline with Platt calibration, threshold-band abstention, parent consistency, and tail-label metrics. Its gate correctly rejects weak targets, non-longitudinal splitting, and pending training rights; the 13-record manual set remains far too small and unadjudicated. |
| Retrieval/ranking ML | B− | Pinned MiniLM embeddings and an MS MARCO cross-encoder now run against a content-addressed 750-observation snapshot with per-query metrics and offline latency. The cross-encoder improves development MRR/nDCG but regresses recall, so the machine-readable gate rejects it. Six single-reviewer queries remain far below a held-out promotion test. |
| O*NET normalization | B− | Conservative occupation candidates cover 733/1,709. Exact occupation-linked O*NET 30.3 software examples normalize 1,126 observed skill mentions on 525 listings, while inherited essential/transferable profiles are explicitly separated from listing facts. Occupation and crosswalk mappings remain unreviewed and only six occupations are profiled. |
| Licensing/provenance | B− | Metadata/evidence-only export, source links, hashes, manifests, and O*NET attribution are present. Source-by-source terms decisions and legal review of excerpts/training use are missing. |
| Forecasting discipline | B | Unsupported numeric forecasts were removed and the signal is null pending 30 days. No backtested forecast exists—which is preferable to a false one. |
| UX/accessibility | B | Natural-language hybrid search, explicit error state, skip link, Escape-close, dialog semantics, pressed term state, safe external links, and visible mobile navigation improved the surface. Automated accessibility tests and a complete assistive-technology audit remain. |
| Reliability/automation | B | Source count gates, strict public JSON Schema validation, build, lint, baseline ML evaluation, tests, and data refresh run in CI. A bounded live benchmark records static delivery latency, throughput, and cost scope. The costly learned benchmark is reproducible locally but not yet a scheduled isolated workflow; CI still does not deploy the direct-upload Cloudflare Pages project after a data commit. |
| Apocalypso integration | B | Version 2 uses explicit null semantics, history threshold, unit, cohort warning, and coverage context. A validated value and consumer contract test remain. |
| Publication readiness | B− | Methods, architecture, evaluation standard, responsible-AI boundaries, strict public JSON Schemas, machine-readable metrics, and a fail-closed 12-gate readiness ledger now exist. Dataset DOI/release, license file, full data dictionary, gold set, adjudication, and reproducible environment are still missing. |

## Publication blockers (P0)

1. Expand and independently adjudicate evaluation data. Six retrieval queries and 13 classification observations can only guard regressions; they cannot support CV claims or scientific conclusions.
2. Build the independent temporal test set and improve the learned candidate. The first pinned MiniLM/cross-encoder run is reproducible but fails recall and evidence gates; do not promote it.
3. Replace weak supervision with independently adjudicated gold labels, validate calibration against those labels, add occupation/source/geography slices, and promote a classifier only if it clears the existing hierarchy, abstention, and tail-label gates.
4. Complete source rights review. Record terms URL, review date, permitted retention, excerpt rule, redistribution, and training permission per source.
5. Accumulate at least 30 stable daily frames before publishing trend signals, and longer before forecasting. Backtest every forecast target.
6. Human-review occupation and software mappings, expand the O*NET profile beyond six occupations, and report mapping precision/coverage on adjudicated data.
7. Make deployment automatic and observable. The scheduled GitHub refresh currently commits data but does not prove that the direct-upload Cloudflare Pages deployment changed.

## High-priority engineering (P1)

- Store HTTP status, ETag/Last-Modified, response hash, latency, and feed schema version in retrieval manifests.
- Add canonical repost clusters using normalized employer/title/location plus content similarity and explicit confidence.
- Extend the published JSON Schema contracts to snapshots and every baseline metric artifact; keep strict validation in CI.
- Add hand-built source fixtures for HTML cleaning, compensation units, title relevance, evidence selection, and ontology regressions.
- Run ML evaluation in CI and fail on missing qrels, metric calculation errors, unexplained large regressions, or test-set mutation.
- Measure browser search p50/p95/p99 now; move retrieval to a versioned service before corpus size makes client computation expensive.
- Finish WCAG testing with keyboard focus trapping/restoration, semantic table structure, visible mobile navigation, and axe/Playwright checks.
- Add a data dictionary, repository/content license, citation file, release checksums, and changelog.

## Technical Fellow evidence bar

The defensible CV bullet today is limited: Jobservatory has a provenance-aware 1,700+ record public corpus from 19 Greenhouse/Lever feeds across 14 declared sectors, durable version/analysis lineage, source-concentration diagnostics, a browser hybrid retrieval baseline, and a reproducible pinned semantic-retrieval/cross-encoder experiment with explicit rejection gates. It is not yet defensible to claim production semantic retrieval, superior cross-encoder reranking, extreme multi-label classification, calibrated predictions, low-latency serving, market trends, or forecasting.

The application-ready bar is reached only when the P0 items are completed and a clean checkout reproduces the held-out metrics and latency report. The most valuable current result is negative but rigorous: generic MiniLM embeddings substantially underperform BM25 on the small development set, while cross-encoder reranking trades better MRR/nDCG for worse recall and is rejected.

The public release ledger currently passes only source-universe completeness and a bounded zero-error static delivery benchmark. It deliberately remains `blocked`; a checklist entry cannot pass without its evidence artifact and manual assurance where required.
