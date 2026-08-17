import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { handleHealth, handleSearch, resetSearchServiceForTests } from "../server/search-service.js";

async function schemas() {
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  for (const name of (await readdir(new URL("../schemas/", import.meta.url))).filter(name => name.endsWith(".schema.json"))) {
    ajv.addSchema(JSON.parse(await readFile(new URL(`../schemas/${name}`, import.meta.url), "utf8")));
  }
  return ajv;
}

function environment({ tamperIndex = false } = {}) {
  return {
    ASSETS: {
      async fetch(input) {
        const pathname = new URL(input instanceof Request ? input.url : input).pathname;
        try {
          let bytes = await readFile(new URL(`../public${pathname}`, import.meta.url));
          if (tamperIndex && pathname.endsWith("index-v1.json")) bytes = Buffer.concat([bytes, Buffer.from(" ")]);
          return new Response(bytes, { status: 200, headers: { "Content-Type": "application/json" } });
        } catch {
          return new Response("not found", { status: 404 });
        }
      },
    },
  };
}

const context = (url, options = {}, env = environment()) => ({ request: new Request(url, options), env });

test("serves schema-valid, versioned BM25 results with cache and observability evidence", async () => {
  resetSearchServiceForTests();
  const ajv = await schemas();
  const validate = ajv.getSchema("https://jobservatory.castalia.institute/schemas/search-response.schema.json");
  const first = await handleSearch(context("https://jobservatory.test/api/v1/search?q=machine%20learning&limit=5"));
  assert.equal(first.status, 200);
  const firstBody = await first.json();
  assert.equal(validate(firstBody), true, ajv.errorsText(validate.errors));
  assert.equal(firstBody.results.length, 5);
  assert.equal(firstBody.timing.indexCacheHit, false);
  assert.equal(firstBody.timing.resultCacheHit, false);
  assert.equal(first.headers.get("x-jobservatory-service"), "jobservatory-search-api-v1");
  assert.equal(first.headers.get("x-jobservatory-model"), "bm25-production-baseline-1.0.0");
  assert.match(first.headers.get("server-timing"), /index;dur=.*rank;dur=.*total;dur=/);
  assert.ok(firstBody.results.every((result, index) => result.rank === index + 1 && result.score > 0));

  const second = await handleSearch(context("https://jobservatory.test/api/v1/search?q=machine%20learning&limit=5"));
  const secondBody = await second.json();
  assert.equal(secondBody.timing.indexCacheHit, true);
  assert.equal(secondBody.timing.resultCacheHit, true);
  assert.deepEqual(secondBody.results, firstBody.results);
});

test("enforces filters and bounded requests", async () => {
  resetSearchServiceForTests();
  const filtered = await handleSearch(context("https://jobservatory.test/api/v1/search?q=AI&domain=Scientific%20AI&minimumPay=100000&limit=10"));
  assert.equal(filtered.status, 200);
  const body = await filtered.json();
  assert.ok(body.results.length > 0);
  assert.ok(body.results.every(result => result.domain === "Scientific AI" && result.compensation.maximum >= 100000));

  for (const url of [
    "https://jobservatory.test/api/v1/search",
    "https://jobservatory.test/api/v1/search?q=x",
    "https://jobservatory.test/api/v1/search?q=machine&limit=51",
    "https://jobservatory.test/api/v1/search?q=machine&minimumPay=nope",
  ]) {
    const response = await handleSearch(context(url));
    assert.equal(response.status, 400);
    assert.equal((await response.json()).error.code, "invalid_request");
  }
  const method = await handleSearch(context("https://jobservatory.test/api/v1/search?q=machine", { method: "POST" }));
  assert.equal(method.status, 405);
  const options = await handleSearch(context("https://jobservatory.test/api/v1/search", { method: "OPTIONS" }));
  assert.equal(options.status, 204);
});

test("health verifies index lineage and corrupted artifacts fail closed", async () => {
  resetSearchServiceForTests();
  const ajv = await schemas();
  const validate = ajv.getSchema("https://jobservatory.castalia.institute/schemas/search-health.schema.json");
  const health = await handleHealth(context("https://jobservatory.test/api/v1/health"));
  assert.equal(health.status, 200);
  const healthBody = await health.json();
  assert.equal(validate(healthBody), true, ajv.errorsText(validate.errors));
  const manifest = JSON.parse(await readFile(new URL("../public/api/search/manifest-v1.json", import.meta.url), "utf8"));
  assert.equal(healthBody.documents, manifest.index.documents);

  resetSearchServiceForTests();
  const failed = await handleSearch(context("https://jobservatory.test/api/v1/search?q=machine", {}, environment({ tamperIndex: true })));
  assert.equal(failed.status, 503);
  assert.equal((await failed.json()).error.code, "service_unavailable");
});
