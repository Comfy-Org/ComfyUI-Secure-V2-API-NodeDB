import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ENTRY = path.resolve(HERE, '../web/autonotes.js')

function check(condition, message) {
  if (!condition) throw new Error(message)
}

async function drain() {
  for (let index = 0; index < 16; index += 1)
    await new Promise((resolve) => setImmediate(resolve))
}

class FakeText {
  constructor(value, ownerDocument) {
    this.textContent = String(value); this.ownerDocument = ownerDocument
    this.children = []; this.parentNode = null
  }
}

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase(); this.ownerDocument = ownerDocument
    this.children = []; this.parentNode = null; this.style = {}
    this.listeners = new Map(); this.textContent = ''; this.value = ''
    this.className = ''; this.title = ''; this.type = ''; this.placeholder = ''
    this.checked = false; this.disabled = false; this.focused = false
  }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child }
  append(...children) { for (const child of children) this.appendChild(child) }
  replaceChildren(...children) {
    for (const child of this.children) child.parentNode = null
    this.children = []; this.append(...children)
  }
  remove() {
    if (!this.parentNode) return
    const index = this.parentNode.children.indexOf(this)
    if (index >= 0) this.parentNode.children.splice(index, 1)
    this.parentNode = null
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? []
    listeners.push(listener); this.listeners.set(type, listeners)
  }
  dispatch(type, event = {}) {
    event.target ??= this
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }
  focus() { this.focused = true }
}

class FakeDocument {
  createElement(tag) { return new FakeElement(tag, this) }
  createTextNode(value) { return new FakeText(value, this) }
}

function node(id, type, title, values = {}, properties = {}) {
  return {
    id, type, getTitle: () => title, getProperties: () => properties,
    widgets: { all: () => Object.entries(values).map(([name, value]) => ({
      name, getValue: () => value,
    })) },
  }
}

function findButtons(root, label) {
  const found = []; const queue = [root]
  while (queue.length) {
    const item = queue.shift()
    if (item.tagName === 'BUTTON' && item.textContent === label) found.push(item)
    queue.push(...item.children)
  }
  return found
}

const document = new FakeDocument()
const sampler = node('1', 'KSampler', 'Sampler', { steps: 20, cfg: 7 })
const checkpoint = node('2', 'CheckpointLoaderSimple', 'Checkpoint', {
  ckpt_name: 'models/modelA.safetensors',
})
const notes = [
  { uuid: 'pinned', name: 'Pinned', content: '<script>bad()</script>',
    format_style: 'markdown', pinned: true, tags: ['always'], trigger_conditions: [] },
  { uuid: 'selected', name: 'Selected', content: 'selected', pinned: false,
    trigger_conditions: [{ type: 'node_selected', node_types: ['KSampler'] }] },
  { uuid: 'selected-attribute', name: 'Selected attribute', content: 'attribute', pinned: false,
    trigger_conditions: [{ type: 'node_selected_attribute', node_type: 'CheckpointLoaderSimple',
      attribute_name: 'ckpt_name', attribute_values: ['modelA'] }] },
  { uuid: 'workflow', name: 'Workflow node', content: 'workflow', pinned: false,
    trigger_conditions: [{ type: 'node_in_workflow', node_types: ['KSampler'] }] },
  { uuid: 'workflow-attribute', name: 'Workflow attribute', content: 'workflow attr', pinned: false,
    trigger_conditions: [{ type: 'node_in_workflow_attribute', node_type: 'KSampler',
      attribute_name: 'steps', attribute_values: ['20'] }] },
  { uuid: 'workflow-name', name: 'Workflow name', content: 'name', pinned: false,
    trigger_conditions: [{ type: 'workflow_name', workflow_names: ['portrait'] }] },
  { uuid: 'hidden', name: 'Hidden', content: 'hidden', pinned: false,
    trigger_conditions: [{ type: 'node_selected', node_types: ['Never'] }] },
]
const storage = new Map([['autonotes/state.json', JSON.stringify({
  version: 1, displayMode: 'automatic', notes,
  folders: [{ uuid: 'folder', parent_uuid: null, name: 'Models' }],
})]])
let failWrites = false
let sidebar
let selectionListener
let nodeChangeListener
let workflowListener
const menus = []
const dialogs = []
const notifications = []

const comfy = {
  storage: {
    async get(name) { return storage.get(name) },
    async set(name, value) {
      if (failWrites) throw new Error('quota rejected')
      storage.set(name, value)
    },
    async remove(name) { storage.delete(name) },
    async list() { return [...storage.keys()] },
  },
  graph: { nodes: () => [sampler, checkpoint] },
  workflow: { current: () => ({ name: 'portrait-study.json' }) },
  onSelectionChanged(listener) { selectionListener = listener; return () => { selectionListener = undefined } },
  onNodeChanged(listener) { nodeChangeListener = listener; return () => { nodeChangeListener = undefined } },
  onWorkflowLoaded(listener) { workflowListener = listener; return () => { workflowListener = undefined } },
  defs: { extend(_selector, apply) { apply({ addMenuItem: (item) => menus.push(item) }); return () => {} } },
  ui: {
    addSidebarTab(definition) { sidebar = definition; return () => {} },
    showDialog(definition) {
      const container = document.createElement('section')
      definition.render(container)
      const record = { definition, container, closed: false }; dialogs.push(record)
      return { close() { record.closed = true; definition.destroy?.() } }
    },
  },
  commands: { notify(definition) { notifications.push(definition) } },
}

