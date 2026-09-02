import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../../../../../..');
const root = path.resolve(here, '..');
const frontend = path.join(repo, 'frontend', 'src');
const tinyPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGMMqFjAwMDAxAAGABC6AWyM4UYOAAAAAElFTkSuQmCC',
  'base64',
);

const objectInfo = {
  'Image Filter': {
    display_name: 'Image Filter', category: 'image_filter',
    input: { required: { images: ['IMAGE'], graph_id: ['STRING', { default: '' }] } },
    output: ['IMAGE', 'LATENT', 'MASK', 'STRING', 'STRING', 'STRING', 'STRING'],
    output_name: ['images', 'latents', 'masks', 'extra1', 'extra2', 'extra3', 'indexes'],
  },
  'Text Image Filter': {
    display_name: 'Text Image Filter', category: 'image_filter',
    input: { required: { image: ['IMAGE'], text: ['STRING'], graph_id: ['STRING', { default: '' }] } },
    output: ['IMAGE', 'STRING', 'STRING', 'STRING', 'STRING'],
  },
  'Mask Image Filter': {
    display_name: 'Mask Image Filter', category: 'image_filter',
    input: { required: { image: ['IMAGE'], graph_id: ['STRING', { default: '' }] } },
    output: ['IMAGE', 'MASK', 'STRING', 'STRING', 'STRING'],
  },
  'Pick from List': {
    display_name: 'Pick from List', category: 'image_filter/helpers',
    input: { required: { anything: ['*'], indexes: ['STRING'] } },
    output: ['STRING'], output_name: ['picks'], output_is_list: [true],
  },
};

const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

const listeners = new Map()
const settings = new Map([
  ['Image Filter.UI.Play Sound', false],
  ['Image Filter.UI.Sound Timeout', 0],
  ['Image Filter.UI.Small Window', false],
  ['Image Filter.UI.Start Zoomed', 0],
  ['Image Filter.Actions.Autosend Identical', false],
  ['Image Filter.Actions.Multiple Selection', 0],
  ['Image Filter.Video.FPS', 5],
])
window.__requests = []
window.__uploads = []
window.__nativeDestroy = 0
window.__sounds = []
window.__notifications = []
window.__nativeTitles = []
let executing = null
const executingListeners = []

const response = (body = '{}') => ({
  ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body),
})

function widget(name, initial = '') {
  let value = initial
  let hidden = false
  return {
    name, widgetType: 'text',
    getValue: () => value,
    setValue(next) { value = next },
    getOptions: () => ({}),
    setHidden(next) { hidden = Boolean(next) },
    isHidden: () => hidden,
    on: () => () => {},
  }
}
const graphWidget = widget('graph_id')
const previewWidget = widget('$$canvas-image-preview')
const widgets = [graphWidget, previewWidget]
const inputs = [{ name: 'anything', type: '*', connectedType: 'IMAGE', modify() {} }]
const outputs = [{ name: 'picks', type: 'STRING', modify() {} }]
const slotCollection = (values) => ({
  all: () => values,
  get: (ref) => typeof ref === 'number' ? values[ref] : values.find((v) => v.name === ref),
  at: (index) => values.at(index),
})
const node = {
  id: '1', type: 'Image Filter', graphId: 'root', title: 'Image Filter Test',
  mode: 0, collapsed: false, pinned: false,
  snapshot() {
    return {
      id: '1', type: this.type, graphId: this.graphId, title: this.title,
      mode: 0, collapsed: false, pinned: false,
      position: { x: 10, y: 20 }, size: { width: 320, height: 240 },
      properties: {},
    }
  },
  getTitle() { return this.title },
  getProperties: () => ({}),
  isSerializingWidgets: () => true,
  getSize: () => ({ width: 320, height: 240 }),
  getPosition: () => ({ x: 10, y: 20 }),
  inputs: slotCollection(inputs), outputs: slotCollection(outputs),
  widgets: {
    all: () => widgets,
    get: (name) => widgets.find((item) => item.name === name),
  },
}

