import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error('frontend source path is required');

const extensions = new Map();
const backendListeners = new Map();
const queueListeners = [];
const requests = [];
const viewed = [];
const notifications = [];
const timers = new Map();
const images = [];
let nextTimer = 1;

class FakeImage {
  constructor(name) {
    this.name = name;
    this.width = name.includes('wide') ? 800 : 400;
    this.height = name.includes('tall') ? 800 : 400;
    this.closed = false;
  }
  close() { this.closed = true; }
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
    async fetch(route, init) {
      if (route.startsWith('/view?')) {
        const parsed = new URL(`https://host.invalid${route}`);
        const name = parsed.searchParams.get('filename');
        viewed.push({
          name,
          type: parsed.searchParams.get('type'),
          subfolder: parsed.searchParams.get('subfolder'),
        });
        return { ok: true, status: 200, async blob() { return { name }; } };
      }
      assert.equal(route, '/secure-nodes/interactions/respond');
      requests.push(JSON.parse(init.body));
      return { ok: true, status: 200 };
    },
  },
  commands: { notify(value) { notifications.push(value); } },
  queue: {
    onInterrupted(listener) { queueListeners.push(listener); return () => {}; },
  },
};

const context = vm.createContext({
  console,
  URL,
  URLSearchParams,
  createImageBitmap: async (blob) => {
    const image = new FakeImage(blob.name);
    images.push(image);
    return image;
  },
  setTimeout(callback) {
    const id = nextTimer++;
    timers.set(id, callback);
    return id;
  },
  clearTimeout(id) { timers.delete(id); },
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

function button(definition) {
  const listeners = new Map();
  return {
    definition,
    disabled: Boolean(definition.disabled),
    setDisabled(value) { this.disabled = Boolean(value); },
    on(event, listener) { listeners.set(event, listener); return () => listeners.delete(event); },
    activate() { if (!this.disabled) listeners.get('activate')?.(); },
  };
}

function makeNode(id) {
  const node = {
    id: String(id),
    buttons: new Map(),
    canvasDef: undefined,
    canvasHandle: undefined,
    constraints: undefined,
    setSizeConstraints(value) { this.constraints = value; },
  };
  node.widgets = {
    add(definition) {
      const value = button(definition);
      node.buttons.set(definition.name, value);
      return value;
    },
    canvas(definition) {
      node.canvasDef = definition;
      node.canvasHandle = {
        redraws: 0,
        redraw() { this.redraws += 1; },
      };
      return node.canvasHandle;
    },
  };
  extensions.get('ImagePreviewPause').created(node);
  return node;
}

function emit(requestId, nodeId, filenames, overrides = {}) {
  backendListeners.get('secure-node-interaction')({
    request_id: requestId,
    node_id: String(nodeId),
    kind: 'image-choice',
    timeout_seconds: 540,
    payload: {
      variant: 'image-preview-pause.inline-v1',
      images: filenames.map((filename) => ({
        filename,
        type: 'temp',
        subfolder: 'preview-pause',
      })),
      count: filenames.length,
      ...overrides,
    },
  });
}

async function flush() {
  for (let index = 0; index < 16; index += 1) await Promise.resolve();
}

function draw(node, size = [500, 300]) {
  const calls = [];
  const context2d = {
    fillRect() {},
    fillText() {},
    drawImage(image, x, y, width, height) {
      calls.push({ name: image.name, x, y, width, height });
    },
    set fillStyle(_value) {}, set font(_value) {},
    set textAlign(_value) {}, set textBaseline(_value) {},
  };
  node.canvasDef.draw(context2d, size, { textColor: '#fff' });
  return calls;
}

const first = makeNode('1');
const second = makeNode('2');
assert.equal(first.constraints.minWidth, 320);
assert.equal(first.constraints.minHeight, 390);
emit('node-one', '1', ['wide-one.png', 'tall-one.png']);
emit('node-two', '2', ['second.png']);
await flush();
assert.deepEqual(viewed.map((value) => value.name), [
  'wide-one.png', 'tall-one.png', 'second.png',
]);
assert.equal(first.buttons.get('✔️ Continue').disabled, false);
assert.equal(second.buttons.get('⛔ Cancel').disabled, false);
assert.equal(draw(first).length, 2);

// Concurrent nodes retain their own opaque response IDs even when answered in
// reverse order. A duplicate event never creates another request.
emit('node-one', '1', ['duplicate.png']);
second.buttons.get('✔️ Continue').activate();
first.buttons.get('⛔ Cancel').activate();
await flush();
assert.deepEqual(requests, [
  { request_id: 'node-two', response: { action: 'continue' } },
  { request_id: 'node-one', response: { action: 'cancel' } },
]);
assert.equal(viewed.some((value) => value.name === 'duplicate.png'), false);
first.buttons.get('✔️ Continue').activate();
await flush();
assert.equal(requests.length, 2);

// Repeated executions of one graph node serialize only their presentation;
// each keeps its own one-use token.
emit('queued-a', '1', ['a.png']);
emit('queued-b', '1', ['b.png']);
await flush();
assert.equal(viewed.at(-1).name, 'a.png');
first.buttons.get('✔️ Continue').activate();
await flush();
assert.equal(requests.at(-1).request_id, 'queued-a');
assert.equal(viewed.at(-1).name, 'b.png');
first.buttons.get('⛔ Cancel').activate();
await flush();
assert.equal(requests.at(-1).request_id, 'queued-b');

// Invalid payloads and unknown nodes are ignored without fetching previews.
const viewedBeforeInvalid = viewed.length;
emit('wrong-variant', '1', ['bad.png'], { variant: 'other' });
emit('traversal', '1', ['../bad.png']);
emit('unknown', '404', ['unknown.png']);
backendListeners.get('secure-node-interaction')({
  request_id: 'wrong-kind', node_id: '1', kind: 'prompt-await', payload: {},
});
await flush();
assert.equal(viewed.length, viewedBeforeInvalid);

// A local expiry removes the one-use token and disables late actions.
emit('expires', '2', ['expires.png']);
await flush();
const expiry = [...timers.entries()].at(-1);
expiry[1]();
second.buttons.get('✔️ Continue').activate();
await flush();
assert.equal(requests.some((value) => value.request_id === 'expires'), false);

// Teardown cancels active and queued interactions independently, releases all
// bitmaps, and remounting does not duplicate the pack-level listener.
emit('remove-active', '1', ['remove-a.png']);
emit('remove-queued', '1', ['remove-b.png']);
await flush();
extensions.get('ImagePreviewPause').removed(first);
await flush();
assert.deepEqual(requests.slice(-2), [
  { request_id: 'remove-active', response: { action: 'cancel' } },
  { request_id: 'remove-queued', response: { action: 'cancel' } },
]);
assert.equal(backendListeners.size, 1);
assert.ok(images.every((image) => image.closed));

const remounted = makeNode('1');
emit('remounted', '1', ['remounted.png']);
await flush();
assert.equal(remounted.buttons.get('✔️ Continue').disabled, false);
queueListeners[0]();
remounted.buttons.get('✔️ Continue').activate();
await flush();
assert.equal(requests.some((value) => value.request_id === 'remounted'), false);
assert.equal(notifications.length, 0);

console.log('PASS: ImagePreviewPause correlation, batch UI, expiry, and teardown');
