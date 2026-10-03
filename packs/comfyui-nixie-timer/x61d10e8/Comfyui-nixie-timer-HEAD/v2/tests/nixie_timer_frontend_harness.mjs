import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const sourcePath = new URL("../web/nixie_timer.js", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8").replace(
  'import { comfy } from "/comfy/api/v2.js";',
  "const comfy = globalThis.__comfy;",
);

class ClassList {
  constructor(element) {
    this.element = element;
    this.values = new Set();
  }
  add(...names) { for (const name of names) this.values.add(name); }
  remove(...names) { for (const name of names) this.values.delete(name); }
  contains(name) { return this.values.has(name); }
}

class TextNode {
  constructor(text, document) { this.textContent = text; this.ownerDocument = document; }
}

class Element {
  constructor(tagName, document, fragment = false) {
    this.tagName = tagName;
    this.ownerDocument = document;
    this.fragment = fragment;
    this.children = [];
    this.dataset = {};
    this.style = {};
    this.classList = new ClassList(this);
    this._className = "";
    this._textContent = "";
  }
  set className(value) {
    this._className = value;
    this.classList.values = new Set(String(value).split(/\s+/).filter(Boolean));
  }
  get className() { return this._className; }
  set textContent(value) { this._textContent = String(value); this.children = []; }
  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent ?? "").join("");
  }
  append(...items) {
    for (const item of items) {
      if (item?.fragment) this.children.push(...item.children);
      else this.children.push(item);
    }
  }
  replaceChildren(...items) {
    this.children = [];
    this._textContent = "";
    this.append(...items);
  }
}

class MockDocument {
  createElement(name) { return new Element(name, this); }
  createDocumentFragment() { return new Element("fragment", this, true); }
  createTextNode(text) { return new TextNode(text, this); }
}

