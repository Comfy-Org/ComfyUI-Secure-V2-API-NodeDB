import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath, pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
const rendererSource = fs.readFileSync(path.join(path.dirname(entry), "panorama_viewer.js"), "utf8");
const combined = `${source}\n${rendererSource}`;
for (const forbidden of [
  /\.\.\/\.\.\/\.\.\/scripts\//,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|data:image|cdn\.jsdelivr|cdnjs/,
]) assert.doesNotMatch(combined, forbidden);
assert.match(source, /getOutputImages\(\)/);
assert.match(source, /widgets\.mount\(/);

class FakeGl {
  constructor() {
    Object.assign(this, {
      VERTEX_SHADER: 1, FRAGMENT_SHADER: 2, COMPILE_STATUS: 3, LINK_STATUS: 4,
      ARRAY_BUFFER: 5, STATIC_DRAW: 6, TEXTURE_2D: 7, TEXTURE_WRAP_S: 8,
      TEXTURE_WRAP_T: 9, REPEAT: 10, CLAMP_TO_EDGE: 11, TEXTURE_MIN_FILTER: 12,
      TEXTURE_MAG_FILTER: 13, LINEAR: 14, UNPACK_FLIP_Y_WEBGL: 15, RGBA: 16,
      UNSIGNED_BYTE: 17, TEXTURE0: 18, TRIANGLES: 19, FLOAT: 20,
    });
    this.uploads = [];
    this.draws = 0;
    this.deleted = [];
  }
  createShader(type) { return { type }; } shaderSource() {} compileShader() {}
  getShaderParameter() { return true; } getShaderInfoLog() { return ""; }
  deleteShader() {} createProgram() { return { kind: "program" }; } attachShader() {}
  linkProgram() {} getProgramParameter() { return true; } getProgramInfoLog() { return ""; }
  createBuffer() { return { kind: "buffer" }; } createTexture() { return { kind: "texture" }; }
  getAttribLocation() { return 0; } getUniformLocation(_program, name) { return name; }
  bindBuffer() {} bufferData() {} bindTexture() {} texParameteri() {} viewport() {}
  useProgram() {} enableVertexAttribArray() {} vertexAttribPointer() {} activeTexture() {}
  uniform1i() {} uniform1f() {} pixelStorei() {}
  texImage2D(...args) { this.uploads.push(args.at(-1).src); }
  drawArrays() { this.draws += 1; }
  deleteTexture(value) { this.deleted.push(value.kind); }
  deleteBuffer(value) { this.deleted.push(value.kind); }
  deleteProgram(value) { this.deleted.push(value.kind); }
}

class Element {
  constructor(tag, owner) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = owner;
    this.children = [];
    this.listeners = new Map();
    this.style = {};
    this.textContent = "";
    this.attributes = new Map();
    this.clientWidth = 360;
    this.clientHeight = 280;
    this.gl = tag === "canvas" ? new FakeGl() : undefined;
  }
  append(...items) { this.children.push(...items); }
  addEventListener(name, listener) {
    const values = this.listeners.get(name) || [];
    values.push(listener);
    this.listeners.set(name, values);
  }
  removeEventListener(name, listener) {
    this.listeners.set(name, (this.listeners.get(name) || []).filter((item) => item !== listener));
  }
  dispatch(name, extra = {}) {
    const event = { clientX: 0, clientY: 0, pointerId: 1, deltaY: 0,
      preventDefault() { this.prevented = true; }, ...extra };
    for (const listener of this.listeners.get(name) || []) listener(event);
    return event;
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); if (name === "src") this._src = ""; }
  setPointerCapture() {} releasePointerCapture() {}
  getContext(name) { assert.equal(name, "webgl"); return this.gl; }
  getBoundingClientRect() { return { width: this.clientWidth, height: this.clientHeight }; }
  set src(value) { this._src = value; imageLoads.push(value); queueMicrotask(() => this.onload?.()); }
  get src() { return this._src; }
}

let now = 0;
let rafId = 0;
const rafs = new Map();
const imageLoads = [];
const view = {
  devicePixelRatio: 2,
  performance: { now: () => now },
  requestAnimationFrame(callback) { const id = ++rafId; rafs.set(id, callback); return id; },
  cancelAnimationFrame(id) { rafs.delete(id); },
};
const ownerDocument = { defaultView: view, createElement(tag) { return new Element(tag, ownerDocument); } };
function step(time) {
  now = time;
  const current = [...rafs.values()];
  rafs.clear();
  for (const callback of current) callback(time);
}

const extensions = new Map();
const comfy = { defs: { extend(selector, callback) {
  const hooks = {};
  callback({
    onCreated(fn) { hooks.created = fn; },
    onExecuted(fn) { hooks.executed = fn; },
    onResized(fn) { hooks.resized = fn; },
    onRemoved(fn) { hooks.removed = fn; },
  });
  extensions.set(selector, hooks);
} } };

