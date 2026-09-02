/** Real opaque-iframe proof for DebugNode-ComfyUI's bounded readouts. */
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../../../../../../');
const SRC = path.join(REPO, 'frontend/src');
const TARGET = process.env.TARGET_JS || path.join(HERE, '../js/debugnode.js');
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

const node = {
  id: '17', type: 'WTFDebugNode', comfyClass: 'WTFDebugNode',
  graphId: 'debug-graph',
  widgets: collection([]),
  inputs: collection([]),
  outputs: collection([]),
  getProperties: () => ({}),
  isSerializingWidgets: () => window.__serializeWidgets,
  setSerializeWidgets(value) { window.__serializeWidgets = value },
  setSizeConstraints(value) { window.__sizeConstraints = value },
  snapshot: () => ({
    id: '17', type: 'WTFDebugNode', title: '🐜 WTF?',
    graphId: 'debug-graph', mode: 0, collapsed: false, pinned: false,
    color: '', bgColor: '', shape: 'box',
    position: { x: 0, y: 0 }, size: { width: 240, height: 120 },
  }),
}

window.__extensions = []
window.__serializeWidgets = true
window.__sizeConstraints = undefined
const graphFeedBuilder = { onCreated() {}, onRemoved() {} }
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url === '/object_info') {
        return {
          ok: true,
          json: async () => ({
            WTFDebugNode: {
              display_name: '🐜 WTF?', category: 'debug',
              input: { required: { anything: ['*', {}] } }, output: [],
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
  workflow: { documentId: () => 'doc-debugnode' },
  onWorkflowLoaded() { return () => {} },
  defs: {
    extend(selector, apply) {
      if (typeof selector === 'function') {
        apply(graphFeedBuilder)
        return () => {}
      }
      const record = { selector, executed: [], removed: [] }
      apply({
        onExecuted: (fn) => record.executed.push(fn),
        onRemoved: (fn) => record.removed.push(fn),
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
  await host.load('/extensions/debugnode/debugnode.js')
  const extension = await waitFor(
    () => window.__extensions.find(
      (entry) => entry.selector === 'WTFDebugNode'),
    'WTFDebugNode extension registration',
  )

  extension.executed[0](node, { raw: { items: [
    { type: "<class 'str'>", len: 5, value: 'hello' },
    {
      type: 'Tensor', len: 2, shape: '[2, 3, 4]',
      firstIterItem: '<redacted tensor slice shape=[3, 4]>',
      value: '<IMAGE tensor shape=[2, 3, 4] dtype=torch.float32 device=cpu>',
    },
  ] } })
  await waitFor(() => node.widgets.get('value 1'), 'multi-item readouts')
  const multiNames = node.widgets.names()
  const tensorValue = node.widgets.get('value 1')?.getValue()
  const missingShapeDisabled = node.widgets.get('shape 0')?.disabled
  const typeReadoutDisabled = node.widgets.get('type 0')?.disabled

  extension.executed[0](node, { raw: { items: [
    { type: "<class 'dict'>", len: 0, value: '{}' },
  ] } })
  await waitFor(() => node.widgets.get('value'), 'single-item readouts')
  const singleNames = node.widgets.names()
  const singleValue = node.widgets.get('value')?.getValue()
  const textareaType = node.widgets.get('value')?.widgetType

  extension.executed[0](node, { raw: { items: 'invalid' } })
  await waitFor(() => node.widgets.names().length === 0, 'invalid-result cleanup')
  const invalidNames = node.widgets.names()

  extension.executed[0](node, { raw: { items: [
    { type: 'opaque VALUE', value: '<opaque VALUE>' },
  ] } })
  await waitFor(() => node.widgets.get('value'), 'removed-hook fixture')
  extension.removed[0](node)
  await waitFor(() => node.widgets.names().length === 0, 'removed cleanup')

  return {
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    multiNames,
    tensorValue,
    missingShapeDisabled,
    typeReadoutDisabled,
    singleNames,
    singleValue,
    textareaType,
    invalidNames,
    removedNames: node.widgets.names(),
    serializeWidgets: window.__serializeWidgets,
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
  if (url === '/extensions/debugnode/debugnode.js') {
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
  assert(result.multiNames.length === 10,
    'multi-item execution did not create exactly ten readouts');
  assert(result.multiNames[0] === 'type 0' && result.multiNames[9] === 'value 1',
    'multi-item names do not preserve the upstream numbering');
  assert(result.tensorValue.includes('<IMAGE tensor shape=[2, 3, 4]'),
    'redacted tensor summary did not reach the readout');
  assert(result.missingShapeDisabled === true,
    'an absent diagnostic field remained enabled');
  assert(result.typeReadoutDisabled === false,
    'a populated diagnostic field remained disabled');
  assert(JSON.stringify(result.singleNames) === JSON.stringify([
    'type', 'len()', 'shape', 'type of first iter() item', 'value',
  ]), 'single-item reconciliation left stale numbered widgets');
  assert(result.singleValue === '{}', 'single value did not update');
  assert(result.textareaType === 'textarea', 'value is not a textarea');
  assert(result.invalidNames.length === 0, 'invalid results left stale widgets');
  assert(result.removedNames.length === 0, 'removed node left pack widgets');
  assert(result.serializeWidgets === false, 'readouts remained serializable');
  assert(result.sizeConstraints?.autoHeight === true,
    'node was not sized to its readouts');
  console.log('debugnode opaque iframe harness: PASS');
} finally {
  await browser.close();
  server.close();
}
