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
    const oldValue = this.value;
    this.value = value;
    this.emit("change", value, oldValue);
  }
  setOption(key, value) { this.options[key] = value; }
  on(event, listener) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(listener);
    return () => this.listeners.get(event)?.delete(listener);
  }
  emit(event, ...args) {
    for (const listener of [...(this.listeners.get(event) ?? [])]) listener(...args);
  }
  count(event) { return this.listeners.get(event)?.size ?? 0; }
}

class Node {
  constructor(values) {
    this.map = new Map(Object.entries(values).map(([name, value]) => [name, new Widget(name, value)]));
    this.widgets = { get: (name) => this.map.get(name) };
  }
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

assert.deepEqual([...definitions.keys()], ["Wan22ResolutionPresets"]);
const hooks = definitions.get("Wan22ResolutionPresets");
const mode14 = "Wan2.2 - 14B Models (I2V/T2V)";
const mode5 = "Wan2.2 - 5B Model (TI2V)";
const node = new Node({
  mode: mode14,
  aspect_ratio: "16:9 Landscape",
  resolution: "1280x720",
});
hooks.created(node);
assert.equal(node.map.get("mode").count("change"), 1);
assert.equal(node.map.get("aspect_ratio").count("change"), 1);
assert.equal(node.map.get("mode").options.tooltip,
  "CRITICAL INFO: Use Wan2.1 VAE. Resolutions must be divisible by 16.");
assert.deepEqual(JSON.parse(JSON.stringify(node.map.get("aspect_ratio").options.values)), [
  "16:9 Landscape", "9:16 Portrait", "4:3 Landscape", "3:4 Portrait",
  "3:2 Landscape", "2:3 Portrait", "1:1 Square", "21:9 Cinematic",
]);
assert.deepEqual(JSON.parse(JSON.stringify(node.map.get("resolution").options.values)), [
  "512x288", "768x432", "896x512", "1024x576", "1280x704",
  "1280x720", "1344x768", "1536x864", "1600x896",
]);

node.map.get("mode").setValue(mode5);
assert.equal(node.map.get("mode").options.tooltip,
  "CRITICAL INFO: Use Wan2.2 VAE. Resolutions must be divisible by 32.");
assert.deepEqual(JSON.parse(JSON.stringify(node.map.get("resolution").options.values)), [
  "512x288", "896x512", "1024x576", "1280x704", "1344x768", "1600x896",
]);
assert.equal(node.map.get("resolution").value, "1280x704");

node.map.get("aspect_ratio").setValue("21:9 Cinematic");
assert.deepEqual(JSON.parse(JSON.stringify(node.map.get("resolution").options.values)), ["1792x768"]);
assert.equal(node.map.get("resolution").value, "1792x768");

const peer = new Node({
  mode: mode14,
  aspect_ratio: "not-a-ratio",
  resolution: "not-a-resolution",
});
hooks.created(peer);
assert.equal(peer.map.get("aspect_ratio").value, "16:9 Landscape");
assert.equal(peer.map.get("resolution").value, "1280x704");
assert.equal(node.map.get("aspect_ratio").value, "21:9 Cinematic", "state is node-scoped");

hooks.configured(peer);
assert.equal(peer.map.get("mode").count("change"), 1, "configuration does not duplicate listeners");
hooks.created(peer);
assert.equal(peer.map.get("mode").count("change"), 1, "remount replaces listeners");
assert.equal(peer.map.get("aspect_ratio").count("change"), 1);
hooks.removed(peer);
assert.equal(peer.map.get("mode").count("change"), 0);
assert.equal(peer.map.get("aspect_ratio").count("change"), 0);
hooks.removed(peer);

console.log("PASS: Wan2.2 resolution dynamic combos, isolation, and teardown");
