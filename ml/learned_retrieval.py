#!/usr/bin/env python3
"""Benchmark pinned learned retrieval models against Jobservatory baselines."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import platform
import statistics
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import CrossEncoder, SentenceTransformer

from retrieval_lab import RetrievalIndex, ndcg_at, recall_at, reciprocal_rank

ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "ml" / "eval" / "queries.json"
SNAPSHOT_MANIFEST = ROOT / "ml" / "eval" / "snapshots" / "manifest.json"
METRICS_PATH = ROOT / "public" / "api" / "ml" / "learned-retrieval-metrics.json"
MODEL_MANIFEST_PATH = ROOT / "public" / "api" / "ml" / "learned-retrieval-manifest.json"

EMBEDDING_ID = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "b8903db39f65d93ae28d49a37c4f3fa90c5f94e0"
RERANKER_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
RERANKER_REVISION = "c5ee24cb16019beea0893ab7796b1df96625c6b8"
RERANK_DEPTH = 50


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_corpus() -> tuple[dict, dict, Path]:
    manifest = json.loads(SNAPSHOT_MANIFEST.read_text())
    path = ROOT / manifest["snapshot"]
    if sha256(path) != manifest["compressedSha256"]:
        raise RuntimeError("compressed evaluation snapshot does not match its manifest")
    with gzip.open(path, "rt") as handle:
        corpus = json.load(handle)
    canonical = (json.dumps(corpus, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    if hashlib.sha256(canonical).hexdigest() != manifest["canonicalSha256"]:
        raise RuntimeError("canonical evaluation corpus does not match its manifest")
    return corpus, manifest, path


def metrics_for(run: list[str], grades: dict[str, int]) -> dict[str, float]:
    relevant = {doc_id for doc_id, grade in grades.items() if grade > 0}
    return {
        "recall@5": recall_at(run, relevant, 5),
        "recall@10": recall_at(run, relevant, 10),
        "recall@50": recall_at(run, relevant, 50),
        "mrr": reciprocal_rank(run, relevant),
        "ndcg@10": ndcg_at(run, grades, 10),
    }


def round_metrics(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 4) for key, value in values.items()}


def latency_summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    percentile = lambda p: ordered[min(round((len(ordered) - 1) * p), len(ordered) - 1)]
    return {
        "meanMs": round(statistics.mean(values), 2),
        "p50Ms": round(percentile(0.50), 2),
        "p95Ms": round(percentile(0.95), 2),
        "p99Ms": round(percentile(0.99), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"))
    args = parser.parse_args()

    corpus, corpus_manifest, snapshot_path = load_frozen_corpus()
    qrels = json.loads(QUERY_PATH.read_text())
    observations = corpus["observations"]
    index = RetrievalIndex(observations)
    device = args.device or ("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")

    started = time.perf_counter()
    embedding = SentenceTransformer(EMBEDDING_ID, revision=EMBEDDING_REVISION, device=device)
    embedding_load_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    reranker = CrossEncoder(RERANKER_ID, revision=RERANKER_REVISION, device=device)
    reranker_load_ms = (time.perf_counter() - started) * 1000

    embedding.encode(["warmup"], normalize_embeddings=True, show_progress_bar=False)
    reranker.predict([["warmup", "warmup document"]], show_progress_bar=False)
    started = time.perf_counter()
    document_embeddings = embedding.encode(index.texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    corpus_encode_ms = (time.perf_counter() - started) * 1000

    aggregates = {name: Counter() for name in ("bm25", "learned_dense", "bm25_dense_rrf", "cross_encoder")}
    latencies = {name: [] for name in ("bm25", "learnedDense", "fusion", "crossEncoder", "endToEnd")}
    per_query = []
    by_id = {doc_id: position for position, doc_id in enumerate(index.ids)}

    for query in qrels["queries"]:
        query_started = time.perf_counter()
        started = time.perf_counter()
        bm25 = index.bm25(query["query"])
        latencies["bm25"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        query_embedding = embedding.encode([query["query"]], normalize_embeddings=True, show_progress_bar=False)[0]
        scores = np.asarray(document_embeddings) @ np.asarray(query_embedding)
        learned_dense = sorted(zip(index.ids, scores.tolist()), key=lambda item: (-item[1], item[0]))
        latencies["learnedDense"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        fused = index.rrf(bm25, learned_dense)
        latencies["fusion"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        candidates = fused[:RERANK_DEPTH]
        pairs = [[query["query"], index.texts[by_id[doc_id]]] for doc_id, _ in candidates]
        cross_scores = reranker.predict(pairs, batch_size=32, show_progress_bar=False).tolist()
        reranked_head = sorted(zip((doc_id for doc_id, _ in candidates), cross_scores), key=lambda item: (-item[1], item[0]))
        reranked = reranked_head + fused[RERANK_DEPTH:]
        latencies["crossEncoder"].append((time.perf_counter() - started) * 1000)
        latencies["endToEnd"].append((time.perf_counter() - query_started) * 1000)

        runs = {"bm25": bm25, "learned_dense": learned_dense, "bm25_dense_rrf": fused, "cross_encoder": reranked}
        row = {"id": query["id"], "query": query["query"], "metrics": {}}
        for name, scored in runs.items():
            values = metrics_for([doc_id for doc_id, _ in scored], query["judgments"])
            aggregates[name].update(values)
            row["metrics"][name] = round_metrics(values)
        per_query.append(row)

    count = len(qrels["queries"])
    aggregate = {name: round_metrics({key: value / count for key, value in totals.items()}) for name, totals in aggregates.items()}
    candidate = aggregate["cross_encoder"]
    baseline = aggregate["bm25"]
    development_improvement = {
        key: round(candidate[key] - baseline[key], 4) for key in ("recall@5", "recall@10", "recall@50", "mrr", "ndcg@10")
    }
    evidence_eligible = bool(qrels.get("eligibleForPromotionDecision"))
    quality_criteria = {
        "ndcg@10Improves": development_improvement["ndcg@10"] > 0,
        "mrrNonInferior": development_improvement["mrr"] >= 0,
        "recall@5NonInferior": development_improvement["recall@5"] >= 0,
        "recall@10NonInferior": development_improvement["recall@10"] >= 0,
        "recall@50NonInferior": development_improvement["recall@50"] >= 0,
    }
    quality_pass = all(quality_criteria.values())
    promotion = {
        "status": "eligible" if evidence_eligible and quality_pass else "not_eligible",
        "qualityGatePass": quality_pass,
        "qualityCriteria": quality_criteria,
        "evidenceGatePass": evidence_eligible,
        "reasons": [
            reason for condition, reason in (
                (quality_pass, "Candidate did not improve nDCG@10 without regressing MRR or Recall@5/10/50."),
                (evidence_eligible, "Independent, adjudicated, temporally held-out judgments are required."),
            ) if not condition
        ],
    }
    report = {
        "schemaVersion": "jobservatory.learned-retrieval-eval.v1",
        "corpus": {**corpus_manifest, "compressedBytes": snapshot_path.stat().st_size},
        "evaluation": {
            "split": qrels.get("split"),
            "queries": count,
            "annotationStatus": qrels.get("annotationStatus"),
            "adjudicationStatus": qrels.get("adjudicationStatus"),
            "eligibleForPromotionDecision": evidence_eligible,
        },
        "models": {
            "bm25": {"implementation": "jobservatory RetrievalIndex", "parameters": {"k1": 1.2, "b": 0.75}},
            "embedding": {"id": EMBEDDING_ID, "revision": EMBEDDING_REVISION, "license": "Apache-2.0", "normalized": True},
            "fusion": {"method": "reciprocal-rank fusion", "k": 60},
            "reranker": {"id": RERANKER_ID, "revision": RERANKER_REVISION, "license": "Apache-2.0", "depth": RERANK_DEPTH},
        },
        "aggregate": aggregate,
        "developmentDeltaCrossEncoderVsBm25": development_improvement,
        "perQuery": per_query,
        "promotion": promotion,
        "latency": {
            "scope": "single-process offline benchmark; excludes HTTP, concurrency, and model download",
            "device": device,
            "modelLoadMs": {"embedding": round(embedding_load_ms, 2), "crossEncoder": round(reranker_load_ms, 2)},
            "corpusEncoding": {"observations": len(observations), "totalMs": round(corpus_encode_ms, 2), "documentsPerSecond": round(len(observations) / (corpus_encode_ms / 1000), 2)},
            "warmQuery": {name: latency_summary(values) for name, values in latencies.items()},
        },
        "limitations": [
            "Development judgments are single-reviewer and not independently adjudicated.",
            "Six queries are insufficient to estimate generalization or statistical uncertainty.",
            "Latency is an offline single-process measurement, not a production load test.",
            "Evidence excerpts may omit relevant content from source listings.",
        ],
    }
    model_manifest = {
        "schemaVersion": "jobservatory.model-manifest.v1",
        "task": "retrieval-and-reranking",
        "models": report["models"],
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "device": device,
            "numpy": importlib.metadata.version("numpy"),
            "torch": importlib.metadata.version("torch"),
            "sentenceTransformers": importlib.metadata.version("sentence-transformers"),
            "transformers": importlib.metadata.version("transformers"),
            "lockfileSha256": sha256(ROOT / "uv.lock"),
        },
        "evaluationCorpusCanonicalSha256": corpus_manifest["canonicalSha256"],
        "qrelsSha256": sha256(QUERY_PATH),
        "promotion": promotion,
    }
    if args.write:
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        METRICS_PATH.write_text(json.dumps(report, indent=2) + "\n")
        MODEL_MANIFEST_PATH.write_text(json.dumps(model_manifest, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
