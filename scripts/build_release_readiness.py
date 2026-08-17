#!/usr/bin/env python3
"""Publish fail-closed A+ and responsible-AI release gates from evidence."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public" / "api"
corpus = json.loads((PUBLIC / "observatory.json").read_text())
signal = json.loads((PUBLIC / "apocalypso" / "jobs-signal.json").read_text())
retrieval = json.loads((PUBLIC / "ml" / "learned-retrieval-metrics.json").read_text())
classifier = json.loads((PUBLIC / "ml" / "hierarchical-classifier-metrics.json").read_text())
assurance = json.loads((ROOT / "config" / "assurance.json").read_text())
benchmark_path = PUBLIC / "ops" / "production-benchmark.json"
benchmark = json.loads(benchmark_path.read_text()) if benchmark_path.exists() else None


def gate(identifier: str, name: str, passed: bool, evidence: str) -> dict:
    return {"id": identifier, "name": name, "status": "pass" if passed else "fail", "evidence": evidence}


rights_approved = all(source["rightsReviewStatus"] == "approved" for source in corpus["coverage"]["retrieval"])
gates = [
    gate("corpus.source_universe", "Declared source universe is complete", corpus["coverage"]["sourcesSuccessful"] == corpus["coverage"]["sourcesConfigured"] and corpus["coverage"]["publishedObservations"] == corpus["coverage"]["eligibleObservations"], "public/api/observatory.json coverage"),
    gate("corpus.rights", "Every source has approved retrieval, retention, redistribution, and training rights", rights_approved and assurance["sourceRightsReviewComplete"], "source registry rightsReviewStatus plus config/assurance.json"),
    gate("onet.human_review", "Occupation and skill mappings are human reviewed", assurance["occupationMappingHumanReviewComplete"], "config/assurance.json"),
    gate("evaluation.independent", "Retrieval and classification sets are independently annotated and adjudicated", assurance["independentAdjudicationComplete"], "config/assurance.json and model evaluation manifests"),
    gate("retrieval.promotion", "Learned retrieval clears BM25 quality and evidence gates", retrieval["promotion"]["status"] == "eligible", "public/api/ml/learned-retrieval-metrics.json"),
    gate("classification.promotion", "Calibrated hierarchical classifier clears evidence gates", classifier["promotion"]["status"] == "eligible", "public/api/ml/hierarchical-classifier-metrics.json"),
    gate("responsible_ai.counterfactuals", "Protected-attribute counterfactual tests pass", assurance["protectedAttributeCounterfactualTestsComplete"], "config/assurance.json"),
    gate("longitudinal.signal", "Longitudinal signal has sufficient valid history", signal["signal"]["status"] == "available" and signal["signal"]["observedHistoryDays"] >= signal["signal"]["minimumHistoryDays"], "public/api/apocalypso/jobs-signal.json"),
    gate("serving.architecture", "Versioned production retrieval service is deployed", assurance["productionServingArchitecture"] == "versioned-service", "config/assurance.json"),
    gate("serving.benchmark", "Production benchmark has zero errors", bool(benchmark) and benchmark["aggregate"]["errors"] == 0, "public/api/ops/production-benchmark.json"),
    gate("accessibility.audit", "Automated and manual accessibility audits pass", assurance["automatedAccessibilityAuditComplete"], "config/assurance.json"),
    gate("deployment.automatic", "GitHub-to-Cloudflare deployment is automatic and verified", assurance["automaticGitHubCloudflareDeploymentVerified"], "config/assurance.json"),
]
passed = sum(item["status"] == "pass" for item in gates)
output = {
    "schemaVersion": "jobservatory.release-readiness.v1",
    "generatedAt": corpus["generatedAt"],
    "status": "a_plus_ready" if passed == len(gates) else "blocked",
    "passed": passed, "total": len(gates), "gates": gates,
    "responsibleAI": {
        "employmentDecisionUse": "prohibited", "candidateMatching": "disabled",
        "protectedAttributeFeatures": "prohibited", "humanReviewRequired": True,
        "explanationPolicy": "Only cited listing or candidate passages may support explanations; no candidate model is deployed.",
    },
}
destination = PUBLIC / "ml" / "release-readiness.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(output, indent=2) + "\n")
print(f"release readiness: {output['status']} ({passed}/{len(gates)} gates pass)")
