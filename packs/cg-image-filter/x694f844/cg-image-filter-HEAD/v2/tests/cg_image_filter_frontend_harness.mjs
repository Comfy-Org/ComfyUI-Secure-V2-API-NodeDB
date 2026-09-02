import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(process.env.TARGET_JS, 'utf8');
const subscriptions = new Map();
const extensions = [];
const requests = [];
const sounds = [];
const defaults = new Map();
let dialog;

class Element {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.listeners = new Map();
    this.style = { cssText: '' };
    this.textContent = '';
    this.value = '';
  }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  prepend(...children) { this.children.unshift(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  addEventListener(name, callback) {
    const callbacks = this.listeners.get(name) || [];
    callbacks.push(callback);
    this.listeners.set(name, callbacks);
  }
  async dispatch(name, detail = {}) {
    for (const callback of this.listeners.get(name) || []) await callback(detail);
  }
  getBoundingClientRect() { return { width: 100, height: 100 }; }
}

const document = {
  createElement: (tag) => new Element(tag),
  createTextNode(text) { return { textContent: String(text), children: [] }; },
};

function descendants(root) {
  return [root, ...(root.children || []).flatMap(descendants)];
}

function find(tag, text) {
  const value = descendants(dialog.container).find((item) =>
    item.tagName === tag.toUpperCase() &&
    (text === undefined || item.textContent === text));
  assert.ok(value, `missing ${tag} ${text || ''}`);
  return value;
}

function response(body = '{}') {
  return { ok: true, status: 200, json: async () => JSON.parse(body), text: async () => body };
}

const comfy = {
  settings: {
    declare(definition) { defaults.set(definition.id, definition.defaultValue); },
    get(id) {
      if (id === 'Image Filter.UI.Play Sound') return false;
      if (id === 'Image Filter.UI.Sound Timeout') return 0;
      return defaults.get(id);
    },
  },
  backend: {
    on(event, callback) {
      const callbacks = subscriptions.get(event) || [];
      callbacks.push(callback);
      subscriptions.set(event, callbacks);
      return () => {};
    },
    url(value) { return `https://host.invalid${value}`; },
    async fetch(route, init = {}) {
      requests.push({ route, method: init.method, body: init.body });
      return response();
    },
  },
  commands: {
    async playSound(value) { sounds.push(value); },
    notify() {},
  },
  executionNode: () => ({ id: '1', getTitle: () => 'Pinned Image Filter' }),
  onExecutingNodeChanged: () => () => {},
  graph: { node: () => ({ getTitle: () => 'Pinned Image Filter' }) },
  ui: {
    showDialog(definition) {
      const container = new Element('div');
      let closed = false;
      const handle = {
        close() {
          if (closed) return;
          closed = true;
          definition.destroy?.();
        },
      };
      dialog = { definition, container, handle, get closed() { return closed; } };
      definition.render(container);
      return handle;
    },
  },
  defs: {
    extend(selector, apply) {
      const hooks = {};
      apply({
        hideWidget(name) { hooks.hidden = name; },
        onCreated(callback) { hooks.created = callback; },
        onConfigured(callback) { hooks.configured = callback; },
        onConnectionsChanged(callback) { hooks.connections = callback; },
      });
      extensions.push({ selector, hooks });
      return () => {};
    },
  },
};

const context = vm.createContext({
  console, document, URL, URLSearchParams, TextEncoder, Uint8Array,
  Blob, setTimeout, clearTimeout, setInterval, clearInterval,
});
const facade = new vm.SyntheticModule(['comfy'], function initialize() {
  this.setExport('comfy', comfy);
}, { context, identifier: '/comfy/api/v2.js' });
const module = new vm.SourceTextModule(source, {
  context, identifier: 'https://guest.invalid/extensions/cg-image-filter/image_filter.js',
  initializeImportMeta(meta) {
    meta.url = 'https://guest.invalid/extensions/cg-image-filter/image_filter.js';
  },
});
await module.link(async (specifier) => {
  assert.equal(specifier, '/comfy/api/v2.js');
  return facade;
});
await module.evaluate();

assert.deepEqual(extensions.map((item) => item.selector), [
  'Image Filter', 'Text Image Filter', 'Mask Image Filter', 'Pick from List',
]);
assert.ok(extensions.slice(0, 3).every((item) => item.hooks.hidden === 'graph_id'));
assert.equal(typeof extensions[3].hooks.connections, 'function');
const modified = [];
const dynamicNode = {
  inputs: { at: () => ({ connectedType: 'IMAGE', modify: (value) => modified.push(['input', value]) }) },
  outputs: { at: () => ({ modify: (value) => modified.push(['output', value]) }) },
};
extensions[3].hooks.connections(dynamicNode, {
  side: 'input', index: 0, connected: true,
});
assert.deepEqual(structuredClone(modified), [
  ['input', { type: 'IMAGE' }], ['output', { type: 'IMAGE' }],
]);
let graphValue;
let previewHidden = false;
extensions[2].hooks.created({
  graphId: 'graph-42',
  widgets: { get(name) {
    if (name === 'graph_id') return { setValue(value) { graphValue = value; } };
    if (name === '$$canvas-image-preview') return { setHidden(value) { previewHidden = value; } };
    return undefined;
  } },
});
assert.equal(graphValue, 'graph-42');
assert.equal(previewHidden, true);
assert.equal((subscriptions.get('secure-node-interaction') || []).length, 1);
for (const ambient of ['window', 'parent', 'app', 'fetch', 'XMLHttpRequest', 'WebSocket', 'localStorage']) {
  assert.equal(vm.runInContext(`typeof ${ambient}`, context), 'undefined', `${ambient} leaked`);
}

const emit = async (detail) => {
  for (const callback of subscriptions.get('secure-node-interaction') || []) callback(detail);
  await new Promise((resolve) => setImmediate(resolve));
};

const base = {
  request_id: 'choice-reset', kind: 'image-choice', node_id: '1',
  payload: {
    variant: 'cg-image-filter.image-choice-v1',
    images: [{ filename: 'one.png', type: 'temp', subfolder: '' }],
    count: 1, allsame: false, extras: ['a', 'b', 'c'], tip: '{{tag}} choose',
    video_frames: 1, graph_id: 'g', sound: 'ding.mp3',
  },
};
await emit(base);
assert.equal(dialog.definition.title, 'Pinned Image Filter');
await find('button', 'Reset timer').dispatch('click');
await new Promise((resolve) => setImmediate(resolve));
assert.deepEqual(JSON.parse(requests.at(-1).body), {
  request_id: 'choice-reset', response: { reset: true },
});
assert.equal(dialog.closed, true);

await emit({ ...base, request_id: 'choice-send' });
assert.equal(typeof dialog.definition.onKeyDown, 'function');
await dialog.definition.onKeyDown({ key: 'Enter', editableTarget: false });
await new Promise((resolve) => setImmediate(resolve));
assert.deepEqual(JSON.parse(requests.at(-1).body), {
  request_id: 'choice-send',
  response: { cancelled: false, selected: [0], extras: ['a', 'b', 'c'] },
});

await emit({
  request_id: 'text-send', kind: 'prompt-await', node_id: '2',
  payload: {
    variant: 'cg-image-filter.text-edit-v1',
    images: [{ filename: 'text.png', type: 'temp', subfolder: '' }],
    text: 'before', extras: ['', '', ''], tip: '', textareaheight: 150,
  },
});
const textarea = find('textarea');
textarea.value = 'stale-local-value';
await textarea.dispatch('input', { value: 'worker-event-value' });
await find('button', 'Send').dispatch('click');
await new Promise((resolve) => setImmediate(resolve));
assert.equal(JSON.parse(requests.at(-1).body).response.text, 'worker-event-value');

await emit({
  request_id: 'text-reuse', kind: 'prompt-await', node_id: '2',
  timeout_seconds: 30,
  payload: {
    variant: 'cg-image-filter.text-edit-v1',
    images: [{ filename: 'text.png', type: 'temp', subfolder: '' }],
    text: 'new run', extras: ['', '', ''], tip: '', textareaheight: 150,
  },
});
const reuse = find('textarea');
await reuse.dispatch('click');
await reuse.dispatch('click');
await reuse.dispatch('click');
assert.equal(reuse.value, 'worker-event-value');
assert.ok(descendants(dialog.container).some((item) => item.textContent === '30s'));
const beforeEditableEnter = requests.length;
await dialog.definition.onKeyDown({ key: 'Enter', editableTarget: true });
await new Promise((resolve) => setImmediate(resolve));
assert.equal(requests.length, beforeEditableEnter);
await dialog.definition.onKeyDown({ key: 'Enter', editableTarget: false });
await new Promise((resolve) => setImmediate(resolve));
assert.equal(JSON.parse(requests.at(-1).body).response.text, 'worker-event-value');
assert.equal(sounds.length, 0);

console.log('cg-image-filter frontend harness: PASS');
