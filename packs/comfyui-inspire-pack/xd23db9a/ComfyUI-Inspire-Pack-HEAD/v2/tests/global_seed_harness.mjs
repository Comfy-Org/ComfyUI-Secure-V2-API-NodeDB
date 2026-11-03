// Runs v2/web/global_seed.js against a host double, for tests/test_global_seed.py.
//
//   TARGET_JS=<v2/web/global_seed.js> SCENARIOS=<scenarios.json> WORK=<writable dir> node global_seed_harness.mjs
//
// For each scenario run it records the graph before the run, the prompt and the embedded workflow the host
// builds from the graph after the module's onBeforeRun (with the same rules test_global_seed.py uses to
// build the original's prompt), and the graph after the cleanup and onAfterRun. Prints JSON.

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const target = process.env.TARGET_JS;
const scenariosPath = process.env.SCENARIOS;
const work = process.env.WORK;
if (!target || !scenariosPath || !work) throw new Error("TARGET_JS, SCENARIOS and WORK are required");

const IMPORT_LINE = 'import { comfy } from "/comfy/api/v2.js";';
const source = fs.readFileSync(target, "utf8");
if (source.split(IMPORT_LINE).length !== 2) throw new Error("module must import comfy exactly once");

const spec = JSON.parse(fs.readFileSync(scenariosPath, "utf8"));
let state = null; // the current scenario's graph
const listeners = { before: [], after: [] };

function widgetHandle(record) {
  return {
    name: record.name,
    getValue: () => record.value,
    setValue: (value) => { record.value = value; },
    isHidden: () => record.hidden === true,
  };
}

function nodeHandle(record) {
  const widgets = record.widgets.map(widgetHandle);
  return {
    id: String(record.id),
    type: record.type,
    getMode: () => record.mode || "always",
    widgets: {
      get: (name) => widgets.find((widget) => widget.name === name),
      all: () => widgets.slice(),
    },
    inputs: {
      byName: (name) => (record.connected || []).includes(name)
        ? { name, isConnected: true, isWidgetInput: true } : undefined,
    },
  };
}

globalThis.__comfy = {
  defs: {
    get: (type) => (spec.defs[type] ? { type, inputs: spec.defs[type].map((name) => ({ name })) } : undefined),
  },
  graph: {
    root: () => (state ? { nodes: () => state.nodes.map(nodeHandle) } : undefined),
    queryNodes: (query) => {
      if (!query || query.scope !== "root-and-subgraphs") throw new Error("unexpected query");
      return [...state.nodes, ...(state.subgraph_nodes || [])].map(nodeHandle);
    },
  },
  queue: {
    onBeforeRun: (listener) => { listeners.before.push(listener); return () => {}; },
    onAfterRun: (listener) => { listeners.after.push(listener); return () => {}; },
  },
};

fs.mkdirSync(work, { recursive: true });
const moduleFile = path.join(work, "global_seed.under_test.mjs");
fs.writeFileSync(moduleFile, source.replace(IMPORT_LINE, "const comfy = globalThis.__comfy;"));
await import(pathToFileURL(moduleFile).href);
if (listeners.before.length !== 1 || listeners.after.length !== 1) throw new Error("expected one listener each");

const snapshot = () => JSON.parse(JSON.stringify(state));

function inPrompt(record) {
  const mode = record.mode || "always";
  return mode !== "never" && mode !== "bypass" && spec.defs[record.type] !== undefined;
}

// The host's prompt and workflow, built from the graph (same rules as the Python side).
function buildPrompt() {
  const prompt = {};
  const add = (record, id) => {
    const inputs = {};
    for (const name of spec.defs[record.type]) {
      if ((record.connected || []).includes(name)) inputs[name] = ["999", 0];
      else {
        const widget = record.widgets.find((item) => item.name === name);
        if (widget) inputs[name] = widget.value;
      }
    }
    prompt[id] = { class_type: record.type, inputs };
  };
  for (const record of state.nodes) if (inPrompt(record)) add(record, String(record.id));
  for (const record of state.subgraph_nodes || []) if (inPrompt(record)) add(record, `sg:${record.id}`);
  return prompt;
}

function buildWorkflow() {
  return { nodes: state.nodes.map((record) => ({ id: record.id, type: record.type, widgets_values: record.widgets.map((w) => w.value) })) };
}

const results = {};
for (const scenario of spec.scenarios) {
  state = JSON.parse(JSON.stringify({ nodes: scenario.nodes, subgraph_nodes: scenario.subgraph_nodes || [] }));
  const runs = [];
  for (let index = 0; index < (scenario.runs || 1); index += 1) {
    const before = snapshot();
    const cleanup = listeners.before[0]();
    const prompt = buildPrompt();
    const workflow = buildWorkflow();
    if (typeof cleanup === "function") cleanup();
    listeners.after[0]({ promptIds: [`run-${index}`], rejected: 0 });
    runs.push({ before, prompt, workflow, after: snapshot() });
  }
  results[scenario.name] = runs;
}
process.stdout.write(JSON.stringify(results));
