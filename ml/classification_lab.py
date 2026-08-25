#!/usr/bin/env python3
"""Evaluate current multi-label skill rules against committed development labels."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_MANIFEST = ROOT / "ml" / "eval" / "snapshots" / "classifier-corpus-manifest.json"
LABELS = ROOT / "ml" / "eval" / "classification_labels.json"
OUTPUT = ROOT / "public" / "api" / "ml" / "classification-metrics.json"


def divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def load_frozen_observations() -> tuple[dict[str, dict], dict]:
    """Load the content-addressed evaluation corpus, not the changing live slice."""
    manifest = json.loads(CORPUS_MANIFEST.read_text())
    snapshot = (ROOT / manifest["snapshot"]).resolve()
    if ROOT not in snapshot.parents:
        raise RuntimeError("classifier snapshot must remain inside the repository")
    with gzip.open(snapshot, "rb") as source:
        canonical = source.read()
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != manifest["canonicalSha256"]:
        raise RuntimeError("classifier snapshot digest does not match its manifest")
    dataset = json.loads(canonical)
    observations = {item["observationId"]: item for item in dataset["observations"]}
    if len(observations) != manifest["observations"]:
        raise RuntimeError("classifier snapshot size does not match its manifest")
    return observations, manifest


def main() -> int:
    observations, corpus_manifest = load_frozen_observations()
    annotations = json.loads(LABELS.read_text())["annotations"]
    missing = [row["observationId"] for row in annotations if row["observationId"] not in observations]
    if missing:
        raise RuntimeError(f"annotated observations missing from frozen evaluation corpus: {missing}")
    universe = sorted({label for row in annotations for label in row["labels"]} | {hit["label"] for row in annotations for hit in observations[row["observationId"]]["classifications"]["skills"]})
    totals = Counter()
    per_label = {}
    exact = 0
    predicted_count = 0
    support = Counter(label for row in annotations for label in row["labels"])
    for label in universe:
        tp = fp = fn = 0
        for row in annotations:
            expected = set(row["labels"])
            predicted = {hit["label"] for hit in observations[row["observationId"]]["classifications"]["skills"]}
            tp += int(label in expected and label in predicted)
            fp += int(label not in expected and label in predicted)
            fn += int(label in expected and label not in predicted)
        precision, recall = divide(tp, tp + fp), divide(tp, tp + fn)
        per_label[label] = {"support": support[label], "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(divide(2 * precision * recall, precision + recall), 4)}
        totals.update(tp=tp, fp=fp, fn=fn)
    for row in annotations:
        predicted = {hit["label"] for hit in observations[row["observationId"]]["classifications"]["skills"]}
        expected = set(row["labels"])
        exact += int(predicted == expected)
        predicted_count += len(predicted)
    micro_precision = divide(totals["tp"], totals["tp"] + totals["fp"])
    micro_recall = divide(totals["tp"], totals["tp"] + totals["fn"])
    macro_f1 = sum(row["f1"] for row in per_label.values()) / max(len(per_label), 1)
    tail = [row["recall"] for row in per_label.values() if 0 < row["support"] <= 2]
    report = {
        "schemaVersion": "jobservatory.classification-eval.v1",
        "task": "multi-label skill extraction",
        "evaluation": {
            "observations": len(annotations), "labels": len(universe),
            "judgmentPolicy": "single-reviewer development annotations over a frozen extraction snapshot; not independently adjudicated or held out",
            "frozenCorpus": {
                "observations": corpus_manifest["observations"],
                "generatedAt": corpus_manifest["sourceGeneratedAt"],
                "canonicalSha256": corpus_manifest["canonicalSha256"],
            },
        },
        "aggregate": {
            "microPrecision": round(micro_precision, 4), "microRecall": round(micro_recall, 4),
            "microF1": round(divide(2 * micro_precision * micro_recall, micro_precision + micro_recall), 4),
            "macroF1": round(macro_f1, 4), "tailLabelRecall": round(sum(tail) / max(len(tail), 1), 4),
            "exactMatch": round(exact / len(annotations), 4), "meanPredictedLabels": round(predicted_count / len(annotations), 3),
            "calibration": None,
        },
        "perLabel": per_label,
        "limitations": [
            "The report evaluates the frozen reference extraction snapshot; it does not silently substitute a changing live corpus.",
            "Current rules emit binary decisions without probabilities, so calibration cannot yet be measured.",
            "The small development set is useful for regression detection but insufficient for publication-grade model comparison.",
            "Occupation, labor-effect, maturity, and responsibility labels remain unevaluated and must not be presented as validated predictions.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["aggregate"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
