const state = { package: null, packageSha256: null, kind: null, index: 0, judgments: new Map() };
const byId = id => document.getElementById(id);
const elements = {
  setup: byId("setup"), reviewer: byId("reviewer"), shell: byId("task-shell"), card: byId("task-card"), export: byId("export"),
  file: byId("package-file"), loadStatus: byId("load-status"), reviewerId: byId("reviewer-id"), independent: byId("independent"),
  kind: byId("task-kind"), progressText: byId("progress-text"), progress: byId("progress"), heading: byId("task-heading"), query: byId("query"),
  stratum: byId("stratum"), facts: byId("facts"), evidence: byId("evidence"), controls: byId("judgment-controls"), note: byId("note"),
  previous: byId("previous"), next: byId("next"), nextUnanswered: byId("next-unanswered"), exportButton: byId("export-button"), exportStatus: byId("export-status"),
};

function storageKey() { return `jobservatory-annotation:${state.packageSha256}`; }

async function sha256(bytes) {
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return `sha256:${[...new Uint8Array(hash)].map(value => value.toString(16).padStart(2, "0")).join("")}`;
}

function validatePackage(value) {
  if (!value || !Array.isArray(value.tasks) || !value.protocolId || !["a", "b"].includes(value.reviewerSlot)) throw new Error("Not a Jobservatory reviewer package.");
  const kind = value.schemaVersion?.includes("retrieval") ? "retrieval" : value.schemaVersion?.includes("classification") ? "classification" : null;
  if (!kind || value.tasks.length === 0 || new Set(value.tasks.map(task => task.taskId)).size !== value.tasks.length) throw new Error("Package task contract is invalid.");
  return kind;
}

function blankJudgment(task) {
  return state.kind === "retrieval"
    ? { taskId: task.taskId, grade: null, note: "" }
    : { taskId: task.taskId, labels: Object.fromEntries(Object.keys(state.package.labelOntology).map(name => [name, []])), insufficientEvidence: null, note: "" };
}

function restore() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(storageKey())); } catch { /* ignore corrupt local draft */ }
  if (saved?.packageSha256 !== state.packageSha256) return;
  const taskIds = new Set(state.package.tasks.map(task => task.taskId));
  for (const judgment of saved.judgments || []) if (taskIds.has(judgment.taskId)) state.judgments.set(judgment.taskId, judgment);
  elements.reviewerId.value = saved.reviewerId || "";
  elements.independent.checked = Boolean(saved.independent);
  state.index = Math.min(Math.max(saved.index || 0, 0), state.package.tasks.length - 1);
}

function save() {
  if (!state.package) return;
  localStorage.setItem(storageKey(), JSON.stringify({
    packageSha256: state.packageSha256, reviewerId: elements.reviewerId.value.trim(), independent: elements.independent.checked,
    index: state.index, judgments: [...state.judgments.values()], savedAt: new Date().toISOString(),
  }));
}

function complete(judgment) {
  return state.kind === "retrieval" ? Number.isInteger(judgment.grade) : typeof judgment.insufficientEvidence === "boolean";
}

function completion() { return state.package.tasks.filter(task => complete(state.judgments.get(task.taskId) || blankJudgment(task))).length; }

function addFact(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt"); term.textContent = label;
  const description = document.createElement("dd"); description.textContent = value || "Not stated";
  wrapper.append(term, description); elements.facts.append(wrapper);
}

function payText(compensation) {
  if (!compensation) return "Not stated";
  const format = new Intl.NumberFormat("en-US", { style: "currency", currency: compensation.currency, maximumFractionDigits: 0 });
  return `${format.format(compensation.minimum)}–${format.format(compensation.maximum)} / ${compensation.period}`;
}

