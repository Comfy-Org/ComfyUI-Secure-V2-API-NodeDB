/** Real browser proof for the picker/upload/gallery path through the host. */
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

const objectInfo = {
  WanMultiImageLoader: {
    display_name: 'Wan Multi-Image Loader',
    category: 'ComfyUI-Wan22FMLF',
    input: {
      required: {
        index: ['INT', { default: 0, min: 0, max: 999 }],
      },
      optional: {
        images_data: ['STRING', {}],
      },
    },
    output: ['IMAGE'],
    output_name: ['image'],
    output_node: false,
  },
};

const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

window.__pickDeclarations = []
window.__uploads = []
window.__packHooks = null
window.__hiddenByBuilder = []
window.__constraintCalls = []

function makeWidget(name, initial) {
  let value = initial
  let hidden = false
  const listeners = new Map()
  return {
    name,
    widgetType: name === 'index' ? 'number' : 'text',
    getValue() { return value },
    setValue(next) {
      const previous = value
      value = next
      for (const callback of listeners.get('change') || []) {
        callback(next, previous)
      }
    },
    getOptions() { return {} },
    setHidden(next) { hidden = Boolean(next) },
    isHidden() { return hidden },
    on(event, callback) {
      const callbacks = listeners.get(event) || []
      callbacks.push(callback)
      listeners.set(event, callbacks)
      return () => {
        const index = callbacks.indexOf(callback)
        if (index >= 0) callbacks.splice(index, 1)
      }
    },
  }
}

const indexWidget = makeWidget('index', 0)
const dataWidget = makeWidget('images_data', '')
window.__widgets = { indexWidget, dataWidget }
const widgetList = [indexWidget, dataWidget]
const emptySlots = { all() { return [] }, get() { return undefined } }
let size = { width: 180, height: 160 }
const node = {
  id: '42',
  type: 'WanMultiImageLoader',
  snapshot() {
    return {
      id: '42', type: this.type, graphId: 'root', title: this.type,
      mode: 0, collapsed: false, pinned: false,
      position: { x: 10, y: 20 }, size: { ...size }, properties: {},
    }
  },
  getProperties() { return {} },
  isSerializingWidgets() { return true },
  getSize() { return { ...size } },
  setSize(next) { size = { ...next } },
  setSizeConstraints(next) {
    window.__constraintCalls.push(structuredClone(next))
  },
  inputs: emptySlots,
  outputs: emptySlots,
  widgets: {
    all() { return widgetList },
    get(name) { return widgetList.find((widget) => widget.name === name) },
    mount(definition) {
      const container = document.createElement('div')
      container.dataset.mount = definition.name
      document.body.append(container)
      definition.render(container)
      window.__mountDefinition = definition
      return {}
    },
  },
}
window.__node = node

function builderFor(selector) {
  const hooks = {}
  return {
    hooks,
    builder: {
      hideWidget(name) { window.__hiddenByBuilder.push(name) },
      onCreated(callback) { hooks.created = callback },
      onConfigured(callback) { hooks.configured = callback },
      onRemoved(callback) { hooks.removed = callback },
    },
  }
}

const comfy = {
  backend: {
    url(value) { return new URL(value, location.origin).href },
    assetUrl(value) { return new URL(value, location.origin).href },
    async fetch(route, init) {
      if (route === '/object_info') {
        return { ok: true, status: 200, json: async () => (${JSON.stringify(objectInfo)}) }
      }
      if (route.startsWith('/secure-nodes/extensions/')) {
        return { ok: true, status: 200, json: async () => ({ capabilities: [] }) }
      }
      if (route === '/upload/image') {
        const body = Array.from(init.body || [])
        const headers = { ...(init.headers || {}) }
        window.__uploads.push({ route, method: init.method, headers, body })
        const number = window.__uploads.length
        const identity = {
          name: number === 1 ? 'opaque10.png' : 'opaque2.png',
          type: 'input',
          subfolder: 'wan22',
        }
        return {
          ok: true,
          status: 200,
          async text() { return JSON.stringify(identity) },
        }
      }
      throw new Error('unexpected backend URL: ' + route)
    },
  },
  defs: {
    extend(selector, apply) {
      const record = builderFor(selector)
      apply(record.builder)
      if (selector === 'WanMultiImageLoader') window.__packHooks = record.hooks
      return () => {}
    },
  },
  graph: {
    nodes() { return [node] },
    node(id) { return String(id) === '42' ? node : undefined },
    pointerPosition() { return { x: 0, y: 0 } },
    selection() { return [] },
  },
  workflow: { documentId() { return 'wan22fmlf-iframe' } },
  onWorkflowLoaded() { return () => {} },
}

