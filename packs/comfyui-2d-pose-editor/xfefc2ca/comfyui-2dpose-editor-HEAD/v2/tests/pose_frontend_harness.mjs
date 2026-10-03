import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const entry = path.resolve(process.argv[2]);
const mainSource = fs.readFileSync(entry, 'utf8');
assert.doesNotMatch(mainSource, /(?:^|[^A-Za-z])document\s*\./);
assert.doesNotMatch(mainSource, /(?:^|[^A-Za-z])window\s*\./);
assert.doesNotMatch(mainSource, /localStorage|indexedDB|fetch\s*\(|comfy\.backend|graph\.serialize|FileReader/);
assert.match(mainSource, /comfy\.files\.pick/);
assert.match(mainSource, /beforeSerialize/);

class FakeContext {
  constructor() { this.calls = []; }
  _call(name, ...args) { this.calls.push([name, ...args]); }
  clearRect(...a) { this._call('clearRect', ...a); } fillRect(...a) { this._call('fillRect', ...a); }
  drawImage(...a) { this._call('drawImage', ...a); } save() {} restore() {} translate() {}
  scale() {} rotate() {} beginPath() {} arc() {} fill() {} stroke() {} moveTo() {} lineTo() {}
  clip() {} roundRect() {} strokeRect() {} closePath() {} setLineDash() {}
}

class Element {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase(); this.ownerDocument = doc; this.children = [];
    this.listeners = new Map(); this.style = {}; this.value = ''; this.textContent = '';
    this.title = ''; this.width = 0; this.height = 0; this.tabIndex = -1; this.closed = false;
    if (tag === 'canvas') this.context = new FakeContext();
  }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.append(item); return item; }
  replaceChildren(...items) { this.children = [...items]; }
  addEventListener(name, listener) { const list = this.listeners.get(name) || []; list.push(listener); this.listeners.set(name, list); }
  dispatch(name, event = {}) { for (const listener of this.listeners.get(name) || []) listener({ type: name, preventDefault() { event.prevented = true; }, stopPropagation() {}, ...event }); }
  focus() { this.focused = true; }
  getContext() { return this.context; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 384, height: 384 }; }
  setPointerCapture() {}
  toDataURL() { return `data:image/png;base64,${Buffer.from(`${this.width}x${this.height}`).toString('base64')}`; }
}

const ownerDocument = { createElement(tag) { return new Element(tag, ownerDocument); } };
const descendants = (root) => [root, ...(root.children || []).flatMap(descendants)];
const findTitle = (root, title) => descendants(root).find((item) => item.title === title);

const picks = [];
const bitmaps = [];
let extension;
const comfy = {
  files: { async pick(options) { assert.equal(options.maxBytes, 16 * 1024 * 1024); return picks.shift(); } },
  defs: { extend(selector, callback) {
    const hooks = {};
    callback({ onCreated(fn) { hooks.created = fn; }, onConnectionsChanged(fn) { hooks.connections = fn; } });
    extension = { selector, hooks };
  } },
};

const context = vm.createContext({
  console, Blob, Buffer,
  createImageBitmap: async (blob) => {
    const bitmap = { width: bitmaps.length === 0 ? 1024 : bitmaps.length === 1 ? 800 : 320,
      height: bitmaps.length === 0 ? 1024 : bitmaps.length === 1 ? 400 : 240,
      close() { this.closed = true; } };
    assert.ok(blob.size > 0); bitmaps.push(bitmap); return bitmap;
  },
});
const cache = new Map();
async function loadModule(filename) {
  filename = path.resolve(filename);
  if (cache.has(filename)) return cache.get(filename);
  const source = fs.readFileSync(filename, 'utf8');
  const module = new vm.SourceTextModule(source, { context, identifier: pathToFileURL(filename).href });
  cache.set(filename, module);
  await module.link(async (specifier, referencing) => {
    if (specifier === '/comfy/api/v2.js') {
      const stub = new vm.SyntheticModule(['comfy'], function () { this.setExport('comfy', comfy); }, { context });
      await stub.link(() => {}); return stub;
    }
    return loadModule(path.resolve(path.dirname(fileURLToPath(referencing.identifier)), specifier));
  });
  return module;
}
const module = await loadModule(entry); await module.evaluate();
const ns = module.namespace;
assert.equal(extension.selector, 'PoseEditor2D');

