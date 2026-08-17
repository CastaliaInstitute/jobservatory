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
assert corpus["summary"]["observations"] == len(records)
assert corpus["coverage"]["publishedObservations"] == len(records)
assert corpus["coverage"]["eligibleObservations"] >= len(records)
assert corpus["coverage"]["sourcesSuccessful"] == corpus["coverage"]["sourcesConfigured"]
assert not corpus["coverage"]["sourceFailures"]
assert all(item["status"] == "ok" and item["httpStatus"] == 200 and item["rightsReviewStatus"] for item in corpus["coverage"]["retrieval"])
assert len({item["observationId"] for item in records}) == len(records)
assert len({item["analysisId"] for item in records}) == len(records)
for item in records:
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", item["contentHash"])
    assert item["roleRelevance"]["tier"] in {"direct", "applied"}
    assert item["descriptionPolicy"] == "metadata-and-evidence-only"
    assert item["classifications"]["laborEffect"]["label"] == "unclassified"
    assert item["extraction"]["reviewStatus"] == "unreviewed"
    assert "<" not in json.dumps(item["classifications"])

assert signal["schemaVersion"] == "apocalypso.signal.v2"
if signal["signal"]["status"] == "insufficient_history":
    assert signal["signal"]["value"] is None
else:
    assert isinstance(signal["signal"]["value"], (int, float))

print(f"validated {len(records)} observations and {len(corpus['coverage']['retrieval'])} source manifests")
