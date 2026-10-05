import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|\/scripts\/api\.js/,
  /LiteGraph|app\.graph|app\.canvas/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|innerHTML/,
]) assert.doesNotMatch(source, forbidden);


class FakeWidget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.listeners = new Map();
  }
  getValue() { return this.value; }
  setValue(value) { this.value = value; }
  on(event, listener) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(listener);
    return () => this.listeners.get(event)?.delete(listener);
  }
  emit(event, value) {
    this.value = value;
    for (const listener of [...(this.listeners.get(event) || [])]) listener(value);
  }
  listenerCount(event) { return this.listeners.get(event)?.size || 0; }
}


class FakeSlot {
  constructor(name, type) {
    this.name = name;
    this.type = type;
  }
  modify(options) { Object.assign(this, options); }
}


class FakeOutputs {
  constructor(count = 10) {
    this.items = Array.from({ length: count }, (_, index) =>
      new FakeSlot(String(index + 1), "FLOAT"));
  }
  get length() { return this.items.length; }
  add(name, type) {
    const slot = new FakeSlot(name, type);
    this.items.push(slot);
    return slot;
  }
  remove({ index }) { this.items.splice(index, 1); }
  all() { return this.items; }
}


class FakeCanvas {
  constructor() {
    this.width = 0;
    this.height = 0;
    this.style = {};
    this.listeners = new Map();
    this.captured = new Set();
    const noop = () => {};
    this.context = {
      clearRect: noop, fillRect: noop, beginPath: noop, arc: noop,
      setLineDash: noop, stroke: noop, fillText: noop, moveTo: noop,
      lineTo: noop, closePath: noop, fill: noop,
    };
  }
  getContext(kind) { return kind === "2d" ? this.context : null; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 500, height: 500 }; }
  addEventListener(name, listener) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name).add(listener);
  }
  removeEventListener(name, listener) { this.listeners.get(name)?.delete(listener); }
  listenerCount() {
    return [...this.listeners.values()].reduce((total, items) => total + items.size, 0);
  }
  dispatch(name, options = {}) {
    const event = {
      clientX: 0, clientY: 0, pointerId: 1, prevented: false,
      preventDefault() { this.prevented = true; },
      ...options,
    };
    for (const listener of [...(this.listeners.get(name) || [])]) listener(event);
    return event;
  }
  setPointerCapture(pointerId) { this.captured.add(pointerId); }
  releasePointerCapture(pointerId) { this.captured.delete(pointerId); }
}


class FakeContainer {
  constructor() {
    this.style = {};
    this.children = [];
    this.ownerDocument = { createElement: (tag) => {
      assert.equal(tag, "canvas");
      return new FakeCanvas();
    } };
  }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; }
}


class FakeNode {
  constructor(id, axes = 5, weights = "") {
    this.id = id;
    this.graphId = undefined;
    this.map = new Map([
      ["axes_count", new FakeWidget("axes_count", axes)],
      ["_weights_sync", new FakeWidget("_weights_sync", weights)],
    ]);
    this.outputs = new FakeOutputs();
    this.mounts = [];
    this.widgets = {
      get: (name) => this.map.get(name),
      mount: (spec) => { this.mounts.push(spec); return spec; },
    };
  }
  setSizeConstraints(value) { this.sizeConstraints = value; }
  setSize(value) { this.size = value; }
}


const definitions = new Map();
const comfy = {
  defs: {
    extend(selector, configure) {
      const hooks = { hidden: [] };
      configure({
        hideWidget(name) { hooks.hidden.push(name); },
        onCreated(callback) { hooks.created = callback; },
        onConfigured(callback) { hooks.configured = callback; },
        onRemoved(callback) { hooks.removed = callback; },
      });
      definitions.set(selector, hooks);
    },
  },
};


const context = vm.createContext({
  console, Promise, Math, Number, Object, String, Array, Set, Map, WeakMap,
});
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


assert.equal(module.namespace.clampAxes(2), 3);
assert.equal(module.namespace.clampAxes(11), 10);
assert.equal(module.namespace.clampAxes("bad"), 5);
assert.deepEqual(Array.from(module.namespace.parseWeights("0,0.25,1.5,2", 4)),
  [0, 0.25, 1.5, 2]);
