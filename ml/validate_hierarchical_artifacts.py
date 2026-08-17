#!/usr/bin/env python3
"""Validate frozen classifier lineage, artifact integrity, and rejection gates."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "public" / "api" / "ml" / "hierarchical-classifier-manifest.json"
METRICS = ROOT / "public" / "api" / "ml" / "hierarchical-classifier-metrics.json"
CORPUS_MANIFEST = ROOT / "ml" / "eval" / "snapshots" / "classifier-corpus-manifest.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    manifest = json.loads(MANIFEST.read_text())
    metrics = json.loads(METRICS.read_text())
    corpus_manifest = json.loads(CORPUS_MANIFEST.read_text())
    corpus_path = ROOT / corpus_manifest["snapshot"]
    model_path = ROOT / manifest["artifact"]
    require(digest(corpus_path) == corpus_manifest["compressedSha256"], "classifier corpus compressed hash mismatch")
    with gzip.open(corpus_path, "rt") as handle:
        corpus = json.load(handle)
    canonical = (json.dumps(corpus, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    require(hashlib.sha256(canonical).hexdigest() == corpus_manifest["canonicalSha256"], "classifier corpus canonical hash mismatch")
    require(len(corpus["observations"]) == corpus_manifest["observations"], "classifier corpus count mismatch")
    require(digest(model_path) == manifest["artifactSha256"], "classifier artifact hash mismatch")
    with gzip.open(model_path, "rt") as handle:
        model = json.load(handle)
    uncompressed = (json.dumps(model, sort_keys=True, separators=(",", ":")) + "\n").encode()
    require(hashlib.sha256(uncompressed).hexdigest() == manifest["uncompressedSha256"], "classifier model canonical hash mismatch")
    require(manifest["trainingCorpusCanonicalSha256"] == corpus_manifest["canonicalSha256"], "classifier training lineage mismatch")
    require(metrics["data"]["corpusCanonicalSha256"] == corpus_manifest["canonicalSha256"], "classifier metrics lineage mismatch")
    require(sum(metrics["data"]["splits"].values()) == corpus_manifest["observations"], "classifier split count mismatch")
    require(len(model["labels"]) == metrics["hierarchy"]["leafLabels"] == len(model["baseModels"]), "classifier label/model count mismatch")
    require(metrics["hierarchy"]["parentConsistency"] == 1.0, "hierarchy consistency gate failed")
    require(metrics["promotion"]["status"] == "not_eligible" and not metrics["promotion"]["evidenceGatePass"], "weak-label classifier incorrectly eligible")
    require(all(math.isfinite(value) for value in metrics["aggregate"].values()), "non-finite classifier metric")
    print("validated hierarchical classifier snapshot, model, metrics, hierarchy, and rejection gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
