#!/usr/bin/env python3
"""Build the fail-closed, source-level rights review register."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
CORPUS_PATH = ROOT / "public" / "api" / "observatory.json"
OUTPUT_PATH = ROOT / "public" / "api" / "governance" / "source-rights-register.json"
REVIEW_INPUT_PATH = ROOT / "config" / "source-rights-decisions.json"


def board_url(ats: str, source_key: str) -> str:
    if ats == "greenhouse":
        return f"https://job-boards.greenhouse.io/{source_key}"
    if ats == "lever":
        return f"https://jobs.lever.co/{source_key}"
    return f"https://jobs.ashbyhq.com/{source_key}"


def main() -> int:
    config_bytes = CONFIG_PATH.read_bytes()
    config = json.loads(config_bytes)
    review_input_bytes = REVIEW_INPUT_PATH.read_bytes()
    review_input = json.loads(review_input_bytes)
    corpus = json.loads(CORPUS_PATH.read_text())
    retrieved = {(item["ats"], item["sourceKey"]): item for item in corpus["coverage"]["retrieval"]}
    reviews = []
    for ats in ("greenhouse", "lever", "ashby"):
        policy = config["atsPolicies"][ats]
        for source in config.get(ats, []):
            source_key = source.get("board") or source.get("site")
            evidence = retrieved[(ats, source_key)]
            registry_decisions = {
                "retrieval": source["rightsReviewStatus"],
                "metadataRetention": source["rightsReviewStatus"],
                "shortExcerptPublication": source.get("redistributionReviewStatus", policy["redistributionReviewStatus"]),
                "redistribution": source.get("redistributionReviewStatus", policy["redistributionReviewStatus"]),
                "modelTraining": source.get("modelTrainingReviewStatus", policy["modelTrainingReviewStatus"]),
                "rawResponseRetention": "not_requested",
            }
            source_id = f"{ats}:{source_key}"
            override = review_input["reviews"].get(source_id, {})
            decisions = {**registry_decisions, **override.get("decisions", {})}
            decision_evidence = {
                "employerTermsUrl": None,
                "reviewer": None,
                "reviewedAt": None,
                "notes": "Technical public-API access is documented, but no legal conclusion is inferred from accessibility. Employer-specific terms and an accountable review are still required.",
                **override.get("decisionEvidence", {}),
            }
            registry_aligned = decisions == registry_decisions
            blockers = [name for name, status in decisions.items() if status == "pending"]
            if any(status == "approved" for status in decisions.values()) and not all(decision_evidence.get(name) for name in ("employerTermsUrl", "reviewer", "reviewedAt")):
                blockers.append("decisionEvidence")
            if not registry_aligned:
                blockers.append("registryAlignment")
            reviews.append({
                "sourceId": source_id,
                "employer": source["employer"],
                "ats": ats,
                "sourceKey": source_key,
                "sector": source["sector"],
                "jobBoardUrl": board_url(ats, source_key),
                "technicalAccess": {
                    "accessBasis": policy["accessBasis"],
                    "documentationUrl": policy["documentationUrl"],
                    "documentationReviewedAt": policy["documentationReviewedAt"],
                    "lastSuccessfulResponseSha256": evidence["responseHash"],
                    "lastSuccessfulHttpStatus": evidence["httpStatus"],
                },
                "retentionPolicy": source["retentionPolicy"],
                "decisions": decisions,
                "decisionEvidence": decision_evidence,
                "registryAligned": registry_aligned,
                "blockers": sorted(blockers),
            })
    known_source_ids = {review["sourceId"] for review in reviews}
    unknown_review_ids = sorted(set(review_input["reviews"]) - known_source_ids)
    if unknown_review_ids:
        raise ValueError(f"rights review input contains unknown source IDs: {unknown_review_ids}")
    reviews.sort(key=lambda item: item["sourceId"])
    decision_statuses = [status for review in reviews for status in review["decisions"].values()]
    actionable = [status for status in decision_statuses if status != "not_requested"]
    approved = sum(status == "approved" for status in actionable)
    output = {
        "schemaVersion": "jobservatory.source-rights-register.v1",
        "generatedAt": corpus["generatedAt"],
        "sourceRegistryVersion": config["registryVersion"],
        "sourceRegistrySha256": "sha256:" + hashlib.sha256(config_bytes).hexdigest(),
        "reviewInputSha256": "sha256:" + hashlib.sha256(review_input_bytes).hexdigest(),
        "policy": {
            "fullDescriptionsRepublished": False,
            "sourceContentModelTrainingEnabled": False,
            "defaultDecision": "pending",
            "notice": "Public technical access is not a license. Every decision requires source-specific evidence and an accountable reviewer.",
        },
        "summary": {
            "sources": len(reviews),
            "actionableDecisions": len(actionable),
            "approvedDecisions": approved,
            "pendingDecisions": sum(status == "pending" for status in actionable),
            "rejectedDecisions": sum(status == "rejected" for status in actionable),
            "status": "approved" if actionable and approved == len(actionable) else "pending",
        },
        "reviews": reviews,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n")
    print(f"source rights register: {len(reviews)} sources; status={output['summary']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
