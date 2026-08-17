#!/usr/bin/env python3
"""Build blind temporal annotation packages and fail-closed readiness evidence."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from retrieval_lab import RetrievalIndex

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "ml" / "eval" / "independent"
PROTOCOL_PATH = BASE / "protocol.json"
CORPUS_MANIFEST_PATH = BASE / "corpus-manifest.json"
PACKAGE_DIR = BASE / "packages"
SUBMISSION_DIR = BASE / "submissions"
PUBLIC_PATH = ROOT / "public" / "api" / "ml" / "independent-evaluation-readiness.json"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def family(record: dict) -> str:
    return record["entityResolution"]["postingFamilyId"]


def evidence(record: dict) -> list[str]:
    excerpts: list[str] = []
    seen: set[str] = set()
    for name in ("aiRelationship", "systemLayer", "skills"):
        for hit in record["classifications"].get(name, []):
            excerpt = " ".join(hit.get("evidence", "").split())[:500]
            if excerpt and excerpt not in seen:
                excerpts.append(excerpt)
                seen.add(excerpt)
    return excerpts[:8]


def blind_record(record: dict) -> dict:
    compensation = record.get("compensation")
    return {
        "title": record["title"],
        "location": record["location"],
        "seniority": record["seniority"],
        "domain": record["domain"],
        "compensation": compensation,
        "evidenceExcerpts": evidence(record),
        "evidencePolicy": "metadata-and-short-evidence-only",
    }


def opaque_id(protocol_id: str, kind: str, source: str) -> str:
    raw = f"{protocol_id}\0{kind}\0{source}".encode()
    return f"{kind[:1]}-{hashlib.sha256(raw).hexdigest()[:20]}"


def temporal_split(records: list[dict], protocol: dict) -> tuple[list[dict], list[dict], dict]:
    config = protocol["temporalSplit"]
    cutoff = parse_time(config["cutoff"])
    known = [record for record in records if record.get(config["timestampField"])]
    before = [record for record in known if parse_time(record[config["timestampField"]]) < cutoff]
    after = [record for record in known if parse_time(record[config["timestampField"]]) >= cutoff]
    before_families = {family(record) for record in before}
    after_families = {family(record) for record in after}
    crossing = before_families & after_families
    holdout = [record for record in after if family(record) not in crossing]
    training = before
    leakage = {family(record) for record in training} & {family(record) for record in holdout}
    report = {
        "timestampField": config["timestampField"],
        "cutoff": config["cutoff"],
        "semantics": "source-publication temporal split from one frozen corpus snapshot; not a longitudinal observation-history holdout",
        "knownTimestampRecords": len(known),
        "excludedUnknownTimestampRecords": len(records) - len(known),
        "trainingCandidates": len(training),
        "rawHoldoutCandidates": len(after),
        "holdoutCandidates": len(holdout),
        "crossingFamiliesQuarantined": len(crossing),
        "postingFamilyLeakage": len(leakage),
        "status": "pass" if len(training) >= config["minimumTrainingCandidates"] and len(holdout) >= config["minimumHoldoutCandidates"] and not leakage else "fail",
    }
    return training, holdout, report


def retrieval_tasks(protocol: dict, holdout: list[dict]) -> list[dict]:
    index = RetrievalIndex(holdout)
    by_id = {row["observationId"]: row for row in holdout}
    limit = protocol["retrieval"]["candidatesPerQuery"]
    tasks: list[dict] = []
    for query in protocol["retrieval"]["queries"]:
        bm25 = [item[0] for item in index.bm25(query["query"])[:limit * 3]]
        dense = [item[0] for item in index.dense(query["query"])[:limit * 3]]
        pool: list[str] = []
        pooled_families: set[str] = set()
        for left, right in zip(bm25, dense):
            for observation_id in (left, right):
                posting_family = family(by_id[observation_id])
                if observation_id not in pool and posting_family not in pooled_families:
                    pool.append(observation_id)
                    pooled_families.add(posting_family)
                if len(pool) == limit:
                    break
            if len(pool) == limit:
                break
        for observation_id in pool:
            task_id = opaque_id(protocol["protocolId"], "retrieval", f"{query['id']}\0{observation_id}")
            tasks.append({
                "taskId": task_id,
                "queryId": query["id"],
                "query": query["query"],
                "stratum": query["stratum"],
                "document": blind_record(by_id[observation_id]),
                "judgment": None,
            })
    return tasks


def stratified_sample(records: list[dict], size: int, protocol_id: str) -> list[dict]:
    unique_by_family: dict[str, dict] = {}
    for record in sorted(records, key=lambda row: hashlib.sha256(f"{protocol_id}\0{row['observationId']}".encode()).hexdigest()):
        unique_by_family.setdefault(family(record), record)
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in unique_by_family.values():
        groups[f"{record['domain']}\0{record['seniority']}"].append(record)
    for key in groups:
        groups[key].sort(key=lambda row: hashlib.sha256(f"{protocol_id}\0{row['observationId']}".encode()).hexdigest())
    selected: list[dict] = []
    keys = sorted(groups)
    while len(selected) < min(size, len(unique_by_family)):
        changed = False
        for key in keys:
            if groups[key] and len(selected) < size:
                selected.append(groups[key].pop(0))
                changed = True
        if not changed:
            break
    return selected


def classification_tasks(protocol: dict, holdout: list[dict]) -> list[dict]:
    sample = stratified_sample(holdout, protocol["classification"]["sampleSize"], protocol["protocolId"])
    return [{
        "taskId": opaque_id(protocol["protocolId"], "classification", record["observationId"]),
        "document": blind_record(record),
        "labels": {name: [] for name in protocol["classification"]["families"]},
        "insufficientEvidence": None,
    } for record in sample]


def write_packages(protocol: dict, retrieval: list[dict], classification: list[dict], corpus_manifest: dict) -> dict:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    result = {"taskSetSha256": {"retrieval": digest(retrieval), "classification": digest(classification)}, "packages": {}}
    for kind, tasks in (("retrieval", retrieval), ("classification", classification)):
        result["packages"][kind] = {}
        for slot in ("a", "b"):
            ordered = list(tasks)
            random.Random(f"{protocol['protocolId']}:{kind}:{slot}").shuffle(ordered)
            package = {
                "schemaVersion": f"jobservatory.{kind}-annotation-package.v1",
                "protocolId": protocol["protocolId"],
                "reviewerSlot": slot,
                "blind": True,
                "blinding": ["employer", "source", "sourceUrl", "observationId", "existingTargetLabels", "modelScores", "candidateRankProvenance"],
                "corpus": {"snapshot": corpus_manifest["snapshot"], "canonicalSha256": corpus_manifest["canonicalSha256"]},
                "taskSetSha256": result["taskSetSha256"][kind],
                "instructions": "See ml/eval/independent/README.md",
                "tasks": ordered,
            }
            if kind == "classification":
                package["labelOntology"] = protocol["classification"]["families"]
            path = PACKAGE_DIR / f"{kind}-reviewer-{slot}.json"
            path.write_bytes(canonical(package))
            result["packages"][kind][slot] = {
                "path": str(path.relative_to(ROOT)),
                "sha256": file_digest(path),
                "tasks": len(tasks),
            }
    return result


def load_submission(kind: str, slot: str, package: dict, tasks: list[dict], protocol: dict) -> tuple[dict | None, list[str]]:
    path = SUBMISSION_DIR / f"{kind}-reviewer-{slot}.json"
    blockers: list[str] = []
    if not path.exists():
        return None, [f"{kind}.reviewer_{slot}.missing"]
    try:
        value = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None, [f"{kind}.reviewer_{slot}.invalid_json"]
    expected_ids = {task["taskId"] for task in tasks}
    judgments = value.get("judgments", [])
    actual_ids = [row.get("taskId") for row in judgments]
    reviewer = value.get("reviewer", {})
    if value.get("protocolId") != protocol["protocolId"]:
        blockers.append(f"{kind}.reviewer_{slot}.protocol_mismatch")
    if value.get("packageSha256") != package["sha256"]:
        blockers.append(f"{kind}.reviewer_{slot}.package_hash_mismatch")
    if not reviewer.get("id") or not reviewer.get("independent") or not reviewer.get("completedAt"):
        blockers.append(f"{kind}.reviewer_{slot}.independence_declaration_incomplete")
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != expected_ids:
        blockers.append(f"{kind}.reviewer_{slot}.task_coverage_invalid")
    if kind == "retrieval":
        if any(type(row.get("grade")) is not int or row["grade"] not in (0, 1, 2, 3) for row in judgments):
            blockers.append(f"{kind}.reviewer_{slot}.invalid_grade")
    else:
        families = protocol["classification"]["families"]
        for row in judgments:
            labels = row.get("labels")
            if not isinstance(row.get("insufficientEvidence"), bool) or not isinstance(labels, dict) or set(labels) != set(families):
                blockers.append(f"{kind}.reviewer_{slot}.invalid_label_shape")
                break
            if any(not isinstance(labels[name], list) or not set(labels[name]).issubset(set(options)) for name, options in families.items()):
                blockers.append(f"{kind}.reviewer_{slot}.unknown_label")
                break
    return value, blockers


def weighted_kappa(left: list[int], right: list[int]) -> float | None:
    if not left or len(left) != len(right):
        return None
    n = 4
    observed = [[0] * n for _ in range(n)]
    for a, b in zip(left, right):
        observed[a][b] += 1
    ca = [sum(row) for row in observed]
    cb = [sum(observed[i][j] for i in range(n)) for j in range(n)]
    total = len(left)
    observed_disagreement = sum(observed[i][j] * ((i - j) / (n - 1)) ** 2 for i in range(n) for j in range(n)) / total
    expected_disagreement = sum(ca[i] * cb[j] / total * ((i - j) / (n - 1)) ** 2 for i in range(n) for j in range(n)) / total
    return 1 - observed_disagreement / expected_disagreement if expected_disagreement else (1.0 if observed_disagreement == 0 else 0.0)


def binary_kappa(left: list[int], right: list[int]) -> float | None:
    if not left or len(left) != len(right):
        return None
    agreement = sum(a == b for a, b in zip(left, right)) / len(left)
    pa = sum(left) / len(left)
    pb = sum(right) / len(right)
    expected = pa * pb + (1 - pa) * (1 - pb)
    return (agreement - expected) / (1 - expected) if expected < 1 else (1.0 if agreement == 1 else 0.0)


def agreement(kind: str, a: dict, b: dict, protocol: dict) -> tuple[dict, set[str]]:
    left = {row["taskId"]: row for row in a["judgments"]}
    right = {row["taskId"]: row for row in b["judgments"]}
    disagreements: set[str] = set()
    if kind == "retrieval":
        ids = sorted(left)
        for task_id in ids:
            if left[task_id]["grade"] != right[task_id]["grade"]:
                disagreements.add(task_id)
        score = weighted_kappa([left[x]["grade"] for x in ids], [right[x]["grade"] for x in ids])
        return {
            "weightedCohenKappa": round(score, 4),
            "exactAgreement": round(1 - len(disagreements) / len(ids), 4),
            "relevantGradesReviewerA": sum(left[x]["grade"] >= 2 for x in ids),
            "relevantGradesReviewerB": sum(right[x]["grade"] >= 2 for x in ids),
            "irrelevantGradesReviewerA": sum(left[x]["grade"] == 0 for x in ids),
            "irrelevantGradesReviewerB": sum(right[x]["grade"] == 0 for x in ids),
            "disagreements": len(disagreements),
        }, disagreements
    families = protocol["classification"]["families"]
    binary_left: list[int] = []
    binary_right: list[int] = []
    jaccards: list[float] = []
    for task_id in sorted(left):
        a_labels = {(name, label) for name in families for label in left[task_id]["labels"][name]}
        b_labels = {(name, label) for name in families for label in right[task_id]["labels"][name]}
        if a_labels != b_labels or left[task_id]["insufficientEvidence"] != right[task_id]["insufficientEvidence"]:
            disagreements.add(task_id)
        union = a_labels | b_labels
        jaccards.append(len(a_labels & b_labels) / len(union) if union else 1.0)
        for name, options in families.items():
            for label in options:
                binary_left.append(int(label in left[task_id]["labels"][name]))
                binary_right.append(int(label in right[task_id]["labels"][name]))
    score = binary_kappa(binary_left, binary_right)
    return {
        "binaryCohenKappa": round(score, 4),
        "meanLabelJaccard": round(sum(jaccards) / len(jaccards), 4),
        "positiveAssignmentsReviewerA": sum(binary_left),
        "positiveAssignmentsReviewerB": sum(binary_right),
        "exactTaskAgreement": round(1 - len(disagreements) / len(left), 4),
        "disagreements": len(disagreements),
    }, disagreements


def adjudication_status(disagreements: dict[str, set[str]], reviewers: set[str], protocol: dict) -> tuple[dict, list[str], dict | None]:
    path = SUBMISSION_DIR / "adjudication.json"
    expected = disagreements["retrieval"] | disagreements["classification"]
    if not path.exists():
        return {"status": "missing", "requiredDecisions": len(expected), "completedDecisions": 0, "coverage": 0.0}, ["adjudication.missing"], None
    try:
        value = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"status": "invalid", "requiredDecisions": len(expected), "completedDecisions": 0, "coverage": 0.0}, ["adjudication.invalid_json"], None
    blockers: list[str] = []
    person = value.get("adjudicator", {})
    if not person.get("id") or person.get("id") in reviewers or not person.get("independentOfReviewers") or not person.get("completedAt"):
        blockers.append("adjudication.independence_invalid")
    retrieval = value.get("retrieval", [])
    classification = value.get("classification", [])
    actual_r = {row.get("taskId") for row in retrieval}
    actual_c = {row.get("taskId") for row in classification}
    if actual_r != disagreements["retrieval"] or actual_c != disagreements["classification"]:
        blockers.append("adjudication.disagreement_coverage_invalid")
    if any(type(row.get("finalGrade")) is not int or row["finalGrade"] not in (0, 1, 2, 3) or not row.get("rationale") for row in retrieval):
        blockers.append("adjudication.retrieval_decision_invalid")
    families = protocol["classification"]["families"]
    for row in classification:
        labels = row.get("finalLabels", {})
        if set(labels) != set(families) or any(not set(labels[name]).issubset(set(options)) for name, options in families.items()) or not isinstance(row.get("insufficientEvidence"), bool) or not row.get("rationale"):
            blockers.append("adjudication.classification_decision_invalid")
            break
    completed = len(actual_r & disagreements["retrieval"]) + len(actual_c & disagreements["classification"])
    coverage = completed / len(expected) if expected else 1.0
    required_coverage = protocol["agreementThresholds"]["adjudicationCoverage"]
    return {"status": "pass" if not blockers and coverage >= required_coverage else "fail", "requiredDecisions": len(expected), "completedDecisions": completed, "coverage": round(coverage, 4)}, blockers, value


def finalize_gold(protocol: dict, holdout: list[dict], valid: dict[str, dict[str, dict]], adjudication: dict, corpus_manifest: dict) -> dict:
    """Write adjudicated labels only after every readiness condition passes."""
    retrieval_a = {row["taskId"]: row for row in valid["retrieval"]["a"]["judgments"]}
    retrieval_b = {row["taskId"]: row for row in valid["retrieval"]["b"]["judgments"]}
    classification_a = {row["taskId"]: row for row in valid["classification"]["a"]["judgments"]}
    classification_b = {row["taskId"]: row for row in valid["classification"]["b"]["judgments"]}
    adjudicated_retrieval = {row["taskId"]: row for row in adjudication["retrieval"]}
    adjudicated_classification = {row["taskId"]: row for row in adjudication["classification"]}
    retrieval_map: dict[str, tuple[str, str]] = {}
    for query in protocol["retrieval"]["queries"]:
        for record in holdout:
            task_id = opaque_id(protocol["protocolId"], "retrieval", f"{query['id']}\0{record['observationId']}")
            retrieval_map[task_id] = (query["id"], record["observationId"])
    classification_map = {opaque_id(protocol["protocolId"], "classification", record["observationId"]): record["observationId"] for record in holdout}
    qrels: dict[str, dict[str, int]] = {query["id"]: {} for query in protocol["retrieval"]["queries"]}
    for task_id, left in retrieval_a.items():
        right = retrieval_b[task_id]
        grade = left["grade"] if left["grade"] == right["grade"] else adjudicated_retrieval[task_id]["finalGrade"]
        query_id, observation_id = retrieval_map[task_id]
        qrels[query_id][observation_id] = grade
    retrieval_gold = {
        "schemaVersion": "jobservatory.adjudicated-retrieval-qrels.v1",
        "protocolId": protocol["protocolId"],
        "corpus": {"snapshot": corpus_manifest["snapshot"], "canonicalSha256": corpus_manifest["canonicalSha256"]},
        "annotationPolicy": "two independent reviewers plus distinct adjudicator for every disagreement",
        "eligibleForPromotionDecision": True,
        "queries": [{**query, "judgments": qrels[query["id"]]} for query in protocol["retrieval"]["queries"]],
    }
    classification_gold = []
    for task_id, left in classification_a.items():
        right = classification_b[task_id]
        if left["labels"] == right["labels"] and left["insufficientEvidence"] == right["insufficientEvidence"]:
            final_labels, insufficient = left["labels"], left["insufficientEvidence"]
        else:
            decision = adjudicated_classification[task_id]
            final_labels, insufficient = decision["finalLabels"], decision["insufficientEvidence"]
        classification_gold.append({"observationId": classification_map[task_id], "labels": final_labels, "insufficientEvidence": insufficient})
    classification_output = {
        "schemaVersion": "jobservatory.adjudicated-classification-gold.v1",
        "protocolId": protocol["protocolId"],
        "corpus": {"snapshot": corpus_manifest["snapshot"], "canonicalSha256": corpus_manifest["canonicalSha256"]},
        "annotationPolicy": "two independent reviewers plus distinct adjudicator for every disagreement",
        "eligibleForPromotionDecision": True,
        "annotations": sorted(classification_gold, key=lambda row: row["observationId"]),
    }
    destination = BASE / "gold"
    destination.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, value in (("retrieval", retrieval_gold), ("classification", classification_output)):
        path = destination / f"{name}.json"
        path.write_bytes(canonical(value))
        paths[name] = {"path": str(path.relative_to(ROOT)), "sha256": file_digest(path)}
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--finalize", action="store_true", help="Write adjudicated gold artifacts; fails unless every evidence gate passes")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL_PATH.read_text())
    corpus_manifest = json.loads(CORPUS_MANIFEST_PATH.read_text())
    snapshot = ROOT / corpus_manifest["snapshot"]
    if file_digest(snapshot) != "sha256:" + corpus_manifest["compressedSha256"]:
        raise RuntimeError("evaluation snapshot compressed hash mismatch")
    with gzip.open(snapshot, "rt") as handle:
        corpus = json.load(handle)
    _, holdout, split = temporal_split(corpus["observations"], protocol)
    retrieval = retrieval_tasks(protocol, holdout)
    classification = classification_tasks(protocol, holdout)
    package_manifest = write_packages(protocol, retrieval, classification, corpus_manifest)
    blockers: list[str] = []
    submissions: dict[str, dict] = {}
    valid: dict[str, dict[str, dict]] = {"retrieval": {}, "classification": {}}
    for kind, tasks in (("retrieval", retrieval), ("classification", classification)):
        submissions[kind] = {}
        for slot in ("a", "b"):
            value, errors = load_submission(kind, slot, package_manifest["packages"][kind][slot], tasks, protocol)
            blockers.extend(errors)
            submissions[kind][slot] = {"status": "valid" if value is not None and not errors else "missing" if errors == [f"{kind}.reviewer_{slot}.missing"] else "invalid", "blockers": errors}
            if value is not None and not errors:
                valid[kind][slot] = value
                submissions[kind][slot]["reviewerId"] = value["reviewer"]["id"]
    metrics: dict[str, dict | None] = {"retrieval": None, "classification": None}
    disagreements = {"retrieval": set(), "classification": set()}
    reviewer_ids: set[str] = set()
    for kind in ("retrieval", "classification"):
        if set(valid[kind]) == {"a", "b"}:
            ids = {valid[kind][slot]["reviewer"]["id"] for slot in ("a", "b")}
            reviewer_ids |= ids
            if len(ids) != 2:
                blockers.append(f"{kind}.reviewers_not_distinct")
            metrics[kind], disagreements[kind] = agreement(kind, valid[kind]["a"], valid[kind]["b"], protocol)
    if metrics["retrieval"] is not None and metrics["retrieval"]["weightedCohenKappa"] < protocol["agreementThresholds"]["retrievalWeightedKappa"]:
        blockers.append("retrieval.agreement_below_threshold")
    if metrics["retrieval"] is not None:
        if min(metrics["retrieval"]["relevantGradesReviewerA"], metrics["retrieval"]["relevantGradesReviewerB"]) < protocol["agreementThresholds"]["retrievalMinimumRelevantPerReviewer"]:
            blockers.append("retrieval.relevant_grade_support_below_minimum")
        if min(metrics["retrieval"]["irrelevantGradesReviewerA"], metrics["retrieval"]["irrelevantGradesReviewerB"]) < protocol["agreementThresholds"]["retrievalMinimumIrrelevantPerReviewer"]:
            blockers.append("retrieval.irrelevant_grade_support_below_minimum")
    if metrics["classification"] is not None:
        if metrics["classification"]["binaryCohenKappa"] < protocol["agreementThresholds"]["classificationBinaryKappa"] or metrics["classification"]["meanLabelJaccard"] < protocol["agreementThresholds"]["classificationMeanLabelJaccard"]:
            blockers.append("classification.agreement_below_threshold")
        if min(metrics["classification"]["positiveAssignmentsReviewerA"], metrics["classification"]["positiveAssignmentsReviewerB"]) < protocol["agreementThresholds"]["classificationMinimumPositiveAssignmentsPerReviewer"]:
            blockers.append("classification.positive_label_support_below_minimum")
    adjudication, adjudication_blockers, adjudication_value = adjudication_status(disagreements, reviewer_ids, protocol)
    blockers.extend(adjudication_blockers)
    if split["status"] != "pass":
        blockers.append("temporal_split.invalid")
    output = {
        "schemaVersion": "jobservatory.independent-evaluation-readiness.v1",
        "generatedAt": corpus.get("generatedAt"),
        "protocol": {"id": protocol["protocolId"], "path": str(PROTOCOL_PATH.relative_to(ROOT)), "sha256": file_digest(PROTOCOL_PATH)},
        "corpus": {"snapshot": corpus_manifest["snapshot"], "canonicalSha256": corpus_manifest["canonicalSha256"], "observations": corpus_manifest["observations"]},
        "temporalSplit": split,
        "blindPackages": package_manifest,
        "submissions": submissions,
        "agreement": metrics,
        "adjudication": adjudication,
        "eligibleForPromotionDecision": not blockers,
        "status": "ready" if not blockers else "awaiting_independent_review",
        "blockers": sorted(set(blockers)),
        "claims": {"independentAnnotationsComplete": not blockers, "longitudinalObservationHoldout": False, "sourcePublicationTemporalHoldout": split["status"] == "pass"},
    }
    rendered = json.dumps(output, indent=2) + "\n"
    if args.write:
        PUBLIC_PATH.parent.mkdir(parents=True, exist_ok=True)
        PUBLIC_PATH.write_text(rendered)
    if args.finalize:
        if blockers or adjudication_value is None:
            raise RuntimeError("cannot finalize gold artifacts while independent evaluation readiness is blocked")
        paths = finalize_gold(protocol, holdout, valid, adjudication_value, corpus_manifest)
        print(json.dumps({"goldArtifacts": paths}, indent=2))
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
