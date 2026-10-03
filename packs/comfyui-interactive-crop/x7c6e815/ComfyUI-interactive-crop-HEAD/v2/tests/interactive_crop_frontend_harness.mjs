import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error('frontend source path is required');

const extensions = new Map();
const backendListeners = new Map();
const queueListeners = [];
const requests = [];
const notifications = [];
const timers = new Map();
let nextTimer = 1;

class FakeImage {
  constructor() {
    this.width = 800;
    this.height = 400;
    this.naturalWidth = 800;
    this.naturalHeight = 400;
    this.closed = false;
  }
  close() { this.closed = true; }
}

function fakeTimer(callback) {
  const id = nextTimer++;
  timers.set(id, callback);
  return id;
}

function clearFakeTimer(id) {
  timers.delete(id);
}

const comfy = {
  defs: {
    extend(type, callback) {
      const hooks = {};
      callback({
        onCreated(fn) { hooks.created = fn; },
        onRemoved(fn) { hooks.removed = fn; },
      });
      extensions.set(type, hooks);
    },
  },
  backend: {
    on(event, listener) {
      if (backendListeners.has(event)) throw new Error(`duplicate listener ${event}`);
      backendListeners.set(event, listener);
      return () => backendListeners.delete(event);
    },
    url(route) { return `https://host.invalid${route}`; },
    async fetch(route, init) {
      if (route.startsWith('/view?')) {
        return { ok: true, status: 200, async blob() { return { type: 'image/png' }; } };
      }
      requests.push({ route, body: JSON.parse(init.body) });
      return { ok: true, status: 200 };
    },
  },
  commands: {
    notify(value) { notifications.push(value); },
  },
  queue: {
    onInterrupted(listener) { queueListeners.push(listener); return () => {}; },
  },
};

const context = vm.createContext({
  console,
  URLSearchParams,
  createImageBitmap: async () => new FakeImage(),
  setTimeout: fakeTimer,
  clearTimeout: clearFakeTimer,
});
const module = new vm.SourceTextModule(fs.readFileSync(sourcePath, 'utf8'), {
  context,
  identifier: sourcePath,
});
await module.link(async (specifier) => {
  assert.equal(specifier, '/comfy/api/v2.js');
  const api = new vm.SyntheticModule(['comfy'], function initialize() {
    this.setExport('comfy', comfy);
  }, { context });
  await api.link(() => {});
  await api.evaluate();
  return api;
});
await module.evaluate();

assert.equal(extensions.size, 1);
assert.equal(backendListeners.size, 1);
assert.equal(queueListeners.length, 1);

function widget(name, value = undefined) {
  const listeners = new Map();
  return {
    name,
    value,
    disabled: false,
    getValue() { return this.value; },
    setValue(next) { this.value = next; },
    setDisabled(next) { this.disabled = Boolean(next); },
    on(event, listener) { listeners.set(event, listener); return () => listeners.delete(event); },
    activate() { listeners.get('activate')?.(); },
  };
}

function makeNode(id) {
  const values = new Map([['force_original_ratio', widget('force_original_ratio', false)]]);
  const node = {
    id: String(id),
    constraints: undefined,
    canvasDef: undefined,
    canvasHandle: undefined,
    buttons: new Map(),
    setSizeConstraints(value) { this.constraints = value; },
  };
  node.widgets = {
    get(name) { return values.get(name); },
    add(definition) {
      const value = widget(definition.name, definition.value);
      value.disabled = Boolean(definition.disabled);
      values.set(definition.name, value);
      node.buttons.set(definition.name, value);
      return value;
    },
    canvas(definition) {
      node.canvasDef = definition;
      node.canvasHandle = {
        redraws: 0,
        widget: widget(definition.name),
        redraw() { this.redraws += 1; },
      };
      values.set(definition.name, node.canvasHandle.widget);
      return node.canvasHandle;
    },
  };
  extensions.get('InteractiveCrop').created(node);
  return node;
}

function context2d() {
  return {
    image: undefined,
    clearRect() {}, fillRect() {}, fillText() {}, beginPath() {}, rect() {}, clip() {},
    save() {}, restore() {}, strokeRect() {},
    drawImage(_image, x, y, width, height) { this.image = { x, y, width, height }; },
    set fillStyle(_value) {}, set strokeStyle(_value) {}, set lineWidth(_value) {},
    set textAlign(_value) {}, set textBaseline(_value) {}, set font(_value) {},
  };
}

const theme = {
  surface: '#111', surfaceHovered: '#222', border: '#555',
  text: '#fff', textSecondary: '#aaa',
};

function eventAt(x, y, { button = 0, buttons = 1 } = {}) {
  return {
    x, y,
    event: {
      button, buttons,
      prevented: false,
      preventDefault() { this.prevented = true; },
    },
  };
}

function emit(requestId, nodeId, payload = {}) {
  backendListeners.get('secure-node-interaction')({
    request_id: requestId,
    node_id: String(nodeId),
    kind: 'image-choice',
    timeout_seconds: 240,
    payload: {
      variant: 'interactive-crop.inline-v1',
      image: { filename: `${requestId}.png`, type: 'temp', subfolder: 'crop' },
      width: 800,
      height: 400,
      force_original_ratio: false,
      ...payload,
    },
  });
}

function draw(node, size = [400, 360]) {
  const ctx = context2d();
  node.canvasDef.draw(ctx, size, theme);
  assert.ok(ctx.image, 'active preview should draw');
  return ctx.image;
}