const context = vm.createContext({
  console, URL, Event, EventTarget, TextEncoder, Map, Set, Promise, String,
  Number, Array, Object, Date, Math, RegExp, JSON, crypto: globalThis.crypto,
  queueMicrotask, setImmediate,
})
const facade = new vm.SyntheticModule(['comfy'], function initialize() {
  this.setExport('comfy', comfy)
}, { context, identifier: '/comfy/api/v2.js' })
const entry = new vm.SourceTextModule(fs.readFileSync(ENTRY, 'utf8'), {
  context, identifier: ENTRY,
})
await entry.link(async (specifier) => {
  if (specifier === '/comfy/api/v2.js') return facade
  throw new Error(`unexpected import ${specifier}`)
})
await entry.evaluate(); await drain()

check(sidebar?.id === 'autonotes.sidebar', 'sidebar registration changed')
check(menus.length === 1 && menus[0].label.includes('Create AutoNote'),
  'node context action changed')
check(typeof selectionListener === 'function' && typeof nodeChangeListener === 'function'
  && typeof workflowListener === 'function', 'typed context listeners were not installed')
for (const name of ['window', 'parent', 'document', 'fetch', 'XMLHttpRequest',
  'WebSocket', 'app', 'api', 'localStorage', 'indexedDB']) {
  check(vm.runInContext(`typeof ${name}`, context) === 'undefined', `${name} leaked into guest`)
}

const initiallyVisible = entry.namespace.visibleNotes().map(({ uuid }) => uuid).sort()
check(JSON.stringify(initiallyVisible) === JSON.stringify([
  'pinned', 'workflow', 'workflow-attribute', 'workflow-name',
]), `automatic workflow matching changed: ${JSON.stringify(initiallyVisible)}`)

selectionListener([checkpoint]); await drain()
let selectedVisible = entry.namespace.visibleNotes().map(({ uuid }) => uuid)
check(selectedVisible.includes('selected-attribute') && !selectedVisible.includes('selected'),
  'selected attribute matching changed')
selectionListener([sampler]); await drain()
selectedVisible = entry.namespace.visibleNotes().map(({ uuid }) => uuid)
check(selectedVisible.includes('selected') && !selectedVisible.includes('selected-attribute'),
  'selected node matching changed')

const host = document.createElement('main')
await sidebar.render(host); await drain()
check(findButtons(host, 'Add').length === 1 && findButtons(host, 'Folders').length === 1,
  'sidebar controls changed')
check(findButtons(host, 'Edit').length === selectedVisible.length,
  'sidebar did not render the automatic result set')

menus[0].run(checkpoint); await drain()
const editor = dialogs.at(-1)
check(editor?.definition.title === 'Add AutoNote', 'node-menu editor did not open')
const shell = editor.container.children[0]
shell.children[0].value = 'Checkpoint tips'
shell.children[4].value = 'model, portrait'
shell.children[5].value = '# Safe\n<script>not html</script>'
shell.children[8].children[1].dispatch('click')
await drain()
let persisted = JSON.parse(storage.get('autonotes/state.json'))
check(persisted.notes.some((item) => item.name === 'Checkpoint tips'
  && item.trigger_conditions[0].node_types[0] === 'CheckpointLoaderSimple'),
  'node-menu note did not persist with its trigger')

const countBeforeFailure = persisted.notes.length
menus[0].run(sampler); await drain()
const failedEditor = dialogs.at(-1); const failedShell = failedEditor.container.children[0]
failedShell.children[0].value = 'Must not commit'
failWrites = true
failedShell.children[8].children[1].dispatch('click')
await drain(); failWrites = false
persisted = JSON.parse(storage.get('autonotes/state.json'))
check(persisted.notes.length === countBeforeFailure
  && !persisted.notes.some((item) => item.name === 'Must not commit'),
  'failed storage write mutated durable state')
check(notifications.some((item) => item.severity === 'error'
  && item.detail.includes('quota rejected')), 'storage failure was not surfaced')

const source = fs.readFileSync(ENTRY, 'utf8')
for (const forbidden of ['innerHTML', 'outerHTML', 'insertAdjacentHTML',
  'localStorage', 'indexedDB', 'fetch(', 'document.', 'window.', 'setInterval(']) {
  check(!source.includes(forbidden), `unsafe frontend primitive present: ${forbidden}`)
}

console.log('AutoNotes frontend behavior and security ok')
