#!/usr/bin/env python3
"""Build a deterministic, machine-readable data card from the published corpus."""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "public" / "api" / "observatory.json"
OUTPUT_PATH = ROOT / "public" / "api" / "data-card.json"
raw = CORPUS_PATH.read_bytes()
corpus = json.loads(raw)
retrieval = corpus["coverage"]["retrieval"]
rights = Counter(item["rightsReviewStatus"] for item in retrieval)
training_permitted = all(item["modelTrainingReviewStatus"] == "approved" for item in retrieval)

card = {
    "schemaVersion": "jobservatory.data-card.v1",
    "generatedAt": corpus["generatedAt"],
    "corpus": {
        "schemaVersion": corpus["schemaVersion"],
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "unitOfAnalysis": "A public job-listing observation retrieved at a particular time.",
        "descriptionPolicy": "metadata-and-evidence-only",
    },
    "coverage": {
        "employers": corpus["summary"]["employers"],
        "observations": corpus["summary"]["observations"],
        "configuredSources": corpus["coverage"]["sourcesConfigured"],
        "successfulSources": corpus["coverage"]["sourcesSuccessful"],
        "atsProviders": corpus["coverage"]["atsProviders"],
        "sectors": corpus["coverage"]["sectors"],
        "largestEmployerShare": corpus["summary"]["sourceConcentration"]["largestEmployerShare"],
        "herfindahlHirschmanIndex": corpus["summary"]["sourceConcentration"]["herfindahlHirschmanIndex"],
    },
    "provenance": {
        "sourceRegistryVersion": corpus["coverage"]["sourceRegistryVersion"],
        "sourceManifests": len(retrieval),
        "allFeedsSuccessful": corpus["coverage"]["sourcesSuccessful"] == corpus["coverage"]["sourcesConfigured"],
        "allFeedResponsesHashed": all(item.get("responseHash", "").startswith("sha256:") for item in retrieval),
        "durableVersionLedger": "data/observation_versions.ndjson",
        "dailyPresenceSnapshots": "data/snapshots/YYYY-MM-DD.json",
    },
    "rights": {
        "reviewStatusCounts": dict(sorted(rights.items())),
        "allSourcesApproved": all(item["rightsReviewStatus"] == "approved" and item["redistributionReviewStatus"] == "approved" and item["modelTrainingReviewStatus"] == "approved" for item in retrieval),
        "accessBasis": sorted({item["accessBasis"] for item in retrieval}),
        "fullDescriptionsRepublished": False,
        "modelTrainingPermitted": training_permitted,
        "notice": "A documented public API establishes technical access, not permission to redistribute employer-authored content or train models. Those reviews remain separate and fail closed.",
    },
    "labels": {
        "extractionVersion": corpus["methods"]["extraction"],
        "ontologyVersion": corpus["methods"]["ontology"],
        "reviewStatus": corpus["methods"]["labelReview"],
        "onetVersion": corpus["onet"]["version"],
        "onetLicense": corpus["onet"]["license"],
        "semantics": "Rule-derived labels and O*NET candidates are unreviewed inferences; occupation-inherited profiles are context, not listing facts.",
    },
    "intendedUses": ["labor-market research within the declared source universe", "retrieval and classification evaluation", "aggregate term and compensation analysis with coverage warnings"],
    "prohibitedUses": ["automated employment decisions", "candidate screening or rejection", "claims of labor-market representativeness", "model training on source content until rights approval"],
    "knownLimitations": ["Curated employer cohort", "source and employer concentration", "one-day longitudinal history at initial publication", "unreviewed weak labels", "missing compensation is not missing at random", "reposts and location variants are not fully resolved"],
}
OUTPUT_PATH.write_text(json.dumps(card, indent=2) + "\n")
print(f"data card: {card['coverage']['observations']} observations; rights approved={card['rights']['allSourcesApproved']}")
