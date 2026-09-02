/** Real allow-scripts iframe proof for the quadMoons V2 frontend. */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(here, '../../../../../../../')
const frontend = path.join(repo, 'frontend', 'src')
const extension = readFileSync(path.resolve(here, '../js/extension.js'), 'utf8')
const types = [
  'quadmoonThebutton', 'quadmoonKSampler', 'quadmoonRotationalSampler',
  'quadmoonLoadConfigs', 'quadmoonSavePrompt', 'quadmoonSaveNeg',
]
const objectInfo = Object.fromEntries(types.map((type) => [type, {
  display_name: type, category: 'QuadmoonNodes',
  input: { required: {} }, output: [],
}]))

const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

const waitFor = async (predicate, label) => {
  for (let index = 0; index < 400; index += 1) {
    const value = predicate()
    if (value) return value
    await new Promise((resolve) => setTimeout(resolve, 10))
  }
  throw new Error('timed out waiting for ' + label)
}

function makeWidget(def) {
  let value = def.value
  const events = new Map()
  return {
    name: def.name, widgetType: def.type, options: def.options ?? {},
    hidden: def.hidden === true, disabled: def.disabled === true,
    serialize: def.serialize,
    getValue: () => value,
    setValue(next) {
      const old = value; value = next
      for (const callback of events.get('change') ?? []) callback(next, old)
    },
    getOptions() { return this.options },
    setOption(name, next) { this.options[name] = next },
    setHidden(next) { this.hidden = Boolean(next) },
    setDisabled(next) { this.disabled = Boolean(next) },
    setLabel(next) { this.label = next },
    on(name, callback) {
      const values = events.get(name) ?? []; values.push(callback); events.set(name, values)
      return () => {}
    },
    hasListeners(name) { return (events.get(name) ?? []).length > 0 },
    activate() { for (const callback of events.get('activate') ?? []) callback(value) },
  }
}

function collection(initial) {
  const values = initial.map(makeWidget)
  return {
    all: () => values.slice(), names: () => values.map((item) => item.name),
    at: (index) => values[index],
    get: (name) => values.find((item) => item.name === name),
    add(def) { const item = makeWidget(def); values.push(item); return item },
    remove(name) { const i = values.findIndex((item) => item.name === name); if (i >= 0) values.splice(i, 1) },
  }
}

function makeNode(id, type, widgets = []) {
  const constraints = []
  return {
    id: String(id), type, comfyClass: type, graphId: 'quad-graph',
    widgets: collection(widgets), inputs: collection([]), outputs: collection([]),
    getProperties: () => ({}), isSerializingWidgets: () => true,
    setSizeConstraints(value) { constraints.push(structuredClone(value)) },
    snapshot: () => ({
      id: String(id), type, title: type, graphId: 'quad-graph', mode: 0,
      collapsed: false, pinned: false, color: '', bgColor: '', shape: 'box',
      position: { x: 0, y: 0 }, size: { width: 240, height: 120 }, properties: {},
    }),
    state: () => ({ constraints: structuredClone(constraints) }),
  }
}

const buttonNode = makeNode(1, 'quadmoonThebutton')
const samplerNode = makeNode(2, 'quadmoonKSampler', [
  { type: 'combo', name: 'upscale_latent', value: 'No' },
  { type: 'combo', name: 'upscale_method', value: 'nearest-exact' },
  { type: 'number', name: 'ratio', value: 1.5 },
])
const rotationNode = makeNode(3, 'quadmoonRotationalSampler', [
  { type: 'combo', name: 'upscale_latent', value: 'Yes' },
  { type: 'combo', name: 'upscale_method', value: 'bicubic' },
  { type: 'number', name: 'ratio', value: 2 },
])
const loaderNode = makeNode(4, 'quadmoonLoadConfigs', [
  { type: 'combo', name: 'config_names', value: '----NONE----', options: { values: [] } },
])
const saveNode = makeNode(5, 'quadmoonSavePrompt')
const nodes = [buttonNode, samplerNode, rotationNode, loaderNode, saveNode]
window.__extensions = []
window.__queueRuns = 0
window.__interrupts = 0
window.__storage = new Map([['quadmoons/config-names-v1', ['restored config']]])

const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (route) => {
      if (route === '/object_info') return { ok: true, json: async () => (${JSON.stringify(objectInfo)}) }
      throw new Error('unexpected backend route ' + route)
    },
  },
  graph: {
    nodes: () => nodes,
    node: (id) => nodes.find((node) => node.id === String(id)),
    nodesOfType: (type) => nodes.filter((node) => node.type === type),
    selection: () => [],
  },
  workflow: { documentId: () => 'quad-document' },
  onWorkflowLoaded: () => () => {},
  queue: {
    run: async () => { window.__queueRuns += 1; return true },
    interrupt: async () => { window.__interrupts += 1 },
  },
  storage: {
    get: async (key) => window.__storage.get(key),
    set: async (key, value) => { window.__storage.set(key, structuredClone(value)) },
  },
  defs: {
    extend(selector, apply) {
      if (typeof selector === 'function') {
        apply({ onCreated() {}, onRemoved() {} })
        return () => {}
      }
      const record = { selector, created: [], executed: [] }
      apply({
        onCreated: (callback) => record.created.push(callback),
        onExecuted: (callback) => record.executed.push(callback),
        onRemoved: () => {},
      })
      window.__extensions.push(record)
      return () => {}
    },
  },
}

