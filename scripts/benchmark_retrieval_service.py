#!/usr/bin/env python3
"""Benchmark and contract-check the live versioned retrieval service."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "api" / "ops" / "retrieval-service-benchmark.json"
MANIFEST = json.loads((ROOT / "public" / "api" / "search" / "manifest-v1.json").read_text())
DEFAULT_TARGET = "https://jobservatory.castalia.institute"
WORKLOAD = [
    {"query": "machine learning", "filters": {}},
    {"query": "principal retrieval", "filters": {}},
    {"query": "model serving infrastructure", "filters": {"domain": "ML engineering"}},
    {"query": "AI safety evaluation", "filters": {"domain": "Safety & governance"}},
    {"query": "robotics software engineer", "filters": {"domain": "Robotics & embedded"}},
    {"query": "scientific AI chemistry", "filters": {"domain": "Scientific AI"}},
    {"query": "generative AI product", "filters": {"domain": "Product & leadership"}},
    {"query": "forecasting", "filters": {"minimumPay": "100000"}},
]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(round((len(ordered) - 1) * fraction), len(ordered) - 1)]


def summarize(values: list[float]) -> dict:
    return {
        "p50Ms": round(percentile(values, 0.50), 3),
        "p95Ms": round(percentile(values, 0.95), 3),
        "p99Ms": round(percentile(values, 0.99), 3),
        "meanMs": round(statistics.mean(values), 3),
    }


def validate_body(body: dict, spec: dict, headers) -> list[str]:
    failures = []
    lineage = body.get("lineage", {})
    if body.get("schemaVersion") != "jobservatory.search-response.v1":
        failures.append("response_schema_version")
    if lineage.get("serviceVersion") != MANIFEST["serviceVersion"]:
        failures.append("service_version")
    if lineage.get("modelId") != MANIFEST["model"]["modelId"]:
        failures.append("model_id")
    if lineage.get("indexSha256") != MANIFEST["index"]["sha256"]:
        failures.append("index_sha256")
    if lineage.get("corpusGeneratedAt") != MANIFEST["corpus"]["generatedAt"]:
        failures.append("corpus_generated_at")
    if headers.get("X-Jobservatory-Service") != MANIFEST["serviceVersion"]:
        failures.append("service_header")
    if headers.get("X-Jobservatory-Model") != MANIFEST["model"]["modelId"]:
        failures.append("model_header")
    if headers.get("X-Jobservatory-Index") != MANIFEST["index"]["sha256"]:
        failures.append("index_header")
    if not headers.get("Server-Timing"):
        failures.append("server_timing_header")
    try:
        uuid.UUID(body.get("requestId", ""))
    except (ValueError, AttributeError, TypeError):
        failures.append("request_id")
    results = body.get("results", [])
    if not results or len(results) > 10:
        failures.append("result_count")
    if [result.get("rank") for result in results] != list(range(1, len(results) + 1)):
        failures.append("rank_sequence")
    if any(results[index]["score"] < results[index + 1]["score"] for index in range(len(results) - 1)):
        failures.append("score_order")
    for key, expected in spec["filters"].items():
        if key == "domain" and any(result.get("domain") != expected for result in results):
            failures.append("domain_filter")
        if key == "minimumPay" and any(not result.get("compensation") or result["compensation"]["maximum"] < float(expected) for result in results):
            failures.append("minimum_pay_filter")
    return sorted(set(failures))


def fetch(target: str, spec: dict) -> dict:
    parameters = {"q": spec["query"], "limit": "10", **spec["filters"]}
    url = f"{target}/api/v1/search?{urllib.parse.urlencode(parameters)}"
    request = urllib.request.Request(url, headers={"User-Agent": "JobservatoryRetrievalBenchmark/1.0"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            latency = (time.perf_counter() - started) * 1000
            body = json.loads(payload)
            failures = validate_body(body, spec, response.headers)
            return {
                "query": spec["query"], "status": response.status, "latencyMs": latency,
                "applicationMs": body.get("timing", {}).get("totalMs"),
                "indexCacheHit": body.get("timing", {}).get("indexCacheHit"),
                "resultCacheHit": body.get("timing", {}).get("resultCacheHit"),
                "bytes": len(payload), "failures": failures, "error": None,
            }
    except Exception as error:
        return {
            "query": spec["query"], "status": None, "latencyMs": (time.perf_counter() - started) * 1000,
            "applicationMs": None, "indexCacheHit": None, "resultCacheHit": None,
            "bytes": 0, "failures": [], "error": type(error).__name__,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--requests", type=int, default=80)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    target = args.target.rstrip("/")
    for spec in WORKLOAD[:4]:
        fetch(target, spec)
    specs = [WORKLOAD[index % len(WORKLOAD)] for index in range(args.requests)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        rows = [future.result() for future in as_completed(executor.submit(fetch, target, spec) for spec in specs)]
    duration = time.perf_counter() - started
    external = [row["latencyMs"] for row in rows]
    application = [row["applicationMs"] for row in rows if isinstance(row["applicationMs"], (int, float))]
    errors = sum(row["status"] != 200 or row["error"] is not None for row in rows)
    contract_failures = sum(bool(row["failures"]) for row in rows)
    external_summary = summarize(external)
    application_summary = summarize(application) if application else None
    criteria = {"errors": 0, "contractFailures": 0, "externalP95MsMaximum": 1000, "applicationP95MsMaximum": 250}
    passed = (
        errors == criteria["errors"]
        and contract_failures == criteria["contractFailures"]
        and external_summary["p95Ms"] <= criteria["externalP95MsMaximum"]
        and bool(application_summary)
        and application_summary["p95Ms"] <= criteria["applicationP95MsMaximum"]
    )
    cpu_upper_bound_ms = application_summary["meanMs"] if application_summary else 0
    monthly_cpu_upper_bound = cpu_upper_bound_ms * 1_000_000
    paid_cpu_overage = max(0, monthly_cpu_upper_bound - 30_000_000) / 1_000_000 * 0.02
    output = {
        "schemaVersion": "jobservatory.retrieval-service-benchmark.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "target": target,
        "lineage": {
            "serviceVersion": MANIFEST["serviceVersion"], "modelId": MANIFEST["model"]["modelId"],
            "indexSha256": MANIFEST["index"]["sha256"], "corpusGeneratedAt": MANIFEST["corpus"]["generatedAt"],
        },
        "workload": {
            "requests": args.requests, "concurrency": args.concurrency, "warmupRequests": 4,
            "queries": len(WORKLOAD), "limit": 10, "clientRegion": "US East", "cacheState": "uncontrolled production isolate placement after explicit warmup",
        },
        "criteria": criteria,
        "aggregate": {
            "requests": len(rows), "successes": len(rows) - errors, "errors": errors, "contractFailures": contract_failures,
            "durationSeconds": round(duration, 3), "requestsPerSecond": round(len(rows) / duration, 3),
            "bytesTransferred": sum(row["bytes"] for row in rows),
            "external": external_summary, "application": application_summary,
            "indexCacheHitRate": round(sum(row["indexCacheHit"] is True for row in rows) / len(rows), 4),
            "resultCacheHitRate": round(sum(row["resultCacheHit"] is True for row in rows) / len(rows), 4),
        },
        "costModel": {
            "architecture": "Cloudflare Pages Function with two static-asset reads per cold isolate and in-isolate index/result caches",
            "pricingSource": "https://developers.cloudflare.com/workers/platform/pricing/",
            "pricingCheckedAt": "2026-08-17",
            "freePlanRequestsPerDay": 100000,
            "paidPlanMinimumMonthlyUSD": 5,
            "paidPlanIncludedRequestsPerMonth": 10000000,
            "paidPlanAdditionalUSDPerMillionRequests": 0.30,
            "paidPlanIncludedCpuMillisecondsPerMonth": 30000000,
            "paidPlanAdditionalUSDPerMillionCpuMilliseconds": 0.02,
            "measuredTotalMsAsConservativeCpuUpperBound": cpu_upper_bound_ms,
            "estimatedPaidCostUSDAtOneMillionMonthlyRequests": round(5 + paid_cpu_overage, 2),
            "assumptions": [
                "The estimate assumes this service is the only account workload and uses measured application wall time as a conservative upper bound on billable CPU time.",
                "One million evenly distributed monthly requests average below the Free plan's 100,000 daily request quota, but that quota is account-wide.",
                "Cloudflare states there are no additional Workers Paid data-transfer charges; static assets remain free, while every Function request counts as a Workers request.",
            ],
        },
        "status": "pass" if passed else "fail",
        "limitations": [
            "This is a bounded single-client US East test, not a globally distributed capacity test.",
            "Cloudflare isolate placement and CDN state are uncontrolled; warmups do not guarantee every concurrent request reaches a warm isolate.",
            "Application timing is service wall time reported by the Function, not Cloudflare's billable CPU metric.",
            "The service intentionally deploys the BM25 baseline; relevance promotion remains blocked on an independently adjudicated temporal test set.",
        ],
    }
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
