/** Real allow-scripts iframe proof for both Y7 frontend registrations. */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(here, '../../../../../../../')
const frontend = path.join(repo, 'frontend', 'src')
const root = path.resolve(here, '..')

const objectInfo = {
  Y7_SideBySide: {
    display_name: 'Y7 SBS (Image)', category: 'Y7 SBS',
    description: 'Convert one image and depth map to stereoscopic 3D.',
    input: { required: {} }, output: ['IMAGE'],
  },
  Y7_VideoSideBySide: {
    display_name: 'Y7 SBS (Video)', category: 'Y7 SBS',
    description: 'Convert video frames and depth maps to stereoscopic 3D.',
    input: { required: {} }, output: ['IMAGE'],
  },
}

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

function collection() {
  return { all: () => [], get: () => undefined }
}

function makeNode(id, type, initial) {
  let size = { ...initial }
  const constraints = []
  return {
    id: String(id), type,
    snapshot: () => ({
      id: String(id), type, title: type, graphId: 'graph-1', mode: 0,
      collapsed: false, pinned: false, color: '', bgColor: '', shape: 'box',
      position: { x: 0, y: 0 }, size: { ...size }, properties: {},
    }),
    getProperties: () => ({}), isSerializingWidgets: () => true,
    getSize: () => ({ ...size }), setSize: (next) => { size = { ...next } },
    setSizeConstraints: (next) => constraints.push(structuredClone(next)),
    widgets: collection(), inputs: collection(), outputs: collection(),
    state: () => ({ size: { ...size }, constraints: structuredClone(constraints) }),
  }
}

const imageNode = makeNode(7, 'Y7_SideBySide', { width: 180, height: 90 })
const videoNode = makeNode(8, 'Y7_VideoSideBySide', { width: 200, height: 100 })
const nodes = [imageNode, videoNode]
window.__extensions = []
window.__dialog = undefined

const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (route) => {
      if (route === '/object_info') return {
        ok: true, status: 200, json: async () => (${JSON.stringify(objectInfo)}),
      }
      if (route.startsWith('/secure-nodes/extensions/')) return {
        ok: true, status: 200, json: async () => ({ capabilities: [] }),
      }
      throw new Error('unexpected backend route ' + route)
    },
  },
  graph: {
    nodes: () => nodes,
    node: (id) => nodes.find((candidate) => candidate.id === String(id)),
    nodesOfType: (type) => nodes.filter((candidate) => candidate.type === type),
    selection: () => [], pointerPosition: () => ({ x: 0, y: 0 }),
  },
  workflow: { documentId: () => 'y7-sbs-document' },
  onWorkflowLoaded: () => () => {},
  defs: {
    extend(selector, apply) {
      const record = { selector, created: [], menus: [] }
      apply({
        onCreated: (callback) => record.created.push(callback),
        onRemoved: () => {},
        addMenuItem: (item) => record.menus.push(item),
      })
      window.__extensions.push(record)
      return () => {}
    },
  },
  ui: {
    showDialog(definition) {
      const container = document.createElement('section')
      document.body.appendChild(container)
      definition.render(container)
      window.__dialog = { title: definition.title, text: container.textContent }
      return { close: () => container.remove() }
    },
  },
}

const host = new SecureExtensionHost({
  comfy, bootstrapUrl: '/guest.js', match: () => true,
})
window.__host = host
window.__start = async () => {
  await host.load('/extensions/y7-sbs/sbs.js')
  await host.load('/extensions/y7-sbs/help_popup.js')
  const imageSize = await waitFor(
    () => window.__extensions.find((item) =>
      item.selector === 'Y7_SideBySide' && item.created.length > 0),
    'image sizing registration',
  )
  const videoSize = await waitFor(
    () => window.__extensions.find((item) =>
      item.selector === 'Y7_VideoSideBySide' && item.created.length > 0),
    'video sizing registration',
  )
  imageSize.created[0](imageNode, { restored: false, loading: false })
  videoSize.created[0](videoNode, { restored: false, loading: false })

  const help = await waitFor(
    () => window.__extensions.find((item) =>
      item.selector === 'Y7_SideBySide' &&
      item.menus.some((menu) => menu.label === 'Show Y7 SBS help')),
    'help menu registration',
  )
  help.menus[0].run(imageNode)
  await waitFor(() => window.__dialog, 'help dialog')
  const dialogPanel = await waitFor(
    () => host.inspect().panels.find((panel) => panel.key.includes(':dialog:')),
    'host-mounted help content',
  )

  return {
    sandboxes: [...document.querySelectorAll('iframe')].map(
      (frame) => frame.getAttribute('sandbox')),
    loadResults: host.loadResults,
    packErrors: host.packErrors || [],
    image: imageNode.state(), video: videoNode.state(),
    menuLabel: help.menus[0].label,
    dialog: window.__dialog,
    dialogText: dialogPanel.text,
  }
}
<\/script></body>`

const server = http.createServer((request, response) => {
  const url = request.url.split('?')[0]
  const send = (body, type) => {
    response.writeHead(200, {
      'Content-Type': type,
      'Access-Control-Allow-Origin': '*',
    })
    response.end(body)
  }
  if (url === '/') return send(pageSource, 'text/html')
  if (url === '/guest.js') {
    return send(readFileSync(path.join(frontend, 'guest.mjs')), 'text/javascript')
  }
  if (url === '/comfy/api/v2.js') {
    return send('export const comfy = globalThis.comfy\n', 'text/javascript')
  }
  if (url === '/extensions/y7-sbs/sbs.js') {
    return send(readFileSync(path.join(root, 'js', 'sbs.js')), 'text/javascript')
  }
  if (url === '/extensions/y7-sbs/help_popup.js') {
    return send(readFileSync(path.join(root, 'js', 'help_popup.js')), 'text/javascript')
  }
  if (url.startsWith('/src/')) {
    const file = path.join(frontend, url.slice('/src/'.length))
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript')
  }
  response.writeHead(404)
  response.end('not found')
})

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const browser = await chromium.launch({ headless: true })

try {
  const page = await browser.newPage()
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(String(error)))
  await page.goto(`http://127.0.0.1:${server.address().port}/`)
  await page.waitForTimeout(500)
  assert.deepEqual(pageErrors, [])
  await page.waitForFunction(() => typeof window.__start === 'function', null,
    { timeout: 10_000 })
  const result = await page.evaluate(() => window.__start())
  assert.equal(result.sandboxes.length, 1)
  assert.deepEqual(result.sandboxes, ['allow-scripts'])
  assert.equal(result.loadResults.length, 2)
  assert.ok(result.loadResults.every((item) => item.ok))
  assert.deepEqual(result.packErrors, [])
  assert.deepEqual(pageErrors, [])
  assert.deepEqual(result.image.size, { width: 240, height: 150 })
  assert.deepEqual(result.video.size, { width: 250, height: 150 })
  assert.deepEqual(result.image.constraints.at(-1), { minWidth: 240, minHeight: 150 })
  assert.deepEqual(result.video.constraints.at(-1), { minWidth: 250, minHeight: 150 })
  assert.equal(result.menuLabel, 'Show Y7 SBS help')
  assert.equal(result.dialog.title, 'Y7 SBS (Image)')
  assert.equal(result.dialogText, objectInfo.Y7_SideBySide.description)
  console.log('Y7 SBS frontend opaque iframe harness: PASS')
} finally {
  await browser.close()
  await new Promise((resolve) => server.close(resolve))
}
