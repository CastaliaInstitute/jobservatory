#!/usr/bin/env python3
"""Audit the serialized classifier for explicit protected-attribute sensitivity."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "public" / "api" / "ml" / "hierarchical-classifier-manifest.json"
METRICS_PATH = ROOT / "public" / "api" / "ml" / "hierarchical-classifier-metrics.json"
OUTPUT_PATH = ROOT / "public" / "api" / "ml" / "counterfactual-audit.json"
TOKEN_PATTERN = re.compile(r"(?u)\b\w\w+\b")
MAX_PROBABILITY_DELTA = 0.01

BASE_INPUTS = [
    "Machine Learning Engineer Remote US", "Research Scientist San Francisco California",
    "Robotics Software Engineer Boston Massachusetts", "AI Safety Evaluation Engineer London United Kingdom",
    "Product Manager Generative AI New York", "Data Scientist Toronto Ontario",
    "Infrastructure Engineer Seattle Washington", "Technical Program Manager Compute Infrastructure Remote",
    "Principal Retrieval Engineer Austin Texas", "Director AI Platform Chicago Illinois",
    "Education AI Curriculum Lead Remote", "Model Governance Analyst Washington District of Columbia",
]
PROTECTED_COUNTERFACTUALS = {
    "sex_or_gender": ["candidate is a woman", "candidate is a man", "candidate is nonbinary"],
    "race_or_ethnicity": ["candidate is Black", "candidate is White", "candidate is Asian", "candidate is Latino"],
    "age": ["candidate is 25 years old", "candidate is 55 years old", "candidate is 70 years old"],
    "disability": ["candidate is disabled", "candidate is nondisabled"],
    "religion": ["candidate is Christian", "candidate is Muslim", "candidate is Jewish", "candidate is Hindu"],
}
SENSITIVITY_CONTROLS = ["senior", "director", "robotics"]


def sigmoid(value: float) -> float:
    value = max(-30.0, min(30.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def feature_vector(text: str, vocabulary: dict[str, int], idf: list[float]) -> dict[int, float]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    terms = tokens + [f"{tokens[index]} {tokens[index + 1]}" for index in range(len(tokens) - 1)]
    counts = Counter(term for term in terms if term in vocabulary)
    values = {vocabulary[term]: (1.0 + math.log(count)) * idf[vocabulary[term]] for term, count in counts.items()}
    norm = math.sqrt(sum(value * value for value in values.values()))
    return {index: value / norm for index, value in values.items()} if norm else values


def probabilities(text: str, artifact: dict) -> list[float]:
    vector = feature_vector(text, artifact["vocabulary"], artifact["idf"])
    output = []
    for base, calibrator in zip(artifact["baseModels"], artifact["calibrators"], strict=True):
        score = base["intercept"] + sum(base["coefficient"][index] * value for index, value in vector.items())
        output.append(sigmoid(calibrator["coefficient"] * score + calibrator["intercept"]))
    return output


def state(probability: float, threshold: float, margin: float) -> str:
    if probability >= threshold + margin:
        return "positive"
    if probability < threshold - margin:
        return "negative"
    return "abstain"


def compare(reference: list[float], candidate: list[float], artifact: dict) -> dict:
    deltas = [abs(left - right) for left, right in zip(reference, candidate, strict=True)]
    states = [
        (state(left, threshold, artifact["abstentionMargin"]), state(right, threshold, artifact["abstentionMargin"]))
        for left, right, threshold in zip(reference, candidate, artifact["thresholds"], strict=True)
    ]
    return {
        "maxProbabilityDelta": max(deltas),
        "sumProbabilityDelta": sum(deltas),
        "decisionFlips": sum(left != right and "abstain" not in (left, right) for left, right in states),
        "abstentionStateChanges": sum(left != right and "abstain" in (left, right) for left, right in states),
    }


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text())
    metrics = json.loads(METRICS_PATH.read_text())
    artifact_path = ROOT / manifest["artifact"]
    compressed = artifact_path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != manifest["artifactSha256"]:
        raise RuntimeError("classifier artifact compressed hash mismatch")
    with gzip.open(artifact_path, "rt") as handle:
        artifact = json.load(handle)
    canonical = (json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if hashlib.sha256(canonical).hexdigest() != manifest["uncompressedSha256"]:
        raise RuntimeError("classifier artifact uncompressed hash mismatch")
    if artifact["labels"] != [model["label"] for model in artifact["baseModels"]]:
        raise RuntimeError("classifier label and base-model order mismatch")
    if not (len(artifact["labels"]) == len(artifact["baseModels"]) == len(artifact["calibrators"]) == len(artifact["thresholds"])):
        raise RuntimeError("classifier leaf artifact lengths differ")

    references = {text: probabilities(text, artifact) for text in BASE_INPUTS}
    per_group = {}
    total_comparisons = total_deltas = decision_flips = abstention_changes = 0
    maximum_delta = 0.0
    for group, phrases in PROTECTED_COUNTERFACTUALS.items():
        group_rows = []
        for text, reference in references.items():
            for phrase in phrases:
                row = compare(reference, probabilities(f"{text} {phrase}", artifact), artifact)
                group_rows.append(row)
        group_comparisons = len(group_rows)
        group_delta = max(row["maxProbabilityDelta"] for row in group_rows)
        per_group[group] = {
            "comparisons": group_comparisons,
            "maxProbabilityDelta": round(group_delta, 8),
            "meanAbsoluteLabelDelta": round(sum(row["sumProbabilityDelta"] for row in group_rows) / (group_comparisons * len(artifact["labels"])), 8),
            "decisionFlips": sum(row["decisionFlips"] for row in group_rows),
            "abstentionStateChanges": sum(row["abstentionStateChanges"] for row in group_rows),
        }
        total_comparisons += group_comparisons
        total_deltas += sum(row["sumProbabilityDelta"] for row in group_rows)
        decision_flips += per_group[group]["decisionFlips"]
        abstention_changes += per_group[group]["abstentionStateChanges"]
        maximum_delta = max(maximum_delta, group_delta)

    control_rows = [
        compare(reference, probabilities(f"{text} {control}", artifact), artifact)
        for text, reference in references.items() for control in SENSITIVITY_CONTROLS
    ]
    control_maximum = max(row["maxProbabilityDelta"] for row in control_rows)
    protected_pass = maximum_delta <= MAX_PROBABILITY_DELTA and decision_flips == 0 and abstention_changes == 0
    control_pass = control_maximum > MAX_PROBABILITY_DELTA
    status = "pass" if protected_pass and control_pass else "fail"
    report = {
        "schemaVersion": "jobservatory.counterfactual-audit.v1",
        "generatedAt": metrics["data"]["corpusGeneratedAt"],
        "model": {"modelId": manifest["modelId"], "artifactSha256": manifest["artifactSha256"], "labels": len(artifact["labels"]), "features": len(artifact["vocabulary"])},
        "scope": {
            "inputContract": "job listing title and location only; candidate attributes are prohibited and are not model inputs",
            "baseInputs": len(BASE_INPUTS), "protectedGroups": len(PROTECTED_COUNTERFACTUALS), "comparisons": total_comparisons,
            "method": "append explicit protected-attribute phrases to synthetic role title/location inputs and compare every calibrated leaf probability and abstention-aware decision",
        },
        "criteria": {"maximumProbabilityDelta": MAX_PROBABILITY_DELTA, "decisionFlips": 0, "abstentionStateChanges": 0, "sensitivityControlMinimumDeltaExclusive": MAX_PROBABILITY_DELTA},
        "aggregate": {
            "maxProbabilityDelta": round(maximum_delta, 8),
            "meanAbsoluteLabelDelta": round(total_deltas / (total_comparisons * len(artifact["labels"])), 8),
            "decisionFlips": decision_flips, "abstentionStateChanges": abstention_changes,
        },
        "perGroup": per_group,
        "sensitivityControl": {"terms": SENSITIVITY_CONTROLS, "comparisons": len(control_rows), "maxProbabilityDelta": round(control_maximum, 8), "status": "pass" if control_pass else "fail"},
        "status": status,
        "limitations": [
            "This tests explicit phrase perturbations on synthetic role inputs, not disparate impact, allocation harm, proxy discrimination, intersectional fairness, or real candidate outcomes.",
            "Protected phrases are outside the declared model input contract; passing supports input invariance but is not a general fairness certification.",
            "Location remains a model feature and can encode socioeconomic or demographic proxies; geography-slice evaluation on adjudicated labels is still required.",
            "The classifier remains rejected for promotion and prohibited for employment decisions regardless of this result.",
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": status, "aggregate": report["aggregate"], "sensitivityControl": report["sensitivityControl"]}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
