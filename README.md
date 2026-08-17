# Jobservatory

Castalia's AI Labor Observatory: a longitudinal research dataset and public interface for examining how organizations operationalize AI through job design.

## Research object

The unit of analysis is a **listing observation at a particular time**, not a timeless job record. Each observation stores source metadata, first/last seen timestamps, a content hash, version lineage, normalized classifications, explicit compensation when disclosed, and short evidence spans. Full descriptions are not republished.

Model-derived labels—labor effect, human role, and organizational maturity—are explicitly marked as inferences.

## Current prototype

- 250 curated observations from public Greenhouse feeds
- ML engineering, scientific AI, robotics, product leadership, education, safety, governance, and evaluation
- daily version detection and two-year summary history
- evidence ledger, skill co-occurrence view, compensation signals, and scenario forecast
- public JSON corpus at `/api/observatory.json`
- Apocalypso signal at `/api/apocalypso/jobs-signal.json`

## Development

```bash
npm install
npm run data:collect
npm run dev
npm test
```

The collector uses only Python's standard library and a local SQLite ledger. The SQLite file is intentionally ignored; public, license-conscious exports and daily history are committed.

## Deployment

The site is a static Vite build for Cloudflare Pages:

- build command: `npm run build`
- output directory: `dist`
- production branch: `main`

The scheduled GitHub Action refreshes observations daily, verifies the build, and commits changed public exports. Production is published at `jobservatory.castalia.institute` through Cloudflare Pages.

## Method limits

The corpus is curated rather than statistically representative. Listing language measures employer intent and organizational design, not realized hiring, productivity, or displacement. Forecasts are scenarios to test against future observations and BLS outcomes—not point predictions.
