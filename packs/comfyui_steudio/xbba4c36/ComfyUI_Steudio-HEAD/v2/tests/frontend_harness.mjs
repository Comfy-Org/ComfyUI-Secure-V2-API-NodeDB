/** Real allow-scripts iframe proof for Steudio's readout extension. */
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../../../../../../');
const FRONTEND = path.join(REPO, 'frontend/src');
const PACK_ROOT = path.resolve(HERE, '..');
const TYPES = ['Ratio Calculator', 'Sequence Generator', 'Display UI'];

const objectInfo = Object.fromEntries(TYPES.map((type) => [type, {
  display_name: type,
  category: 'Steudio/Utils',
  input: { required: {} },
  output: type === 'Display UI' ? [] : ['STRING'],
}]));

const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

const waitFor = async (predicate, label) => {
  for (let index = 0; index < 300; index += 1) {
    const value = predicate()
    if (value) return value
    await new Promise((resolve) => setTimeout(resolve, 10))
  }
  throw new Error('timed out waiting for ' + label)
}

function makeWidget(def) {
  let value = def.value
  return {
    name: def.name,
    widgetType: def.type,
    disabled: def.disabled === true,
    serialize: def.serialize,
    options: def.options ?? {},
    hidden: def.hidden === true,
    getValue: () => value,
    setValue(next) { value = next },
    getOptions() { return this.options },
    setOption(name, next) { this.options[name] = next },
    setHidden(next) { this.hidden = Boolean(next) },
    setDisabled(next) { this.disabled = Boolean(next) },
    on() { return () => {} },
  }
}

function collection(initial = []) {
  const values = initial.slice()
  return {
    all: () => values.slice(),
    names: () => values.map((value) => value.name),
    get: (ref) => typeof ref === 'string'
      ? values.find((value) => value.name === ref)
      : values[ref?.index],
    add(def) {
      if (values.some((value) => value.name === def.name)) {
        throw new Error('duplicate widget ' + def.name)
      }
      const widget = makeWidget(def)
      values.push(widget)
      return widget
    },
    remove(name) {
      const index = values.findIndex((value) => value.name === name)
      if (index >= 0) values.splice(index, 1)
    },
  }
}

function makeNode(id, type) {
  const widgets = collection()
  return {
    id: String(id), type, comfyClass: type, graphId: 'steudio-graph',
    widgets, inputs: collection(), outputs: collection(),
    getProperties: () => ({}), isSerializingWidgets: () => true,
    setSizeConstraints(value) { this.constraints = structuredClone(value) },
    snapshot: () => ({
      id: String(id), type, title: type, graphId: 'steudio-graph', mode: 0,
      collapsed: false, pinned: false, color: '', bgColor: '', shape: 'box',
      position: { x: 0, y: 0 }, size: { width: 240, height: 120 },
    }),
  }
}

const types = ${JSON.stringify(TYPES)}
const nodes = types.map((type, index) => makeNode(index + 1, type))
window.__extensions = []
const graphFeedBuilder = { onCreated() {}, onRemoved() {} }
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url === '/object_info') return {
        ok: true, status: 200, json: async () => (${JSON.stringify(objectInfo)}),
      }
      if (url.startsWith('/secure-nodes/extensions/')) return {
        ok: true, status: 200, json: async () => ({ capabilities: [] }),
      }
      throw new Error('unexpected backend URL: ' + url)
    },
  },
  graph: {
    nodes: () => nodes,
    node: (id) => nodes.find((node) => node.id === String(id)),
    nodesOfType: (type) => nodes.filter((node) => node.type === type),
    selection: () => [], pointerPosition: () => ({ x: 0, y: 0 }),
  },
  workflow: { documentId: () => 'steudio-document' },
  onWorkflowLoaded: () => () => {},
  defs: {
    extend(selector, apply) {
      if (typeof selector === 'function') {
        apply(graphFeedBuilder)
        return () => {}
      }
      const record = { selector, created: [], executed: [] }
      apply({
        onCreated: (callback) => record.created.push(callback),
        onExecuted: (callback) => record.executed.push(callback),
      })
      window.__extensions.push(record)
      return () => {}
    },
  },
}

