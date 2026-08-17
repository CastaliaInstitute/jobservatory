# Versioned retrieval serving

## Production contract

`GET /api/v1/search` accepts a required `q` of 2–256 characters, `limit` from 1–50, and optional exact `domain`, exact `seniority`, location substring, and `minimumPay` filters. `OPTIONS` supports CORS. Other methods and malformed bounds fail with structured 4xx responses.

Every successful response includes:

- observation IDs and display metadata;
- BM25 and total scores with deterministic tie-breaking;
- service, model, index, and corpus versions;
- cold/warm index and result-cache state;
- application timing in the body and `Server-Timing`;
- request, service, model, and index headers.

`GET /api/v1/health` loads and verifies the same serving artifact before reporting healthy. The Function returns 503 if the static manifest/index is absent, has the wrong byte length or SHA-256, or disagrees on model, corpus, or document lineage.

## Index lifecycle

`npm run serving:index` deterministically creates:

- `/api/search/index-v1.json`: compact documents and an inverted term-to-postings index;
- `/api/search/manifest-v1.json`: exact bytes, SHA-256, document count, build/model/service versions, and corpus timestamp.

The build consumes only Jobservatory's already-public metadata and short evidence spans. It does not restore or publish full descriptions. Every corpus refresh rebuilds the index; a deployment atomically replaces the Pages bundle and Function together.

## Model boundary

The service deliberately deploys `bm25-production-baseline-1.0.0`. The unrestricted MiniLM/cross-encoder experiment regresses development recall. A newer recall-guarded cross-encoder clears the development quality gate but remains ineligible because it lacks independent temporal adjudication. The API's `promotionStatus: baseline_only` prevents service architecture from being confused with learned-model promotion.

The browser queries the service after a 200 ms debounce and falls back to its prior in-memory hybrid baseline only on network or service failure. This preserves access while keeping the authoritative server lineage measurable.

## Caching and observability

Each isolate verifies and caches the 2.1 MB index promise. It also keeps an insertion-ordered cache of at most 100 query/filter/limit candidate sets, scoped to the exact index SHA. Raw queries are not written to logs; structured events include request ID, query length/token count, filter-presence booleans, result counts, cache state, and timings.

Responses are `no-store` so request IDs and timing evidence cannot be replayed from an intermediary cache. The service does not claim durable log retention or SLO alerting until Cloudflare observability configuration and alert evidence are published.

## Cost and limits

Pages Function requests are billed as Workers requests. As checked on 2026-08-17, Cloudflare documents 100,000 requests/day on Workers Free and, on Workers Paid Standard, a $5 monthly minimum including 10 million requests and 30 million CPU milliseconds; overages are separately priced. The production benchmark publishes an assumption-bound one-million-request estimate and treats reported service wall time as a conservative CPU upper bound. Account-wide usage and actual Cloudflare CPU telemetry remain external to that estimate.

Sources: [Pages Functions API and `ASSETS`](https://developers.cloudflare.com/pages/functions/api-reference/), [Pages Functions pricing](https://developers.cloudflare.com/pages/functions/pricing/), and [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/).