assert.deepEqual(Array.from(module.namespace.parseWeights("bad", 4)), [1, 1, 1, 1]);
assert.deepEqual(Array.from(module.namespace.parseWeights("-1,1,1", 3)), [1, 1, 1]);
assert.deepEqual(Array.from(module.namespace.parseWeights("1,".repeat(200), 3)), [1, 1, 1]);
assert.equal(module.namespace.formatWeights([0, 0.256, 2]), "0.00,0.26,2.00");
assert.equal(module.namespace.projectedWeight(0, 5, 250, 250), 0);
assert.equal(module.namespace.projectedWeight(0, 5, 250, -100), 2);

const hooks = definitions.get("RadarWeightsNode");
assert.ok(hooks, "the exact Python node id is extended");
assert.deepEqual(hooks.hidden, ["_weights_sync"]);

const first = new FakeNode("same-id", 5, "0.25,0.50,0.75,1.00,1.25");
const second = new FakeNode("same-id", 3, "2,1,0.5");
first.graphId = "graph-a";
second.graphId = "graph-b";
hooks.created(first);
hooks.created(second);

assert.equal(first.outputs.length, 5);
assert.deepEqual(first.outputs.all().map((slot) => slot.name), ["1", "2", "3", "4", "5"]);
assert.notDeepEqual(first.outputs.all()[0].position, first.outputs.all()[1].position);
assert.equal(first.map.get("_weights_sync").getValue(), "0.25,0.50,0.75,1.00,1.25");
assert.equal(second.map.get("_weights_sync").getValue(), "2.00,1.00,0.50");
assert.equal(first.size.width, 540);
assert.equal(first.size.height, 570);
assert.equal(first.map.get("axes_count").listenerCount("change"), 1);

const firstContainer = new FakeContainer();
first.mounts[0].render(firstContainer);
const firstCanvas = firstContainer.children[0];
assert.equal(firstCanvas.listenerCount(), 5);

// First point is initially weight 0.25: y = 250 - 28.75.
const down = firstCanvas.dispatch("pointerdown", { clientX: 250, clientY: 221.25 });
assert.equal(down.prevented, true);
firstCanvas.dispatch("pointermove", { clientX: 250, clientY: 250 });
firstCanvas.dispatch("pointerup", { clientX: 250, clientY: 250 });
assert.equal(first.map.get("_weights_sync").getValue(), "0.00,0.50,0.75,1.00,1.25");
assert.equal(second.map.get("_weights_sync").getValue(), "2.00,1.00,0.50",
  "same ids in different graphs retain independent serialized state");

first.map.get("axes_count").emit("change", 3);
assert.equal(first.outputs.length, 3);
assert.equal(first.map.get("_weights_sync").getValue(), "0.00,0.50,0.75");
first.map.get("axes_count").emit("change", 5);
assert.equal(first.outputs.length, 5);
assert.equal(first.map.get("_weights_sync").getValue(), "0.00,0.50,0.75,1.00,1.25",
  "shrink/regrow restores the remembered radar points");

first.map.get("_weights_sync").setValue("1.11,1.22,1.33,1.44,1.55");
hooks.configured(first);
assert.equal(first.map.get("_weights_sync").getValue(), "1.11,1.22,1.33,1.44,1.55");
first.map.get("_weights_sync").setValue("malformed");
hooks.configured(first);
assert.equal(first.map.get("_weights_sync").getValue(), "1.00,1.00,1.00,1.00,1.00",
  "malformed serialized state fails closed to upstream defaults");

first.mounts[0].destroy();
assert.equal(firstCanvas.listenerCount(), 0);
assert.equal(firstContainer.children.length, 0);
hooks.removed(first);
assert.equal(first.map.get("axes_count").listenerCount("change"), 0);
first.map.get("axes_count").emit("change", 8);
assert.equal(first.outputs.length, 5, "removed nodes cannot mutate after teardown");

const secondContainer = new FakeContainer();
second.mounts[0].render(secondContainer);
assert.equal(secondContainer.children[0].listenerCount(), 5,
  "tearing down one graph does not disturb another graph");
hooks.removed(second);
assert.equal(secondContainer.children.length, 0);
assert.equal(second.map.get("axes_count").listenerCount("change"), 0);

console.log("PASS: secure RadarWeight mounted lifecycle, geometry, state, isolation, and cleanup");
