/** Opaque-iframe proof for the secure generation-id frontend. */
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../../../../../../');
const SRC = path.join(REPO, 'frontend/src');
const TARGET = process.env.TARGET_JS || path.join(HERE, '../js/show_generation_id.js');
const PACK_SOURCE = readFileSync(TARGET, 'utf8');
const TYPES = [
  'LumaText2Video',
  'LumaImage2Video',
  'LumaInterpolateGenerations',
  'LumaExtendGeneration',
  'LumaImageGeneration',
  'LumaModifyImage',
];

const PAGE = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

const waitFor = async (predicate, label) => {
  for (let i = 0; i < 300; i++) {
    const value = predicate()
    if (value) return value
    await new Promise((resolve) => setTimeout(resolve, 10))
  }
  throw new Error('timed out waiting for ' + label)
}

function makeWidget(def) {
  let value = def.value
  let disabled = def.disabled === true
  return {
    name: def.name,
    widgetType: def.type,
    get disabled() { return disabled },
    getValue: () => value,
    setValue(next) { value = next },
    setDisabled(next) { disabled = next === true },
    getOptions: () => ({}),
    setOption() {},
    setHidden() {},
    on() { return () => {} },
  }
}

function collection(initial) {
  const values = initial.slice()
  return {
    get length() { return values.length },
    all: () => values.slice(),
    names: () => values.map((value) => value.name),
    at: (index) => values[index],
    get: (ref) => typeof ref === 'string'
      ? values.find((value) => value.name === ref)
      : values[ref?.index],
    add(def) {
      if (values.some((value) => value.name === def.name)) {
        throw new Error('duplicate widget ' + def.name)
      }
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

const filename = makeWidget({ type: 'text', name: 'filename', value: '' })
const node = {
  id: '7', type: 'LumaText2Video', comfyClass: 'LumaText2Video',
  graphId: 'graph-1', widgets: collection([filename]),
  inputs: collection([]), outputs: collection([]),
  getProperties: () => ({}),
  isSerializingWidgets: () => true,
  setSizeConstraints(value) { window.__sizeConstraints = value },
  snapshot: () => ({
    id: '7', type: 'LumaText2Video', comfyClass: 'LumaText2Video',
    title: 'Text to Video', graphId: 'graph-1', mode: 0,
    collapsed: false, pinned: false, color: '', bgColor: '', shape: 'box',
    position: { x: 0, y: 0 }, size: { width: 240, height: 120 },
  }),
}

window.__extensions = []
window.__executing = []
window.__sizeConstraints = undefined
const graphFeedBuilder = { onCreated() {}, onRemoved() {} }
const objectInfo = Object.fromEntries(${JSON.stringify(TYPES)}.map((type) => [
  type,
  {
    name: type, display_name: type, category: 'LumaAI',
    input: { required: {} }, output: [],
  },
]))
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url === '/object_info') {
        return { ok: true, json: async () => objectInfo }
      }
      throw new Error('unexpected backend URL: ' + url)
    },
  },
  graph: {
    nodes: () => [node], node: (id) => String(id) === node.id ? node : undefined,
    nodesOfType: (type) => type === node.type ? [node] : [], selection: () => [],
  },
  workflow: { documentId: () => 'doc-luma' },
  onWorkflowLoaded() { return () => {} },
  executingNode() { return undefined },
  onExecutingNodeChanged(fn) { window.__executing.push(fn); return () => {} },
  defs: {
    extend(selector, apply) {
      if (typeof selector === 'function') {
        apply(graphFeedBuilder)
        return () => {}
      }
      const record = { selector, executed: [] }
      apply({ onExecuted: (fn) => record.executed.push(fn) })
      window.__extensions.push(record)
      return () => {}
    },
  },
}

const host = new SecureExtensionHost({
  comfy, bootstrapUrl: '/guest.js', match: () => true,
})

window.__start = async () => {
  await host.load('/extensions/luma/show_generation_id.js')
  const extension = await waitFor(
    () => window.__extensions.find((entry) => entry.selector === 'LumaText2Video'),
    'LumaText2Video extension registration',
  )
  const executing = await waitFor(() => window.__executing[0], 'executing listener')
  executing(node)
  await waitFor(
    () => node.widgets.get('gen_output')?.getValue() === 'generating...',
    'running readout',
  )
  extension.executed[0](node, { text: ['generation-123'], raw: {} })
  await waitFor(
    () => node.widgets.get('gen_output')?.getValue() === 'generation-123',
    'generation readout',
  )
  return {
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    loadResults: host.loadResults, packErrors: host.packErrors || [],
    selectors: window.__extensions.map((entry) => entry.selector).sort(),
    names: node.widgets.names(),
    value: node.widgets.get('gen_output')?.getValue(),
    disabled: node.widgets.get('gen_output')?.disabled,
    sizeConstraints: window.__sizeConstraints,
  }
}
</script></body>`;

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  const send = (body, type) => {
    res.writeHead(200, {
      'Content-Type': type,
      'Access-Control-Allow-Origin': '*',
    });
    res.end(body);
  };
  if (url === '/guest.js') {
    return send(readFileSync(path.join(SRC, 'guest.mjs'), 'utf8'), 'text/javascript');
  }
  if (url === '/extensions/luma/show_generation_id.js') {
    return send(PACK_SOURCE, 'text/javascript');
  }
  if (url === '/comfy/api/v2.js') {
    return send('export const comfy = globalThis.comfy\n', 'text/javascript');
  }
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
  assert(result.loadResults.length === 1 && result.loadResults[0].ok,
    'pack failed to load through SecureExtensionHost');
  assert(result.packErrors.length === 0,
    'pack raised in its guest: ' + JSON.stringify(result.packErrors));
  assert(JSON.stringify(result.selectors) === JSON.stringify(TYPES.slice().sort()),
    'the six source generation-readout targets were not registered');
  assert(JSON.stringify(result.names) === JSON.stringify(['filename', 'gen_output']),
    'the generation readout was not added exactly once');
  assert(result.value === 'generation-123', 'execution readout did not update');
  assert(result.disabled, 'generation readout remained editable');
  assert(result.sizeConstraints?.autoHeight === true, 'node was not resized');
  console.log('lumaai opaque iframe harness: PASS');
} finally {
  await browser.close();
  server.close();
}
