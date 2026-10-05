import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL, fileURLToPath } from "node:url";

const entry = path.resolve(process.argv[2]);
const webRoot = path.dirname(entry);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|app\.registerExtension|app\.graph|app\.canvas/,
  /(?:^|[^A-Za-z])window\s*\.|(?:^|[^A-Za-z])document\s*\./m,
  /localStorage|sessionStorage|indexedDB|fetch\s*\(|innerHTML/,
  /addEventListener|removeEventListener|XMLHttpRequest|WebSocket/,
]) assert.doesNotMatch(source, forbidden);

const backendListeners = new Map();
const storageWrites = [];
const activeIntervals = new Map();
let intervalSequence = 0;
let overlayDef;
let overlayRemoved = 0;
let actionDef;
let actionRemoved = 0;
let decoded = 0;
const bitmaps = [];
const records = { redraws: 0, regions: [], actionUpdates: [] };

const overlayHandle = {
  redraw() { records.redraws += 1; },
  setInteractive() {},
  setVisible() {},
  setHitRegions(value) { records.regions.push(structuredClone(value)); },
  remove() { overlayRemoved += 1; },
};
const actionHandle = {
  update(value) { records.actionUpdates.push(structuredClone(value)); },
  remove() { actionRemoved += 1; },
};

const nodes = [{ id: "live", type: "LivePreview" }];
const comfy = {
  graph: {
    queryNodes(query) {
      assert.equal(query.scope, "root-and-subgraphs");
      return nodes.filter((node) => node.type === query.type);
    },
  },
  storage: {
    async get(name) {
      assert.equal(name, "live-preview/geometry.json");
      return JSON.stringify({ x: 11, y: 22, width: 420, height: 440 });
    },
    async set(name, value) {
      storageWrites.push([name, JSON.parse(value)]);
    },
  },
  backend: {
    on(event, listener) {
      const listeners = backendListeners.get(event) ?? new Set();
      listeners.add(listener);
      backendListeners.set(event, listeners);
      return () => listeners.delete(listener);
    },
  },
  ui: {
    mountGraphOverlay(definition) {
      overlayDef = definition;
      return overlayHandle;
    },
    addActionBarButton(definition) {
      actionDef = definition;
      return actionHandle;
    },
  },
};

const context = vm.createContext({
  console,
  Blob,
  Promise,
  Math,
  Number,
  Object,
  String,
  Array,
  Set,
  JSON,
  Date,
  TextEncoder,
  structuredClone,
  createImageBitmap: async () => {
    decoded += 1;
    const bitmap = {
      width: 640,
      height: 480,
      closed: 0,
      close() { this.closed += 1; },
    };
    bitmaps.push(bitmap);
    return bitmap;
  },
  setInterval(callback, delay) {
    assert.equal(delay, 1000);
    const id = ++intervalSequence;
    activeIntervals.set(id, callback);
    return id;
  },
  clearInterval(id) { activeIntervals.delete(id); },
});

const moduleCache = new Map();
async function load(identifier) {
  if (moduleCache.has(identifier)) return moduleCache.get(identifier);
  if (identifier === "/comfy/api/v2.js") {
    const stub = new vm.SyntheticModule(["comfy"], function () {
      this.setExport("comfy", comfy);
    }, { context, identifier });
    moduleCache.set(identifier, stub);
    await stub.link(() => {});
    return stub;
  }
  const file = identifier.startsWith("file:")
    ? fileURLToPath(identifier)
    : path.resolve(webRoot, identifier);
  const child = new vm.SourceTextModule(fs.readFileSync(file, "utf8"), {
    context,
    identifier: pathToFileURL(file).href,
  });
  moduleCache.set(identifier, child);
  await child.link(async (specifier, referencing) => {
    if (specifier === "/comfy/api/v2.js") return load(specifier);
    return load(new URL(specifier, referencing.identifier).href);
  });
  return child;
}

const module = await load(pathToFileURL(entry).href);
await module.evaluate();
const live = module.namespace.livePreview;
await live.ready;
const plain = (value) => JSON.parse(JSON.stringify(value));

assert.equal(overlayDef.id, "live-preview.overlay");
assert.equal(overlayDef.interactive, true);
assert.equal(actionDef.id, "live-preview.toggle");
assert.deepEqual([...backendListeners.keys()].sort(), [
  "b_preview", "execution_error", "execution_start", "status",
]);

