#!/usr/bin/env python3
"""Build a compact, pinned O*NET 30.3 skill ontology for mapped occupations."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "ontology" / "onet_30_3_skill_profiles.json"
BASE_URL = "https://www.onetcenter.org/dl_files/database/db_30_3_csv"
FILES = {
    "software_skills": ("software_skills.csv", "6aabb96b464288db849580e6510530efff3f80e25dde2bb23f1fc36bb526b016"),
    "essential_skills": ("essential_skills.csv", "4b709259b07de7e414f2d524365ce79dcce0e1c79c6e9ed35a4bc02163cf3737"),
    "transferable_skills": ("transferable_skills.csv", "23985fa24e0197067c02b3f062f0520839ef15a8980b93518bae68eeb041a841"),
}
OCCUPATIONS = {
    "11-3021.00", "13-1082.00", "15-1221.00", "15-1252.00", "15-2051.00", "17-2199.08",
}
SOFTWARE_CROSSWALK = {
    "AWS": ["Amazon Web Services AWS software"],
    "C++": ["C++"],
    "Go": ["Go"],
    "Kubernetes": ["Kubernetes"],
    "Python": ["Python"],
    "PyTorch": ["PyTorch"],
    "SQL": ["Structured query language SQL"],
    "TensorFlow": ["TensorFlow"],
    "TypeScript": ["TypeScript"],
}


def download(name: str, expected_sha256: str) -> tuple[list[dict], dict]:
    url = f"{BASE_URL}/{name}"
    request = urllib.request.Request(url, headers={"User-Agent": "Jobservatory/0.1 (+https://jobservatory.castalia.institute)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError(f"O*NET source digest changed for {name}: {digest}")
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    return rows, {"url": url, "sha256": digest, "rows": len(rows)}


def rating_profiles(rows: list[dict], family: str) -> dict[str, list[dict]]:
    combined: dict[tuple[str, str], dict] = {}
    for row in rows:
        code = row["O*NET-SOC Code"]
        if code not in OCCUPATIONS or row.get("Recommend Suppress") == "Y" or row.get("Not Relevant") == "Y":
            continue
        key = (code, row["Element ID"])
        item = combined.setdefault(key, {
            "elementId": row["Element ID"], "name": row["Element Name"], "family": family,
            "importance": None, "level": None, "inheritedFromOccupation": True,
        })
        if row["Scale ID"] == "IM":
            item["importance"] = float(row["Data Value"])
        elif row["Scale ID"] == "LV":
            item["level"] = float(row["Data Value"])
    profiles: dict[str, list[dict]] = defaultdict(list)
    for (code, _), item in combined.items():
        if item["importance"] is not None:
            profiles[code].append(item)
    return {code: sorted(items, key=lambda item: (-item["importance"], item["name"]))[:10] for code, items in profiles.items()}


def main() -> int:
    tables = {}
    sources = {}
    for table, (name, digest) in FILES.items():
        tables[table], sources[table] = download(name, digest)

    essential = rating_profiles(tables["essential_skills"], "essential")
    transferable = rating_profiles(tables["transferable_skills"], "transferable")
    software: dict[str, list[dict]] = defaultdict(list)
    titles = {}
    for row in tables["software_skills"]:
        code = row["O*NET-SOC Code"]
        if code not in OCCUPATIONS:
            continue
        titles[code] = row["Title"]
        software[code].append({
            "name": row["Workplace Example"], "elementId": row["Element ID"],
            "category": row["Element Name"], "hotTechnology": row["Hot Technology"] == "Y",
            "inDemand": row["In Demand"] == "Y",
        })
    profiles = {}
    for code in sorted(OCCUPATIONS):
        profiles[code] = {
            "title": titles.get(code),
            "essentialSkills": essential.get(code, []),
            "transferableSkills": transferable.get(code, []),
            "softwareSkills": sorted(software.get(code, []), key=lambda item: item["name"].lower()),
        }
    output = {
        "schemaVersion": "jobservatory.onet-skill-profiles.v1",
        "onetVersion": "30.3",
        "releaseDate": "2026-05",
        "license": "CC BY 4.0",
        "attribution": "Includes information from the O*NET 30.3 Database by USDOL/ETA. Jobservatory selected occupations and compacted fields; USDOL/ETA has not approved, endorsed, or tested these modifications.",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "sourceUrl": "https://www.onetcenter.org/database.html",
        "sources": sources,
        "softwareCrosswalk": SOFTWARE_CROSSWALK,
        "profiles": profiles,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(f"wrote {len(profiles)} O*NET occupation skill profiles to {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
