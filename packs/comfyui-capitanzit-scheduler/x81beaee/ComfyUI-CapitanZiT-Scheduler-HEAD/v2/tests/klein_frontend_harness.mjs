import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error("frontend source path is required");

const definitions = new Map();
const comfy = {
  defs: {
    extend(name, callback) {
      const hooks = {};
      callback({
        onCreated(handler) { hooks.created = handler; },
        onConfigured(handler) { hooks.configured = handler; },
        onRemoved(handler) { hooks.removed = handler; },
      });
      definitions.set(name, hooks);
    },
  },
};

const context = vm.createContext({ console });
const frontend = new vm.SourceTextModule(fs.readFileSync(sourcePath, "utf8"), {
  context,
  identifier: sourcePath,
});
await frontend.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  const api = new vm.SyntheticModule(["comfy"], function initialize() {
    this.setExport("comfy", comfy);
  }, { context });
  await api.link(() => {});
  await api.evaluate();
  return api;
});
await frontend.evaluate();

assert.deepEqual([...definitions.keys()], ["FlowMatchSchedulerKleinEdit"]);
const hooks = definitions.get("FlowMatchSchedulerKleinEdit");

function makeContext() {
  const gradient = { addColorStop() {} };
  return {
    beginPath() {}, moveTo() {}, lineTo() {}, quadraticCurveTo() {}, closePath() {},
    clearRect() {}, fill() {}, stroke() {}, arc() {}, fillText() {},
    createLinearGradient() { return gradient; },
    createRadialGradient() { return gradient; },
    setLineDash() {}, save() {}, restore() {}, translate() {}, rotate() {},
    fillStyle: "", strokeStyle: "", lineWidth: 1, font: "", textAlign: "left",
  };
}

class Widget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.hidden = false;
    this.listeners = new Set();
    this.unsubscribeCount = 0;
    this.history = [];
  }
  getValue() { return this.value; }
  setValue(value) {
    if (Object.is(value, this.value)) return;
    const old = this.value;
    this.value = value;
    this.history.push(value);
    for (const listener of [...this.listeners]) listener(value, old);
  }
  setHidden(hidden) { this.hidden = hidden; }
  on(event, listener) {
    assert.equal(event, "change");
    this.listeners.add(listener);
    return () => {
      if (this.listeners.delete(listener)) this.unsubscribeCount += 1;
    };
  }
}

function makeNode(id, overrides = {}) {
  const values = {
    steps: 4,
    denoise: 1,
    sigma_min: 0,
    shift: 1,
    curve: 1,
    draw_mode: "parametric",
    custom_sigmas: "[]",
    ...overrides,
  };
  const widgets = new Map(Object.entries(values).map(([name, value]) => [name, new Widget(name, value)]));
  const surfaces = new Map();
  const node = {
    id,
    constraints: undefined,
    widgets: {
      get(name) { return widgets.get(name); },
      canvas(definition) {
        const surface = {
          definition,
          redrawCount: 0,
          redraw() { this.redrawCount += 1; },
          widget: new Widget(definition.name, undefined),
        };
        surfaces.set(definition.name, surface);
        return surface;
      },
    },
    setSizeConstraints(value) { this.constraints = value; },
    widgetMap: widgets,
    surfaces,
  };
  hooks.created(node);
  return node;
}

const theme = {
  surface: "#111", surfaceHovered: "#222", border: "#333",
  text: "#eee", textSecondary: "#aaa",
};
const pointer = (x, y, detail = 1) => ({
  x, y,
  event: {
    detail,
    defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true; },
  },
});
const draw = (node) => {
  const surface = node.surfaces.get("klein_graph");
  surface.definition.draw(makeContext(), [320, 326], theme, undefined);
  return surface;
};

// Pure math exposed by the frontend agrees with the upstream controls.
assert.deepEqual(Array.from(frontend.namespace.computeSigmas(4, 1, 0, 1, 1)), [1, 0.75, 0.5, 0.25, 0]);
assert.deepEqual(
  JSON.parse(JSON.stringify(frontend.namespace.xyValues(10, 308, { x: 10, y: 188, width: 300, height: 120 }))),
  { curve: 0.01, shift: 0.01 },
);