function renderRetrieval(judgment) {
  const descriptions = ["Irrelevant", "Related only", "Strong; one material miss", "Direct fit"];
  const fieldset = document.createElement("fieldset"); fieldset.className = "family";
  const legend = document.createElement("legend"); legend.textContent = "Graded relevance"; fieldset.append(legend);
  const grid = document.createElement("div"); grid.className = "choice-grid";
  descriptions.forEach((description, grade) => {
    const label = document.createElement("label");
    const input = document.createElement("input"); input.type = "radio"; input.name = "grade"; input.value = String(grade); input.checked = judgment.grade === grade;
    input.addEventListener("change", () => { judgment.grade = grade; save(); updateProgress(); });
    const text = document.createElement("span"); text.innerHTML = `<b>${grade}</b><small>${description}</small>`;
    label.append(input, text); grid.append(label);
  });
  fieldset.append(grid); elements.controls.append(fieldset);
}

function renderClassification(judgment) {
  for (const [family, options] of Object.entries(state.package.labelOntology)) {
    const fieldset = document.createElement("fieldset"); fieldset.className = "family";
    const legend = document.createElement("legend"); legend.textContent = family.replace(/([A-Z])/g, " $1"); fieldset.append(legend);
    const grid = document.createElement("div"); grid.className = "label-grid";
    for (const option of options) {
      const label = document.createElement("label"); const input = document.createElement("input"); input.type = "checkbox"; input.checked = judgment.labels[family].includes(option);
      input.addEventListener("change", () => { judgment.labels[family] = input.checked ? [...new Set([...judgment.labels[family], option])] : judgment.labels[family].filter(value => value !== option); judgment.insufficientEvidence = false; save(); updateProgress(); });
      const text = document.createElement("span"); text.textContent = option; label.append(input, text); grid.append(label);
    }
    fieldset.append(grid); elements.controls.append(fieldset);
  }
  const decision = document.createElement("fieldset"); decision.className = "family evidence-decision";
  const legend = document.createElement("legend"); legend.textContent = "Evidence sufficiency"; decision.append(legend);
  [[false, "Evidence sufficient"], [true, "Insufficient evidence"]].forEach(([value, text]) => {
    const label = document.createElement("label"); const input = document.createElement("input"); input.type = "radio"; input.name = "evidence"; input.checked = judgment.insufficientEvidence === value;
    input.addEventListener("change", () => { judgment.insufficientEvidence = value; if (value) for (const family of Object.keys(judgment.labels)) judgment.labels[family] = []; save(); updateProgress(); if (value) render(); });
    label.append(input, document.createTextNode(text)); decision.append(label);
  });
  elements.controls.append(decision);
}

function updateProgress() {
  const done = completion(), total = state.package.tasks.length;
  elements.progressText.textContent = `${done} done · ${state.index + 1} / ${total}`; elements.progress.max = total; elements.progress.value = done;
  elements.exportButton.disabled = done !== total || !elements.reviewerId.value.trim() || !elements.independent.checked;
  elements.exportStatus.textContent = done === total ? "All tasks judged. Add the reviewer declaration to enable export." : `${total - done} judgments remain.`;
  if (!elements.exportButton.disabled) elements.exportStatus.textContent = "Submission is complete and ready to download.";
}

function render() {
  const task = state.package.tasks[state.index];
  const judgment = state.judgments.get(task.taskId) || blankJudgment(task); state.judgments.set(task.taskId, judgment);
  elements.kind.textContent = `${state.kind.toUpperCase()} · REVIEWER ${state.package.reviewerSlot.toUpperCase()}`;
  elements.stratum.textContent = state.kind === "retrieval" ? task.stratum : `CLASSIFICATION RECORD ${state.index + 1}`;
  elements.heading.textContent = task.document.title;
  elements.query.textContent = state.kind === "retrieval" ? task.query : "Assign every supported label family; abstain when excerpts are insufficient.";
  elements.facts.replaceChildren(); addFact("Location", task.document.location); addFact("Seniority", task.document.seniority); addFact("Domain", task.document.domain); addFact("Compensation", payText(task.document.compensation));
  elements.evidence.replaceChildren();
  for (const excerpt of task.document.evidenceExcerpts) { const quote = document.createElement("blockquote"); quote.textContent = excerpt; elements.evidence.append(quote); }
  if (!task.document.evidenceExcerpts.length) { const empty = document.createElement("p"); empty.textContent = "No excerpt retained; judge only the supplied metadata or abstain."; elements.evidence.append(empty); }
  elements.controls.replaceChildren();
  if (state.kind === "retrieval") renderRetrieval(judgment); else renderClassification(judgment);
  elements.note.value = judgment.note || "";
  elements.previous.disabled = state.index === 0; elements.next.disabled = state.index === state.package.tasks.length - 1;
  updateProgress();
}