const host = new SecureExtensionHost({
  comfy,
  bootstrapUrl: '/guest.js',
  match: () => true,
  filePicker: async (declaration) => {
    window.__pickDeclarations.push(structuredClone(declaration))
    return [
      new File([new Uint8Array([1, 2, 3])], 'first.png', { type: 'image/png' }),
      new File([new Uint8Array([4, 5])], 'second.png', { type: 'image/png' }),
    ]
  },
})
window.__host = host
window.__start = () => host.load('/extensions/wan22fmlf/wan_multi_image_loader.js')
window.__create = () => window.__packHooks.created(node, {
  restored: false, loading: false,
})
window.__clickSelect = () => {
  const ui = [...host._uiByKey.values()][0]
  const button = [...ui.__shadow.querySelectorAll('button')]
    .find((element) => element.textContent === '📁 Select')
  if (!button) throw new Error('select button was not rendered')
  button.click()
}
<\/script></body>`;

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
  if (url === '/guest.js') {
    return send(readFileSync(path.join(frontend, 'guest.mjs')), 'text/javascript');
  }
  if (url === '/comfy/api/v2.js') {
    return send('export const comfy = globalThis.comfy\n', 'text/javascript');
  }
  if (url === '/extensions/wan22fmlf/wan_multi_image_loader.js') {
    return send(readFileSync(path.join(root, 'js', 'wan_multi_image_loader.js')),
      'text/javascript');
  }
  if (url.startsWith('/src/')) {
    const file = path.join(frontend, url.slice('/src/'.length));
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript');
  }
  response.writeHead(404);
  response.end('not found');
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error)));
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForFunction(() => typeof window.__start === 'function');
  await page.evaluate(() => window.__start());
  try {
    await page.waitForFunction(() => typeof window.__packHooks?.created === 'function',
      null, { timeout: 10_000 });
  } catch (error) {
    error.message += `\n${JSON.stringify(await page.evaluate(() => ({
      loadResults: window.__host.loadResults || [],
      packErrors: window.__host.packErrors || [],
    })))}`;
    throw error;
  }

  await page.evaluate(() => window.__create());
  await page.waitForFunction(() => window.__host._uiByKey.size === 1);
  await page.evaluate(() => window.__clickSelect());
  await page.waitForFunction(() => window.__uploads.length === 2 &&
    JSON.parse(window.__widgets.dataWidget.getValue()).length === 2,
  null, { timeout: 10_000 });
  await page.waitForFunction(() => {
    const ui = [...window.__host._uiByKey.values()][0]
    return ui?.__shadow?.querySelectorAll('img').length === 2
  }, null, { timeout: 10_000 });

  const observed = await page.evaluate(() => {
    const ui = [...window.__host._uiByKey.values()][0]
    return {
      pickDeclarations: window.__pickDeclarations,
      uploads: window.__uploads,
      imagesData: JSON.parse(window.__widgets.dataWidget.getValue()),
      hidden: window.__widgets.dataWidget.isHidden(),
      hiddenByBuilder: window.__hiddenByBuilder,
      constraintCalls: window.__constraintCalls,
      imageSources: [...ui.__shadow.querySelectorAll('img')]
        .map((image) => image.src),
      sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
      packErrors: window.__host.packErrors || [],
      loadResults: window.__host.loadResults || [],
    }
  });

  assert.deepEqual(observed.pickDeclarations, [{
    mimeTypes: [
      'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp',
    ],
    extensions: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'],
    maxBytes: 16 * 1024 * 1024,
    maxFiles: 50,
    maxTotalBytes: 256 * 1024 * 1024,
    multiple: true,
  }]);
  assert.equal(observed.uploads.length, 2);
  assert.ok(observed.uploads.every((upload) => upload.method === 'POST'));
  assert.ok(observed.uploads.every((upload) =>
    upload.headers['Content-Type'].startsWith('multipart/form-data; boundary=')));
  assert.deepEqual(observed.imagesData.map((item) => item.name), [
    'opaque10.png', 'opaque2.png',
  ]);
  assert.ok(observed.imageSources.some((source) =>
    source.includes('/view?filename=opaque10.png')));
  assert.equal(observed.hidden, true);
  assert.deepEqual(observed.hiddenByBuilder, ['images_data']);
  assert.ok(observed.constraintCalls.some((value) =>
    value.minWidth === 420 && value.autoHeight === true));
  assert.equal(observed.sandbox, 'allow-scripts');
  assert.deepEqual(observed.packErrors, []);
  assert.equal(observed.loadResults.length, 1);
  assert.equal(observed.loadResults[0].ok, true);
  assert.deepEqual(pageErrors, []);

  console.log('wan22fmlf opaque iframe harness: PASS');
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
