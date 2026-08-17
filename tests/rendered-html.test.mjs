import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, readFile, readdir } from "node:fs/promises";
import test from "node:test";

test("builds a Cloudflare Pages-ready static site", async () => {
  const html = await readFile(new URL("../dist/index.html", import.meta.url), "utf8");
  const annotation = await readFile(new URL("../dist/annotation.html", import.meta.url), "utf8");
  assert.match(html, /Jobservatory — Castalia AI Labor Observatory/);
  assert.match(html, /canonical/);
  assert.match(annotation, /Annotation Workbench — Jobservatory/);
  assert.match(annotation, /LOCAL-ONLY JUDGMENTS/);
  await access(new URL("../dist/assets/", import.meta.url));
});

test("publishes provenance, evaluation, and safely abstaining signal feeds", async () => {
  const [observatory, dataCard, apocalypso, retrieval, classification, learnedRetrieval, hierarchical, counterfactual, readiness, independentReadiness, benchmark, accessibility, servingManifest, servingIndex, retrievalServiceBenchmark, sourceRightsRegister] = await Promise.all([
    readFile(new URL("../dist/api/observatory.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/data-card.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/apocalypso/jobs-signal.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/retrieval-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/classification-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/learned-retrieval-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/hierarchical-classifier-metrics.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/counterfactual-audit.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/release-readiness.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ml/independent-evaluation-readiness.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ops/production-benchmark.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ops/accessibility-audit.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/search/manifest-v1.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/search/index-v1.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/ops/retrieval-service-benchmark.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/governance/source-rights-register.json", import.meta.url), "utf8"),
  ]);
  const corpus = JSON.parse(observatory);
  const card = JSON.parse(dataCard);
  const signal = JSON.parse(apocalypso);
  const retrievalMetrics = JSON.parse(retrieval);
  const classificationMetrics = JSON.parse(classification);
  const learnedRetrievalMetrics = JSON.parse(learnedRetrieval);
  const hierarchicalMetrics = JSON.parse(hierarchical);
  const counterfactualAudit = JSON.parse(counterfactual);
  const releaseReadiness = JSON.parse(readiness);
  const independentEvaluation = JSON.parse(independentReadiness);
  const productionBenchmark = JSON.parse(benchmark);
  const accessibilityAudit = JSON.parse(accessibility);
  const searchManifest = JSON.parse(servingManifest);
  const searchIndex = JSON.parse(servingIndex);
  const searchBenchmark = JSON.parse(retrievalServiceBenchmark);
  const rightsRegister = JSON.parse(sourceRightsRegister);
  assert.ok(corpus.observations.length >= 100);
  assert.ok(corpus.termIndex.length >= 20);
  assert.ok(corpus.termTimeline.length >= 1);
  assert.equal(corpus.termTimeline.at(-1).date, corpus.generatedAt.slice(0, 10));
  assert.equal(corpus.observations[0].descriptionPolicy, "metadata-and-evidence-only");
  assert.ok(corpus.observations[0].firstSeen);
  assert.ok(corpus.observations.every(item => item.analysisId && item.extraction.methodVersion && item.extraction.ontologyVersion));
  assert.ok(corpus.observations.every(item => item.duplicateGroup === item.entityResolution.exactVariantGroupId));
  assert.ok(corpus.observations.every(item => item.entityResolution.familySize >= item.entityResolution.exactVariantGroupSize));
  assert.equal(corpus.summary.entityResolution.reviewStatus, "unreviewed");
  assert.ok(corpus.observations.every(item => ["direct", "applied"].includes(item.roleRelevance.tier)));
  assert.ok(corpus.observations.every(item => item.classifications.laborEffect.label === "unclassified"));
  assert.ok(corpus.observations.every(item => !JSON.stringify(item.classifications).match(/<[^>]+>/)));
  assert.equal(corpus.coverage.sourcesSuccessful, corpus.coverage.sourcesConfigured);
  assert.equal(corpus.coverage.sourceFailures.length, 0);
  assert.ok(["expanding", "target_met"].includes(corpus.coverage.assessment.status));
  assert.equal(corpus.coverage.assessment.actual.employers, corpus.summary.employers);
  assert.ok(Object.values(corpus.coverage.assessment.checks).some(check => !check));
  assert.ok(corpus.coverage.retrieval.every(source => source.httpStatus === 200 && source.responseHash.startsWith("sha256:") && source.rightsReviewStatus));
  assert.ok(corpus.coverage.eligibleObservations >= corpus.observations.length);
  assert.equal(corpus.onet.version, "30.3");
  assert.equal(corpus.onet.license, "CC BY 4.0");
  assert.equal(card.coverage.observations, corpus.summary.observations);
  assert.equal(card.coverage.configuredSources, corpus.coverage.sourcesConfigured);
  assert.equal(card.rights.allSourcesApproved, false);
  assert.equal(card.rights.modelTrainingPermitted, false);
  assert.equal(rightsRegister.summary.sources, corpus.coverage.sourcesConfigured);
  assert.equal(rightsRegister.summary.status, "pending");
  assert.equal(rightsRegister.summary.approvedDecisions, 0);
  assert.equal(rightsRegister.reviews.length, corpus.coverage.retrieval.length);
  assert.ok(rightsRegister.reviews.every(review => review.registryAligned && review.decisionEvidence.employerTermsUrl === null && review.blockers.length === 5));
  assert.equal(rightsRegister.policy.sourceContentModelTrainingEnabled, false);
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
  assert.equal(counterfactualAudit.status, "pass");
  assert.equal(counterfactualAudit.aggregate.decisionFlips, 0);
  assert.equal(counterfactualAudit.aggregate.abstentionStateChanges, 0);
  assert.ok(counterfactualAudit.sensitivityControl.maxProbabilityDelta > counterfactualAudit.criteria.sensitivityControlMinimumDeltaExclusive);
  assert.equal(releaseReadiness.status, "blocked");
  assert.ok(releaseReadiness.passed < releaseReadiness.total);
  assert.equal(releaseReadiness.responsibleAI.employmentDecisionUse, "prohibited");
  assert.equal(releaseReadiness.responsibleAI.candidateMatching, "disabled");
  assert.equal(releaseReadiness.gates.find(gate => gate.id === "corpus.rights").status, "fail");
  assert.equal(releaseReadiness.gates.find(gate => gate.id === "evaluation.independent").status, "fail");
  assert.equal(independentEvaluation.temporalSplit.status, "pass");
  assert.equal(independentEvaluation.temporalSplit.postingFamilyLeakage, 0);
  assert.equal(independentEvaluation.eligibleForPromotionDecision, false);
  for (const kind of ["retrieval", "classification"]) {
    for (const slot of ["a", "b"]) {
      const record = independentEvaluation.blindPackages.packages[kind][slot];
      const packageText = await readFile(new URL(`../dist${record.publicUrl}`, import.meta.url), "utf8");
      const annotationPackage = JSON.parse(packageText);
      assert.equal(`sha256:${createHash("sha256").update(packageText).digest("hex")}`, record.sha256);
      assert.equal(annotationPackage.tasks.length, record.tasks);
      assert.equal(annotationPackage.reviewerSlot, slot);
      assert.equal(annotationPackage.blind, true);
    }
  }
  assert.equal(releaseReadiness.gates.find(gate => gate.id === "responsible_ai.counterfactuals").status, "pass");
  assert.equal(accessibilityAudit.status, "pass");
  assert.equal(accessibilityAudit.aggregate.violationNodes, 0);
  assert.equal(accessibilityAudit.aggregate.incompleteNodes, 0);
  assert.ok(accessibilityAudit.keyboardChecks.every(check => check.initialFocusOnClose && check.wrapsForward && check.wrapsBackward && check.escapeCloses && check.restoresFocus));
  assert.ok(accessibilityAudit.annotationInteractionChecks.every(check => check.retrievalGradeSelection && check.nextTaskNavigation && check.classificationLabelSelection && check.classificationEvidenceDecision && check.retrievalDraftPersists && check.classificationDraftPersists));
  assert.equal(accessibilityAudit.manualAssurance.status, "required");
  assert.equal(releaseReadiness.gates.find(gate => gate.id === "accessibility.automated").status, "pass");
  assert.equal(releaseReadiness.gates.find(gate => gate.id === "accessibility.assistive_technology").status, "fail");
  assert.equal(searchManifest.serviceVersion, "jobservatory-search-api-v1");
  assert.equal(searchManifest.promotion.status, "baseline_only");
  assert.equal(searchManifest.index.documents, corpus.observations.length);
  assert.equal(searchIndex.statistics.documents, corpus.observations.length);
  assert.equal(searchIndex.corpus.contentSha256, searchManifest.corpus.contentSha256);
  assert.deepEqual(
    searchIndex.documents.map(document => document.observationId),
    searchIndex.documents.map(document => document.observationId).toSorted(),
  );
  const benchmarkMatchesCurrentIndex = searchBenchmark.lineage.indexSha256 === searchManifest.index.sha256
    && searchBenchmark.lineage.corpusContentSha256 === searchManifest.corpus.contentSha256;
  const benchmarkOperational = benchmarkMatchesCurrentIndex
    && searchBenchmark.status === "pass"
    && searchBenchmark.target === "https://jobservatory.castalia.institute"
    && searchBenchmark.aggregate.errors === 0
    && searchBenchmark.aggregate.contractFailures === 0;
  if (searchBenchmark.status === "pass") {
    assert.equal(searchBenchmark.aggregate.errors, 0);
    assert.equal(searchBenchmark.aggregate.contractFailures, 0);
    assert.ok(searchBenchmark.aggregate.application.p95Ms <= searchBenchmark.criteria.applicationP95MsMaximum);
  }
  assert.equal(
    releaseReadiness.gates.find(gate => gate.id === "serving.architecture").status,
    benchmarkOperational ? "pass" : "fail",
  );
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
