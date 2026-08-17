import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

test("builds a Cloudflare Pages-ready static site", async () => {
  const html = await readFile(new URL("../dist/index.html", import.meta.url), "utf8");
  assert.match(html, /Jobservatory — Castalia AI Labor Observatory/);
  assert.match(html, /canonical/);
  await access(new URL("../dist/assets/", import.meta.url));
});

test("publishes the evidence and Apocalypso feeds", async () => {
  const [observatory, apocalypso] = await Promise.all([
    readFile(new URL("../dist/api/observatory.json", import.meta.url), "utf8"),
    readFile(new URL("../dist/api/apocalypso/jobs-signal.json", import.meta.url), "utf8"),
  ]);
  const corpus = JSON.parse(observatory);
  const signal = JSON.parse(apocalypso);
  assert.ok(corpus.observations.length >= 100);
  assert.ok(corpus.termIndex.length >= 20);
  assert.ok(corpus.termTimeline.length >= 1);
  assert.equal(corpus.termTimeline.at(-1).date, corpus.generatedAt.slice(0, 10));
  assert.equal(corpus.observations[0].descriptionPolicy, "metadata-and-evidence-only");
  assert.ok(corpus.observations[0].firstSeen);
  assert.equal(signal.module, "AI");
});