function builder() {
  return {
    hideWidget() {}, onCreated() {}, onConfigured() {}, onRemoved() {},
    onConnectionsChanged() {},
  }
}

const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    on(event, callback) {
      const callbacks = listeners.get(event) || []
      callbacks.push(callback)
      listeners.set(event, callbacks)
      return () => listeners.set(event, callbacks.filter((fn) => fn !== callback))
    },
    async fetch(route, init = {}) {
      if (route === '/object_info') return response(${JSON.stringify(JSON.stringify(objectInfo))})
      if (route.startsWith('/secure-nodes/extensions/')) {
        return response(JSON.stringify({ capabilities: [] }))
      }
      if (route === '/upload/image') {
        window.__uploads.push({ route, method: init.method, bytes: Array.from(init.body || []) })
        return response(JSON.stringify({ name: 'edited-mask.png', type: 'temp', subfolder: 'cg' }))
      }
      if (route === '/secure-nodes/interactions/respond') {
        window.__requests.push(JSON.parse(init.body))
        return response('{}')
      }
      throw new Error('unexpected backend URL: ' + route)
    },
  },
  settings: {
    declare(definition) {
      if (!settings.has(definition.id)) settings.set(definition.id, definition.defaultValue)
    },
    get: (id) => settings.get(id),
    set(id, value) { settings.set(id, value) },
    onChange: () => () => {},
  },
  commands: {
    playSound(value) { window.__sounds.push(structuredClone(value)) },
    notify(value) { window.__notifications.push(structuredClone(value)) },
  },
  executingNode: () => executing,
  onExecutingNodeChanged(callback) {
    executingListeners.push(callback)
    return () => {}
  },
  graph: {
    nodes: () => [node],
    node: (id) => String(id) === '1' ? node : undefined,
    pointerPosition: () => ({ x: 0, y: 0 }), selection: () => [],
  },
  workflow: { documentId: () => 'cg-image-filter-opaque' },
  onWorkflowLoaded: () => () => {},
  defs: {
    extend(_selector, apply) { apply(builder()); return () => {} },
  },
  ui: {
    showDialog(definition) {
      window.__nativeTitles.push(definition.title || '')
      const container = document.createElement('div')
      document.body.append(container)
      window.__nativeContainer = container
      let closed = false
      const handle = {
        close() {
          if (closed) return
          closed = true
          window.__nativeDestroy++
          definition.destroy?.()
          container.remove()
        },
      }
      definition.render(container)
      return handle
    },
  },
}

