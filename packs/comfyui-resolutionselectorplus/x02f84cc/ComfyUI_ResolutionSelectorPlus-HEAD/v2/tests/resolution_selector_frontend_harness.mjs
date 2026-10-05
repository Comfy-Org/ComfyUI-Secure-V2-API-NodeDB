import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js/, /app\.registerExtension|LiteGraph|app\.graph|app\.canvas/,
  /(?:^|[^A-Za-z])document\s*\./m, /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|innerHTML|comfy\.backend|setTimeout|setInterval/,
]) assert.doesNotMatch(source, forbidden);

class Widget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.options = {};
    this.listeners = new Map();
  }
  getValue() { return this.value; }
  setValue(value) {
    if (Object.is(value, this.value)) return;
    const old = this.value;
    this.value = value;
    for (const listener of [...(this.listeners.get("change") ?? [])]) listener(value, old);
  }
  setOption(name, value) { this.options[name] = value; }
  on(name, listener) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name).add(listener);
    return () => this.listeners.get(name)?.delete(listener);
  }
  count(name) { return this.listeners.get(name)?.size ?? 0; }
}

class Node {
  constructor(model, resolution, width = 260) {
    this.map = new Map([
      ["model", new Widget("model", model)],
      ["resolution", new Widget("resolution", resolution)],
    ]);
    this.widgets = { get: (name) => this.map.get(name) };
    this.size = { width, height: 300 };
  }
  getSize() { return { ...this.size }; }
  setSize(size) { this.size = { ...size }; }
}

const definitions = new Map();
const comfy = {
  defs: {
    extend(nodeType, configure) {
      const hooks = {};
      configure({
        onCreated(callback) { hooks.created = callback; },
        onConfigured(callback) { hooks.configured = callback; },
        onRemoved(callback) { hooks.removed = callback; },
      });
      definitions.set(nodeType, hooks);
    },
  },
};

const context = vm.createContext({ console });
const module = new vm.SourceTextModule(source, {
  context,
  identifier: pathToFileURL(entry).href,
});
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  const stub = new vm.SyntheticModule(["comfy"], function () {
    this.setExport("comfy", comfy);
  }, { context });
  await stub.link(() => {});
  return stub;
});
await module.evaluate();

assert.deepEqual([...definitions.keys()], ["ResolutionSelectorPlus"]);
const hooks = definitions.get("ResolutionSelectorPlus");
const preserved = "1536x1024    (3:2 Landscape)";
const node = new Node("SDXL", preserved);
hooks.created(node);
assert.equal(node.size.width, 400);
assert.equal(node.map.get("model").count("change"), 1);
assert.equal(node.map.get("resolution").value, preserved);
assert.ok(node.map.get("resolution").options.values.includes(preserved));
assert.ok(!node.map.get("resolution").options.values.includes("512x512      (1:1 Square)"));

node.map.get("model").setValue("SD 1.5");
assert.equal(node.map.get("resolution").value, "512x512      (1:1 Square)");
assert.ok(node.map.get("resolution").options.values.includes("768x512      (3:2 Landscape)"));

const invalid = new Node("Flux", "not-a-resolution", 500);
hooks.created(invalid);
assert.equal(invalid.size.width, 500);
assert.equal(invalid.map.get("resolution").value,
  invalid.map.get("resolution").options.values[0]);
hooks.configured(invalid);
assert.equal(invalid.map.get("model").count("change"), 1);
hooks.created(invalid);
assert.equal(invalid.map.get("model").count("change"), 1);
assert.equal(node.map.get("model").value, "SD 1.5", "instances are isolated");
hooks.removed(invalid);
assert.equal(invalid.map.get("model").count("change"), 0);
hooks.removed(invalid);

console.log("PASS: ResolutionSelectorPlus filtering, restoration, isolation, and teardown");
