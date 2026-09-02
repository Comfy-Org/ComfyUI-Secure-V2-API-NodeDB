import vm from "node:vm";
import http from "node:http";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";


const HERE = path.dirname(fileURLToPath(import.meta.url));
const JS = path.resolve(HERE, "../js/dynamicnode.js");
const CONFIG = path.resolve(HERE, "../js/dynamic-config.js");
const REPO = path.resolve(HERE, "../../../../../../../");
const OVERLAY_SRC = path.resolve(REPO, "frontend/src");
const SOURCE = readFileSync(JS, "utf8");
const CONFIG_SOURCE = readFileSync(CONFIG, "utf8");


function assert(condition, message) {
  if (!condition) throw new Error(`ASSERT: ${message}`);
}


class Widgets {
  constructor(specs = []) {
    this.values = [];
    for (const spec of specs) this.add(spec);
  }
  get(name) { return this.values.find((item) => item.name === name); }
  names() { return this.values.map((item) => item.name); }
  add(spec) {
    assert(!this.get(spec.name), `duplicate widget ${spec.name}`);
    const listeners = new Set();
    const item = {
      name: spec.name,
      type: spec.type,
      value: spec.value,
      options: { ...(spec.options || {}) },
      getValue() { return this.value; },
      setValue(value) {
        this.value = value;
        for (const listener of listeners) listener({ value });
      },
      on(event, listener) {
        assert(event === "change", `unexpected widget event ${event}`);
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
    };
    this.values.push(item);
    return item;
  }
  remove(name) {
    this.values = this.values.filter((item) => item.name !== name);
  }
}


class Inputs {
  constructor(specs = []) {
    this.values = [];
    for (const spec of specs) this.add(spec.name, spec.type, spec.options, spec);
  }
  all() { return [...this.values]; }
  names() { return this.values.map((item) => item.name); }
  add(name, type, options = {}, extra = {}) {
    const owner = this;
    const slot = {
      id: `slot-${Math.random()}`,
      name,
      type,
      isConnected: Boolean(extra.isConnected),
      options: { ...options },
      modify(change) {
        Object.assign(this, change);
        if (change.widget) this.options.widget = change.widget;
      },
    };
    owner.values.push(slot);
    return slot;
  }
  remove(target) {
    const id = typeof target === "string" ? target : target.id;
    this.values = this.values.filter((item) => item.id !== id && item.name !== id);
  }
  reorder(names) {
    const used = new Set();
    const ordered = [];
    for (const name of names) {
      const slot = this.values.find((item) => item.name === name && !used.has(item));
      if (slot) { ordered.push(slot); used.add(slot); }
    }
    ordered.push(...this.values.filter((item) => !used.has(item)));
    this.values = ordered;
  }
}


function fakeNode(inputs, widgets = []) {
  return {
    id: `node-${Math.random()}`,
    inputs: new Inputs(inputs),
    widgets: new Widgets(widgets),
  };
}


async function load() {
  const extensions = new Map();
  const comfy = {
    defs: {
      extend(type, apply) {
        const hooks = {};
        apply({
          onCreated(fn) { hooks.onCreated = fn; },
          onConfigured(fn) { hooks.onConfigured = fn; },
          onConnectionsChanged(fn) { hooks.onConnectionsChanged = fn; },
          onRemoved(fn) { hooks.onRemoved = fn; },
        });
        extensions.set(type, hooks);
      },
    },
  };
  const context = vm.createContext({ console });
  const source = new vm.SourceTextModule(readFileSync(JS, "utf8"), {
    context, identifier: JS,
  });
  const config = new vm.SourceTextModule(readFileSync(CONFIG, "utf8"), {
    context, identifier: CONFIG,
  });
  await source.link((specifier) => {
    if (specifier === "/comfy/api/v2.js") {
      return new vm.SyntheticModule(["comfy"], function expose() {
        this.setExport("comfy", comfy);
      }, { context, identifier: specifier });
    }
    assert(specifier === "./dynamic-config.js", `unexpected import ${specifier}`);
    return config;
  });
  await source.evaluate();
  return { extensions, context };
}


const { extensions, context } = await load();
assert(extensions.size === 26, "dynamic extension census changed");

const listHooks = extensions.get("Basic data handling: ListCreate");
const list = fakeNode(
  [{ name: "item_0", type: "*", options: { widget: "item_0" } }],
  [{ name: "item_0", type: "text", value: "" }],
);
listHooks.onCreated(list, { restored: false, loading: false });
assert(list.inputs.names().join() === "item_0", "fresh empty list grew");
list.widgets.get("item_0").setValue("alpha");
assert(list.inputs.names().join() === "item_0,item_1", "active list did not grow");
list.widgets.get("item_1").setValue("beta");
assert(list.inputs.names().join() === "item_0,item_1,item_2", "second row did not grow");
list.widgets.get("item_1").setValue("");
assert(list.inputs.names().join() === "item_0,item_1", "extra empty row was not removed");
assert(list.widgets.get("item_1").getValue() === "", "placeholder was not renumbered");

const dictHooks = extensions.get("Basic data handling: DictCreate");
const dict = fakeNode(
  [
    { name: "key_0", type: "STRING", options: { widget: "key_0" } },
    { name: "value_0", type: "*", options: { widget: "value_0" } },
  ],
  [
    { name: "key_0", type: "text", value: "" },
    { name: "value_0", type: "text", value: "" },
  ],
);
dictHooks.onCreated(dict, { restored: false, loading: false });
dict.widgets.get("key_0").setValue("first");
assert(dict.inputs.names().join() === "key_0,value_0,key_1,value_1",
  "paired dict row did not grow together");
dict.widgets.get("value_1").setValue("second");
assert(dict.inputs.names().join() ===
  "key_0,value_0,key_1,value_1,key_2,value_2", "dict trailing pair missing");
dict.widgets.get("key_0").setValue("");
assert(dict.inputs.names().join() === "key_0,value_0,key_1,value_1",
  "dict empty pair removal/renumber failed");
assert(dict.widgets.get("value_0").getValue() === "second",
  "dict active pair value was lost while renumbering");

const branchHooks = extensions.get("Basic data handling: IfElifElse");
const branch = fakeNode([
  { name: "if", type: "BOOLEAN" },
  { name: "then", type: "*" },
  { name: "elif_0", type: "BOOLEAN" },
  { name: "then_0", type: "*" },
  { name: "else", type: "*" },
]);
branchHooks.onCreated(branch, { restored: false, loading: false });
branch.inputs.all().find((slot) => slot.name === "elif_0").isConnected = true;
branchHooks.onConnectionsChanged(branch, { side: "input" });
assert(branch.inputs.names().join() ===
  "if,then,elif_0,then_0,elif_1,then_1,else", "branch pair placement changed");

const formulaHooks = extensions.get("Basic data handling: MathFormula");
const formula = fakeNode([{ name: "a", type: "FLOAT,INT", isConnected: true }]);
formulaHooks.onCreated(formula, { restored: false, loading: false });
assert(formula.inputs.names().join() === "a,b", "letter growth changed");

const restored = fakeNode(
  [{ name: "item_0", type: "*", isConnected: true }],
  [{ name: "item_0", type: "text", value: "saved" }],
);
listHooks.onCreated(restored, { restored: false, loading: true });
listHooks.onConnectionsChanged(restored, { side: "input" });
assert(restored.inputs.names().join() === "item_0", "loading barrier mutated node");
restored.inputs = new Inputs([
  { name: "item_0", type: "*", isConnected: true },
  { name: "item_1", type: "*", isConnected: false },
]);
restored.widgets = new Widgets([
  { name: "item_0", type: "text", value: "saved" },
  { name: "item_1", type: "text", value: "" },
]);
listHooks.onConfigured(restored);
assert(restored.inputs.names().join() === "item_0,item_1",
  "configured restore changed exact rows");
listHooks.onRemoved(restored);

for (const name of ["window", "document", "app", "LiteGraph", "fetch"]) {
  assert(context?.[name] === undefined, `${name} leaked into the iframe`);
}

console.log("basic data handling frontend harness: PASS");


const FIXTURE = `
import { comfy } from "/comfy/api/v2.js";
comfy.defs.define({
  type: "BasicDataHandlingHarnessSource",
  title: "BDH source",
  category: "tests",
  execution: "frontend",
  inputs: [],
  outputs: [{ name: "value", type: "*" }],
  resolve: () => ({ "0": { literal: "linked" } }),
});
comfy.defs.define({
  type: "Basic data handling: ListCreate",
  title: "Create List",
  category: "Basic/LIST",
  execution: "frontend",
  inputs: [{ name: "item_0", type: "*", widget: "item_0" }],
  outputs: [{ name: "LIST", type: "LIST" }],
  widgets: [{ type: "text", name: "item_0", value: "" }],
  resolve: () => ({ "0": { literal: [] } }),
});
`;


function serveModules() {
  const server = http.createServer((request, response) => {
    response.setHeader("Access-Control-Allow-Origin", "*");
    response.setHeader("Content-Type", "text/javascript");
    if (request.url === "/dynamicnode.js") response.end(SOURCE);
    else if (request.url === "/dynamic-config.js") response.end(CONFIG_SOURCE);
    else if (request.url === "/fixture.js") response.end(FIXTURE);
    else if (request.url === "/comfy/api/v2.js") {
      response.end("export const comfy = globalThis.comfy\n");
    } else {
      response.statusCode = 404;
      response.end("not found");
    }
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}


async function productionProof() {
  const { chromium } = await import(
    path.resolve(REPO, "frontend/tests/_deps.mjs")
  );
  const server = await serveModules();
  const address = server.address();
  const base = `http://127.0.0.1:${address.port}`;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  try {
    await page.route("**/secure-nodes/src/**", async (route) => {
      const url = new URL(route.request().url());
      const marker = "/secure-nodes/src/";
      const relative = decodeURIComponent(url.pathname.slice(
        url.pathname.indexOf(marker) + marker.length,
      ));
      assert(relative && !relative.split("/").includes(".."),
        `invalid overlay route ${relative}`);
      const file = path.resolve(OVERLAY_SRC, relative);
      assert(file.startsWith(`${OVERLAY_SRC}${path.sep}`),
        `overlay route escaped root ${relative}`);
      await route.fulfill({
        status: 200,
        contentType: file.endsWith(".json") ? "application/json" : "text/javascript",
        body: readFileSync(file),
      });
    });
    const appUrl = process.env.APP_URL || "http://127.0.0.1:5191";
    await page.goto(`${appUrl}/?secureNodes=1`);
    await page.waitForFunction(
      () => globalThis.__COMFY_SECURE_NODES_READY__ === true
        && !!globalThis.app?.graph && !!globalThis.comfy,
      undefined,
      { timeout: 120000 },
    );
    await page.evaluate(async ({ pack, fixture }) => {
      const host = globalThis.__COMFY_SECURE_NODES_HOST__;
      await host.load(pack);
      await host.load(fixture);
    }, { pack: `${base}/dynamicnode.js`, fixture: `${base}/fixture.js` });
    await page.waitForFunction(
      () => globalThis.comfy.defs.has("Basic data handling: ListCreate"),
    );
    const result = await page.evaluate(async () => {
      const comfy = globalThis.comfy;
      const waitFor = async (predicate, description) => {
        const deadline = Date.now() + 8000;
        while (Date.now() < deadline) {
          if (predicate()) return;
          await new Promise((resolve) => setTimeout(resolve, 50));
        }
        throw new Error(`production probe timed out: ${description}`);
      };
      const source = comfy.graph.add("BasicDataHandlingHarnessSource", {
        position: { x: 20, y: 20 },
      });
      const source2 = comfy.graph.add("BasicDataHandlingHarnessSource", {
        position: { x: 20, y: 180 },
      });
      const list = comfy.graph.add("Basic data handling: ListCreate", {
        position: { x: 320, y: 20 },
      });
      await new Promise((resolve) => setTimeout(resolve, 500));
      source.outputs.at(0).connectTo(list.id, "item_0");
      await waitFor(() => list.inputs.byName("item_1"), "first trailing row");
      source2.outputs.at(0).connectTo(list.id, "item_1");
      await waitFor(() => list.inputs.byName("item_2"), "connected trailing row");
      list.widgets.get("item_0").setValue("saved");
      const workflow = globalThis.app.graph.serialize();
      await globalThis.app.loadGraphData(workflow);
      await waitFor(() => globalThis.app.graph.getNodeById(list.id), "graph reload");
      await new Promise((resolve) => setTimeout(resolve, 900));
      const restored = globalThis.app.graph.getNodeById(list.id);
      return {
        inputs: restored.inputs.map((input) => input.name),
        widgets: restored.widgets.map((widget) => widget.name),
        value: restored.widgets.find((widget) => widget.name === "item_0")?.value,
        errors: globalThis.__COMFY_SECURE_NODES_HOST__.packErrors ?? [],
      };
    });
    assert(result.inputs.join() === "item_0,item_1,item_2",
      `production dynamic inputs changed: ${JSON.stringify(result)}`);
    assert(result.widgets.join() === "item_0,item_1,item_2",
      `production dynamic widgets changed: ${JSON.stringify(result)}`);
    assert(result.value === "saved", "production widget value did not restore");
    assert(result.errors.length === 0,
      `production worker errors: ${JSON.stringify(result.errors)}`);
    console.log("basic data handling production iframe harness: PASS");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}


if (process.argv.includes("--production")) await productionProof();
