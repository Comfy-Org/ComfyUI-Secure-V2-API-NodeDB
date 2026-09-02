/**
 * Real SecureExtensionHost proof for every frontend intent in this pack.
 *
 * The pack is evaluated inside the production allow-scripts iframe/worker
 * bridge.  Host-owned node/widget fakes expose only the published V2 facade;
 * the assertions below cover the worker-local hooks and dynamic submenu as
 * well as the confined managed-preview request which leaves the sandbox.
 */
import { existsSync, readFileSync } from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../../../../../../../')
const SRC = path.join(REPO, 'frontend/src')
const TARGET = process.env.TARGET_JS || path.join(HERE, '../web/autotrigger.js')
const PACK_SOURCE = readFileSync(TARGET, 'utf8')

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

function widget(name, value) {
  const listeners = new Map()
  const options = {}
  return {
    name,
    widgetType: 'combo',
    getValue: () => value,
    setValue(next) {
      value = next
      for (const fn of listeners.get('change') || []) fn(next)
    },
    getOptions: () => ({ ...options }),
    setOption(key, next) { options[key] = next },
    setHidden() {},
    on(event, fn) {
      const entries = listeners.get(event) || []
      entries.push(fn)
      listeners.set(event, entries)
      return () => {
        const index = entries.indexOf(fn)
        if (index >= 0) entries.splice(index, 1)
      }
    },
  }
}

function collection(values = []) {
  return {
    all: () => values,
    get: (ref) => typeof ref === 'string'
      ? values.find((value) => value.name === ref)
      : values[ref?.index],
  }
}

function node({ id, type, widgets = [], images = [], imageIndex }) {
  return {
    id: String(id),
    type,
    snapshot: () => ({
      id: String(id), type, title: type, graphId: 'graph-1', mode: 0,
      collapsed: false, pinned: false, color: '', bgColor: '', shape: 'box',
      position: { x: 0, y: 0 }, size: { width: 240, height: 120 },
    }),
    widgets: collection(widgets),
    inputs: collection(),
    outputs: collection(),
    getProperties: () => ({}),
    isSerializingWidgets: () => true,
    getOutputImages: () => images.slice(),
    getDisplayedImageIndex: () => imageIndex,
  }
}

const loaderWidget = widget('lora_name', {
  content: 'nested/demo.safetensors',
  image: '/view?filename=untrusted.png&type=temp',
})
const loader = node({
  id: 7, type: 'LoraLoaderAdvanced', widgets: [loaderWidget],
})
const output = node({
  id: 42, type: 'PreviewNode', imageIndex: 1,
  images: [
    '/view?filename=first.png&type=output',
    '/view?filename=result.png&subfolder=nested&type=output&rand=1',
  ],
})
const nodes = [loader, output]

window.__assignmentRequest = undefined
window.__previewRequest = undefined
window.__defsRefreshes = 0
window.__previewSource = undefined
window.__workflowLoaded = []
window.__settingsListeners = new Map()
window.__extensions = []

const graphFeedBuilder = { onCreated() {}, onRemoved() {} }
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url, options = {}) => {
      if (url === '/object_info') {
        return {
          ok: true,
          json: async () => ({
            LoraLoaderAdvanced: {
              display_name: 'LoRA Loader Advanced', category: 'loaders',
              input: { required: { lora_name: [['demo.safetensors'], {}] } },
              output: [],
            },
            LoraLoaderStackedAdvanced: {
              display_name: 'LoRA Loader Stacked Advanced', category: 'loaders',
              input: { required: { lora_name: [['demo.safetensors'], {}] } },
              output: [],
            },
            PreviewNode: {
              display_name: 'Preview Node', category: 'image',
              input: { required: {} }, output: ['IMAGE'],
            },
          }),
        }
      }
      if (url === '/secure-nodes/assets/model-preview') {
        window.__previewRequest = JSON.parse(options.body)
        return new Response(new Blob([new Uint8Array([82, 73, 70, 70])], {
          type: 'image/webp',
        }), { status: 200, headers: { 'Content-Type': 'image/webp' } })
      }
      if (url === '/secure-nodes/assets/assign-model-preview') {
        window.__assignmentRequest = JSON.parse(options.body)
        return new Response(JSON.stringify({ ok: true }), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
      throw new Error('unexpected backend URL: ' + url)
    },
  },
  graph: {
    nodes: () => nodes,
    node: (id) => nodes.find((candidate) => candidate.id === String(id)),
    nodesOfType: (type) => nodes.filter((candidate) => candidate.type === type),
    pointerPosition: () => ({ x: 12, y: 34 }),
    selection: () => [],
  },
  workflow: { documentId: () => 'doc-lora-auto-trigger' },
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
      const record = { selector, created: [], removed: [], menus: [] }
      const builder = {
        onCreated: (fn) => record.created.push(fn),
        onRemoved: (fn) => record.removed.push(fn),
        addMenuItem: (item) => record.menus.push(item),
      }
      apply(builder)
      window.__extensions.push(record)
      return () => {}
    },
    refresh: async () => { window.__defsRefreshes++ },
  },
  settings: {
    declare(def) { this._values ??= new Map(); this._values.set(def.id, 1) },
    get(id) { return this._values?.get(id) },
    set(id, value) {
      this._values ??= new Map()
      this._values.set(id, value)
      for (const fn of window.__settingsListeners.get(id) || []) fn(value)
    },
    onChange(id, fn) {
      const entries = window.__settingsListeners.get(id) || []
      entries.push(fn)
      window.__settingsListeners.set(id, entries)
      return () => {}
    },
  },
}

const host = new SecureExtensionHost({
  comfy,
  bootstrapUrl: '/guest.js',
  match: () => true,
  provideComboOptionPreviewSource: (source) => {
    window.__previewSource = source
  },
})
window.__host = host

