/** Production opaque-iframe proof for QQ Nodes' bounded index widget. */
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../../../../../../');
const SRC = path.join(REPO, 'frontend/src');
const TARGET = process.env.TARGET_JS || path.join(HERE, '../js/extension.js');
const PACK_SOURCE = readFileSync(TARGET, 'utf8');

const PAGE = `<!doctype html><meta charset="utf-8"><body><script type="module">
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
  const listeners = new Map()
  return {
    name: def.name,
    widgetType: def.type,
    label: def.name,
    hidden: def.hidden === true,
    disabled: def.disabled === true,
    serialize: def.serialize,
    getValue: () => value,
    setValue(next) { value = next },
    setHidden(next) { this.hidden = Boolean(next) },
    setDisabled(next) { this.disabled = Boolean(next) },
    setLabel(next) { this.label = String(next) },
    getOptions: () => ({}),
    setOption() {},
    on(event, callback) {
      listeners.set(event, callback)
      return () => listeners.delete(event)
    },
    activate() { listeners.get('activate')?.() },
  }
}

function widgets(initial) {
  const values = initial.slice()
  return {
    get: (name) => values.find((value) => value.name === name),
    at: (index) => values[index],
    all: () => values.slice(),
    names: () => values.map((value) => value.name),
    add(def) {
      if (values.some((value) => value.name === def.name)) throw new Error('duplicate widget')
      const value = makeWidget(def)
      values.push(value)
      return value
    },
    remove(name) {
      const index = values.findIndex((value) => value.name === name)
      if (index >= 0) values.splice(index, 1)
    },
  }
}

const index = makeWidget({ type: 'number', name: 'index', value: 0 })
const node = {
  id: '41', type: 'XY Grid Helper', comfyClass: 'XY Grid Helper',
  graphId: 'qq-graph', widgets: widgets([index]),
  inputs: { all: () => [], names: () => [], get: () => undefined },
  outputs: { all: () => [], names: () => [], get: () => undefined },
  getProperties: () => ({}),
  snapshot: () => ({
    id: '41', type: 'XY Grid Helper', title: 'XY Grid Helper',
    graphId: 'qq-graph', mode: 0, collapsed: false, pinned: false,
    color: '', bgColor: '', shape: 'box',
    position: { x: 0, y: 0 }, size: { width: 240, height: 120 },
  }),
}

window.__extension = undefined
window.__afterRun = []
window.__hidden = []
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url !== '/object_info') throw new Error('unexpected backend URL: ' + url)
      return { ok: true, json: async () => ({
        'XY Grid Helper': {
          display_name: 'XY Grid Helper', category: 'QQNodes/XYGrid',
          input: { required: {
            row_list: ['LIST', {}], column_list: ['LIST', {}],
          }, optional: { index: ['INT', { default: 0 }] } },
          output: ['AXIS_VALUE', 'AXIS_VALUE', 'XY_GRID_CONTROL'],
        },
      }) }
    },
  },
  graph: {
    nodes: () => [node],
    node: (id) => String(id) === node.id ? node : undefined,
    nodesOfType: (type) => type === node.type ? [node] : [],
    selection: () => [],
  },
  workflow: { documentId: () => 'qq-document' },
  onWorkflowLoaded() { return () => {} },
  queue: {
    onAfterRun(callback) { window.__afterRun.push(callback); return () => {} },
  },
  defs: {
    extend(selector, apply) {
      const record = { selector, created: [], executed: [], removed: [] }
      apply({
        hideWidget: (name) => window.__hidden.push(name),
        onCreated: (callback) => record.created.push(callback),
        onExecuted: (callback) => record.executed.push(callback),
        onRemoved: (callback) => record.removed.push(callback),
      })
      window.__extension = record
      return () => {}
    },
  },
}

const host = new SecureExtensionHost({ comfy, bootstrapUrl: '/guest.js', match: () => true })

window.__start = async () => {
  await host.load('/extensions/qq/extension.js')
  const extension = await waitFor(() => window.__extension, 'extension registration')
  const afterRun = await waitFor(() => window.__afterRun[0], 'queue subscription')
  extension.created[0](node, { restored: false, loading: false })
  await waitFor(() => node.widgets.get('qq_reset'), 'reset button')
  const button = node.widgets.get('qq_reset')

  extension.executed[0](node, { raw: { total_images: [12] } })
  await waitFor(() => button.label === 'Reset - 0 of 12', 'total label')
  afterRun({ promptIds: ['one', 'two'], rejected: 0 })
  await waitFor(() => index.getValue() === 2, 'accepted-run advancement')
  const advancedLabel = button.label
  button.activate()
  await waitFor(() => index.getValue() === 0, 'reset activation')
  const resetLabel = button.label
  extension.removed[0](node)
  afterRun({ promptIds: ['three'], rejected: 0 })

  return {
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    hidden: window.__hidden,
    widgetNames: node.widgets.names(),
    buttonSerialize: button.serialize,
    advancedLabel,
    resetLabel,
    finalIndex: index.getValue(),
  }
}
</script></body>`;

const server = http.createServer((request, response) => {
  const url = request.url.split('?')[0];
  const send = (body, type) => {
    response.writeHead(200, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' });
    response.end(body);
  };
  if (url === '/guest.js') return send(readFileSync(path.join(SRC, 'guest.mjs'), 'utf8'), 'text/javascript');
  if (url === '/extensions/qq/extension.js') return send(PACK_SOURCE, 'text/javascript');
  if (url === '/comfy/api/v2.js') return send('export const comfy = globalThis.comfy\n', 'text/javascript');
  if (url.startsWith('/src/')) {
    const file = path.join(SRC, url.slice('/src/'.length));
    if (existsSync(file)) return send(readFileSync(file, 'utf8'), 'text/javascript');
  }
  return send(PAGE, 'text/html');
});

function assert(condition, message) {
  if (!condition) throw new Error('ASSERT: ' + message);
}

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const { port } = server.address();
const browser = await chromium.launch();
const page = await browser.newPage();
page.on('console', (message) => console.error('browser console:', message.text()));
page.on('pageerror', (error) => console.error('browser pageerror:', error));

try {
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForFunction(() => typeof window.__start === 'function');
  const result = await page.evaluate(() => window.__start());
  assert(result.sandbox === 'allow-scripts', 'iframe gained same-origin authority');
  assert(result.loadResults.length === 1 && result.loadResults[0].ok, 'extension did not load');
  assert(result.packErrors.length === 0, 'extension raised: ' + JSON.stringify(result.packErrors));
  assert(JSON.stringify(result.hidden) === JSON.stringify(['index']), 'index widget was not hidden');
  assert(result.widgetNames.includes('qq_reset'), 'reset button was not created');
  assert(result.buttonSerialize === false, 'reset button entered workflow serialization');
  assert(result.advancedLabel === 'Reset - 2 of 12', 'accepted runs did not advance the index');
  assert(result.resetLabel === 'Reset', 'activation did not reset the button');
  assert(result.finalIndex === 0, 'removed node kept receiving queue events');
  console.log('QQ Nodes opaque iframe harness: PASS');
} finally {
  await browser.close();
  server.close();
}
