#!/usr/bin/env python3
"""Freeze the minimum public fields needed to reproduce classifier training."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public" / "api" / "observatory.json"
DIRECTORY = ROOT / "ml" / "eval" / "snapshots"
MANIFEST = DIRECTORY / "classifier-corpus-manifest.json"
FIELDS = (
    "observationId", "duplicateGroup", "title", "location", "retrievedAt",
    "sourceUpdatedAt", "sourcePublishedAt", "classifications", "domain", "seniority",
)


def main() -> int:
    source = json.loads(SOURCE.read_text())
    dataset = {
        "schemaVersion": "jobservatory.classifier-corpus.v1",
        "sourceGeneratedAt": source["generatedAt"],
        "targetProvenance": "versioned rule-generated weak labels",
        "featurePolicy": "model uses title and location only",
        "observations": [{field: row.get(field) for field in FIELDS} for row in source["observations"]],
    }
    canonical = (json.dumps(dataset, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    canonical_digest = hashlib.sha256(canonical).hexdigest()
    path = DIRECTORY / f"classifier-corpus-{canonical_digest[:16]}.json.gz"
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(canonical)
    manifest = {
        "schemaVersion": "jobservatory.classifier-corpus-manifest.v1",
        "snapshot": str(path.relative_to(ROOT)), "observations": len(dataset["observations"]),
        "canonicalSha256": canonical_digest, "compressedSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sourceGeneratedAt": source["generatedAt"], "fields": list(FIELDS),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
