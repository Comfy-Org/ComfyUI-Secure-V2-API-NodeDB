/** Real allow-scripts iframe proof for all five Prompt Reader extensions. */
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '../../../../../../../');
const SRC = path.join(REPO, 'frontend/src');
const ROOT = path.resolve(HERE, '..');
const MODULES = [
  'extractorDisplay.js', 'loaderDisplay.js', 'parameterDisplay.js',
  'promptDisplay.js', 'seedGen.js',
];
const objectInfo = Object.fromEntries([
  'SDPromptReader', 'SDBatchLoader', 'SDParameterExtractor',
  'SDParameterGenerator',
].map((type) => [type, {
  display_name: type, category: 'SD Prompt Reader', description: '',
  input: { required: {} }, output: [],
}]));

const PAGE = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

const waitFor = async (predicate, label) => {
  for (let index = 0; index < 400; index += 1) {
    const value = predicate()
    if (value) return value
    await new Promise((resolve) => setTimeout(resolve, 10))
  }
  throw new Error('timed out waiting for ' + label)
}

function widget(def) {
  let value = def.value
  const listeners = new Map()
  return {
    name: def.name, widgetType: def.type, serialize: def.serialize,
    options: { ...(def.options ?? {}) }, disabled: def.disabled === true,
    hidden: false, label: def.name,
    getValue: () => value,
    setValue(next) { value = next },
    getOptions() { return this.options },
    setOption(name, next) { this.options[name] = next },
    setHidden(next) { this.hidden = Boolean(next) },
    setDisabled(next) { this.disabled = Boolean(next) },
    setLabel(next) { this.label = String(next) },
    on(name, fn) {
      const values = listeners.get(name) ?? []
      values.push(fn)
      listeners.set(name, values)
      return () => listeners.set(name, values.filter((item) => item !== fn))
    },
    emit(name, event) { for (const fn of listeners.get(name) ?? []) fn(event) },
  }
}

function collection(initial) {
  const values = initial.map(widget)
  return {
    all: () => values.slice(), names: () => values.map((item) => item.name),
    get: (ref) => typeof ref === 'string'
      ? values.find((item) => item.name === ref)
      : values[ref?.index],
    add(def) {
      if (values.some((item) => item.name === def.name)) {
        throw new Error('duplicate widget ' + def.name)
      }
      const result = widget(def)
      values.push(result)
      return result
    },
    remove(name) {
      const index = values.findIndex((item) => item.name === name)
      if (index >= 0) values.splice(index, 1)
    },
  }
}

function slots() {
  return { all: () => [], names: () => [], get: () => undefined }
}

function makeNode(id, type, initial) {
  let size = { width: 240, height: 100 }
  const node = {
    id: String(id), type, comfyClass: type, graphId: 'prompt-reader-graph',
    widgets: collection(initial), inputs: slots(), outputs: slots(),
    getProperties: () => ({}), isSerializingWidgets: () => true,
    getSize: () => ({ ...size }), setSize(next) { size = { ...next } },
    snapshot: () => ({
      id: String(id), type, title: type, graphId: 'prompt-reader-graph', mode: 0,
      collapsed: false, pinned: false, color: '', bgColor: '', shape: 'box',
      position: { x: 0, y: 0 }, size: { ...size }, properties: {},
    }),
  }
  return node
}

const reader = makeNode(1, 'SDPromptReader', [])
const loader = makeNode(2, 'SDBatchLoader', [])
const extractor = makeNode(3, 'SDParameterExtractor', [
  { name: 'parameter', type: 'combo', value: 'parameters not loaded',
    options: { values: ['parameters not loaded'] } },
])
const generator = makeNode(4, 'SDParameterGenerator', [
  { name: 'seed', type: 'number', value: 5,
    options: { min: -3, max: 1125899906842624, step: 10 } },
  { name: 'width', type: 'number', value: 512 },
  { name: 'height', type: 'number', value: 512 },
  { name: 'aspect_ratio', type: 'combo', value: 'custom', options: { values: ['custom'] } },
])
const nodes = [reader, loader, extractor, generator]
window.__extensions = []
window.__beforeRun = []

