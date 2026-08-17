#!/usr/bin/env python3
"""Create a deterministic, content-addressed evaluation corpus snapshot."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public" / "api" / "observatory.json"
SNAPSHOT_DIR = ROOT / "ml" / "eval" / "snapshots"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def main() -> int:
    source = json.loads(SOURCE.read_text())
    payload = canonical_bytes(source)
    digest = hashlib.sha256(payload).hexdigest()
    snapshot_name = f"corpus-{digest[:16]}.json.gz"
    snapshot_path = SNAPSHOT_DIR / snapshot_name
    manifest_path = SNAPSHOT_DIR / "manifest.json"
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(payload)
    manifest = {
        "schemaVersion": "jobservatory.eval-corpus.v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "source": "public/api/observatory.json",
        "snapshot": f"ml/eval/snapshots/{snapshot_name}",
        "canonicalSha256": digest,
        "compressedSha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        "observations": len(source["observations"]),
        "generatedAt": source.get("generatedAt"),
        "immutability": "A changed canonical digest requires a new snapshot filename.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
