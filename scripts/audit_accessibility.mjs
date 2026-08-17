#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const outputUrl = new URL("../public/api/ops/accessibility-audit.json", import.meta.url);
const corpusUrl = new URL("../public/api/observatory.json", import.meta.url);
const axeSource = await readFile(require.resolve("axe-core/axe.min.js"), "utf8");
const corpus = JSON.parse(await readFile(corpusUrl, "utf8"));
const host = "127.0.0.1";
const port = Number(process.env.JOBSERVATORY_A11Y_PORT || 4175);
const baseUrl = `http://${host}:${port}`;
const tags = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const viewports = [
  { id: "desktop", width: 1440, height: 1000 },
  { id: "mobile", width: 390, height: 844 },
];

const preview = spawn(
  process.platform === "win32" ? "node_modules/.bin/vite.cmd" : "node_modules/.bin/vite",
  ["preview", "--host", host, "--port", String(port), "--strictPort"],
  { cwd: new URL("../", import.meta.url), stdio: ["ignore", "pipe", "pipe"] },
);
let previewOutput = "";
preview.stdout.on("data", chunk => { previewOutput += chunk; });
preview.stderr.on("data", chunk => { previewOutput += chunk; });

async function waitForPreview() {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    if (preview.exitCode !== null) throw new Error(`Vite preview exited early:\n${previewOutput}`);
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {
      // The preview process is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error(`Timed out waiting for Vite preview:\n${previewOutput}`);
}

async function runAxe(page, viewport, state) {
  await page.addScriptTag({ content: axeSource });
  const result = await page.evaluate(async runTags => globalThis.axe.run(document, {
    runOnly: { type: "tag", values: runTags },
    resultTypes: ["violations", "incomplete", "inapplicable", "passes"],
  }), tags);
  return {
    viewport,
    state,
    rulesEvaluated: result.passes.length + result.violations.length + result.incomplete.length + result.inapplicable.length,
    passes: result.passes.length,
    incomplete: result.incomplete.map(item => ({
      id: item.id,
      impact: item.impact,
      help: item.help,
      nodes: item.nodes.map(node => ({ target: node.target, failureSummary: node.failureSummary })),
    })),
    violations: result.violations.map(item => ({
      id: item.id,
      impact: item.impact,
      help: item.help,
      helpUrl: item.helpUrl,
      nodes: item.nodes.map(node => ({ target: node.target, failureSummary: node.failureSummary })),
    })),
  };
}

async function auditViewport(browser, viewport) {
  const page = await browser.newPage({ viewport });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator(".row-title").first().waitFor({ state: "visible", timeout: 20_000 });
  const states = [await runAxe(page, viewport.id, "ledger-loaded")];

  const opener = page.locator(".row-title").first();
  await opener.focus();
  await opener.click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor({ state: "visible" });
  const initialFocusOnClose = await page.locator(".close").evaluate(element => element === document.activeElement);
  states.push(await runAxe(page, viewport.id, "evidence-dialog-open"));

  await page.locator(".source-button").focus();
  await page.keyboard.press("Tab");
  const wrapsForward = await page.locator(".close").evaluate(element => element === document.activeElement);
  await page.keyboard.press("Shift+Tab");
  const wrapsBackward = await page.locator(".source-button").evaluate(element => element === document.activeElement);
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });
  const escapeCloses = await page.getByRole("dialog").count() === 0;
  await page.waitForFunction(() => document.activeElement?.classList.contains("row-title"), undefined, { timeout: 1_000 }).catch(() => undefined);
  const restoresFocus = await opener.evaluate(element => element === document.activeElement);
  const keyboard = { initialFocusOnClose, wrapsForward, wrapsBackward, escapeCloses, restoresFocus };
  await page.close();
  return { states, keyboard };
}

let browser;
try {
  await waitForPreview();
  browser = await chromium.launch({ headless: true });
  const results = [];
  const keyboardChecks = [];
  for (const viewport of viewports) {
    const result = await auditViewport(browser, viewport);
    results.push(...result.states);
    keyboardChecks.push({ viewport: viewport.id, ...result.keyboard });
  }
  const violations = results.flatMap(result => result.violations);
  const violationNodes = violations.reduce((total, item) => total + item.nodes.length, 0);
  const seriousOrCriticalNodes = violations
    .filter(item => item.impact === "serious" || item.impact === "critical")
    .reduce((total, item) => total + item.nodes.length, 0);
  const incompleteNodes = results.reduce((total, result) => total + result.incomplete.reduce((subtotal, item) => subtotal + item.nodes.length, 0), 0);
  const keyboardPassed = keyboardChecks.every(check => Object.entries(check).every(([name, value]) => name === "viewport" || value));
  const status = violationNodes === 0 && seriousOrCriticalNodes === 0 && incompleteNodes === 0 && keyboardPassed ? "pass" : "fail";
  const report = {
    schemaVersion: "jobservatory.accessibility-audit.v1",
    generatedAt: corpus.generatedAt,
    target: {
      artifact: "built Cloudflare Pages static bundle served by Vite preview",
      route: "/",
      states: ["ledger-loaded", "evidence-dialog-open"],
      viewports,
    },
    standard: {
      target: "WCAG 2.2 Level AA",
      automatedEngine: "axe-core",
      automatedEngineVersion: JSON.parse(await readFile(require.resolve("axe-core/package.json"), "utf8")).version,
      ruleTags: tags,
      browser: `Chromium ${browser.version()}`,
    },
    criteria: {
      violationNodes: 0,
      seriousOrCriticalNodes: 0,
      incompleteNodes: 0,
      keyboardChecksMustAllPass: true,
    },
    aggregate: {
      auditedStates: results.length,
      rulesEvaluated: results.reduce((total, result) => total + result.rulesEvaluated, 0),
      passedRuleResults: results.reduce((total, result) => total + result.passes, 0),
      violationNodes,
      seriousOrCriticalNodes,
      incompleteRuleResults: results.reduce((total, result) => total + result.incomplete.length, 0),
      incompleteNodes,
    },
    keyboardChecks,
    results,
    manualAssurance: {
      status: "required",
      scope: "screen-reader and assistive-technology review by a qualified human remains separate and incomplete",
    },
    status,
    limitations: [
      "Automated rules cannot prove conformance or replace evaluation by people who use assistive technologies.",
      "The audit covers the primary route after corpus load and with the evidence dialog open at desktop and mobile viewports.",
      "External source pages and downloaded JSON artifacts are outside this UI audit.",
      "Axe incomplete results require review but do not count as violations in this automated gate.",
    ],
  };
  await writeFile(outputUrl, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify({ status, aggregate: report.aggregate, keyboardChecks }, null, 2));
  if (status !== "pass") process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  preview.kill("SIGTERM");
}
