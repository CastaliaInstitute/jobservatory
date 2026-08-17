#!/usr/bin/env python3
"""Validate committed learned-retrieval evidence without downloading models."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "public" / "api" / "ml" / "learned-retrieval-metrics.json"
MODEL_MANIFEST = ROOT / "public" / "api" / "ml" / "learned-retrieval-manifest.json"
CORPUS_MANIFEST = ROOT / "ml" / "eval" / "snapshots" / "manifest.json"
QRELS = ROOT / "ml" / "eval" / "queries.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    metrics = json.loads(METRICS.read_text())
    model = json.loads(MODEL_MANIFEST.read_text())
    corpus = json.loads(CORPUS_MANIFEST.read_text())
    qrels = json.loads(QRELS.read_text())
    snapshot = ROOT / corpus["snapshot"]

    require(digest(snapshot) == corpus["compressedSha256"], "snapshot compressed hash mismatch")
    with gzip.open(snapshot, "rt") as handle:
        unpacked = json.load(handle)
    canonical = (json.dumps(unpacked, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    require(hashlib.sha256(canonical).hexdigest() == corpus["canonicalSha256"], "snapshot canonical hash mismatch")
    require(len(unpacked["observations"]) == corpus["observations"], "snapshot observation count mismatch")
    require(model["evaluationCorpusCanonicalSha256"] == corpus["canonicalSha256"], "model/corpus lineage mismatch")
    require(model["qrelsSha256"] == digest(QRELS), "model/qrels lineage mismatch")
    require(metrics["corpus"]["canonicalSha256"] == corpus["canonicalSha256"], "metrics/corpus lineage mismatch")
    require(metrics["evaluation"]["queries"] == len(qrels["queries"]), "query count mismatch")
    require(not qrels["eligibleForPromotionDecision"], "development qrels cannot authorize promotion")

    delta = metrics["developmentDeltaRecallGuardedVsBm25"]
    criteria = metrics["promotion"]["qualityCriteria"]
    expected = {
        "ndcg@10Improves": delta["ndcg@10"] > 0,
        "mrrNonInferior": delta["mrr"] >= 0,
        "recall@5NonInferior": delta["recall@5"] >= 0,
        "recall@10NonInferior": delta["recall@10"] >= 0,
        "recall@50NonInferior": delta["recall@50"] >= 0,
    }
    require(criteria == expected, "quality criteria do not match recorded metric deltas")
    require(metrics["promotion"]["qualityGatePass"] == all(expected.values()), "quality gate mismatch")
    require(metrics["promotion"]["qualityGatePass"], "recall-guarded development candidate did not clear quality gate")
    require(all(delta[key] == 0 for key in ("recall@5", "recall@10", "recall@50")), "recall guards did not preserve reported cutoff recall")
    require(metrics["models"]["reranker"]["recallGuardBands"] == [[1, 5], [6, 10], [11, 50]], "recall guard bands changed")
    for row in metrics["perQuery"]:
        for key in ("recall@5", "recall@10", "recall@50"):
            require(row["metrics"]["recall_guarded_cross_encoder"][key] == row["metrics"]["bm25"][key], f"{row['id']} {key} recall guard mismatch")
    require(metrics["aggregate"]["cross_encoder_unrestricted"]["recall@10"] < metrics["aggregate"]["bm25"]["recall@10"], "unrestricted recall regression is no longer represented")
    require(not metrics["promotion"]["evidenceGatePass"], "unadjudicated development evidence passed gate")
    require(metrics["promotion"]["status"] == "not_eligible", "development candidate incorrectly eligible")
    print("validated learned retrieval snapshot, recall guards, metrics, and evidence rejection gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
