import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|innerHTML|addDOMWidget/,
  /prototype\./,
]) assert.doesNotMatch(source, forbidden);

class Context {
  constructor() {
    this.strokes = 0;
    this.lines = [];
  }
  clearRect() {}
  setLineDash() {}
  beginPath() { this.lines.push([]); }
  moveTo(x, y) { this.lines.at(-1).push(["M", x, y]); }
  lineTo(x, y) { this.lines.at(-1).push(["L", x, y]); }
  stroke() { this.strokes += 1; }
  strokeRect() { this.strokes += 1; }
}

class Element {
  constructor(tag, owner) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = owner;
    this.children = [];
    this.attributes = new Map();
    this.style = {};
    this.clientWidth = 320;
    if (tag === "canvas") {
      this.width = 0;
      this.height = 0;
      this.context = new Context();
    }
  }
  replaceChildren(...items) { this.children = [...items]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getContext(kind) {
    assert.equal(kind, "2d");
    return this.context;
  }
}

const ownerDocument = {
  createElement(tag) { return new Element(tag, ownerDocument); },
};

class Widget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.listeners = new Set();
  }
  getValue() { return this.value; }
  setValue(value) {
    const old = this.value;
    this.value = value;
    for (const listener of [...this.listeners]) listener(value, old);
  }
  on(event, listener) {
    assert.equal(event, "change");
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

let extension;
const comfy = { defs: { extend(selector, callback) {
  const hooks = {};
  callback({
    onCreated(fn) { hooks.created = fn; },
    onResized(fn) { hooks.resized = fn; },
    onRemoved(fn) { hooks.removed = fn; },
  });
  extension = { selector, hooks };
} } };

const context = vm.createContext({ console, Math, Number });
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

assert.deepEqual([...extension.selector], ["Bleach Bypass", "RGB Curve"]);
const api = module.namespace;
assert.equal(api.normalizedTanh(0, 4, 0.5), 0);
assert.equal(api.normalizedTanh(1, 4, 0.5), 1);
assert.ok(Math.abs(api.normalizedTanh(0.5, 4, 0.5) - 0.5) < 1e-12);

function makeNode(slopeValue, offsetValue) {
  const controls = new Map([
    ["slope", new Widget("slope", slopeValue)],
    ["shadow_offset", new Widget("shadow_offset", offsetValue)],
  ]);
  let mountDef;
  let mountCount = 0;
  const node = {
    widgets: {
      get(name) { return controls.get(name); },
      mount(def) {
        mountDef = def;
        mountCount += 1;
        controls.set(def.name, new Widget(def.name));
      },
    },
    setSizeConstraints(value) { this.constraints = value; },
  };
  return {
    node,
    controls,
    get mountDef() { return mountDef; },
    get mountCount() { return mountCount; },
  };
}

const first = makeNode(4, 0.5);
extension.hooks.created(first.node);
extension.hooks.created(first.node);
assert.equal(first.mountCount, 1);
assert.equal(
  JSON.stringify(first.node.constraints),
  JSON.stringify({ minWidth: 280, minHeight: 350 }),
);
assert.equal(first.mountDef.height, 230);
assert.equal(first.mountDef.serialize, false);
assert.equal(first.mountDef.sendToPrompt, false);

const container = new Element("div", ownerDocument);
first.mountDef.render(container);
const canvas = container.children[0];
assert.equal(canvas.tagName, "CANVAS");
assert.equal(canvas.attributes.get("aria-label"), "RGB curve preview");
assert.equal(canvas.width, 320);
assert.equal(canvas.height, 220);
assert.equal(first.controls.get("slope").listeners.size, 1);
assert.equal(first.controls.get("shadow_offset").listeners.size, 1);
const initialStrokes = canvas.context.strokes;
first.controls.get("slope").setValue(8);
assert.ok(canvas.context.strokes > initialStrokes);
const curve = canvas.context.lines.at(-1);
assert.equal(curve.length, 100);
assert.deepEqual(curve[0], ["M", 0, 220]);
assert.ok(Math.abs(curve.at(-1)[1] - 320) < 1e-9);
assert.ok(Math.abs(curve.at(-1)[2]) < 1e-9);

container.clientWidth = 480;
extension.hooks.resized(first.node);
assert.equal(canvas.width, 480);

const second = makeNode(2, 0.25);
extension.hooks.created(second.node);
const secondContainer = new Element("div", ownerDocument);
second.mountDef.render(secondContainer);
const secondStrokes = secondContainer.children[0].context.strokes;
first.controls.get("shadow_offset").setValue(0.75);
assert.equal(secondContainer.children[0].context.strokes, secondStrokes,
  "nodes remain isolated");

first.mountDef.destroy();
extension.hooks.removed(first.node);
assert.equal(container.children.length, 0);
assert.equal(first.controls.get("slope").listeners.size, 0);
assert.equal(first.controls.get("shadow_offset").listeners.size, 0);
extension.hooks.removed(first.node);

second.mountDef.destroy();
extension.hooks.removed(second.node);
assert.equal(second.controls.get("slope").listeners.size, 0);

console.log("PASS: secure M3D curve preview behavior, isolation, and teardown");