function emitter() {
  const listeners = new Set();
  return {
    add(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    invoke(value) {
      let result;
      for (const listener of [...listeners]) result = listener(value);
      return result;
    },
    emit(value) { this.invoke(value); },
    get size() { return listeners.size; },
  };
}

const callbacks = {};
const queueEvents = {
  before: emitter(), after: emitter(), rejected: emitter(), pending: emitter(), interrupted: emitter(),
};
const backendEvents = new Map();
const localeEvents = emitter();
let localeValue = "en-US";
let pending = 0;

const comfy = {
  defs: {
    extend(type, configure) {
      assert.equal(type, "NixieTimer");
      const builder = {
        onCreated(fn) { callbacks.created = fn; },
        onConfigured(fn) { callbacks.configured = fn; },
        onResized(fn) { callbacks.resized = fn; },
        onRemoved(fn) { callbacks.removed = fn; },
      };
      configure(builder);
    },
  },
  queue: {
    pending: () => pending,
    onBeforeRun: (fn) => queueEvents.before.add(fn),
    onAfterRun: (fn) => queueEvents.after.add(fn),
    onRejected: (fn) => queueEvents.rejected.add(fn),
    onPendingChanged: (fn) => queueEvents.pending.add(fn),
    onInterrupted: (fn) => queueEvents.interrupted.add(fn),
  },
  backend: {
    on(name, listener) {
      if (!backendEvents.has(name)) backendEvents.set(name, emitter());
      return backendEvents.get(name).add(listener);
    },
  },
  settings: {
    get(id) { assert.equal(id, "Comfy.Locale"); return localeValue; },
    onChange(id, listener) { assert.equal(id, "Comfy.Locale"); return localeEvents.add(listener); },
  },
};

const intervals = new Map();
const frames = new Map();
const cancelledFrames = [];
let nextTimer = 1;
let now = 1000;
const context = vm.createContext({
  __comfy: comfy,
  Date,
  Map,
  Set,
  Math,
  Number,
  Object,
  String,
  Promise,
  console,
  queueMicrotask,
  performance: { now: () => now },
  setInterval(callback, delay) {
    assert.equal(delay, 100);
    const id = nextTimer++;
    intervals.set(id, callback);
    return id;
  },
  clearInterval(id) { intervals.delete(id); },
  requestAnimationFrame(callback) {
    const id = nextTimer++;
    frames.set(id, callback);
    return id;
  },
  cancelAnimationFrame(id) { cancelledFrames.push(id); frames.delete(id); },
});
new vm.Script(source, { filename: sourcePath.pathname }).runInContext(context);

assert.deepEqual(Object.keys(callbacks).sort(), ["configured", "created", "removed", "resized"]);

const document = new MockDocument();
function makeNode(id, color = "红色") {
  const colorEvents = emitter();
  let value = color;
  const colorWidget = {
    getValue: () => value,
    on(name, listener) { assert.equal(name, "change"); return colorEvents.add(listener); },
    set(next) { value = next; colorEvents.emit(); },
    get listeners() { return colorEvents.size; },
  };
  const mounts = [];
  const node = {
    id,
    graphId: "root",
    constraints: undefined,
    getSize: () => ({ width: 320, height: 140 }),
    setSizeConstraints(value_) { this.constraints = value_; },
    widgets: {
      get(name) { return name === "tube_color" ? colorWidget : undefined; },
      mount(definition) {
        const container = document.createElement("div");
        const handle = {
          definition,
          container,
          heights: [],
          setHeight(height) { this.heights.push(height); },
        };
        mounts.push(handle);
        definition.render(container);
        return handle;
      },
    },
  };
  node.colorWidget = colorWidget;
  node.mounts = mounts;
  return node;
}

function flushFrames() {
  const pendingFrames = [...frames.values()];
  frames.clear();
  for (const callback of pendingFrames) callback(now);
}

function timerText(node) {
  const panel = node.mounts[0].container.children[1];
  return panel.children[3].textContent;
}

function panel(node) { return node.mounts[0].container.children[1]; }
function labelText(node) { return [panel(node).children[0].textContent, panel(node).children[2].textContent]; }
function listenerCount() {
  return queueEvents.before.size + queueEvents.after.size + queueEvents.rejected.size +
    queueEvents.pending.size + queueEvents.interrupted.size + localeEvents.size +
    (backendEvents.get("execution_error")?.size ?? 0);
}

const first = makeNode("1", "绿色");
const second = makeNode("2", "紫色");
callbacks.created(first);
callbacks.created(second);
flushFrames();
assert.equal(first.constraints.minWidth, 180);
assert.equal(first.constraints.autoHeight, true);
assert.equal(first.mounts.length, 1);
assert.equal(second.mounts.length, 1);
assert.equal(panel(first).dataset.theme, "green");
assert.equal(panel(second).dataset.theme, "purple");
assert.deepEqual(labelText(first), ["World Clock", "Inference Time"]);
assert.equal(intervals.size, 1, "all instances share one tick interval");
assert.equal(listenerCount(), 7, "all instances share one observer set");
assert.equal(first.colorWidget.listeners, 1);
assert.equal(second.colorWidget.listeners, 1);

localeValue = "de-DE";
localeEvents.emit(localeValue);
assert.deepEqual(labelText(first), ["Weltuhr", "Inferenzzeit"]);
localeValue = "xx-YY";
localeEvents.emit(localeValue);
assert.deepEqual(labelText(second), ["World Clock", "Inference Time"], "unknown locale falls back to English");

assert.equal(queueEvents.before.size, 1);

// Queue lifecycle: both instances render the same retained elapsed time.
const cleanupAccepted = queueEvents.before.invoke();
assert.equal(panel(first).classList.contains("paused"), false);
now = 4600;
for (const tick of intervals.values()) tick();
assert.equal(timerText(first), "00:00:03");
assert.equal(timerText(second), timerText(first));
pending = 1;
queueEvents.after.emit({ promptIds: ["prompt-1"], submissions: [], rejected: 0 });
queueEvents.pending.emit(1);
cleanupAccepted?.();
await Promise.resolve();
assert.equal(panel(first).classList.contains("paused"), false, "accepted run survives submit cleanup");
now = 6800;
pending = 0;
queueEvents.pending.emit(0);
assert.equal(timerText(first), "00:00:05");
assert.equal(timerText(second), "00:00:05");
assert.equal(panel(first).classList.contains("paused"), true);

now = 7000;
queueEvents.before.invoke();
now = 7350;
queueEvents.rejected.emit({});
assert.equal(panel(first).classList.contains("paused"), true, "rejection stops timer");

now = 8000;
queueEvents.before.invoke();
now = 8500;
queueEvents.interrupted.emit();
assert.equal(panel(first).classList.contains("paused"), true, "interruption stops timer");

now = 9000;
queueEvents.before.invoke();
now = 9600;
backendEvents.get("execution_error").emit({ node_id: "elsewhere" });
assert.equal(panel(first).classList.contains("paused"), true, "execution error stops timer");

now = 10000;
const cleanupRejectedTransport = queueEvents.before.invoke();
cleanupRejectedTransport?.();
await Promise.resolve();
assert.equal(panel(first).classList.contains("paused"), true, "failed submission cleanup stops timer");

first.colorWidget.set("白色");
assert.equal(panel(first).dataset.theme, "white");
callbacks.resized(first, { width: 500, height: 140 });
callbacks.resized(first, { width: 640, height: 140 });
assert.ok(cancelledFrames.length > 0, "superseded resize frame is cancelled");
flushFrames();
assert.equal(panel(first).style.transform, "scale(2)");
assert.equal(first.mounts[0].heights.at(-1), 208);

callbacks.removed(first);
assert.equal(intervals.size, 1, "shared lifecycle remains for the other instance");
assert.equal(first.colorWidget.listeners, 0);
callbacks.removed(first);
callbacks.removed(second);
assert.equal(intervals.size, 0);
assert.equal(listenerCount(), 0, "last removal unsubscribes every shared observer");
assert.equal(second.colorWidget.listeners, 0);

const third = makeNode("3", "青色");
callbacks.created(third);
flushFrames();
assert.equal(intervals.size, 1);
assert.equal(listenerCount(), 7, "remount does not duplicate handlers");
third.mounts[0].definition.destroy();
callbacks.removed(third);
assert.equal(intervals.size, 0);
assert.equal(listenerCount(), 0);
assert.equal(frames.size, 0);

console.log("nixie timer frontend behavior/security tests passed");
