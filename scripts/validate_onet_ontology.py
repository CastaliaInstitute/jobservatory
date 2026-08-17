#!/usr/bin/env python3
"""Validate the committed compact O*NET skill ontology and attribution."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "ontology" / "onet_30_3_skill_profiles.json"
data = json.loads(path.read_text())

assert data["schemaVersion"] == "jobservatory.onet-skill-profiles.v1"
assert data["onetVersion"] == "30.3"
assert data["license"] == "CC BY 4.0"
assert "USDOL/ETA has not approved" in data["attribution"]
assert len(data["profiles"]) == 6
assert all(re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) and source["rows"] > 0 for source in data["sources"].values())
official_names = {item["name"] for profile in data["profiles"].values() for item in profile["softwareSkills"]}
assert all(any(name in official_names for name in names) for names in data["softwareCrosswalk"].values())
assert all(item["inheritedFromOccupation"] for profile in data["profiles"].values() for family in ("essentialSkills", "transferableSkills") for item in profile[family])
print("validated pinned O*NET 30.3 skill ontology, crosswalks, and attribution")