const host = new SecureExtensionHost({
  comfy, bootstrapUrl: '/guest.js', match: () => true, capabilities: [],
})
window.__host = host
window.__start = () => host.load('/extensions/cg-image-filter/image_filter.js')
window.__emit = (pack, requestId, kind, payload, timeoutSeconds) => {
  const detail = {
    pack, request_id: requestId, kind, node_id: '1', payload,
    ...(timeoutSeconds === undefined ? {} : { timeout_seconds: timeoutSeconds }),
  }
  for (const callback of listeners.get('secure-node-interaction') || []) callback(detail)
}
window.__click = (label) => {
  const record = [...host._dialogs.values()][0]
  const button = [...record.ui.__shadow.querySelectorAll('button')]
    .find((item) => item.textContent === label)
  if (!button) throw new Error('missing dialog button ' + label)
  button.click()
}
window.__dismiss = () => [...host._dialogs.values()][0].handle.close()
window.__focusTextArea = () => {
  const record = [...host._dialogs.values()][0]
  record.ui.__shadow.querySelector('textarea').focus()
}
window.__setExecuting = (value) => {
  executing = value ? node : undefined
  for (const callback of executingListeners) callback(executing)
}
window.__state = () => {
  const record = [...host._dialogs.values()][0]
  const canvas = record?.ui?.__shadow?.querySelector('canvas')
  const iframe = document.querySelector('iframe')
  return {
    dialogs: host._dialogs.size,
    mounts: host._uiByKey.size,
    requests: window.__requests,
    uploads: window.__uploads.length,
    canvasTitle: canvas?.title || '',
    countdown: [...(record?.ui?.__shadow?.querySelectorAll('span') || [])]
      .map((item) => item.textContent).find((text) => /^\\d+s$/.test(text)) || '',
    sandbox: iframe?.getAttribute('sandbox'),
    sameOriginDocument: iframe?.contentDocument !== null,
    loadResults: host.loadResults || [], packErrors: host.packErrors || [],
    notifications: window.__notifications,
    nativeTitles: window.__nativeTitles,
    nativeDestroy: window.__nativeDestroy,
    focused: document.activeElement === window.__nativeContainer,
  }
}
</script></body>`;

const server = http.createServer((request, response) => {
  const url = request.url.split('?')[0];
  const send = (body, type) => {
    response.writeHead(200, {
      'Content-Type': type,
      'Access-Control-Allow-Origin': '*',
    });
    response.end(body);
  };
  if (url === '/') return send(pageSource, 'text/html');
  if (url === '/guest.js') return send(readFileSync(path.join(frontend, 'guest.mjs')), 'text/javascript');
  if (url === '/comfy/api/v2.js') return send('export const comfy = globalThis.comfy\n', 'text/javascript');
  if (url === '/extensions/cg-image-filter/image_filter.js') {
    return send(readFileSync(path.join(root, 'js', 'image_filter.js')), 'text/javascript');
  }
  if (url.startsWith('/extensions/cg-image-filter/audio/')) return send('', 'audio/mpeg');
  if (url === '/view') return send(tinyPng, 'image/png');
  if (url.startsWith('/src/')) {
    const file = path.join(frontend, url.slice('/src/'.length));
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript');
  }
  response.writeHead(404);
  response.end('not found');
});

const choicePayload = {
  variant: 'cg-image-filter.image-choice-v1',
  images: [{ filename: 'one.png', type: 'temp', subfolder: '' }],
  count: 1, allsame: false, extras: ['a', 'b', 'c'], tip: 'choose',
  video_frames: 1, graph_id: 'root', sound: 'ding.mp3',
};
const maskPayload = {
  variant: 'cg-image-filter.mask-edit-v1',
  image: { filename: 'source.png', type: 'temp', subfolder: '' },
  extras: ['x', 'y', 'z'], tip: 'paint', sound: 'beep.mp3',
};
const textPayload = {
  variant: 'cg-image-filter.text-edit-v1',
  images: [{ filename: 'text.png', type: 'temp', subfolder: '' }],
  text: 'editable text', extras: ['', '', ''], tip: '', textareaheight: 150,
};

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error)));
  page.on('console', (message) => {
    if (message.type() === 'error') pageErrors.push(message.text());
  });
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.evaluate(() => window.__start());
  await page.waitForFunction(() => window.__state().loadResults.length === 1);
  await page.evaluate(() => window.__setExecuting(true));

  await page.evaluate((payload) => window.__emit('other-pack', 'wrong-pack', 'image-choice', payload), choicePayload);
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal((await page.evaluate(() => window.__state())).dialogs, 0);

  await page.evaluate((payload) => window.__emit(
    'cg-image-filter', 'choice', 'image-choice', payload, 30), choicePayload);
  await page.waitForFunction(() => window.__state().dialogs === 1);
  await page.waitForFunction(() => window.__state().focused === true);
  assert.equal((await page.evaluate(() => window.__state())).countdown, '30s');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => window.__state().requests.some((item) => item.request_id === 'choice'));
  await page.waitForFunction(() => window.__state().dialogs === 0);
  let state = await page.evaluate(() => window.__state());
  assert.deepEqual(state.requests.find((item) => item.request_id === 'choice').response, {
    cancelled: false, selected: [0], extras: ['a', 'b', 'c'],
  });

  // Dialog-wide shortcuts must not steal Enter from an editable child. The
  // host derives this boolean without exposing the DOM target to the worker.
  await page.evaluate((payload) => window.__emit(
    'cg-image-filter', 'editable-enter', 'prompt-await', payload, 30), textPayload);
  await page.waitForFunction(() => window.__state().dialogs === 1);
  await page.evaluate(() => window.__focusTextArea());
  await page.keyboard.press('Enter');
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.ok(!(await page.evaluate(() => window.__state())).requests
    .some((item) => item.request_id === 'editable-enter'));
  assert.equal((await page.evaluate(() => window.__state())).dialogs, 1);
  await page.evaluate(() => window.__click('Send'));
  await page.waitForFunction(() => window.__state().requests
    .some((item) => item.request_id === 'editable-enter'));
  await page.waitForFunction(() => window.__state().dialogs === 0);

  await page.evaluate((payload) => window.__emit('cg-image-filter', 'mask-reset', 'mask-edit', payload), maskPayload);
  try {
    await page.waitForFunction(() => window.__state().dialogs === 1, null, { timeout: 10_000 });
  } catch (error) {
    throw new Error(`${error}\n${JSON.stringify(await page.evaluate(() => window.__state()))}`);
  }
  await page.evaluate(() => window.__click('Reset timer'));
  await page.waitForFunction(() => window.__state().requests.some((item) => item.request_id === 'mask-reset'));
  assert.deepEqual((await page.evaluate(() => window.__state())).requests
    .find((item) => item.request_id === 'mask-reset').response, { reset: true });
  await page.waitForFunction(() => window.__state().dialogs === 0);

  await page.evaluate((payload) => window.__emit('cg-image-filter', 'mask-send', 'mask-edit', payload), maskPayload);
  await page.waitForFunction(() => window.__state().dialogs === 1);
  await page.waitForFunction(() => window.__state().canvasTitle === 'mask-ready', null, { timeout: 10_000 });
  await page.evaluate(() => window.__click('Send'));
  await page.waitForFunction(() => window.__state().uploads === 1 &&
    window.__state().requests.some((item) => item.request_id === 'mask-send'), null, { timeout: 10_000 });
  state = await page.evaluate(() => window.__state());
  assert.deepEqual(state.requests.find((item) => item.request_id === 'mask-send').response, {
    cancelled: false,
    mask: { name: 'edited-mask.png', type: 'temp', subfolder: 'cg' },
    extras: ['x', 'y', 'z'],
  });

  await page.evaluate((payload) => window.__emit('cg-image-filter', 'host-dismiss', 'image-choice', payload), choicePayload);
  await page.waitForFunction(() => window.__state().dialogs === 1);
  await page.evaluate(() => window.__dismiss());
  await page.waitForFunction(() => window.__state().requests.some((item) => item.request_id === 'host-dismiss'));
  assert.deepEqual((await page.evaluate(() => window.__state())).requests
    .find((item) => item.request_id === 'host-dismiss').response, {
      cancelled: true,
    });

  // The published lifecycle bridge projects a NodeHandle and then closes a
  // stale dialog without attempting to answer an already-expired token.
  await page.evaluate((payload) => window.__emit('cg-image-filter', 'lifecycle-close', 'image-choice', payload), choicePayload);
  await page.waitForFunction(() => window.__state().dialogs === 1);
  await page.evaluate(() => window.__setExecuting(false));
  await page.waitForFunction(() => window.__state().dialogs === 0);
  state = await page.evaluate(() => window.__state());
  assert.ok(!state.requests.some((item) => item.request_id === 'lifecycle-close'));
  assert.ok(state.nativeTitles.includes('Image Filter Test'));
  assert.equal(state.sandbox, 'allow-scripts');
  assert.equal(state.sameOriginDocument, false);
  assert.equal(state.dialogs, 0);
  assert.equal(state.mounts, 0);
  assert.equal(state.nativeDestroy, 6);
  assert.deepEqual(state.packErrors, []);
  assert.equal(state.loadResults[0].ok, true);
  assert.deepEqual(pageErrors, []);

  console.log('cg-image-filter opaque iframe harness: PASS');
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
