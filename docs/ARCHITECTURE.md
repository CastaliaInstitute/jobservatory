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
       -> retrieval evaluation -> deployed hybrid search
       -> classification evaluation
       -> term frames
       -> Apocalypso signal (withholds value until valid)
```

The current static Cloudflare Pages deployment runs retrieval in the browser over 750 compact observations. This is appropriate for the prototype, not the target serving architecture.

## Data and model contracts

| Boundary | Required contract | Current state |
|---|---|---|
| Source → ingestion | source identity, retrieval time, source update time, URL, HTTP success, response hash/size, latency, fetched/eligible counts | Implemented for six Greenhouse feeds; raw immutable snapshots are intentionally not retained pending rights review |
| Observation identity | `sourceId`, full-content SHA-256, `observationId`, first/last seen, listing version | Implemented; daily presence snapshots make disappearances independent of the 750-record publication cap |
| Analysis identity | `analysisId`, extraction and ontology versions, review state, evidence | Implemented; analysis revisions are distinct from listing revisions |
| Occupation mapping | O*NET-SOC code/version, inferred flag, review state | Conservative title rules currently map 321/750 and abstain on the remainder |
| Retrieval | query, corpus/index version, ranked IDs, component scores, latency | Rankings implemented; component scores and timing are not yet exposed by the UI |
| Evaluation | immutable queries/qrels, split, model/index version, Recall@K, MRR, nDCG | Small single-reviewer development set implemented; no held-out or adjudicated set yet |
| Classification | hierarchical label IDs, probabilities, threshold version, evidence | Binary rules and label names implemented; probabilities, hierarchy, calibration, and a trained model are absent |
| Apocalypso | signal definition, unit, cohort, history threshold, uncertainty, null semantics | Version 2 emits `insufficient_history` and `null`; no fabricated pressure score |

## Retrieval stack

The deployed baseline uses BM25, a 512-dimensional fixed feature-hashed word unigram/bigram representation, reciprocal-rank fusion, and a transparent title/metadata interaction reranker. The fixed dense representation is not called a semantic embedding, and the interaction model is not called a cross-encoder.

The next candidate stack is:

1. PostgreSQL for normalized metadata and observation lineage.
2. OpenSearch or Tantivy for BM25 and faceting.
3. pgvector or a dedicated ANN index for versioned learned embeddings.
4. A small cross-encoder over the fused top 50.
5. A Go retrieval service returning component scores, evidence, model versions, and timing.
6. Python/PyTorch training and evaluation jobs with frozen datasets and model cards.

Promotion requires a held-out improvement, no protected-attribute proxy regression, and a measured latency/cost budget. A more complicated model does not ship merely because it is more fashionable.

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
