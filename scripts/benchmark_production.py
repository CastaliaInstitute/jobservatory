#!/usr/bin/env python3
"""Run a bounded concurrent benchmark against production static assets."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "api" / "ops" / "production-benchmark.json"
TARGET = "https://jobservatory.castalia.institute"
ROUTES = ["/", "/", "/", "/", "/", "/", "/api/ml/learned-retrieval-metrics.json", "/api/ml/hierarchical-classifier-metrics.json", "/api/apocalypso/jobs-signal.json", "/api/observatory.json"]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(round((len(ordered) - 1) * fraction), len(ordered) - 1)]


def fetch(path: str) -> dict:
    request = urllib.request.Request(TARGET + path, headers={"User-Agent": "JobservatoryBenchmark/0.1"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            return {"path": path, "status": response.status, "latencyMs": (time.perf_counter() - started) * 1000, "bytes": len(payload), "cacheControl": response.headers.get("Cache-Control"), "error": None}
    except Exception as error:
        return {"path": path, "status": None, "latencyMs": (time.perf_counter() - started) * 1000, "bytes": 0, "cacheControl": None, "error": type(error).__name__}


def summary(rows: list[dict]) -> dict:
    latencies = [row["latencyMs"] for row in rows]
    return {"requests": len(rows), "successes": sum(row["status"] == 200 for row in rows), "errors": sum(row["status"] != 200 for row in rows), "p50Ms": round(percentile(latencies, 0.50), 2), "p95Ms": round(percentile(latencies, 0.95), 2), "p99Ms": round(percentile(latencies, 0.99), 2), "meanMs": round(statistics.mean(latencies), 2), "bytesTransferred": sum(row["bytes"] for row in rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    paths = [ROUTES[index % len(ROUTES)] for index in range(args.requests)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        rows = [future.result() for future in as_completed(executor.submit(fetch, path) for path in paths)]
    duration = time.perf_counter() - started
    aggregate = summary(rows)
    aggregate.update(durationSeconds=round(duration, 3), requestsPerSecond=round(len(rows) / duration, 2))
    per_route = {path: summary([row for row in rows if row["path"] == path]) for path in sorted(set(paths))}
    output = {
        "schemaVersion": "jobservatory.production-benchmark.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "target": TARGET,
        "workload": {"requests": args.requests, "concurrency": args.concurrency, "routeWeights": dict(Counter(paths)), "clientRegion": "US East", "cacheState": "uncontrolled production CDN cache"},
        "aggregate": aggregate, "perRoute": per_route,
        "costModel": {
            "architecture": "Cloudflare Pages static assets with no Pages Functions directory",
            "pricingSource": "https://developers.cloudflare.com/pages/functions/pricing/#static-asset-requests",
            "pricingCheckedAt": "2026-08-17", "staticAssetRequestCostUSD": 0,
            "staticAssetBandwidthCostUSD": 0, "estimatedIncrementalDeliveryCostUSDAtOneMillionMonthlyRequests": 0,
            "exclusions": ["domain registration", "paid Cloudflare plan fees", "build limits", "future Functions, Workers, databases, vector indexes, model inference, logs, and egress outside static Pages"],
        },
        "limitations": ["Single-client US East measurement is not a global latency study.", "Latency includes response transfer time and is affected by uncontrolled CDN cache state and local network conditions.", "This measures static delivery, not the proposed production retrieval/model-serving service.", "A larger distributed load test requires a declared traffic budget and abuse-safe test window."],
    }
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    return 0 if aggregate["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
