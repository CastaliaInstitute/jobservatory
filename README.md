# Jobservatory

Castalia's AI Labor Observatory: a longitudinal research dataset and public interface for examining how organizations operationalize AI through job design.

## Research object

The unit of analysis is a **listing observation at a particular time**, not a timeless job record. Each observation stores source metadata, first/last seen timestamps, a content hash, version lineage, normalized classifications, explicit compensation when disclosed, and short evidence spans. Full descriptions are not republished.

Rule-derived labels are explicitly marked as unreviewed inferences. Unsupported labor effects abstain rather than defaulting to augmentation.

## Current prototype

- 2,100+ published observations from 26 public feeds across Greenhouse, Lever, and Ashby, spanning 18 declared sectors
- ML engineering, scientific AI, robotics, product leadership, education, safety, governance, and evaluation
- append-only source/analysis versions, full eligible-set daily presence snapshots, and summary frames retained for up to two years
- evidence ledger, compensation signals, term map, and working hybrid retrieval laboratory
- BM25, fixed dense-hash, reciprocal-rank fusion, and transparent interaction-reranking baselines
- committed retrieval and multi-label development judgments with reproducible metrics
- pinned learned sentence-embedding and cross-encoder experiment with a machine-enforced rejection gate
- exact O*NET 30.3 software-skill normalization and occupation-inherited skill profiles with provenance-safe semantics
- versioned hierarchical weak-label classifier with Platt calibration, abstention, tail-label metrics, and a machine-enforced rejection gate
- scoped serialized-model protected-phrase counterfactual audit with a positive sensitivity control
- reproducible axe-core WCAG 2.2 AA and keyboard-dialog audit across desktop/mobile rendered states
- public JSON corpus at `/api/observatory.json`
- content-addressed data card at `/api/data-card.json`
- Apocalypso signal at `/api/apocalypso/jobs-signal.json`
- fail-closed A+ release ledger at `/api/ml/release-readiness.json`
- bounded production delivery benchmark at `/api/ops/production-benchmark.json`
- versioned Cloudflare Pages retrieval service at `/api/v1/search` with health at `/api/v1/health`
- content-addressed BM25 baseline index and manifest under `/api/search/`
- published JSON Schema contracts under `/schemas/`

## Development

```bash
npm install
npm run data:collect
npm run ml:evaluate
npm run dev
npm test
```

The collector uses only Python's standard library. Local SQLite is a convenience index and is ignored; the append-only version ledger, daily eligible-set snapshots, public metadata/evidence export, and aggregate history are committed.

## Deployment

The site is a Vite application with a Cloudflare Pages Function for versioned retrieval:

- build command: `npm run build`
- output directory: `dist`
- production branch: `main`
- pinned runtime configuration: `wrangler.toml`

The scheduled GitHub Action refreshes observations daily, rebuilds the content-addressed serving index, reruns ML evaluation, verifies lint/build/tests—including the actual local Pages runtime—and commits changed research artifacts. Production is published at `jobservatory.castalia.institute` through a Cloudflare Pages direct-upload project. Automated deployment is not yet configured because the repository has no Cloudflare credentials; a successful refresh therefore does not prove the live deployment was updated.

## Method limits

The corpus is curated rather than statistically representative. Listing language measures employer intent and organizational design, not realized hiring, productivity, or displacement. No numeric forecast is currently published. Apocalypso returns a null signal until longitudinal requirements are met.

The current evaluation sets are small, single-reviewer development fixtures. They are useful for regression detection but insufficient for scientific or CV performance claims. The production service therefore exposes the BM25 baseline and identifies the learned candidate as rejected. See [the methodology](docs/METHODOLOGY.md), [architecture](docs/ARCHITECTURE.md), [serving contract](docs/SERVING.md), [evaluation standard](docs/MODEL_EVALUATION_STANDARD.md), [responsible-AI controls](docs/RESPONSIBLE_AI.md), and [A+ critical review](docs/A_PLUS_REVIEW.md).
