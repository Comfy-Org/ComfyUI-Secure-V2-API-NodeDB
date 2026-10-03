import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath, pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const mainSource = fs.readFileSync(entry, "utf8");
const viewerSource = fs.readFileSync(path.join(path.dirname(entry), "compare_viewer.js"), "utf8");
const combined = `${mainSource}\n${viewerSource}`;
for (const forbidden of [
  /\/scripts\/app\.js/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|data:image|FileReader|innerHTML/,
]) assert.doesNotMatch(combined, forbidden);
assert.match(mainSource, /getOutputImages\(\)/);
assert.match(mainSource, /widgets\.mount\(/);

class FakeContext {
  constructor() { this.calls = []; this.clearCount = 0; }
  record(name, ...args) { this.calls.push([name, ...args]); }
  setTransform(...args) { this.record("setTransform", ...args); }
  clearRect(...args) { this.clearCount += 1; this.record("clearRect", ...args); }
  fillRect(...args) { this.record("fillRect", ...args); }
  fillText(...args) { this.record("fillText", ...args); }
  drawImage(image, ...args) { this.record("drawImage", image.src, ...args); }
  save() { this.record("save"); } restore() { this.record("restore"); }
  beginPath() { this.record("beginPath"); } rect(...args) { this.record("rect", ...args); }
  clip() { this.record("clip"); } moveTo(...args) { this.record("moveTo", ...args); }
  lineTo(...args) { this.record("lineTo", ...args); } stroke() { this.record("stroke"); }
  arc(...args) { this.record("arc", ...args); } fill() { this.record("fill"); }
}

const dimensions = new Map([
  ["/view/old-a.png", [640, 480]], ["/view/old-b.png", [800, 400]],
  ["/view/new-a.png", [1000, 500]], ["/view/new-b.png", [500, 1000]],
]);
const createdImages = [];
class Element {
  constructor(tag, owner) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = owner;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.style = {};
    this.clientWidth = 400;
    this.clientHeight = 300;
    this.naturalWidth = 0;
    this.naturalHeight = 0;
    if (tag === "canvas") this.context = new FakeContext();
    if (tag === "img") createdImages.push(this);
  }
  append(...items) { this.children.push(...items); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); if (name === "src") this._src = ""; }
  addEventListener(name, listener) {
    const values = this.listeners.get(name) || [];
    values.push(listener);
    this.listeners.set(name, values);
  }
  removeEventListener(name, listener) {
    this.listeners.set(name, (this.listeners.get(name) || []).filter((item) => item !== listener));
  }
  dispatch(name, extra = {}) {
    const event = { clientX: 0, clientY: 0, pointerId: 1,
      preventDefault() { this.prevented = true; }, ...extra };
    for (const listener of this.listeners.get(name) || []) listener(event);
    return event;
  }
  getContext(name) { assert.equal(name, "2d"); return this.context; }
  getBoundingClientRect() { return { left: 10, top: 20, width: this.clientWidth, height: this.clientHeight }; }
  setPointerCapture() {} releasePointerCapture() {}
  set src(value) { this._src = value; }
  get src() { return this._src || ""; }
  triggerLoad() {
    [this.naturalWidth, this.naturalHeight] = dimensions.get(this.src) || [0, 0];
    this.width = this.naturalWidth;
    this.height = this.naturalHeight;
    this.onload?.();
  }
}
const ownerDocument = {
  defaultView: { devicePixelRatio: 2 },
  createElement(tag) { return new Element(tag, ownerDocument); },
};

let extension;
const comfy = { defs: { extend(selector, callback) {
  const hooks = {};
  callback({
    onCreated(fn) { hooks.created = fn; }, onExecuted(fn) { hooks.executed = fn; },
    onResized(fn) { hooks.resized = fn; }, onRemoved(fn) { hooks.removed = fn; },
  });
  extension = { selector, hooks };
} } };

const context = vm.createContext({ console, Math, Number });
const modules = new Map();
async function load(filename) {
  const absolute = path.resolve(filename);
  if (modules.has(absolute)) return modules.get(absolute);
  const module = new vm.SourceTextModule(fs.readFileSync(absolute, "utf8"), {
    context, identifier: pathToFileURL(absolute).href,
  });
  modules.set(absolute, module);
  await module.link(async (specifier, referencing) => {
    if (specifier === "/comfy/api/v2.js") {
      const stub = new vm.SyntheticModule(["comfy"], function () { this.setExport("comfy", comfy); }, { context });
      await stub.link(() => {});
      return stub;
    }
    return load(path.resolve(path.dirname(fileURLToPath(referencing.identifier)), specifier));
  });
  return module;
}

