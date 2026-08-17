#!/usr/bin/env python3
"""Fail-closed semantic checks for generated research artifacts."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
corpus = json.loads((ROOT / "public/api/observatory.json").read_text())
signal = json.loads((ROOT / "public/api/apocalypso/jobs-signal.json").read_text())
records = corpus["observations"]

assert corpus["schemaVersion"] == "0.2.0"
assert corpus["onet"]["version"] == "30.3"
assert corpus["onet"]["license"] == "CC BY 4.0"
assert "not listing-stated requirements" in corpus["onet"]["profileSemantics"]
assert corpus["summary"]["observations"] == len(records)
assert corpus["coverage"]["publishedObservations"] == len(records)
assert corpus["coverage"]["eligibleObservations"] >= len(records)
assert corpus["coverage"]["sourcesSuccessful"] == corpus["coverage"]["sourcesConfigured"]
assert corpus["coverage"]["sourceRegistryVersion"].startswith("jobservatory-sources-")
assert "not labor-market completeness" in corpus["coverage"]["definition"]
assert not corpus["coverage"]["sourceFailures"]
assert all(item["status"] == "ok" and item["httpStatus"] == 200 and item["rightsReviewStatus"] and item["ats"] in {"greenhouse", "lever", "ashby"} and item["sourceKey"] for item in corpus["coverage"]["retrieval"])
assert all(item["feedSchemaVersion"] and item["accessBasis"].startswith("official-public-") and item["documentationUrl"].startswith("https://") and item["documentationReviewedAt"] and item["redistributionReviewStatus"] and item["modelTrainingReviewStatus"] for item in corpus["coverage"]["retrieval"])
assert sum(corpus["coverage"]["atsProviders"].values()) == corpus["coverage"]["sourcesSuccessful"]
assert corpus["coverage"]["assessment"]["status"] in {"expanding", "target_met"}
assert "labor-market representativeness" in corpus["coverage"]["assessment"]["semantics"]
assert corpus["coverage"]["assessment"]["actual"]["employers"] == corpus["summary"]["employers"]
assert corpus["coverage"]["assessment"]["actual"]["sectors"] == len(corpus["coverage"]["sectors"])
assert corpus["summary"]["sourceConcentration"]["largestEmployerShare"] <= 1
assert corpus["summary"]["sourceConcentration"]["herfindahlHirschmanIndex"] <= 1
assert corpus["summary"]["entityResolution"]["methodVersion"].startswith("jobservatory-entity-resolution-")
assert corpus["summary"]["entityResolution"]["postingFamilies"] <= len(records)
assert len({item["observationId"] for item in records}) == len(records)
assert len({item["analysisId"] for item in records}) == len(records)
for item in records:
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", item["contentHash"])
    assert item["roleRelevance"]["tier"] in {"direct", "applied"}
    assert item["descriptionPolicy"] == "metadata-and-evidence-only"
    assert item["classifications"]["laborEffect"]["label"] == "unclassified"
    assert item["extraction"]["reviewStatus"] == "unreviewed"
    assert item["duplicateGroup"] == item["entityResolution"]["exactVariantGroupId"]
    assert item["entityResolution"]["reviewStatus"] == "unreviewed"
    assert item["entityResolution"]["familySize"] >= item["entityResolution"]["exactVariantGroupSize"] >= 1
    assert "<" not in json.dumps(item["classifications"])
    for skill in item["classifications"]["skills"]:
        if "onetSoftwareSkill" in skill:
            normalized = skill["onetSoftwareSkill"]
            assert normalized["occupationCode"] == item["onetOccupation"]["code"]
            assert normalized["onetVersion"] == "30.3"
            assert normalized["normalizationBasis"] == "listing evidence plus occupation-linked exact crosswalk"

assert signal["schemaVersion"] == "apocalypso.signal.v2"
if signal["signal"]["status"] == "insufficient_history":
    assert signal["signal"]["value"] is None
else:
    assert isinstance(signal["signal"]["value"], (int, float))

print(f"validated {len(records)} observations and {len(corpus['coverage']['retrieval'])} source manifests")