const drawCalls = [];
const drawing = new Proxy({
  drawImage(...args) { drawCalls.push(args); },
  measureText() { return { width: 1 }; },
}, {
  get(target, property) {
    if (property in target) return target[property];
    return () => {};
  },
  set(target, property, value) { target[property] = value; return true; },
});
overlayDef.draw(drawing, [1000, 800], {});
assert.deepEqual(plain(live.state.geometry), { x: 11, y: 22, width: 420, height: 440 });
assert.deepEqual(records.regions.at(-1), []);

actionDef.run({});
overlayDef.draw(drawing, [1000, 800], {});
assert.equal(live.state.visible, true);
assert.deepEqual(records.regions.at(-1), [
  { kind: "rect", x: 11, y: 22, width: 420, height: 32 },
  { kind: "rect", x: 409, y: 440, width: 22, height: 22 },
]);

function emit(event, detail) {
  for (const listener of backendListeners.get(event) ?? []) listener(detail);
}

emit("execution_start", {});
assert.equal(live.state.status, "active");
assert.equal(activeIntervals.size, 1);
emit("b_preview", new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" }));
await new Promise((resolve) => setImmediate(resolve));
assert.equal(decoded, 1);
assert.equal(live.state.previewCount, 1);
overlayDef.draw(drawing, [1000, 800], {});
assert.ok(drawCalls.some((args) => args[0] === bitmaps[0]));

for (const callback of activeIntervals.values()) callback();
assert.equal(live.state.fps, 1);
emit("status", { exec_info: { queue_remaining: 0 } });
assert.equal(live.state.status, "idle");
assert.equal(activeIntervals.size, 0);
emit("execution_error", {});
assert.equal(live.state.status, "error");

const pointer = (pointerId, x, y) => ({ pointerId, viewport: { x, y } });
overlayDef.onPointerDown(pointer(7, 100, 35));
overlayDef.onPointerMove(pointer(7, 180, 95));
assert.deepEqual(plain(live.state.geometry), { x: 91, y: 82, width: 420, height: 440 });
overlayDef.onPointerUp(pointer(7, 180, 95));
await new Promise((resolve) => setImmediate(resolve));
assert.deepEqual(storageWrites.at(-1)[1], plain(live.state.geometry));

const beforeResize = structuredClone(live.state.geometry);
overlayDef.onPointerDown(pointer(
  8,
  beforeResize.x + beforeResize.width - 2,
  beforeResize.y + beforeResize.height - 2,
));
overlayDef.onPointerMove(pointer(
  8,
  beforeResize.x + beforeResize.width + 98,
  beforeResize.y + beforeResize.height + 48,
));
assert.equal(live.state.geometry.width, 520);
assert.equal(live.state.geometry.height, 490);
overlayDef.onPointerCancel(pointer(8, 0, 0));

overlayDef.onPointerDown(pointer(
  9,
  live.state.geometry.x + live.state.geometry.width - 17,
  live.state.geometry.y + 16,
));
assert.equal(live.state.visible, false);
assert.equal(live.state.userHidden, true);
emit("execution_start", {});
assert.equal(live.state.visible, false, "an explicit close survives later executions");
actionDef.run({});
assert.equal(live.state.visible, true);
assert.equal(live.state.userHidden, false);

nodes.splice(0);
emit("b_preview", new Blob([new Uint8Array([9])], { type: "image/png" }));
await new Promise((resolve) => setImmediate(resolve));
assert.equal(decoded, 1, "frames are ignored when no activation node exists");
nodes.push({ id: "live", type: "LivePreview" });
emit("b_preview", new Blob([new Uint8Array([9])], { type: "text/plain" }));
await new Promise((resolve) => setImmediate(resolve));
assert.equal(decoded, 1, "non-image payloads are rejected");

live.remove();
live.remove();
assert.equal(bitmaps[0].closed, 1);
assert.equal(overlayRemoved, 1);
assert.equal(actionRemoved, 1);
assert.equal(activeIntervals.size, 0);
assert.ok([...backendListeners.values()].every((listeners) => listeners.size === 0));
assert.deepEqual(records.regions.at(-1), []);

const geometry = await load(pathToFileURL(path.join(webRoot, "geometry.js")).href);
if (geometry.status !== "evaluated") await geometry.evaluate();
assert.deepEqual(
  plain(geometry.namespace.clampGeometry(
    { x: -4, y: 999, width: 10, height: 900 }, { width: 500, height: 400 },
  )),
  { x: 0, y: 0, width: 200, height: 400 },
);
assert.equal(geometry.namespace.sanitizeStoredGeometry({ x: 1, y: 2, width: "3", height: 4 }), undefined);

console.log("PASS: Live Preview overlay, frames, geometry, storage, and teardown");