const first = makeNode("one");
const surface = draw(first);
assert.equal(surface.definition.height, 326);
assert.equal(surface.definition.serialize, false);
assert.equal(surface.definition.sendToPrompt, false);
assert.deepEqual(JSON.parse(JSON.stringify(first.constraints)), { minWidth: 300, minHeight: 326 });
assert.equal(first.widgetMap.get("draw_mode").hidden, true);
assert.equal(first.widgetMap.get("custom_sigmas").hidden, false);

// XY pad updates both values, remains captured outside its bounds, and clamps.
surface.definition.onPointerDown(pointer(10, 308));
assert.equal(first.widgetMap.get("curve").value, 0.01);
assert.equal(first.widgetMap.get("shift").value, 0.01);
surface.definition.onPointerMove(pointer(500, 0));
assert.equal(first.widgetMap.get("curve").value, 10);
assert.equal(first.widgetMap.get("shift").value, 20);
surface.definition.onPointerUp(pointer(500, 0));

// Toggle seeds the exact schedule and serializes it through the original widgets.
first.widgetMap.get("curve").setValue(1);
first.widgetMap.get("shift").setValue(1);
surface.definition.onPointerDown(pointer(160, 20));
assert.equal(first.widgetMap.get("draw_mode").value, "draw");
assert.equal(first.widgetMap.get("custom_sigmas").value, "[1,0.75,0.5,0.25,0]");
draw(first);

// Edge drag changes denoise and the saved first sigma; middle drag changes a value.
let state = frontend.namespace.__testing.editors.get("one");
let firstDot = state.screenDots[0];
surface.definition.onPointerDown(pointer(firstDot.x, firstDot.y));
surface.definition.onPointerMove(pointer(firstDot.x, 108));
surface.definition.onPointerUp(pointer(firstDot.x, 108));
assert.equal(first.widgetMap.get("denoise").value, 0.5);
assert.equal(JSON.parse(first.widgetMap.get("custom_sigmas").value)[0], 0.5);
draw(first);
state = frontend.namespace.__testing.editors.get("one");
const middle = state.screenDots[2];
surface.definition.onPointerDown(pointer(middle.x, middle.y));
surface.definition.onPointerMove(pointer(120, 80));
surface.definition.onPointerUp(pointer(120, 80));
assert.notEqual(JSON.parse(first.widgetMap.get("custom_sigmas").value)[2], 0);

// A hand-authored schedule replaces displayed dots and survives configured restore.
first.widgetMap.get("custom_sigmas").setValue("[1.25,0.7,0.2,0.1,0]");
draw(first);
assert.deepEqual(Array.from(
  frontend.namespace.__testing.editors.get("one").dots,
  (dot) => dot.sigma,
), [1.25, 0.7, 0.2, 0.1, 0]);
hooks.configured(first);
assert.deepEqual(Array.from(
  frontend.namespace.__testing.editors.get("one").dots,
  (dot) => dot.sigma,
), [1.25, 0.7, 0.2, 0.1, 0]);
first.widgetMap.get("custom_sigmas").setValue("not-json");
assert.deepEqual(Array.from(
  frontend.namespace.__testing.editors.get("one").dots,
  (dot) => dot.sigma,
), [1.25, 0.7, 0.2, 0.1, 0]);

// Step changes reseed on the next draw, while separate nodes remain isolated.
first.widgetMap.get("steps").setValue(6);
draw(first);
assert.equal(JSON.parse(first.widgetMap.get("custom_sigmas").value).length, 7);
const second = makeNode("two", { draw_mode: "draw", custom_sigmas: "[2,1,0]", steps: 2 });
draw(second);
assert.deepEqual(Array.from(
  frontend.namespace.__testing.editors.get("two").dots,
  (dot) => dot.sigma,
), [2, 1, 0]);

// Removal releases every subscription; remounting gets one clean editor.
const before = surface.redrawCount;
hooks.removed(first);
assert.equal(frontend.namespace.__testing.editors.has("one"), false);
for (const widget of first.widgetMap.values()) assert.equal(widget.listeners.size, 0);
first.widgetMap.get("curve").setValue(2);
assert.equal(surface.redrawCount, before);
const remounted = makeNode("one");
assert.equal(frontend.namespace.__testing.editors.size, 2);
hooks.removed(remounted);
hooks.removed(second);
assert.equal(frontend.namespace.__testing.editors.size, 0);

console.log("PASS: Klein graph math, serialized draw state, pointer geometry, and teardown");