function screenPoint(box, imageX, imageY) {
  return {
    x: box.x + imageX / 800 * box.width,
    y: box.y + imageY / 400 * box.height,
  };
}

function drag(node, box, from, to) {
  const start = screenPoint(box, from[0], from[1]);
  const end = screenPoint(box, to[0], to[1]);
  node.canvasDef.onPointerDown(eventAt(start.x, start.y));
  node.canvasDef.onPointerMove(eventAt(end.x, end.y));
  node.canvasDef.onPointerUp(eventAt(end.x, end.y, { buttons: 0 }));
}

async function flush() {
  for (let index = 0; index < 12; index += 1) await Promise.resolve();
}

const first = makeNode('1');
const second = makeNode('2');
assert.equal(first.constraints.minWidth, 300);
assert.equal(first.constraints.minHeight, 460);
emit('request-one', '1');
emit('request-two', '2');
await flush();
assert.equal(first.buttons.get('Apply Crop / Skip').disabled, false);
assert.equal(second.buttons.get('Apply Crop / Skip').disabled, false);

// CSS-coordinate mapping stays exact when the mounted canvas is resized. The
// host owns device-pixel scaling, so pointer and draw coordinates share units.
let box = draw(first, [400, 360]);
drag(first, box, [100, 50], [500, 250]);
box = draw(first, [300, 300]);
drag(first, box, [300, 150], [400, 200]); // move
box = draw(first, [300, 300]);
drag(first, box, [600, 300], [700, 350]); // south-east handle
first.buttons.get('Apply Crop / Skip').activate();

const secondBox = draw(second, [520, 320]);
drag(second, secondBox, [20, 30], [220, 180]);
second.buttons.get('Apply Crop / Skip').activate();
await flush();

assert.equal(requests.length, 2);
assert.deepEqual(requests[0].body, {
  request_id: 'request-one',
  response: { action: 'continue', x0: 200, y0: 100, x1: 700, y1: 350 },
});
assert.deepEqual(requests[1].body, {
  request_id: 'request-two',
  response: { action: 'continue', x0: 20, y0: 30, x1: 220, y1: 180 },
});

// Finished controls cannot send a late response.
first.buttons.get('Apply Crop / Skip').activate();
first.buttons.get('Cancel Run').activate();
await flush();
assert.equal(requests.length, 2);

// Two executions of one graph node are queued and keep their one-use tokens.
emit('queued-a', '1');
emit('queued-b', '1');
await flush();
first.buttons.get('Apply Crop / Skip').activate(); // no selection => passthrough a
await flush();
assert.equal(requests.at(-1).body.request_id, 'queued-a');
assert.deepEqual(requests.at(-1).body.response, { action: 'passthrough' });
assert.equal(first.buttons.get('Apply Crop / Skip').disabled, false);
first.buttons.get('Cancel Run').activate();
await flush();
assert.equal(requests.at(-1).body.request_id, 'queued-b');
assert.deepEqual(requests.at(-1).body.response, { action: 'cancel' });

// Aspect lock applies to a new selection.
first.widgets.get('force_original_ratio').setValue(true);
emit('ratio', '1');
await flush();
box = draw(first, [460, 360]);
drag(first, box, [80, 40], [400, 360]);
first.buttons.get('Apply Crop / Skip').activate();
await flush();
const ratioResponse = requests.at(-1).body.response;
assert.equal(ratioResponse.action, 'continue');
assert.ok(Math.abs(
  (ratioResponse.x1 - ratioResponse.x0) / (ratioResponse.y1 - ratioResponse.y0) - 2,
) < 0.02);

// Unknown variants, kinds, and nodes never create or answer a session.
const beforeIgnored = requests.length;
backendListeners.get('secure-node-interaction')({
  request_id: 'wrong-kind', node_id: '1', kind: 'prompt-await', payload: {},
});
backendListeners.get('secure-node-interaction')({
  request_id: 'wrong-variant', node_id: '1', kind: 'image-choice',
  payload: { variant: 'other' },
});
emit('unknown-node', '404');
await flush();
assert.equal(requests.length, beforeIgnored);

// Expiry locally disables the controls and ignores late clicks.
emit('expires', '2');
await flush();
const expiryTimer = [...timers.entries()].at(-1);
expiryTimer[1]();
second.buttons.get('Apply Crop / Skip').activate();
await flush();
assert.equal(requests.length, beforeIgnored);

// Removal cancels active and queued invocations, does not cross their tokens,
// and leaves no timers or per-node state behind. Remounting installs no second
// backend listener.
emit('remove-active', '1');
emit('remove-queued', '1');
await flush();
extensions.get('InteractiveCrop').removed(first);
await flush();
assert.deepEqual(requests.slice(-2).map((item) => item.body), [
  { request_id: 'remove-active', response: { action: 'cancel' } },
  { request_id: 'remove-queued', response: { action: 'cancel' } },
]);
assert.equal(backendListeners.size, 1);
assert.equal([...timers.values()].length, 0);

const remounted = makeNode('1');
emit('remount', '1');
await flush();
assert.equal(remounted.buttons.get('Apply Crop / Skip').disabled, false);
queueListeners[0]();
remounted.buttons.get('Cancel Run').activate();
await flush();
assert.equal(requests.at(-1).body.request_id, 'remove-queued');
assert.equal(notifications.length, 0);

console.log('PASS: Interactive Crop mounted UI, concurrency, scaling, and teardown');