const context = vm.createContext({ console, Float32Array, Math, Number, performance: view.performance,
  requestAnimationFrame: view.requestAnimationFrame, cancelAnimationFrame: view.cancelAnimationFrame,
  queueMicrotask });
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

const entryModule = await load(entry);
await entryModule.evaluate();
const renderer = modules.get(path.resolve(path.dirname(entry), "panorama_viewer.js")).namespace;
assert.deepEqual({ ...renderer.dragView(10, 5, 20, -30) }, { lon: 8, lat: 2 });
assert.equal(renderer.zoomFov(75, 1000), 90);
assert.equal(renderer.zoomFov(35, -1000), 30);
assert.deepEqual([0, 1, 2, 0], [0, 50, 100, 150].map((time) => renderer.frameAt(time, 20, 3)));
assert.deepEqual([...extensions.keys()], ["PanoramaViewerNode", "PanoramaVideoViewerNode"]);

function createNode(frames, fps = 30) {
  let mount;
  let outputFrames = frames;
  return {
    node: {
      widgets: {
        mount(def) { mount = def; return {}; },
        get(name) { return name === "fps" ? { getValue: () => fps } : undefined; },
      },
      setSizeConstraints(value) { this.constraints = value; },
      getOutputImages() { return outputFrames; },
    },
    mount: () => mount,
    setFrames(value) { outputFrames = value; },
  };
}

const still = createNode(["/view/still.png", "/view/ignored.png"]);
extensions.get("PanoramaViewerNode").created(still.node);
assert.equal(JSON.stringify(still.node.constraints), JSON.stringify({ minWidth: 340, minHeight: 380 }));
const stillDef = still.mount();
assert.equal(stillDef.height, 300);
assert.equal(stillDef.serialize, false);
assert.equal(stillDef.sendToPrompt, false);
const stillContainer = new Element("div", ownerDocument);
stillDef.render(stillContainer);
extensions.get("PanoramaViewerNode").executed(still.node);
await new Promise((resolve) => setImmediate(resolve));
step(0);
assert.deepEqual(imageLoads, ["/view/still.png"]);
const stillCanvas = stillContainer.children.find((item) => item.tagName === "CANVAS");
assert.equal(stillCanvas.width, 720);
assert.equal(stillCanvas.height, 560);
const dragStart = stillCanvas.dispatch("pointerdown", { clientX: 100, clientY: 100 });
stillCanvas.dispatch("pointermove", { clientX: 130, clientY: 80 });
stillCanvas.dispatch("pointerup");
assert.equal(dragStart.prevented, true);
assert.equal(stillCanvas.dispatch("wheel", { deltaY: 400 }).prevented, true);
step(1);
assert.ok(stillCanvas.gl.draws > 0);
assert.deepEqual(stillCanvas.gl.uploads, ["/view/still.png"]);
stillContainer.clientWidth = 500;
stillContainer.clientHeight = 250;
extensions.get("PanoramaViewerNode").resized(still.node);
step(2);
assert.deepEqual([stillCanvas.width, stillCanvas.height], [1000, 500]);
still.setFrames([]);
extensions.get("PanoramaViewerNode").executed(still.node);
assert.equal(stillContainer.children.find((item) => item.tagName === "DIV").textContent,
  "No panorama preview was produced");

const video = createNode(["/view/0.png", "/view/1.png", "/view/2.png"], 20);
extensions.get("PanoramaVideoViewerNode").created(video.node);
const videoDef = video.mount();
const videoContainer = new Element("div", ownerDocument);
videoDef.render(videoContainer);
extensions.get("PanoramaVideoViewerNode").executed(video.node);
await new Promise((resolve) => setImmediate(resolve));
const videoStart = now;
step(videoStart);
step(videoStart + 50);
await new Promise((resolve) => setImmediate(resolve));
step(videoStart + 100);
await new Promise((resolve) => setImmediate(resolve));
assert.deepEqual(imageLoads.slice(-3), ["/view/0.png", "/view/1.png", "/view/2.png"]);
assert.match(videoContainer.children.find((item) => item.tagName === "DIV").textContent, /3 frames · 20 FPS/);

const videoCanvas = videoContainer.children.find((item) => item.tagName === "CANVAS");
videoDef.destroy();
extensions.get("PanoramaVideoViewerNode").removed(video.node);
assert.deepEqual(videoCanvas.gl.deleted.sort(), ["buffer", "program", "texture"]);
assert.equal([...videoCanvas.listeners.values()].flat().length, 0);
assert.equal(rafs.size, 0);
stillDef.destroy();
extensions.get("PanoramaViewerNode").removed(still.node);

console.log("PASS: secure panorama mount, projection controls, playback order, resize, and teardown");
