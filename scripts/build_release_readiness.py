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
counterfactual = json.loads((PUBLIC / "ml" / "counterfactual-audit.json").read_text())
assurance = json.loads((ROOT / "config" / "assurance.json").read_text())
benchmark_path = PUBLIC / "ops" / "production-benchmark.json"
benchmark = json.loads(benchmark_path.read_text()) if benchmark_path.exists() else None
accessibility_path = PUBLIC / "ops" / "accessibility-audit.json"
accessibility = json.loads(accessibility_path.read_text()) if accessibility_path.exists() else None
serving_manifest = json.loads((PUBLIC / "search" / "manifest-v1.json").read_text())
retrieval_benchmark_path = PUBLIC / "ops" / "retrieval-service-benchmark.json"
retrieval_benchmark = json.loads(retrieval_benchmark_path.read_text()) if retrieval_benchmark_path.exists() else None
rights_register_path = PUBLIC / "governance" / "source-rights-register.json"
rights_register = json.loads(rights_register_path.read_text()) if rights_register_path.exists() else None


def gate(identifier: str, name: str, passed: bool, evidence: str) -> dict:
    return {"id": identifier, "name": name, "status": "pass" if passed else "fail", "evidence": evidence}


rights_approved = bool(rights_register) and rights_register["summary"]["status"] == "approved" and rights_register["summary"]["sources"] == corpus["coverage"]["sourcesConfigured"] and all(not review["blockers"] for review in rights_register["reviews"])
gates = [
    gate("corpus.source_universe", "Declared source universe is complete", corpus["coverage"]["sourcesSuccessful"] == corpus["coverage"]["sourcesConfigured"] and corpus["coverage"]["publishedObservations"] == corpus["coverage"]["eligibleObservations"], "public/api/observatory.json coverage"),
    gate("corpus.rights", "Every source has approved retrieval, retention, excerpt publication, redistribution, and training rights", rights_approved and assurance["sourceRightsReviewComplete"], "public/api/governance/source-rights-register.json plus config/assurance.json"),
    gate("onet.human_review", "Occupation and skill mappings are human reviewed", assurance["occupationMappingHumanReviewComplete"], "config/assurance.json"),
    gate("evaluation.independent", "Retrieval and classification sets are independently annotated and adjudicated", assurance["independentAdjudicationComplete"], "config/assurance.json and model evaluation manifests"),
    gate("retrieval.promotion", "Learned retrieval clears BM25 quality and evidence gates", retrieval["promotion"]["status"] == "eligible", "public/api/ml/learned-retrieval-metrics.json"),
    gate("classification.promotion", "Calibrated hierarchical classifier clears evidence gates", classifier["promotion"]["status"] == "eligible", "public/api/ml/hierarchical-classifier-metrics.json"),
    gate("responsible_ai.counterfactuals", "Scoped protected-attribute counterfactual tests pass", counterfactual["status"] == "pass" and assurance["protectedAttributeCounterfactualTestsComplete"], "public/api/ml/counterfactual-audit.json plus config/assurance.json"),
    gate("longitudinal.signal", "Longitudinal signal has sufficient valid history", signal["signal"]["status"] == "available" and signal["signal"]["observedHistoryDays"] >= signal["signal"]["minimumHistoryDays"], "public/api/apocalypso/jobs-signal.json"),
    gate("serving.architecture", "Versioned production baseline retrieval service is deployed and benchmarked", assurance["productionServingArchitecture"] == "versioned-service" and bool(retrieval_benchmark) and retrieval_benchmark["status"] == "pass" and retrieval_benchmark["target"] == "https://jobservatory.castalia.institute" and retrieval_benchmark["lineage"]["serviceVersion"] == serving_manifest["serviceVersion"] and retrieval_benchmark["lineage"]["modelId"] == serving_manifest["model"]["modelId"] and retrieval_benchmark["lineage"]["indexSha256"] == serving_manifest["index"]["sha256"] and retrieval_benchmark["lineage"]["corpusContentSha256"] == serving_manifest["corpus"]["contentSha256"] and retrieval_benchmark["aggregate"]["errors"] == 0 and retrieval_benchmark["aggregate"]["contractFailures"] == 0, "public/api/search/manifest-v1.json plus public/api/ops/retrieval-service-benchmark.json plus config/assurance.json"),
    gate("serving.benchmark", "Production benchmark has zero errors", bool(benchmark) and benchmark["aggregate"]["errors"] == 0, "public/api/ops/production-benchmark.json"),
    gate("accessibility.automated", "Built UI passes automated WCAG and keyboard interaction audits", bool(accessibility) and accessibility["status"] == "pass" and assurance["automatedAccessibilityAuditComplete"], "public/api/ops/accessibility-audit.json plus config/assurance.json"),
    gate("accessibility.assistive_technology", "Qualified human assistive-technology audit passes", assurance["manualAssistiveTechnologyAuditComplete"], "config/assurance.json plus linked human audit report"),
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
