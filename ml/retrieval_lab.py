#!/usr/bin/env python3
"""Dependency-free, reproducible retrieval baselines for Jobservatory.

This is deliberately a baseline laboratory, not a production model. It compares
BM25, a fixed feature-hashed dense representation, reciprocal-rank fusion, and a
transparent query-document interaction reranker against committed relevance
judgments. A neural embedding model and cross-encoder must beat these numbers on
the same split before they are promoted.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "public" / "api" / "observatory.json"
QUERY_PATH = ROOT / "ml" / "eval" / "queries.json"
METRICS_PATH = ROOT / "public" / "api" / "ml" / "retrieval-metrics.json"
TOKEN_RE = re.compile(r"[a-z0-9+#.]{2,}")
DIMENSIONS = 512


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def document_text(observation: dict) -> str:
    evidence = []
    for family in ("aiRelationship", "systemLayer", "skills"):
        for hit in observation["classifications"].get(family, []):
            evidence.extend((hit.get("label", ""), hit.get("evidence", "")))
    return " ".join([
        observation["title"], observation["employer"], observation["location"],
        observation["seniority"], observation["domain"], *evidence,
    ])


class RetrievalIndex:
    def __init__(self, observations: list[dict]):
        self.documents = observations
        self.ids = [item["observationId"] for item in observations]
        self.texts = [document_text(item) for item in observations]
        self.term_frequencies = [Counter(tokens(text)) for text in self.texts]
        self.lengths = [sum(counts.values()) for counts in self.term_frequencies]
        self.average_length = sum(self.lengths) / max(len(self.lengths), 1)
        self.document_frequency = Counter()
        for counts in self.term_frequencies:
            self.document_frequency.update(counts.keys())
        self.dense_documents = [self._dense_vector(text) for text in self.texts]

    @staticmethod
    def _features(text: str) -> list[str]:
        words = tokens(text[:1400])
        word_bigrams = [f"w:{a}_{b}" for a, b in zip(words, words[1:])]
        return [f"w:{word}" for word in words] + word_bigrams

    @staticmethod
    def _dense_vector(text: str) -> dict[int, float]:
        vector: Counter[int] = Counter()
        for feature in RetrievalIndex._features(text):
            digest = 2166136261
            for byte in feature.encode():
                digest ^= byte
                digest = (digest * 16777619) & 0xFFFFFFFF
            bucket = digest % DIMENSIONS
            sign = 1 if digest & 1 else -1
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1
        return {index: value / norm for index, value in vector.items()}

    def bm25(self, query: str, k1: float = 1.2, b: float = 0.75) -> list[tuple[str, float]]:
        query_terms = tokens(query)
        total = len(self.documents)
        scores = []
        for doc_id, counts, length in zip(self.ids, self.term_frequencies, self.lengths):
            score = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self.document_frequency[term]
                inverse_document_frequency = math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))
                denominator = frequency + k1 * (1 - b + b * length / self.average_length)
                score += inverse_document_frequency * frequency * (k1 + 1) / denominator
            scores.append((doc_id, score))
        return sorted(scores, key=lambda item: (-item[1], item[0]))

    def dense(self, query: str) -> list[tuple[str, float]]:
        query_vector = self._dense_vector(query)
        scores = []
        for doc_id, vector in zip(self.ids, self.dense_documents):
            score = sum(value * vector.get(index, 0) for index, value in query_vector.items())
            scores.append((doc_id, score))
        return sorted(scores, key=lambda item: (-item[1], item[0]))

    @staticmethod
    def rrf(*runs: list[tuple[str, float]], k: int = 60) -> list[tuple[str, float]]:
        scores: Counter[str] = Counter()
        for run in runs:
            for rank, (doc_id, _) in enumerate(run, 1):
                scores[doc_id] += 1 / (k + rank)
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))

    def rerank(self, query: str, run: list[tuple[str, float]], depth: int = 50) -> list[tuple[str, float]]:
        """Transparent interaction baseline; explicitly not a neural cross-encoder."""
        query_tokens = set(tokens(query))
        by_id = {item["observationId"]: item for item in self.documents}
        rescored = []
        for rank, (doc_id, score) in enumerate(run[:depth], 1):
            item = by_id[doc_id]
            title_tokens = set(tokens(item["title"]))
            metadata_tokens = set(tokens(f"{item['seniority']} {item['domain']} {item['location']}"))
            title_coverage = len(query_tokens & title_tokens) / max(len(query_tokens), 1)
            metadata_coverage = len(query_tokens & metadata_tokens) / max(len(query_tokens), 1)
            phrase = 1.0 if query.lower() in item["title"].lower() else 0.0
            rescored.append((doc_id, score + 0.08 * title_coverage + 0.03 * metadata_coverage + 0.05 * phrase + 0.001 / rank))
        rescored.sort(key=lambda item: (-item[1], item[0]))
        return rescored + run[depth:]


def recall_at(run: list[str], relevant: set[str], k: int) -> float:
    return len(set(run[:k]) & relevant) / max(len(relevant), 1)


def reciprocal_rank(run: list[str], relevant: set[str]) -> float:
    return next((1 / rank for rank, doc_id in enumerate(run, 1) if doc_id in relevant), 0.0)


def ndcg_at(run: list[str], grades: dict[str, int], k: int) -> float:
    def gain(sequence: list[str]) -> float:
        return sum((2 ** grades.get(doc_id, 0) - 1) / math.log2(rank + 1) for rank, doc_id in enumerate(sequence[:k], 1))
    ideal = [doc_id for doc_id, _ in sorted(grades.items(), key=lambda item: (-item[1], item[0]))]
    denominator = gain(ideal)
    return gain(run) / denominator if denominator else 0.0


def evaluate(index: RetrievalIndex, queries: list[dict]) -> dict:
    missing = sorted({doc_id for query in queries for doc_id in query["judgments"] if doc_id not in set(index.ids)})
    if missing:
        raise RuntimeError(f"judged observations missing from evaluation corpus: {missing}")
    aggregate = {name: Counter() for name in ("bm25", "dense_hash", "rrf", "interaction_rerank")}
    per_query = []
    for query in queries:
        runs = {
            "bm25": index.bm25(query["query"]),
            "dense_hash": index.dense(query["query"]),
        }
        runs["rrf"] = index.rrf(runs["bm25"], runs["dense_hash"])
        runs["interaction_rerank"] = index.rerank(query["query"], runs["rrf"])
        grades = query["judgments"]
        relevant = {doc_id for doc_id, grade in grades.items() if grade > 0}
        row = {"id": query["id"], "query": query["query"], "metrics": {}}
        for name, scored in runs.items():
            ranked = [doc_id for doc_id, _ in scored]
            metrics = {
                "recall@5": recall_at(ranked, relevant, 5),
                "recall@10": recall_at(ranked, relevant, 10),
                "mrr": reciprocal_rank(ranked, relevant),
                "ndcg@10": ndcg_at(ranked, grades, 10),
            }
            row["metrics"][name] = {key: round(value, 4) for key, value in metrics.items()}
            aggregate[name].update(metrics)
        per_query.append(row)
    count = max(len(queries), 1)
    return {
        "schemaVersion": "jobservatory.retrieval-eval.v1",
        "corpus": {"path": "public/api/observatory.json", "observations": len(index.documents)},
        "evaluation": {"queries": len(queries), "judgmentPolicy": "manually selected, graded title-and-evidence relevance; development set, not a held-out test set"},
        "models": {
            "bm25": "Okapi BM25 k1=1.2 b=0.75",
            "dense_hash": f"fixed feature-hashed word unigram/bigram vectors, {DIMENSIONS} dimensions; not a neural semantic model",
            "rrf": "reciprocal-rank fusion k=60",
            "interaction_rerank": "transparent title/metadata token-interaction features over top 50; not a neural cross-encoder",
        },
        "aggregate": {name: {key: round(value / count, 4) for key, value in totals.items()} for name, totals in aggregate.items()},
        "perQuery": per_query,
        "limitations": [
            "The judgments are a small development set and were not independently adjudicated.",
            "Evidence excerpts are incomplete substitutes for licensed full descriptions.",
            "The dense baseline measures whether learned embeddings add value; it is not presented as semantic retrieval.",
            "A neural cross-encoder remains a candidate and must be evaluated on a held-out set before deployment.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="Print top hybrid results instead of evaluating")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--write", action="store_true", help="Write committed metrics JSON")
    args = parser.parse_args()
    corpus = json.loads(CORPUS_PATH.read_text())
    index = RetrievalIndex(corpus["observations"])
    if args.query:
        run = index.rerank(args.query, index.rrf(index.bm25(args.query), index.dense(args.query)))
        by_id = {item["observationId"]: item for item in corpus["observations"]}
        print(json.dumps([{"score": round(score, 6), "observationId": doc_id, "employer": by_id[doc_id]["employer"], "title": by_id[doc_id]["title"]} for doc_id, score in run[:args.top_k]], indent=2))
        return 0
    report = evaluate(index, json.loads(QUERY_PATH.read_text())["queries"])
    rendered = json.dumps(report, indent=2) + "\n"
    if args.write:
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        METRICS_PATH.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
