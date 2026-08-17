import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { chromium } from "playwright";

const root = fileURLToPath(new URL("../", import.meta.url));
const executable = fileURLToPath(new URL(process.platform === "win32" ? "../node_modules/.bin/wrangler.cmd" : "../node_modules/.bin/wrangler", import.meta.url));
const port = 8791;
const baseUrl = `http://127.0.0.1:${port}`;

async function waitForRuntime(process, output) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (process.exitCode !== null) throw new Error(`Wrangler exited before it was ready:\n${output.value}`);
    try {
      const response = await fetch(`${baseUrl}/api/v1/health`);
      if (response.ok) return response;
    } catch {
      // Runtime is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error(`Timed out waiting for Wrangler:\n${output.value}`);
}

test("packages and serves the versioned API in the Cloudflare Pages runtime", { timeout: 45_000 }, async () => {
  const runtime = spawn(executable, ["pages", "dev", "--port", String(port), "--ip", "127.0.0.1"], { cwd: root, stdio: ["ignore", "pipe", "pipe"] });
  const output = { value: "" };
  runtime.stdout.on("data", chunk => { output.value += chunk; });
  runtime.stderr.on("data", chunk => { output.value += chunk; });
  let browser;
  try {
    const health = await waitForRuntime(runtime, output);
    const healthBody = await health.json();
    assert.equal(healthBody.status, "ok");
    assert.equal(healthBody.serviceVersion, "jobservatory-search-api-v1");
    assert.ok(healthBody.documents >= 100);

    const response = await fetch(`${baseUrl}/api/v1/search?q=principal%20retrieval&limit=3`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("x-jobservatory-index"), healthBody.indexSha256);
    assert.equal(response.headers.get("x-jobservatory-model"), healthBody.modelId);
    const body = await response.json();
    assert.equal(body.results.length, 3);
    assert.equal(body.lineage.indexSha256, healthBody.indexSha256);
    assert.match(output.value, /Compiled Worker successfully/);

    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    const input = page.getByPlaceholder("Principal ML retrieval architecture, remote US…");
    await input.fill("principal retrieval");
    await page.getByText("API-ranked observations").waitFor({ state: "visible", timeout: 10_000 });
    assert.ok(Number(await page.locator(".result-count strong").textContent()) > 0);
  } finally {
    if (browser) await browser.close();
    runtime.kill("SIGTERM");
    await new Promise(resolve => {
      runtime.once("exit", resolve);
      setTimeout(resolve, 3_000);
    });
  }
});