const host = new SecureExtensionHost({
  comfy, bootstrapUrl: '/guest.js', match: () => true,
})
window.__host = host
window.__start = async () => {
  await host.load('/extensions/steudio/showText.js')
  const extensions = await waitFor(
    () => window.__extensions.length === 3 ? window.__extensions : undefined,
    'Steudio extension registration',
  )
  for (const node of nodes) {
    extensions.find((entry) => entry.selector === node.type).created[0](node, {
      restored: false, loading: false,
    })
  }
  await waitFor(
    () => nodes.every((node) => node.widgets.get('text_box')),
    'readout widgets',
  )
  extensions.find((entry) => entry.selector === nodes[0].type).executed[0](nodes[0], {
    raw: { text: '16:9\\n2,073,600 pixels' },
  })
  extensions.find((entry) => entry.selector === nodes[1].type).executed[0](nodes[1], {
    raw: { text: '3 INT: [0, 0, 1]\\n3 FLOAT: [0.0, 0.5, 1.0]' },
  })
  extensions.find((entry) => entry.selector === nodes[2].type).executed[0](
    nodes[2], { raw: { text: ['alpha', 'beta'] } },
  )
  await waitFor(
    () => nodes[2].widgets.get('text_box')?.getValue()?.includes('beta'),
    'executed readouts',
  )
  extensions.find((entry) => entry.selector === nodes[2].type).created[0](
    nodes[2], { restored: true, loading: false },
  )
  return {
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    selectors: extensions.map((entry) => entry.selector),
    values: nodes.map((node) => node.widgets.get('text_box').getValue()),
    widgetCounts: nodes.map((node) => node.widgets.names().length),
    serialized: nodes.map((node) => node.widgets.get('text_box').serialize),
    disabled: nodes.map((node) => node.widgets.get('text_box').disabled),
    constraints: nodes.map((node) => node.constraints),
  }
}
<\/script></body>`;

const server = http.createServer((request, response) => {
  const url = request.url.split('?')[0];
  const send = (body, type) => {
    response.writeHead(200, {
      'Content-Type': type, 'Access-Control-Allow-Origin': '*',
    });
    response.end(body);
  };
  if (url === '/') return send(pageSource, 'text/html');
  if (url === '/guest.js') {
    return send(readFileSync(path.join(FRONTEND, 'guest.mjs')), 'text/javascript');
  }
  if (url === '/comfy/api/v2.js') {
    return send('export const comfy = globalThis.comfy\n', 'text/javascript');
  }
  if (url === '/extensions/steudio/showText.js') {
    return send(readFileSync(path.join(PACK_ROOT, 'js/showText.js')), 'text/javascript');
  }
  if (url.startsWith('/src/')) {
    const file = path.join(FRONTEND, url.slice('/src/'.length));
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript');
  }
  response.writeHead(404);
  response.end('not found');
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('console', (message) => console.error('browser console:', message.text()));
  page.on('pageerror', (error) => {
    pageErrors.push(String(error));
    console.error('browser pageerror:', String(error));
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(() => typeof window.__start === 'function');
  const result = await page.evaluate(() => window.__start());
  assert.deepEqual(pageErrors, []);
  assert.equal(result.sandbox, 'allow-scripts');
  assert.equal(result.loadResults.length, 1);
  assert.ok(result.loadResults[0].ok);
  assert.deepEqual(result.packErrors, []);
  assert.deepEqual(result.selectors, TYPES);
  assert.deepEqual(result.widgetCounts, [1, 1, 1]);
  assert.deepEqual(result.serialized, [true, true, true]);
  assert.deepEqual(result.disabled, [true, true, true]);
  assert.equal(result.values[0], '16:9\n2,073,600 pixels');
  assert.equal(result.values[1], '3 INT: [0, 0, 1]\n3 FLOAT: [0.0, 0.5, 1.0]');
  assert.equal(result.values[2], 'alpha\n\nbeta\n');
  assert.deepEqual(result.constraints, [
    { autoHeight: true }, { autoHeight: true }, { autoHeight: true },
  ]);
  console.log('steudio frontend opaque iframe harness: PASS');
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
