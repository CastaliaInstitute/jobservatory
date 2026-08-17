import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import test from "node:test";

test("builds a Cloudflare Pages-ready static site", async () => {
  const html = await readFile(new URL("../dist/index.html", import.meta.url), "utf8");
  assert.match(html, /Jobservatory — Castalia AI Labor Observatory/);
  assert.match(html, /canonical/);
  await access(new URL("../dist/assets/", import.meta.url));
});

test("publishes provenance, evaluation, and safely abstaining signal feeds", async () => {
  const [observatory, dataCard, apocalypso, retrieval, classification, learnedRetrieval, hierarchical, readiness, benchmark] = await Promise.all([
    readFile(new URL("../dist/api/observatory.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/data-card.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/apocalypso/jobs-signal.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/retrieval-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/classification-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/learned-retrieval-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/hierarchical-classifier-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/release-readiness.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ops/production-benchmark.json", import.meta.url), "utf8"),
  ]);
  const corpus = JSON.parse(observatory);
  const card = JSON.parse(dataCard);
  const signal = JSON.parse(apocalypso);
  const retrievalMetrics = JSON.parse(retrieval);
  const classificationMetrics = JSON.parse(classification);
  const learnedRetrievalMetrics = JSON.parse(learnedRetrieval);
  const hierarchicalMetrics = JSON.parse(hierarchical);
  const releaseReadiness = JSON.parse(readiness);
  const productionBenchmark = JSON.parse(benchmark);
  assert.ok(corpus.observations.length >= 100);
  assert.ok(corpus.termIndex.length >= 20);
  assert.ok(corpus.termTimeline.length >= 1);
  assert.equal(corpus.termTimeline.at(-1).date, corpus.generatedAt.slice(0, 10));
  assert.equal(corpus.observations[0].descriptionPolicy, "metadata-and-evidence-only");
  assert.ok(corpus.observations[0].firstSeen);
  assert.ok(corpus.observations.every(item => item.analysisId && item.extraction.methodVersion && item.extraction.ontologyVersion));
  assert.ok(corpus.observations.every(item => ["direct", "applied"].includes(item.roleRelevance.tier)));
  assert.ok(corpus.observations.every(item => item.classifications.laborEffect.label === "unclassified"));
  assert.ok(corpus.observations.every(item => !JSON.stringify(item.classifications).match(/<[^>]+>/)));
  assert.equal(corpus.coverage.sourcesSuccessful, corpus.coverage.sourcesConfigured);
  assert.equal(corpus.coverage.sourceFailures.length, 0);
  assert.ok(corpus.coverage.retrieval.every(source => source.httpStatus === 200 && source.responseHash.startsWith("sha256:") && source.rightsReviewStatus));
  assert.ok(corpus.coverage.eligibleObservations >= corpus.observations.length);
  assert.equal(corpus.onet.version, "30.3");
  assert.equal(corpus.onet.license, "CC BY 4.0");
  assert.equal(card.coverage.observations, corpus.summary.observations);
  assert.equal(card.coverage.configuredSources, corpus.coverage.sourcesConfigured);
  assert.equal(card.rights.allSourcesApproved, false);
  assert.equal(card.rights.modelTrainingPermitted, false);
  assert.equal(card.corpus.descriptionPolicy, "metadata-and-evidence-only");
  assert.ok(corpus.observations.some(item => item.classifications.skills.some(skill => skill.onetSoftwareSkill)));
  assert.equal(signal.module, "AI");
  assert.equal(signal.signal.status, "insufficient_history");
  assert.equal(signal.signal.value, null);
  assert.ok(retrievalMetrics.evaluation.queries >= 6);
  assert.ok(retrievalMetrics.aggregate.bm25["ndcg@10"] >= 0 && retrievalMetrics.aggregate.bm25["ndcg@10"] <= 1);
  assert.ok(classificationMetrics.evaluation.observations >= 10);
  assert.equal(classificationMetrics.aggregate.calibration, null);
  assert.equal(learnedRetrievalMetrics.promotion.status, "not_eligible");
  assert.equal(hierarchicalMetrics.promotion.status, "not_eligible");
  assert.equal(hierarchicalMetrics.hierarchy.parentConsistency, 1);
  assert.ok(hierarchicalMetrics.abstention.microDecisionCoverage < 1);
  assert.equal(releaseReadiness.status, "blocked");
  assert.ok(releaseReadiness.passed < releaseReadiness.total);
  assert.equal(releaseReadiness.responsibleAI.employmentDecisionUse, "prohibited");
  assert.equal(releaseReadiness.responsibleAI.candidateMatching, "disabled");
  assert.equal(releaseReadiness.gates.find(gate => gate.id === "corpus.rights").status, "fail");
  assert.equal(releaseReadiness.gates.find(gate => gate.id === "evaluation.independent").status, "fail");
  assert.equal(productionBenchmark.aggregate.errors, 0);
  assert.ok(productionBenchmark.aggregate.p95Ms > 0);
  assert.ok(productionBenchmark.aggregate.requestsPerSecond > 0);
  await access(new URL("../dist/schemas/observatory.schema.json", import.meta.url));
});

test("commits durable observation lineage and full eligible-set presence", async () => {
  const snapshots = (await readdir(new URL("../data/snapshots/", import.meta.url))).filter(name => name.endsWith(".json")).sort();
  assert.ok(snapshots.length >= 1);
  const [ledger, snapshot] = await Promise.all([readFile(new URL("../data/observation_versions.ndjson", import.meta.url), "utf8"), readFile(new URL(`../data/snapshots/${snapshots.at(-1)}`, import.meta.url), "utf8")]);
  assert.ok(ledger.trim().split("\n").length >= 500);
  const presence = JSON.parse(snapshot);
  assert.ok(presence.eligibleSourceIds.length >= 500);
  assert.equal(Object.keys(presence.contentHashes).length, presence.eligibleSourceIds.length);
});
