# Jobservatory ML architecture

Status: prototype architecture contract, 2026-08-17.

## System boundary

Jobservatory treats a source listing retrieved at a specific time as an observation. It does not treat a URL as a timeless job, and it does not treat an extracted label as a source fact.

```text
public career feeds
  -> retrieval manifest + quality gate
  -> cleaned role-focused text (transient)
  -> source observation hash
  -> version ledger + daily presence snapshot
  -> versioned rule analysis + evidence excerpts
  -> current public corpus
       -> content-addressed BM25 index -> versioned Pages Function
       -> retrieval evaluation -> rejected/promoted learned candidates
       -> classification evaluation
       -> term frames
       -> Apocalypso signal (withholds value until valid)
```

The production Cloudflare Pages deployment exposes `/api/v1/search` and `/api/v1/health`. The Function loads a content-addressed 2,700+ observation inverted index through the Pages `ASSETS` binding, verifies its SHA-256 and lineage, caches the loaded index and up to 100 candidate sets per isolate, and returns version/timing headers. The browser retains the prior hybrid implementation only as a network-failure fallback.

## Data and model contracts

| Boundary | Required contract | Current state |
|---|---|---|
| Source → ingestion | source identity, ATS provider, feed schema, retrieval time, source publication/update time when semantically available, URL, HTTP success, response hash/size, latency, fetched/eligible counts, public-API access basis, and separate redistribution/training review states | Implemented for 53 Greenhouse/Lever/Ashby feeds across 37 sectors; two of five machine-readable coverage targets pass; raw immutable responses are intentionally not retained pending rights review |
| Observation identity | `sourceId`, full-content SHA-256, `observationId`, first/last seen, listing version | Implemented; daily presence snapshots make disappearances independent of the 5,000-record publication cap |
| Analysis identity | `analysisId`, extraction and ontology versions, review state, evidence | Implemented; analysis revisions are distinct from listing revisions |
| Occupation and skill mapping | O*NET-SOC code/version, inferred flag, review state, listing-evidence crosswalk, inherited-profile semantics | Conservative title rules map 1,180+ observations; 1,780+ skill mentions on 820+ listings map to exact occupation-linked O*NET 30.3 software examples; exact counts are machine-readable and mappings remain unreviewed |
| Retrieval | query, corpus/index version, ranked IDs, component scores, latency | Versioned BM25 baseline API exposes result scores, model/index/corpus lineage, cache state, and service/application timing; learned retrieval remains rejected |
| Evaluation | immutable queries/qrels, split, model/index version, Recall@K, MRR, nDCG | Small single-reviewer development set implemented; no held-out or adjudicated set yet |
| Classification | hierarchical label IDs, probabilities, threshold version, evidence | Versioned title/location logistic baseline implements five label families, Platt calibration, threshold-band abstention, tail metrics, and deterministic parents; weak-label and rights gates reject promotion |
| Apocalypso | signal definition, unit, cohort, history threshold, uncertainty, null semantics | Version 2 emits `insufficient_history` and `null`; no fabricated pressure score |
| Release assurance | strict artifact schemas, evidence-bearing gates, prohibited-use policy, manual assurance state | Public 13-gate ledger fails closed; source-universe completeness, static-delivery benchmarking, scoped counterfactual testing, automated accessibility, and versioned baseline serving currently pass |

## Retrieval stack

The production service uses the BM25 baseline because it is the only candidate currently justified by the evaluation evidence. Its compact inverted index is generated deterministically from the public metadata-and-evidence corpus. The earlier browser baseline combines BM25, a 512-dimensional fixed feature-hashed representation, reciprocal-rank fusion, and a transparent title/metadata interaction reranker; it remains a network-failure fallback rather than the authoritative production ranker. The fixed representation is not called a semantic embedding, and the interaction model is not called a cross-encoder.

The first unrestricted offline candidate uses pinned MiniLM sentence embeddings and an MS MARCO cross-encoder. It improves development MRR and nDCG but regresses recall. The frozen recall-guarded candidate instead reranks BM25 only within ranks 1–5, 6–10, and 11–50; it preserves the three declared recall cutoffs while improving development MRR and nDCG. Promotion still rejects it because independent temporal evidence is absent. The target production stack remains:

1. PostgreSQL for normalized metadata and observation lineage.
2. OpenSearch or Tantivy for BM25 and faceting.
3. pgvector or a dedicated ANN index for versioned learned embeddings.
4. A small cross-encoder over the fused top 50.
5. A separately scalable Go or Workers retrieval service returning component scores, evidence, model versions, and timing once measured scale exceeds the Pages Function envelope.
6. Python/PyTorch training and evaluation jobs with frozen datasets and model cards.

Promotion requires a held-out improvement, no protected-attribute proxy regression, and a measured latency/cost budget. A more complicated model does not ship merely because it is more fashionable.

Static delivery and the versioned retrieval service have separate production benchmarks. The retrieval workload checks response schemas, result ordering, filters, lineage headers, cache behavior, p50/p95/p99 external and application time, throughput, errors, and an explicitly assumption-bound Cloudflare cost model. Neither benchmark is relevance-promotion evidence.

## 10× and 100× scale

At roughly 5,000 current documents, precompute document embeddings, move BM25 out of the browser, cache common candidate sets, and keep metadata filtering in SQL. At roughly 50,000 documents plus versions, separate current-document, version-ledger, and annotation stores; build indexes asynchronously; use alias-based atomic index promotion; and partition evaluation by occupation, geography, source, and time.

At either scale, independent teams contribute through versioned schemas, frozen evaluation slices, shadow traffic, model registry approval, and rollbackable index aliases. No team may change label meaning, evidence policy, or cohort construction without an architecture decision record and backfill plan.

## Failure modes

- Employer boilerplate can create false AI and skill matches.
- Source feeds can silently shrink or change HTML structure.
- Expired URLs do not prove that a position was filled.
- Missing compensation is not zero compensation and is not missing at random.
- Employer and source concentration can dominate trends.
- Reposts and location variants can inflate demand.
- LLM explanations can invent candidate qualifications unless constrained to retrieved passages.
- Ranking models can learn prestige, geography, and seniority proxies that disadvantage candidates.

The pipeline therefore fails closed on missing source feeds, marks unreviewed rules, retains evidence, and abstains on unsupported labor effects.