const host = new SecureExtensionHost({ comfy, bootstrapUrl: '/guest.js', match: () => true })
window.__start = async () => {
  await host.load('/extensions/quadmoons/extension.js')
  const records = await waitFor(() => window.__extensions.length === 6 && window.__extensions, 'registrations')
  const recordsFor = (type) => records.filter((record) => record.selector === type)
  recordsFor('quadmoonThebutton')[0].created[0](buttonNode, { restored: false, loading: false })
  recordsFor('quadmoonKSampler')[0].created[0](samplerNode, { restored: false, loading: false })
  recordsFor('quadmoonRotationalSampler')[0].created[0](rotationNode, { restored: false, loading: false })
  recordsFor('quadmoonLoadConfigs')[0].created[0](loaderNode, { restored: false, loading: false })
  await waitFor(() => buttonNode.widgets.get('Start Queue'), 'button widgets')
  await waitFor(() => loaderNode.widgets.get('config_names').getValue() === 'restored config', 'restored config')
  await waitFor(
    () => samplerNode.widgets.get('upscale_latent').hasListeners('change'),
    'sampler change subscription',
  )

  buttonNode.widgets.get('Start Queue').activate()
  buttonNode.widgets.get('Stop Current Queue').activate()
  samplerNode.widgets.get('upscale_latent').setValue('Yes')
  await waitFor(
    () => samplerNode.widgets.get('upscale_method').hidden === false &&
      samplerNode.widgets.get('ratio').hidden === false,
    'sampler widget change',
  )
  recordsFor('quadmoonSavePrompt')[0].executed[0](saveNode, {
    raw: { config_names: ['model.safetensors - portrait'] },
  })
  await waitFor(() => loaderNode.widgets.get('config_names').getValue() === 'model.safetensors - portrait', 'saved config')
  await waitFor(() => window.__queueRuns === 1 && window.__interrupts === 1, 'queue calls')
  return {
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    queueRuns: window.__queueRuns, interrupts: window.__interrupts,
    buttonNames: buttonNode.widgets.names(),
    rebootDisabled: buttonNode.widgets.get('Reboot (unavailable in Secure Nodes)').disabled,
    samplerHidden: [samplerNode.widgets.get('upscale_method').hidden, samplerNode.widgets.get('ratio').hidden],
    rotationHidden: [rotationNode.widgets.get('upscale_method').hidden, rotationNode.widgets.get('ratio').hidden],
    configValue: loaderNode.widgets.get('config_names').getValue(),
    configOptions: loaderNode.widgets.get('config_names').options.values,
  }
}
<\/script></body>`

const server = http.createServer((request, response) => {
  const url = request.url.split('?')[0]
  const send = (body, type = 'text/javascript') => {
    response.writeHead(200, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' })
    response.end(body)
  }
  if (url === '/') return send(pageSource, 'text/html')
  if (url === '/guest.js') return send(readFileSync(path.join(frontend, 'guest.mjs')))
  if (url === '/comfy/api/v2.js') return send('export const comfy = globalThis.comfy\n')
  if (url === '/extensions/quadmoons/extension.js') return send(extension)
  if (url.startsWith('/src/')) {
    const file = path.join(frontend, url.slice('/src/'.length))
    if (existsSync(file)) return send(readFileSync(file))
  }
  response.writeHead(404); response.end('not found')
})

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (error) => { errors.push(String(error)); console.error(error) })
  page.on('console', (message) => console.error('browser:', message.text()))
  await page.goto(`http://127.0.0.1:${server.address().port}/`)
  await page.waitForFunction(() => typeof window.__start === 'function')
  const result = await page.evaluate(() => window.__start())
  assert.equal(result.sandbox, 'allow-scripts')
  assert.equal(result.loadResults.length, 1)
  assert.ok(result.loadResults[0].ok)
  assert.deepEqual(result.packErrors, [])
  assert.deepEqual(errors, [])
  assert.equal(result.queueRuns, 1)
  assert.equal(result.interrupts, 1)
  assert.deepEqual(result.buttonNames, [
    'Stop Current Queue', 'Start Queue', 'Reboot (unavailable in Secure Nodes)',
  ])
  assert.equal(result.rebootDisabled, true)
  assert.deepEqual(result.samplerHidden, [false, false])
  assert.deepEqual(result.rotationHidden, [false, false])
  assert.equal(result.configValue, 'model.safetensors - portrait')
  assert.deepEqual(result.configOptions, ['model.safetensors - portrait'])
  console.log('quadMoons opaque iframe harness: PASS')
} finally {
  await browser.close()
  await new Promise((resolve) => server.close(resolve))
}