async function loadBytes(bytes, label) {
  const text = new TextDecoder().decode(bytes); const value = JSON.parse(text); const kind = validatePackage(value);
  state.package = value; state.packageSha256 = await sha256(bytes); state.kind = kind; state.index = 0; state.judgments = new Map(); elements.reviewerId.value = ""; elements.independent.checked = false; restore();
  elements.loadStatus.textContent = `${label}: ${value.tasks.length} ${kind} tasks · ${state.packageSha256.slice(0, 23)}…`;
  elements.reviewer.classList.remove("hidden"); elements.shell.classList.remove("hidden"); elements.export.classList.remove("hidden"); render(); elements.shell.scrollIntoView({ behavior: "smooth" });
}

for (const button of document.querySelectorAll("[data-package]")) button.addEventListener("click", async () => {
  elements.loadStatus.textContent = "Loading package…";
  try { const response = await fetch(button.dataset.package); if (!response.ok) throw new Error(`HTTP ${response.status}`); await loadBytes(await response.arrayBuffer(), button.textContent.trim()); }
  catch (error) { elements.loadStatus.textContent = `Could not load package: ${error.message}`; }
});
elements.file.addEventListener("change", async () => { const file = elements.file.files[0]; if (!file) return; try { await loadBytes(await file.arrayBuffer(), file.name); } catch (error) { elements.loadStatus.textContent = `Could not load package: ${error.message}`; } });
elements.note.addEventListener("input", () => { const task = state.package.tasks[state.index]; state.judgments.get(task.taskId).note = elements.note.value; save(); });
elements.reviewerId.addEventListener("input", () => { save(); updateProgress(); }); elements.independent.addEventListener("change", () => { save(); updateProgress(); });
elements.previous.addEventListener("click", () => { if (state.index > 0) { state.index--; save(); render(); elements.heading.focus?.(); } });
elements.next.addEventListener("click", () => { if (state.index < state.package.tasks.length - 1) { state.index++; save(); render(); } });
elements.nextUnanswered.addEventListener("click", () => { const total = state.package.tasks.length; for (let offset = 1; offset <= total; offset++) { const index = (state.index + offset) % total; const task = state.package.tasks[index]; if (!complete(state.judgments.get(task.taskId) || blankJudgment(task))) { state.index = index; save(); render(); return; } } elements.export.scrollIntoView({ behavior: "smooth" }); });
elements.exportButton.addEventListener("click", () => {
  updateProgress(); if (elements.exportButton.disabled) return;
  const base = { schemaVersion: `jobservatory.${state.kind}-annotation-submission.v1`, protocolId: state.package.protocolId, packageSha256: state.packageSha256, reviewer: { id: elements.reviewerId.value.trim(), independent: true, completedAt: new Date().toISOString() }, judgments: state.package.tasks.map(task => state.judgments.get(task.taskId)) };
  const blob = new Blob([`${JSON.stringify(base, null, 2)}\n`], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${state.kind}-reviewer-${state.package.reviewerSlot}.json`; link.click(); URL.revokeObjectURL(link.href); elements.exportStatus.textContent = `Downloaded ${link.download}. Submit it through the research team's approved channel.`;
});