await (await load(entry)).evaluate();
const viewerModule = modules.get(path.resolve(path.dirname(entry), "compare_viewer.js")).namespace;
assert.equal(JSON.stringify(viewerModule.fitContain(800, 400, 300, 300)),
  JSON.stringify({ x: 0, y: 75, width: 300, height: 150 }));
assert.equal(JSON.stringify(viewerModule.fitContain(400, 800, 300, 200)),
  JSON.stringify({ x: 100, y: 0, width: 100, height: 200 }));
assert.equal(viewerModule.sliderFromPointer(-50, 10, 400), 0);
assert.equal(viewerModule.sliderFromPointer(500, 10, 400), 1);
assert.equal(viewerModule.sliderFromPointer(210, 10, 400), 0.5);
assert.equal(extension.selector, "ImageCompareNode");

let outputImages = ["/view/old-a.png", "/view/old-b.png"];
let mountDef;
let mountCount = 0;
const node = {
  widgets: {
    get(name) { return name === "image_compare" && mountDef ? {} : undefined; },
    mount(def) { mountCount += 1; mountDef = def; return {}; },
  },
  setSizeConstraints(value) { this.constraints = value; },
  getOutputImages() { return outputImages; },
};
extension.hooks.created(node);
extension.hooks.created(node);
assert.equal(mountCount, 1, "re-adding a node cannot duplicate the mounted comparer");
assert.equal(JSON.stringify(node.constraints), JSON.stringify({ minWidth: 360, minHeight: 400 }));
assert.equal(mountDef.height, 330);
assert.equal(mountDef.serialize, false);
assert.equal(mountDef.sendToPrompt, false);

const container = new Element("div", ownerDocument);
mountDef.render(container);
const canvas = container.children[0];
assert.deepEqual([canvas.width, canvas.height], [800, 600]);
extension.hooks.executed(node);
const oldImages = createdImages.slice(-2);
const staleLoad = oldImages[0].onload;
assert.deepEqual(oldImages.map((item) => item.src), outputImages);

outputImages = ["/view/new-a.png", "/view/new-b.png"];
const beforeReplace = canvas.context.clearCount;
extension.hooks.executed(node);
const newImages = createdImages.slice(-2);
assert.equal(oldImages.every((item) => item.src === ""), true);
assert.ok(canvas.context.clearCount > beforeReplace, "replacement clears stale pixels immediately");
const beforeStale = canvas.context.clearCount;
staleLoad();
assert.equal(canvas.context.clearCount, beforeStale, "late old image load cannot redraw");
newImages[0].triggerLoad();
newImages[1].triggerLoad();
const drawOrder = canvas.context.calls.filter(([name]) => name === "drawImage").slice(-2).map((call) => call[1]);
assert.deepEqual(drawOrder, ["/view/new-b.png", "/view/new-a.png"]);
assert.ok(canvas.context.calls.some((call) => call[0] === "fillText" && call[1] === "1000x500"));
assert.ok(canvas.context.calls.some((call) => call[0] === "fillText" && call[1] === "500x1000"));

const down = canvas.dispatch("pointerdown", { clientX: -100 });
assert.equal(down.prevented, true);
canvas.dispatch("pointermove", { clientX: 1000 });
canvas.dispatch("pointerup", { clientX: 1000 });
assert.ok(canvas.context.calls.some((call) => call[0] === "lineTo" && call[1] === 390));

container.clientWidth = 600;
container.clientHeight = 240;
extension.hooks.resized(node);
assert.deepEqual([canvas.width, canvas.height], [1200, 480]);
const lastNewB = canvas.context.calls.filter((call) => call[0] === "drawImage" && call[1] === "/view/new-b.png").at(-1);
assert.deepEqual(lastNewB.slice(2), [245, 10, 110, 220]);

outputImages = [];
extension.hooks.executed(node);
assert.equal(newImages.every((item) => item.src === ""), true);
assert.ok(canvas.context.calls.some((call) => call[0] === "fillText" && call[1] === "Run the node to compare two images"));

mountDef.destroy();
extension.hooks.removed(node);
assert.deepEqual([canvas.width, canvas.height], [0, 0]);
assert.equal([...canvas.listeners.values()].flat().length, 0);

console.log("PASS: secure image comparer ordering, geometry, replacement races, resize, and teardown");
