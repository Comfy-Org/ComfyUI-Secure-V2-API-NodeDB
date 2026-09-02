/** Real opaque-iframe proof for lora-info's two safe readouts. */
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../../../../../../');
const SRC = path.join(REPO, 'frontend/src');
const TARGET = process.env.TARGET_JS || path.join(HERE, '../js/index.js');
const PACK_SOURCE = readFileSync(TARGET, 'utf8');

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
  return {
    name: def.name,
    widgetType: def.type,
    disabled: def.disabled === true,
    getValue: () => value,
    setValue(next) { value = next },
    getOptions: () => ({}),
    setOption() {},
    setHidden() {},
    on() { return () => {} },
  }
}

function collection(initial) {
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

const loraName = makeWidget({
  type: 'combo', name: 'lora_name', value: 'folder/demo.safetensors',
})
const node = {
  id: '7', type: 'LoraInfo', comfyClass: 'LoraInfo', graphId: 'graph-1',
  widgets: collection([loraName]),
  inputs: collection([]),
  outputs: collection([]),
  getProperties: () => ({}),
  isSerializingWidgets: () => true,
  setSizeConstraints(value) { window.__sizeConstraints = value },
  snapshot: () => ({
    id: '7', type: 'LoraInfo', title: 'Lora Info', graphId: 'graph-1',
    mode: 0, collapsed: false, pinned: false, color: '', bgColor: '',
    shape: 'box', position: { x: 0, y: 0 },
    size: { width: 240, height: 120 },
  }),
}

window.__extensions = []
window.__sizeConstraints = undefined
window.__workflowLoaded = []
const graphFeedBuilder = { onCreated() {}, onRemoved() {} }
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url === '/object_info') {
        return {
          ok: true,
          json: async () => ({
            LoraInfo: {
              display_name: 'Lora Info',
              category: 'jitcoder',
              input: { required: { lora_name: [['folder/demo.safetensors'], {}] } },
              output: ['STRING', 'STRING', 'STRING'],
            },
          }),
        }
      }
      throw new Error('unexpected backend URL: ' + url)
    },
  },
  graph: {
    nodes: () => [node],
    node: (id) => String(id) === node.id ? node : undefined,
    nodesOfType: (type) => type === node.type ? [node] : [],
    selection: () => [],
  },
  workflow: { documentId: () => 'doc-lora-info' },
  onWorkflowLoaded(fn) {
    window.__workflowLoaded.push(fn)
    return () => {}
  },
  defs: {
    extend(selector, apply) {
      if (typeof selector === 'function') {
        apply(graphFeedBuilder)
        return () => {}
      }
      const record = { selector, created: [], executed: [] }
      apply({
        onCreated: (fn) => record.created.push(fn),
        onExecuted: (fn) => record.executed.push(fn),
      })
      window.__extensions.push(record)
      return () => {}
    },
  },
}

const host = new SecureExtensionHost({
  comfy,
  bootstrapUrl: '/guest.js',
  match: () => true,
})
window.__host = host

window.__start = async () => {
  await host.load('/extensions/lora-info/index.js')
  const extension = await waitFor(
    () => window.__extensions.find((entry) => entry.selector === 'LoraInfo'),
    'LoraInfo extension registration',
  )
  extension.created[0](node)
  await waitFor(() => node.widgets.get('Base Model'), 'Base Model readout')
  extension.executed[0](node, {
    raw: {
      model: ['SDXL 1.0'],
      text: ['URL: https://civitai.com/models/123\\nTriggers: alpha,beta'],
    },
  })
  await waitFor(
    () => node.widgets.get('output')?.getValue().includes('Triggers:'),
    'execution readout update',
  )
  return {
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    names: node.widgets.names(),
    model: node.widgets.get('Base Model')?.getValue(),
    output: node.widgets.get('output')?.getValue(),
    modelDisabled: node.widgets.get('Base Model')?.disabled,
    outputDisabled: node.widgets.get('output')?.disabled,
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
  if (url === '/extensions/lora-info/index.js') {
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
  assert(JSON.stringify(result.names) === JSON.stringify([
    'lora_name', 'Base Model', 'output',
  ]), 'safe readouts were not added exactly once');
  assert(result.model === 'SDXL 1.0', 'Base Model readout did not update');
  assert(result.output.includes('Triggers: alpha,beta'),
    'details readout did not update');
  assert(result.modelDisabled && result.outputDisabled,
    'readout widgets remained editable');
  assert(result.sizeConstraints?.autoHeight === true,
    'node was not sized to its readouts');
  console.log('lora-info opaque iframe harness: PASS');
} finally {
  await browser.close();
  server.close();
}
