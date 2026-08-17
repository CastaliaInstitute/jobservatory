#!/usr/bin/env python3
"""Build the compact, versioned BM25 production-serving index."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "public" / "api" / "observatory.json"
INDEX_PATH = ROOT / "public" / "api" / "search" / "index-v1.json"
MANIFEST_PATH = ROOT / "public" / "api" / "search" / "manifest-v1.json"
TOKEN_PATTERN = re.compile(r"[a-z0-9+#.]{2,}")
INDEX_BUILD_VERSION = "jobservatory-serving-index-1.0.0"
MODEL_ID = "bm25-production-baseline-1.0.0"


def tokens(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def search_text(observation: dict) -> str:
    evidence = []
    for family in ("aiRelationship", "systemLayer", "skills"):
        for hit in observation["classifications"][family]:
            evidence.extend((hit["label"], hit["evidence"]))
    return " ".join(
        [
            observation["title"],
            observation["employer"],
            observation["location"],
            observation["seniority"],
            observation["domain"],
            *evidence,
        ]
    )


def compact_json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def main() -> int:
    corpus = json.loads(CORPUS_PATH.read_text())
    documents = []
    inverted: dict[str, list[list[int]]] = defaultdict(list)
    total_terms = 0
    for index, observation in enumerate(corpus["observations"]):
        counts = Counter(tokens(search_text(observation)))
        length = sum(counts.values())
        total_terms += length
        documents.append(
            {
                "observationId": observation["observationId"],
                "employer": observation["employer"],
                "title": observation["title"],
                "location": observation["location"],
                "seniority": observation["seniority"],
                "domain": observation["domain"],
                "compensation": observation["compensation"],
                "sourceUrl": observation["sourceUrl"],
                "length": length,
            }
        )
        for term, frequency in sorted(counts.items()):
            inverted[term].append([index, frequency])

    document_count = len(documents)
    index_artifact = {
        "schemaVersion": "jobservatory.serving-index.v1",
        "generatedAt": corpus["generatedAt"],
        "indexBuildVersion": INDEX_BUILD_VERSION,
        "model": {"modelId": MODEL_ID, "algorithm": "Okapi BM25", "parameters": {"k1": 1.2, "b": 0.75}},
        "corpus": {
            "schemaVersion": corpus["schemaVersion"],
            "generatedAt": corpus["generatedAt"],
            "observations": document_count,
            "descriptionPolicy": corpus["observations"][0]["descriptionPolicy"],
        },
        "statistics": {
            "documents": document_count,
            "terms": total_terms,
            "uniqueTerms": len(inverted),
            "averageDocumentLength": round(total_terms / max(document_count, 1), 8),
        },
        "documents": documents,
        "invertedIndex": dict(sorted(inverted.items())),
    }
    payload = compact_json(index_artifact)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        "schemaVersion": "jobservatory.serving-index-manifest.v1",
        "generatedAt": corpus["generatedAt"],
        "serviceVersion": "jobservatory-search-api-v1",
        "route": "/api/v1/search",
        "index": {
            "path": "/api/search/index-v1.json",
            "sha256": f"sha256:{digest}",
            "bytes": len(payload),
            "documents": document_count,
            "indexBuildVersion": INDEX_BUILD_VERSION,
        },
        "model": index_artifact["model"],
        "corpus": index_artifact["corpus"],
        "promotion": {
            "status": "baseline_only",
            "reason": "The learned candidate remains rejected; production serves the explicit BM25 baseline until held-out promotion evidence exists.",
        },
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_bytes(payload)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"serving index: {document_count} documents, {len(inverted)} terms, {len(payload)} bytes, sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
