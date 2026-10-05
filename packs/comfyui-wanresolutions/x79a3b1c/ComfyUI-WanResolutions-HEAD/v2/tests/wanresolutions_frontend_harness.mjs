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
  /localStorage|indexedDB|fetch\s*\(|innerHTML|comfy\.backend/,
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
    this.value = value;
    this.emit("change", value);
  }
  setOption(key, value) { this.options[key] = value; }
  on(event, listener) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(listener);
    return () => this.listeners.get(event)?.delete(listener);
  }
  emit(event, value) {
    for (const listener of [...(this.listeners.get(event) ?? [])]) listener(value);
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
        onExecuted(callback) { hooks.executed = callback; },
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

assert.deepEqual([...definitions.keys()], ["WanResolutions", "MiniMaxH3Resolutions", "LTXResolutions"]);

const wanHooks = definitions.get("WanResolutions");
const wan = new Node({
  aspect_ratio: "1:1",
  resolution: "High Detail — 832×832",
  official_only: false,
});
wanHooks.created(wan);
assert.equal(wan.map.get("aspect_ratio").count("change"), 1);
assert.equal(wan.map.get("official_only").count("change"), 1);
assert.deepEqual(JSON.parse(JSON.stringify(wan.map.get("resolution").options.values)), [
  "Fast Draft — 480×480", "Preview — 640×640", "High Detail — 832×832",
  "Wan 2.2 Native — 960×960",
]);
wan.map.get("aspect_ratio").setValue("16:9");
assert.equal(wan.map.get("resolution").value, "High Detail — 1104×624");
wan.map.get("official_only").setValue(true);
assert.deepEqual(JSON.parse(JSON.stringify(wan.map.get("resolution").options.values)), [
  "Official 480P — 832×480", "Official 720P — 1280×720",
]);
assert.equal(wan.map.get("resolution").value, "Official 720P — 1280×720");

const peer = new Node({
  aspect_ratio: "1:1", resolution: "Fast Draft — 480×480", official_only: false,
});
wanHooks.created(peer);
wanHooks.executed(wan, { raw: { aspect_resolution_state: [{
  aspect_ratio: "9:16", resolution: "Official 480P — 480×832",
}]} });
assert.equal(wan.map.get("aspect_ratio").value, "9:16");
assert.equal(wan.map.get("resolution").value, "Official 480P — 480×832");
assert.equal(peer.map.get("aspect_ratio").value, "1:1", "execution state is node-scoped");

wanHooks.configured(peer, {});
assert.equal(peer.map.get("aspect_ratio").count("change"), 1, "configuration does not duplicate listeners");
wanHooks.created(peer);
assert.equal(peer.map.get("aspect_ratio").count("change"), 1, "remount replaces listeners");
wanHooks.removed(peer);
assert.equal(peer.map.get("aspect_ratio").count("change"), 0);
assert.equal(peer.map.get("official_only").count("change"), 0);
wanHooks.removed(peer);

const miniHooks = definitions.get("MiniMaxH3Resolutions");
const mini = new Node({ aspect_ratio: "16:9", resolution: "2K (2.25 MP) — 2048×1152" });
miniHooks.created(mini);
mini.map.get("aspect_ratio").setValue("1:1");
assert.equal(mini.map.get("resolution").value, "2K (2.25 MP) — 1536×1536");
assert.equal(mini.map.get("resolution").options.values.length, 8);

const ltxHooks = definitions.get("LTXResolutions");
const ltx = new Node({
  aspect_ratio: "1:1", resolution: "Full HD Output — 1440×1440",
  image_bypass: false, upscaler_power: "none",
});
ltxHooks.created(ltx);
ltx.map.get("aspect_ratio").setValue("16:9");
assert.equal(ltx.map.get("resolution").value, "Full HD Output — 1920×1088");
ltxHooks.executed(ltx, { wanresolutions_state: [{
  aspect_ratio: "3:4", resolution: "Balanced — 640×864",
}] });
assert.equal(ltx.map.get("resolution").value, "Balanced — 640×864");

console.log("PASS: WanResolutions typed dynamic widgets, isolation, and teardown");
