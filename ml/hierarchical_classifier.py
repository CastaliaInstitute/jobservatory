#!/usr/bin/env python3
"""Train a calibrated hierarchical multi-label development baseline."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "public" / "api" / "observatory.json"
CORPUS_MANIFEST = ROOT / "ml" / "eval" / "snapshots" / "classifier-corpus-manifest.json"
MANUAL_LABELS = ROOT / "ml" / "eval" / "classification_labels.json"
METRICS = ROOT / "public" / "api" / "ml" / "hierarchical-classifier-metrics.json"
MANIFEST = ROOT / "public" / "api" / "ml" / "hierarchical-classifier-manifest.json"
MODEL = ROOT / "ml" / "models" / "hierarchical-classifier-v0.1.json.gz"
MARGIN = 0.05


def labels(record: dict) -> set[str]:
    result = {f"skill/{hit['label']}" for hit in record["classifications"]["skills"]}
    result |= {f"layer/{hit['label']}" for hit in record["classifications"]["systemLayer"]}
    result |= {f"relationship/{hit['label']}" for hit in record["classifications"]["aiRelationship"]}
    result.add(f"domain/{record['domain']}")
    result.add(f"seniority/{record['seniority']}")
    return result


def load_corpus() -> tuple[dict, dict]:
    manifest = json.loads(CORPUS_MANIFEST.read_text())
    path = ROOT / manifest["snapshot"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["compressedSha256"]:
        raise RuntimeError("classifier snapshot compressed hash mismatch")
    with gzip.open(path, "rt") as handle:
        corpus = json.load(handle)
    canonical = (json.dumps(corpus, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    if hashlib.sha256(canonical).hexdigest() != manifest["canonicalSha256"]:
        raise RuntimeError("classifier snapshot canonical hash mismatch")
    return corpus, manifest


def model_text(record: dict) -> str:
    # Deliberately excludes employer and rule-selected evidence to reduce source
    # memorization and direct weak-label leakage.
    return f"{record['title']} {record['location']}"


def split_records(records: list[dict]) -> dict[str, list[dict]]:
    """Group repost variants, then order groups by the best available source time."""
    groups: dict[str, list[dict]] = {}
    for record in records:
        groups.setdefault(record["duplicateGroup"], []).append(record)
    ordered = sorted(groups.values(), key=lambda group: (
        max((item.get("sourceUpdatedAt") or item.get("sourcePublishedAt") or item["retrievedAt"]) for item in group),
        group[0]["duplicateGroup"],
    ))
    targets = {"train": 0.70 * len(records), "calibration": 0.85 * len(records)}
    result = {"train": [], "calibration": [], "evaluation": []}
    count = 0
    for group in ordered:
        name = "train" if count < targets["train"] else "calibration" if count < targets["calibration"] else "evaluation"
        result[name].extend(group)
        count += len(group)
    return result


def matrix(records: list[dict], universe: list[str]) -> np.ndarray:
    indexes = {label: index for index, label in enumerate(universe)}
    output = np.zeros((len(records), len(universe)), dtype=np.int8)
    for row, record in enumerate(records):
        for label in labels(record):
            output[row, indexes[label]] = 1
    return output


def sigmoid(value: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(value, -30, 30)))


def precision_recall_f1(y: np.ndarray, prediction: np.ndarray, decided: np.ndarray | None = None) -> tuple[float, float, float]:
    mask = decided if decided is not None else np.ones_like(y, dtype=bool)
    truth, predicted = y[mask], prediction[mask]
    tp = int(np.sum((truth == 1) & (predicted == 1)))
    fp = int(np.sum((truth == 0) & (predicted == 1)))
    fn = int(np.sum((truth == 1) & (predicted == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def calibration_error(y: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> float:
    flat_y, flat_p = y.ravel(), probabilities.ravel()
    error = 0.0
    for lower in np.linspace(0, 1, bins, endpoint=False):
        upper = lower + 1 / bins
        mask = (flat_p >= lower) & (flat_p < upper if upper < 1 else flat_p <= upper)
        if np.any(mask):
            error += np.mean(mask) * abs(float(np.mean(flat_y[mask])) - float(np.mean(flat_p[mask])))
    return error


def choose_threshold(y: np.ndarray, probabilities: np.ndarray) -> float:
    best = (0.0, 0.5)
    for threshold in np.linspace(0.1, 0.9, 81):
        precision, _, f1 = precision_recall_f1(y, probabilities >= threshold)
        candidate = f1 if precision >= 0.60 else f1 * 0.5
        if candidate > best[0]:
            best = (candidate, float(threshold))
    return best[1]


def rounded(value: float) -> float:
    return round(float(value), 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    corpus, corpus_manifest = load_corpus()
    records = corpus["observations"]
    splits = split_records(records)
    universe = sorted({label for record in records for label in labels(record)})
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, max_features=12000, sublinear_tf=True)
    x_train = vectorizer.fit_transform(model_text(record) for record in splits["train"])
    x_cal = vectorizer.transform(model_text(record) for record in splits["calibration"])
    x_eval = vectorizer.transform(model_text(record) for record in splits["evaluation"])
    y_train, y_cal, y_eval = (matrix(splits[name], universe) for name in ("train", "calibration", "evaluation"))

    eval_probabilities = np.zeros_like(y_eval, dtype=float)
    calibrator_data = []
    model_data = []
    thresholds = []
    for index, label in enumerate(universe):
        base = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
        base.fit(x_train, y_train[:, index])
        cal_scores = base.decision_function(x_cal).reshape(-1, 1)
        if len(np.unique(y_cal[:, index])) == 2:
            calibrator = LogisticRegression(max_iter=1000, random_state=42)
            calibrator.fit(cal_scores, y_cal[:, index])
            cal_probabilities = calibrator.predict_proba(cal_scores)[:, 1]
            eval_probabilities[:, index] = calibrator.predict_proba(base.decision_function(x_eval).reshape(-1, 1))[:, 1]
            calibrator_data.append({"coefficient": float(calibrator.coef_[0, 0]), "intercept": float(calibrator.intercept_[0])})
        else:
            cal_probabilities = sigmoid(cal_scores[:, 0])
            eval_probabilities[:, index] = sigmoid(base.decision_function(x_eval))
            calibrator_data.append({"coefficient": 1.0, "intercept": 0.0, "fallback": "uncalibrated-single-class-calibration-split"})
        thresholds.append(choose_threshold(y_cal[:, index], cal_probabilities))
        model_data.append({"label": label, "coefficient": base.coef_[0].tolist(), "intercept": float(base.intercept_[0])})

    thresholds_array = np.asarray(thresholds)
    positive = eval_probabilities >= (thresholds_array + MARGIN)
    negative = eval_probabilities < (thresholds_array - MARGIN)
    decided = positive | negative
    per_label = {}
    supports = Counter(label for record in splits["train"] for label in labels(record))
    for index, label in enumerate(universe):
        precision, recall, f1 = precision_recall_f1(y_eval[:, index], positive[:, index], decided[:, index])
        per_label[label] = {
            "trainSupport": supports[label], "evaluationSupport": int(np.sum(y_eval[:, index])),
            "threshold": rounded(thresholds[index]), "abstentionMargin": MARGIN,
            "coverage": rounded(np.mean(decided[:, index])), "precision": rounded(precision),
            "recall": rounded(recall), "f1": rounded(f1),
        }
    micro = precision_recall_f1(y_eval, positive, decided)
    macro_f1 = float(np.mean([row["f1"] for row in per_label.values()]))
    tail_rows = [row for row in per_label.values() if row["trainSupport"] <= 50]
    brier = float(np.mean((eval_probabilities - y_eval) ** 2))
    ece = calibration_error(y_eval, eval_probabilities)

    parent_consistency = 1.0  # Parents are deterministically emitted iff any child is positive.
    report = {
        "schemaVersion": "jobservatory.hierarchical-classifier-eval.v1",
        "task": "hierarchical multi-label listing classification",
        "data": {
            "corpusGeneratedAt": corpus["sourceGeneratedAt"], "observations": len(records),
            "corpusSnapshot": corpus_manifest["snapshot"], "corpusCanonicalSha256": corpus_manifest["canonicalSha256"],
            "splitMethod": "duplicate-grouped chronological order using source update, source publication, then retrieval time",
            "splitSemantics": "development source-time split; not a longitudinal observation holdout",
            "splits": {name: len(rows) for name, rows in splits.items()},
            "targetProvenance": "versioned rule-generated weak labels",
            "features": "title and location TF-IDF only; employer and rule-selected evidence excluded",
        },
        "hierarchy": {"parents": sorted({label.split('/')[0] for label in universe}), "leafLabels": len(universe), "parentConsistency": parent_consistency},
        "model": {"type": "per-label class-weighted logistic regression plus held-split Platt calibration", "features": len(vectorizer.vocabulary_), "randomSeed": 42},
        "abstention": {"policy": "per-label calibrated threshold plus/minus margin", "margin": MARGIN, "microDecisionCoverage": rounded(np.mean(decided))},
        "aggregate": {
            "microPrecision": rounded(micro[0]), "microRecall": rounded(micro[1]), "microF1": rounded(micro[2]),
            "macroF1": rounded(macro_f1), "tailLabelMacroF1": rounded(np.mean([row["f1"] for row in tail_rows]) if tail_rows else 0),
            "brierScore": rounded(brier), "expectedCalibrationError": rounded(ece),
        },
        "perLabel": per_label,
        "promotion": {
            "status": "not_eligible", "evidenceGatePass": False,
            "reasons": [
                "Targets are rule-generated weak labels rather than independently annotated gold labels.",
                "The split uses source timestamps from one retrieval snapshot, not a longitudinal temporal holdout.",
                "Source-content training rights remain pending.",
            ],
        },
        "limitations": [
            "Metrics measure agreement with weak rules, not semantic ground truth.",
            "Title/location features omit most role-description evidence.",
            "Calibration against weak labels does not establish real-world probability calibration.",
            "No employment or candidate decision may use this research candidate.",
        ],
    }
    artifact = {
        "schemaVersion": "jobservatory.hierarchical-classifier.v1", "labels": universe,
        "vocabulary": {term: int(index) for term, index in vectorizer.vocabulary_.items()}, "idf": vectorizer.idf_.tolist(),
        "baseModels": model_data, "calibrators": calibrator_data, "thresholds": thresholds,
        "abstentionMargin": MARGIN, "hierarchyRule": "emit family parent iff any child is positive",
    }
    artifact_bytes = (json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if args.write:
        METRICS.parent.mkdir(parents=True, exist_ok=True)
        METRICS.write_text(json.dumps(report, indent=2) + "\n")
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        with MODEL.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                compressed.write(artifact_bytes)
        manifest = {
            "schemaVersion": "jobservatory.model-manifest.v1", "modelId": "hierarchical-classifier-v0.1",
            "artifact": str(MODEL.relative_to(ROOT)), "artifactSha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
            "uncompressedSha256": hashlib.sha256(artifact_bytes).hexdigest(),
            "trainingCorpus": corpus_manifest["snapshot"], "trainingCorpusCanonicalSha256": corpus_manifest["canonicalSha256"],
            "metrics": str(METRICS.relative_to(ROOT)), "promotion": report["promotion"],
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"aggregate": report["aggregate"], "abstention": report["abstention"], "promotion": report["promotion"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
