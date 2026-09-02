/** Real allow-scripts iframe/worker proof for both frontend registrations. */
import { existsSync, readFileSync } from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../../../../../../../')
const SRC = path.join(REPO, 'frontend/src')
const HELP = readFileSync(process.env.HELP_JS || path.join(HERE, '../js/help_popup.js'), 'utf8')
const MASK = readFileSync(process.env.MASK_JS || path.join(HERE, '../js/api_key_mask.js'), 'utf8')

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
  const options = {}
  return {
    name,
    widgetType: 'text',
    getValue: () => value,
    setValue: (next) => { value = next },
    getOptions: () => ({ ...options }),
    setOption: (key, next) => { options[key] = next },
    setHidden() {}, setDisabled() {}, setLabel() {},
    on: () => () => {},
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

function node(id, type, widgets = []) {
  return {
    id: String(id), type,
    snapshot: () => ({
      id: String(id), type, title: type, graphId: 'graph-1', mode: 0,
      collapsed: false, pinned: false, color: '', bgColor: '', shape: 'box',
      position: { x: 0, y: 0 }, size: { width: 240, height: 120 },
    }),
    widgets: collection(widgets), inputs: collection(), outputs: collection(),
    getProperties: () => ({}), isSerializingWidgets: () => true,
    getOutputImages: () => [], getDisplayedImageIndex: () => undefined,
  }
}

const keyWidget = widget('ollama_api_key', 'workflow-secret')
const searchNode = node(7, 'OllamaTool_WebSearch', [keyWidget])
const agentNode = node(8, 'OllamaAgent')
const nodes = [searchNode, agentNode]
window.__extensions = []
window.__workflowLoaded = []
window.__dialog = undefined

const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url !== '/object_info') throw new Error('unexpected backend URL: ' + url)
      return {
        ok: true,
        json: async () => ({
          OllamaTool_WebSearch: {
            display_name: 'Web Search', category: 'Ollama/Tools',
            description: 'Search current information safely.',
            input: { required: {}, optional: {} }, output: ['OLLAMA_TOOL'],
          },
          OllamaAgent: {
            display_name: 'Ollama Agent', category: 'Ollama/Agent',
            description: 'Run an agent loop.', input: { required: {} },
            output: ['STRING'],
          },
        }),
      }
    },
  },
  graph: {
    nodes: () => nodes,
    node: (id) => nodes.find((candidate) => candidate.id === String(id)),
    nodesOfType: (type) => nodes.filter((candidate) => candidate.type === type),
    selection: () => [], pointerPosition: () => ({ x: 0, y: 0 }),
  },
  workflow: { documentId: () => 'ollama-describer-doc' },
  onWorkflowLoaded(fn) { window.__workflowLoaded.push(fn); return () => {} },
  defs: {
    extend(selector, apply) {
      const record = { selector, created: [], removed: [], menus: [], hidden: [] }
      const builder = {
        def: undefined,
        onCreated: (fn) => record.created.push(fn),
        onRemoved: (fn) => record.removed.push(fn),
        addMenuItem: (item) => record.menus.push(item),
        hideWidget: (name) => record.hidden.push(name),
      }
      apply(builder)
      window.__extensions.push(record)
      return () => {}
    },
  },
  ui: {
    showDialog(def) {
      const container = document.createElement('section')
      document.body.appendChild(container)
      def.render(container)
      window.__dialog = { title: def.title, container }
      return { close: () => container.remove() }
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
  await host.load('/extensions/ollama-describer/help_popup.js')
  for (const fn of window.__workflowLoaded) fn()

  const help = await waitFor(
    () => window.__extensions.find((entry) =>
      entry.selector === 'OllamaAgent' &&
      entry.menus.some((item) => item.label === 'Show Ollama node help')),
    'help menu registration',
  )
  const menu = help.menus.find((item) => item.label === 'Show Ollama node help')
  await new Promise((resolve) => setTimeout(resolve, 100))
  menu.run(agentNode)
  const dialogPanel = await waitFor(
    () => host.inspect().panels.find((panel) => panel.key.includes(':dialog:')),
    'host help dialog',
  )

  await host.load('/extensions/ollama-describer/api_key_mask.js')
  const mask = await waitFor(
    () => window.__extensions.find((entry) =>
      entry.selector === 'OllamaTool_WebSearch' &&
      entry.hidden.includes('ollama_api_key')),
    'API-key widget registration',
  )

  return {
    sandboxes: [...document.querySelectorAll('iframe')].map(
      (frame) => frame.getAttribute('sandbox')),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    hiddenWidget: mask.hidden[0],
    secretValue: keyWidget.getValue(),
    menuLabel: menu.label,
    dialogTitle: window.__dialog?.title,
    dialogText: dialogPanel.text,
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
  if (url === '/extensions/ollama-describer/help_popup.js') {
    return send(HELP, 'text/javascript')
  }
  if (url === '/extensions/ollama-describer/api_key_mask.js') {
    return send(MASK, 'text/javascript')
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
  assert(result.sandboxes.length === 1, 'expected one iframe for the pack')
  assert(result.sandboxes.every((value) => value === 'allow-scripts'),
    'frontend iframe gained same-origin authority')
  assert(result.loadResults.length === 2 && result.loadResults.every((item) => item.ok),
    'frontend module failed to load through SecureExtensionHost')
  assert(result.packErrors.length === 0,
    'pack raised in its worker: ' + JSON.stringify(result.packErrors))
  assert(result.hiddenWidget === 'ollama_api_key', 'legacy credential widget was not hidden')
  assert(result.secretValue === 'workflow-secret', 'frontend changed the widget value')
  assert(result.menuLabel === 'Show Ollama node help', 'help menu is missing')
  assert(result.dialogTitle === 'Ollama Agent', 'wrong help title')
  assert(result.dialogText === 'Run an agent loop.', 'description was not text-only')
  console.log('Ollama Describer frontend allow-scripts iframe harness: PASS')
} finally {
  await browser.close()
  await new Promise((resolve) => server.close(resolve))
}
