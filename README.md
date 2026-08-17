# Jobservatory

Castalia's AI Labor Observatory: a longitudinal research dataset and public interface for examining how organizations operationalize AI through job design.

## Research object

The unit of analysis is a **listing observation at a particular time**, not a timeless job record. Each observation stores source metadata, first/last seen timestamps, a content hash, version lineage, normalized classifications, explicit compensation when disclosed, and short evidence spans. Full descriptions are not republished.

Rule-derived labels are explicitly marked as unreviewed inferences. Unsupported labor effects abstain rather than defaulting to augmentation.

## Current prototype

- 750 published observations from six public Greenhouse feeds, selected from a larger declared eligible set
- ML engineering, scientific AI, robotics, product leadership, education, safety, governance, and evaluation
- append-only source/analysis versions, full eligible-set daily presence snapshots, and summary frames retained for up to two years
- evidence ledger, compensation signals, term map, and working hybrid retrieval laboratory
- BM25, fixed dense-hash, reciprocal-rank fusion, and transparent interaction-reranking baselines
- committed retrieval and multi-label development judgments with reproducible metrics
- public JSON corpus at `/api/observatory.json`
- Apocalypso signal at `/api/apocalypso/jobs-signal.json`

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

The site is a static Vite build for Cloudflare Pages:

- build command: `npm run build`
- output directory: `dist`
- production branch: `main`

The scheduled GitHub Action refreshes observations daily, reruns ML evaluation, verifies lint/build/tests, and commits changed research artifacts. Production is published at `jobservatory.castalia.institute` through a Cloudflare Pages direct-upload project. Automated deployment is not yet configured because the repository has no Cloudflare credentials; a successful refresh therefore does not prove the live deployment was updated.

## Method limits

The corpus is curated rather than statistically representative. Listing language measures employer intent and organizational design, not realized hiring, productivity, or displacement. No numeric forecast is currently published. Apocalypso returns a null signal until longitudinal requirements are met.

The current evaluation sets are small, single-reviewer development fixtures. They are useful for regression detection but insufficient for scientific or CV performance claims. See [the methodology](docs/METHODOLOGY.md), [architecture](docs/ARCHITECTURE.md), [evaluation standard](docs/MODEL_EVALUATION_STANDARD.md), and [A+ critical review](docs/A_PLUS_REVIEW.md).