// Independent geometry and variant checks.
const model = new ns.PoseModel();
assert.equal(ns.BONE_SPECS.length, 25);
const screen = model.screenToWorld(420, 180);
assert.deepEqual({ x: screen.x, y: screen.y }, { x: 420, y: 180 });
model.pan(60, -30); model.zoom(-500);
const transformed = model.screenToWorld(420, 180);
assert.ok(Math.abs(transformed.x - 320) < 0.001);
assert.ok(Math.abs(transformed.y - 250) < 0.001);
for (const part of ['headBack', 'bodyBack', 'leftOpen', 'rightOpen']) assert.equal(model.toggle(part), true);
assert.equal(model.bones.find((b) => b.name === 'Head').uv, 'headBack');
assert.equal(model.bones.find((b) => b.name === 'Chest').uv, 'chestBack');
assert.equal(model.bones.find((b) => b.name === 'RightHand').uv, 'handOpenR');
assert.equal(model.bones.find((b) => b.name === 'LeftHand').uv, 'handOpenL');
const hand = model.bones.find((b) => b.name === 'LeftHand');
assert.equal(model.drag('LeftHand', hand.gx + 10, hand.gy + 50), true);
assert.notEqual(hand.localAngle, 0);
const history = new ns.PoseHistory(2); const before = model.snapshot();
history.remember(before); model.toggle('headBack'); model.pan(10, 0);
const undone = history.undo(model.snapshot()); assert.deepEqual(undone, before);
assert.ok(history.redo(undone));
assert.equal(JSON.stringify(ns.frameRect('Custom', 800, 400, undefined)), JSON.stringify({ x: 0, y: 96, w: 384, h: 192 }));
assert.equal(JSON.stringify(ns.frameRect('Background', 1, 1, .5)), JSON.stringify({ x: 96, y: 0, w: 192, h: 384 }));

class Widget {
  constructor(name, value) { this.name = name; this.value = value; this.hidden = false; this.serializeListeners = []; }
  getValue() { return this.value; } setValue(value) { this.value = value; } setHidden(value) { this.hidden = value; }
  on(name, callback) { if (name === 'beforeSerialize') this.serializeListeners.push(callback); return () => {}; }
}
const widgets = new Map([
  ['image_data', new Widget('image_data', '')], ['output_size_mode', new Widget('output_size_mode', 'Standard')],
  ['custom_width', new Widget('custom_width', 600)], ['custom_height', new Widget('custom_height', 600)],
]);
let mountDef;
const node = {
  widgets: { get(name) { return widgets.get(name); }, mount(def) { mountDef = def; return {}; } },
  inputs: { byName() { return { isConnected: false }; } },
  setSizeConstraints(value) { this.constraints = value; },
};
extension.hooks.created(node);
assert.ok([...widgets.values()].every((widget) => widget.hidden));
assert.equal(JSON.stringify(node.constraints), JSON.stringify({ minWidth: 430, maxWidth: 430, minHeight: 520 }));
assert.equal(mountDef.serialize, false); assert.equal(mountDef.sendToPrompt, false);

const container = new Element('div', ownerDocument); mountDef.render(container);
assert.equal(container.listeners.has('keydown'), true);
assert.equal((context.listeners || new Map()).size, 0, 'no global keyboard listener');
const canvas = descendants(container).find((item) => item.tagName === 'CANVAS' && item.width === 600);
assert.ok(canvas);
canvas.dispatch('pointerdown', { clientX: 10, clientY: 10, pointerId: 1 });
canvas.dispatch('pointermove', { clientX: 30, clientY: 20, pointerId: 1 });
canvas.dispatch('pointerup', { pointerId: 1 });
canvas.dispatch('wheel', { deltaY: -100 });
container.dispatch('keydown', { ctrlKey: true, metaKey: false, shiftKey: false, key: 'z' });

// Bounded texture, background, and direct-image pickers all render through the mounted surface.
for (const name of ['atlas.png', 'background.webp', 'input.jpg']) picks.push({ name, type: name.endsWith('.jpg') ? 'image/jpeg' : name.endsWith('.webp') ? 'image/webp' : 'image/png', bytes: new Uint8Array([1, 2, 3]) });
for (const title of ['Load texture atlas', 'Load editor background', 'Load direct image']) {
  findTitle(container, title).dispatch('click'); await new Promise((resolve) => setImmediate(resolve));
}
assert.equal(bitmaps.length, 3);
findTitle(container, 'Clear background color').dispatch('click');
findTitle(container, 'Capture pose').dispatch('click');
assert.match(widgets.get('image_data').value, /^data:image\/png;base64,/);

// The base64 is prompt-only. Saving or embedding the workflow cannot retain it.
const serialize = widgets.get('image_data').serializeListeners[0];
for (const destination of ['workflow', 'embedded', 'prompt']) {
  let projected = widgets.get('image_data').value;
  serialize({ context: destination, value: projected, setSerializedValue(value) { projected = value; } });
  assert.equal(destination === 'prompt' ? projected.startsWith('data:image/png') : projected === '', true);
}
assert.doesNotMatch(JSON.stringify(model.snapshot()), /data:image|base64/i);
picks.push({ name: 'too-large.png', type: 'image/png', bytes: new Uint8Array([1]) });
let oversizedClosed = false;
context.createImageBitmap = async () => ({ width: 5000, height: 5000, close() { oversizedClosed = true; } });
await assert.rejects(ns.pickBitmap(), /resource limit/);
assert.equal(oversizedClosed, true);

node.inputs.byName = () => ({ isConnected: true });
extension.hooks.connections(node);
mountDef.destroy(); assert.ok(bitmaps.every((bitmap) => bitmap.closed));

console.log('PASS: secure mounted pose editor behavior, local history, bounded files, and transient serialization');