window.__start = async () => {
  await host.load('/extensions/lora-auto-trigger/autotrigger.js')
  for (const fn of window.__workflowLoaded) fn()

  const loaderExtension = await waitFor(
    () => window.__extensions.find((entry) =>
      entry.selector === 'LoraLoaderAdvanced' && entry.created.length),
    'loader extension registration',
  )
  loaderExtension.created[0](loader)
  await waitFor(
    () => loaderWidget.getValue() === 'nested/demo.safetensors',
    'object-valued combo normalization',
  )
  await waitFor(
    () => loaderWidget.getOptions().useGrouping === true,
    'tree-mode widget options',
  )
  const treeOptions = loaderWidget.getOptions()

  comfy.settings.set('autotrigger.Combo++.Submenu', 2)
  await waitFor(
    () => loaderWidget.getOptions().showThumbnails === true,
    'grid-mode widget options',
  )
  const gridOptions = loaderWidget.getOptions()

  const outputMenu = await waitFor(() => {
    const extension = window.__extensions.find((entry) =>
      entry.selector === 'PreviewNode' && entry.menus.length)
    const menu = extension?.menus.find((item) => item.label === 'Save as LoRA Preview')
    if (!menu || menu.when(output) !== true) return undefined
    const children = menu.items(output)
    return children.length === 1 ? { menu, child: children[0] } : undefined
  }, 'materialized output-image submenu')
  outputMenu.child.run(output)
  await waitFor(() => window.__assignmentRequest, 'managed preview assignment')

  const anchor = document.createElement('button')
  document.body.append(anchor)
  window.__previewSource.show('nested/demo.safetensors', anchor)
  await waitFor(() => host._comboPreviewView, 'managed combo preview')
  const media = host._comboPreviewView.root.querySelector('img,video')

  return {
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    previewRegistrations: host._comboPreviews.size,
    normalizedValue: loaderWidget.getValue(),
    treeOptions,
    gridOptions,
    menuLabel: outputMenu.menu.label,
    childLabel: outputMenu.child.label,
    previewRequest: window.__previewRequest,
    assignmentRequest: window.__assignmentRequest,
    defsRefreshes: window.__defsRefreshes,
    mediaTag: media?.tagName,
    mediaBlob: media?.src?.startsWith('blob:'),
  }
}
</script></body>`

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0]
  const send = (body, type) => {
    res.writeHead(200, {
      'Content-Type': type,
      'Access-Control-Allow-Origin': '*',
    })
    res.end(body)
  }
  if (url === '/guest.js') {
    return send(readFileSync(path.join(SRC, 'guest.mjs'), 'utf8'), 'text/javascript')
  }
  if (url === '/extensions/lora-auto-trigger/autotrigger.js') {
    return send(PACK_SOURCE, 'text/javascript')
  }
  if (url === '/comfy/api/v2.js') {
    return send('export const comfy = globalThis.comfy\n', 'text/javascript')
  }
  if (url.startsWith('/src/')) {
    const file = path.join(SRC, url.slice('/src/'.length))
    if (existsSync(file)) return send(readFileSync(file, 'utf8'), 'text/javascript')
  }
  return send(PAGE, 'text/html')
})

function assert(condition, message) {
  if (!condition) throw new Error('ASSERT: ' + message)
}

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const { port } = server.address()
const browser = await chromium.launch()
const page = await browser.newPage()

try {
  await page.goto(`http://127.0.0.1:${port}/`)
  const result = await page.evaluate(() => window.__start())

  assert(result.sandbox === 'allow-scripts', 'iframe gained same-origin authority')
  assert(result.loadResults.length === 1 && result.loadResults[0].ok,
    'pack failed to load through SecureExtensionHost')
  assert(result.packErrors.length === 0,
    'pack raised in its worker: ' + JSON.stringify(result.packErrors))
  assert(result.previewRegistrations === 1,
    'managed LoRA preview policy did not register')
  assert(result.normalizedValue === 'nested/demo.safetensors',
    'object-valued combo was not normalized')
  assert(JSON.stringify(result.treeOptions) === JSON.stringify({
    useGrouping: true, showThumbnails: false, showItemNavigators: true,
  }), 'tree mode did not use the generic widget options')
  assert(JSON.stringify(result.gridOptions) === JSON.stringify({
    useGrouping: false, showThumbnails: true, showItemNavigators: true,
  }), 'grid mode did not use the generic widget options')
  assert(result.menuLabel === 'Save as LoRA Preview' &&
    result.childLabel === 'nested/demo.safetensors',
  'dynamic LoRA preview submenu was not materialized')
  assert(JSON.stringify(result.previewRequest) === JSON.stringify({
    value: 'nested/demo.safetensors',
    modelCategories: ['loras'],
    candidatePolicy: 'adjacent-model-preview-v1',
    media: ['image/png', 'image/webp', 'image/jpeg', 'video/mp4', 'video/webm'],
  }), 'managed preview registration was not projected exactly')
  assert(JSON.stringify(result.assignmentRequest) === JSON.stringify({
    category: 'loras',
    modelValue: 'nested/demo.safetensors',
    source: { filename: 'result.png', subfolder: 'nested', type: 'output' },
    policy: 'adjacent-model-preview-v1',
  }), 'host did not derive the exact managed output descriptor')
  assert(result.defsRefreshes === 1,
    'successful preview assignment did not refresh definitions')
  assert(result.mediaTag === 'IMG' && result.mediaBlob,
    'host did not render the managed preview response')

  console.log('LoRA Auto Trigger frontend worker/iframe harness: PASS')
} finally {
  await browser.close()
  server.close()
}
