# Learned retrieval candidate model card

Status: **research candidate; rejected for promotion**

This experiment tests whether general-purpose pretrained semantic retrieval and
neural reranking improve Jobservatory search. It does not train on Jobservatory
labels and is not deployed in the browser or a production service.

## Components

- Candidate generator: `sentence-transformers/all-MiniLM-L6-v2`, pinned at
  revision `b8903db39f65d93ae28d49a37c4f3fa90c5f94e0`.
- Lexical baseline: Okapi BM25 (`k1=1.2`, `b=0.75`).
- Fusion: reciprocal-rank fusion (`k=60`).
- Reranker: `cross-encoder/ms-marco-MiniLM-L6-v2`, pinned at revision
  `c5ee24cb16019beea0893ab7796b1df96625c6b8`, over the top 50 fused results.
- Both external models declare Apache-2.0 licenses in their model repositories.

The document representation concatenates title, employer, location, seniority,
domain, and short extracted classification evidence. Full job descriptions are
not retained in the public corpus. The embedding model truncates inputs beyond
256 wordpieces, so late-document evidence may be lost.

## Evaluation

The content-addressed frozen snapshot contains 750 observations. The six graded
queries are a single-reviewer development set, not an independent or temporally
held-out test. Exact hashes, dependency versions, platform, per-query metrics,
and measured offline latency are recorded in
`public/api/ml/learned-retrieval-metrics.json` and
`public/api/ml/learned-retrieval-manifest.json`.

On this development set, the cross-encoder candidate improves MRR from 0.6667
to 0.7269 and nDCG@10 from 0.6026 to 0.6181, but Recall@5 falls from 0.5139 to
0.5000 and Recall@10 falls from 0.6389 to 0.5556. The standalone learned dense
retriever is worse than BM25 on every reported aggregate metric.

The candidate therefore fails the declared quality gate. It separately fails
the evidence gate because the judgments are neither independent, adjudicated,
nor held out. These development numbers must not be used as evidence of
production superiority.

## Intended and prohibited uses

This candidate may be used for offline error analysis and development-set
experiments. It must not be used for employment decisions, candidate scoring,
labor-market prevalence claims, or production model promotion.

## Known risks

- Generic web/search training may not model job-specific relevance.
- Sparse relevance judgments make unjudged relevant documents look incorrect.
- Employer and source concentration can distort aggregate metrics.
- Extracted evidence is incomplete and can propagate upstream classification
  errors.
- Neural scores are not calibrated probabilities or explanations.
- The observed single-process MPS latency is not a service SLO measurement.

The next candidate should be selected on expanded development data, then frozen
before a separately authored temporal test set is unsealed.