const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url === '/object_info') return {
        ok: true, status: 200, json: async () => (${JSON.stringify(objectInfo)}),
      }
      throw new Error('unexpected backend URL: ' + url)
    },
  },
  graph: {
    nodes: () => nodes,
    node: (id) => nodes.find((node) => node.id === String(id)),
    nodesOfType: (type) => nodes.filter((node) => node.type === type),
    selection: () => [],
  },
  workflow: { documentId: () => 'prompt-reader-document' },
  onWorkflowLoaded: () => () => {},
  queue: {
    onBeforeRun(fn) { window.__beforeRun.push(fn); return () => {} },
  },
  defs: {
    extend(selector, apply) {
      const record = { selector, created: [], executed: [], removed: [], menus: [] }
      apply({
        onCreated: (fn) => record.created.push(fn),
        onExecuted: (fn) => record.executed.push(fn),
        onRemoved: (fn) => record.removed.push(fn),
        addMenuItem: (item) => record.menus.push(item),
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
  for (const name of ${JSON.stringify(MODULES)}) {
    await host.load('/extensions/prompt-reader/' + name)
  }
  await waitFor(
    () => window.__extensions.filter((entry) =>
      typeof entry.selector === 'string').length === 5,
    'five registrations: ' + JSON.stringify({
      extensions: window.__extensions.map((entry) => entry.selector),
      loads: host.loadResults,
      errors: host.packErrors || [],
    }),
  )
  for (const record of window.__extensions.filter((entry) =>
    typeof entry.selector === 'string')) {
    const node = nodes.find((candidate) => candidate.type === record.selector)
    for (const callback of record.created) callback(node, { restored: false, loading: false })
  }
  await waitFor(() => generator.widgets.get('steps_display'), 'generator widgets')
  await waitFor(() => generator.widgets.get('Randomize seed each time'), 'seed buttons')

  const executions = Object.fromEntries(window.__extensions.filter((entry) =>
    typeof entry.selector === 'string').map((record) => [
    record.selector + ':' + record.executed.length, record,
  ]))
  executions['SDPromptReader:1'].executed[0](reader, {
    raw: { text: ['positive text', 'negative text', 'Steps: 12'] },
  })
  executions['SDBatchLoader:1'].executed[0](loader, {
    raw: { text: ['set/a.png\\nset/b.webp'] },
  })
  executions['SDParameterExtractor:1'].executed[0](extractor, {
    raw: { text: [['Steps', 'Seed'], 'Steps: 12'] },
  })
  executions['SDParameterGenerator:1'].executed[0](generator, {
    raw: { text: [
      '16:9', 'SDXL 1024px', 1344, 768, 30, 0.8, 24, 6,
      { '1:1': [512, 512], '16:9': [672, 384] },
      { 'SDXL 1024px': 2 },
    ] },
  })
  await waitFor(() => reader.widgets.get('positive')?.getValue() === 'positive text',
    'reader execution')
  await waitFor(() => generator.widgets.get('width')?.getValue() === 1344,
    'generator execution')

  return {
    sandboxes: [...document.querySelectorAll('iframe')].map(
      (frame) => frame.getAttribute('sandbox')),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    registrations: window.__extensions.filter((entry) =>
      typeof entry.selector === 'string').map((record) => record.selector),
    reader: {
      positive: reader.widgets.get('positive').getValue(),
      negative: reader.widgets.get('negative').getValue(),
      setting: reader.widgets.get('setting').getValue(),
      height: reader.getSize().height,
    },
    loader: loader.widgets.get('fileList').getValue(),
    extractor: {
      value: extractor.widgets.get('value_display').getValue(),
      options: extractor.widgets.get('parameter').getOptions().values,
      selected: extractor.widgets.get('parameter').getValue(),
    },
    generator: {
      seed: generator.widgets.get('seed').getValue(),
      width: generator.widgets.get('width').getValue(),
      height: generator.widgets.get('height').getValue(),
      aspect: generator.widgets.get('aspect_ratio').getValue(),
      aspectOptions: generator.widgets.get('aspect_ratio').getOptions().values,
      steps: generator.widgets.get('steps_display').getValue(),
      aspectText: generator.widgets.get('aspect_ratio_display').getValue(),
      buttons: generator.widgets.names().filter((name) => name.includes('seed')),
    },
    menuLabels: window.__extensions.filter((entry) =>
      typeof entry.selector === 'string').flatMap((record) =>
      record.menus.map((item) => item.label)),
    beforeRunCount: window.__beforeRun.length,
  }
}
</script></body>`;

const server = http.createServer((request, response) => {
  const url = request.url.split('?')[0];
  const send = (body, type) => {
    response.writeHead(200, {
      'Content-Type': type, 'Access-Control-Allow-Origin': '*',
    });
    response.end(body);
  };
  if (url === '/') return send(PAGE, 'text/html');
  if (url === '/guest.js') {
    return send(readFileSync(path.join(SRC, 'guest.mjs')), 'text/javascript');
  }
  if (url === '/comfy/api/v2.js') {
    return send('export const comfy = globalThis.comfy\n', 'text/javascript');
  }
  if (url.startsWith('/extensions/prompt-reader/')) {
    const file = path.join(ROOT, 'js', path.basename(url));
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript');
  }
  if (url.startsWith('/src/')) {
    const file = path.join(SRC, url.slice('/src/'.length));
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript');
  }
  response.writeHead(404); response.end('not found');
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(() => typeof window.__start === 'function');
  const result = await page.evaluate(() => window.__start());
  assert.deepEqual(errors, []);
  assert.deepEqual(result.sandboxes, ['allow-scripts']);
  assert.equal(result.loadResults.length, 5);
  assert.ok(result.loadResults.every((entry) => entry.ok));
  assert.deepEqual(result.packErrors, []);
  assert.deepEqual(result.registrations.sort(), [
    'SDBatchLoader', 'SDParameterExtractor', 'SDParameterGenerator',
    'SDParameterGenerator', 'SDPromptReader',
  ]);
  assert.deepEqual(result.reader, {
    positive: 'positive text', negative: 'negative text',
    setting: 'Steps: 12', height: 300,
  });
  assert.equal(result.loader, 'set/a.png\nset/b.webp');
  assert.deepEqual(result.extractor, {
    value: 'Steps: 12', options: ['Steps', 'Seed'], selected: 'Steps',
  });
  assert.equal(result.generator.seed, -1);
  assert.equal(result.generator.width, 1344);
  assert.equal(result.generator.height, 768);
  assert.equal(result.generator.aspect, '16:9 - 1344x768');
  assert.ok(result.generator.aspectOptions.includes('16:9 - 1344x768'));
  assert.ok(result.generator.steps.includes('Refiner start at step: 24'));
  assert.ok(result.generator.aspectText.includes('1344 x 768'));
  assert.deepEqual(result.generator.buttons.sort(), [
    '(Use last queued seed)', 'New fixed random seed',
    'Randomize seed each time', 'seed',
  ]);
  assert.deepEqual(result.menuLabels.sort(), [
    'Randomize seed each time', 'Use last queued seed',
  ]);
  assert.equal(result.beforeRunCount, 1);
  console.log('Prompt Reader frontend opaque iframe harness: PASS');
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
