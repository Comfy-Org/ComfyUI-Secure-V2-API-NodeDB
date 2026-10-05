import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
assert.match(source, /from ["']\/comfy\/api\/v2\.js["']/);
for (const forbidden of [
  /\bwindow\s*\./, /\bdocument\s*\./, /localStorage/, /sessionStorage/,
  /app\.registerExtension/, /LiteGraph/, /app\.graph/, /\._nodes/,
  /MutationObserver/, /\bfetch\s*\(/, /WebSocket/, /XMLHttpRequest/,
]) assert.doesNotMatch(source, forbidden);

const extensions = new Map();
const comfy = {
  defs: {
    extend(type, callback) {
      const hooks = {};
      callback({
        onCreated(fn) { hooks.onCreated = fn; },
        onConfigured(fn) { hooks.onConfigured = fn; },
        onConnectionsChanged(fn) { hooks.onConnectionsChanged = fn; },
        onResized(fn) { hooks.onResized = fn; },
        onRemoved(fn) { hooks.onRemoved = fn; },
      });
      extensions.set(type, hooks);
    },
  },
};

const context = vm.createContext({
  console, Array, Map, Math, Number, Object, Set, String,
});
const comfyModule = new vm.SyntheticModule(["comfy"], function () {
  this.setExport("comfy", comfy);
}, { context, identifier: "secure:comfy-api-v2" });
const module = new vm.SourceTextModule(source, {
  context, identifier: pathToFileURL(entry).href,
});
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  return comfyModule;
});
await comfyModule.evaluate();
await module.evaluate();

assert.deepEqual([...extensions], [
  ["VisualAreaPrompt", extensions.get("VisualAreaPrompt")],
  ["VisualAreaPromptAdvanced", extensions.get("VisualAreaPromptAdvanced")],
]);

class Widget {
  constructor(name, value, options = {}) {
    this.name = name;
    this.value = value;
    this.options = { ...options };
    this.listeners = new Set();
  }
  getValue() { return this.value; }
  setValue(value) {
    if (Object.is(this.value, value)) return;
    const old = this.value;
    this.value = value;
    for (const listener of [...this.listeners]) listener(value, old);
  }
  setOption(name, value) { this.options[name] = value; }
  on(event, listener) {
    assert.equal(event, "change");
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

function makeNode(id, advanced = false) {
  const slots = [];
  const widgets = new Map();
  if (advanced) widgets.set("merge_global", new Widget("merge_global", false));
  widgets.set("image_width", new Widget("image_width", 1024));
  widgets.set("image_height", new Widget("image_height", 1024));
  const properties = new Map();
  const node = {
    id, properties, constraints: null, canvasDefs: [],
    getProperty(name) { return properties.get(name); },
    setProperty(name, value) { properties.set(name, structuredClone(value)); },
    setSizeConstraints(value) { this.constraints = value; },
    inputs: {
      all: () => [...slots],
      add(name, type, options) {
        const slot = {
          id: `${id}:slot:${slots.length}:${name}`, name, type, options,
          isConnected: false,
          modify(patch) { Object.assign(this, patch); },
        };
        slots.push(slot);
        return slot;
      },
      remove(ref) {
        const index = slots.findIndex((slot) => slot.id === ref || slot.name === ref);
        if (index < 0) return false;
        slots.splice(index, 1);
        return true;
      },
    },
    widgets: {
      get: (name) => widgets.get(name),
      add(def) {
        const widget = new Widget(def.name, def.value, def.options);
        widgets.set(def.name, widget);
        return widget;
      },
      canvas(def) {
        const surface = { redraws: 0, redraw() { this.redraws += 1; } };
        node.canvasDefs.push({ def, surface });
        return surface;
      },
    },
    _slots: slots,
    _widgets: widgets,
  };
  return node;
}

const hooks = extensions.get("VisualAreaPrompt");
const first = makeNode("first");
hooks.onCreated(first);
assert.deepEqual(first._slots.map((slot) => slot.name), ["area_conditioning_"]);
assert.deepEqual(first.getProperty("area_values"), [[0, 0, 1, 1, 1]]);
assert.deepEqual(JSON.parse(JSON.stringify(first.constraints)), { minWidth: 240, minHeight: 360 });
assert.equal(first.canvasDefs.length, 1);
assert.equal(first.canvasDefs[0].def.serialize, false);
assert.equal(first.canvasDefs[0].def.sendToPrompt, false);

first._slots[0].isConnected = true;
hooks.onConnectionsChanged(first, {});
assert.deepEqual(first._slots.map((slot) => slot.name), [
  "area_conditioning_0", "area_conditioning_",
]);
first._slots[1].isConnected = true;
hooks.onConnectionsChanged(first, {});
assert.deepEqual(first._slots.map((slot) => slot.name), [
  "area_conditioning_0", "area_conditioning_1", "area_conditioning_",
]);
assert.equal(first.getProperty("area_values").length, 2);

first._widgets.get("area_id").setValue(1);
first._widgets.get("x").setValue(0.25);
first._widgets.get("height").setValue(0.5);
first._widgets.get("conditioning_strength").setValue(3.5);
assert.deepEqual(first.getProperty("area_values")[1], [0.25, 0, 1, 0.5, 3.5]);
assert.equal(first._widgets.get("area_id").options.max, 1);

// State and selections are local to each node instance.
const second = makeNode("second", true);
extensions.get("VisualAreaPromptAdvanced").onCreated(second);
assert.deepEqual(second.getProperty("area_values"), [[0, 0, 1, 1, 1]]);
assert.equal(second._widgets.get("x").getValue(), 0);
assert.equal(second._slots.length, 1);
assert.notEqual(second.canvasDefs[0].surface, first.canvasDefs[0].surface);

// Corrupt persisted properties are repaired rather than shared or rendered.
second.setProperty("area_values", [[NaN, 0, 1, 1, 1], [0, 0, 9, 1, 1]]);
extensions.get("VisualAreaPromptAdvanced").onConfigured(second, {});
assert.deepEqual(second.getProperty("area_values"), [[0, 0, 1, 1, 1]]);

const drawCalls = [];
const drawing = {
  globalAlpha: 1, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {},
  clearRect(...args) { drawCalls.push(["clear", ...args]); },
  fillRect(...args) { drawCalls.push(["fill", ...args]); },
  strokeRect(...args) { drawCalls.push(["stroke", ...args]); },
};
first.canvasDefs[0].def.draw(
  drawing, [320, 220],
  { border: "#333", surface: "#111", textSecondary: "#777", text: "#fff" },
);
assert.equal(drawCalls[0][0], "clear");
assert.ok(drawCalls.filter((call) => call[0] === "stroke").length >= 2);
const beforeResize = first.canvasDefs[0].surface.redraws;
hooks.onResized(first, { width: 400, height: 500 });
assert.equal(first.canvasDefs[0].surface.redraws, beforeResize + 1);

// Removal unsubscribes every widget listener and is idempotent.
assert.ok([...first._widgets.values()].some((widget) => widget.listeners.size));
hooks.onRemoved(first);
assert.ok([...first._widgets.values()].every((widget) => widget.listeners.size === 0));
hooks.onRemoved(first);
first._widgets.get("x").setValue(0.9);
assert.equal(first.getProperty("area_values")[1][0], 0.25);

console.log("PASS: Visual Area dynamic slots, local canvas, persistence, isolation, and teardown");
