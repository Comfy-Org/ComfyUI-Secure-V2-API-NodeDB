import { comfy } from '/comfy/api/v2.js'

const STORE = 'autonotes/state.json'
const MAX_STATE_BYTES = 4 * 1024 * 1024
const MAX_NOTES = 500
const MAX_FOLDERS = 200
const MAX_CONTENT_BYTES = 512 * 1024
const MAX_NAME = 160
const MAX_TAGS = 32
const MAX_CONDITIONS = 32
const TRIGGER_TYPES = new Set([
  'node_selected', 'node_selected_attribute', 'node_in_workflow',
  'node_in_workflow_attribute', 'workflow_name',
])

let state = { version: 1, displayMode: 'all', notes: [], folders: [] }
let selectedNodes = []
let sidebarRoot
let refreshQueued = false

const bytes = (value) => new TextEncoder().encode(String(value)).byteLength
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key)
const text = (value, max = MAX_NAME) =>
  typeof value === 'string' ? value.slice(0, max) : ''
const nullableId = (value) =>
  value == null || value === '' ? null : text(value, 128)
const makeId = () => globalThis.crypto?.randomUUID?.()
  ?? `note-${Date.now()}-${Math.random().toString(16).slice(2)}`

function stringList(value, maxItems = 64, maxLength = 256) {
  if (!Array.isArray(value)) return []
  return value.slice(0, maxItems)
    .filter((item) => typeof item === 'string')
    .map((item) => item.slice(0, maxLength))
}

function normalizeCondition(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || !TRIGGER_TYPES.has(value.type)) return undefined
  return {
    type: value.type,
    node_types: stringList(value.node_types),
    node_type: nullableId(value.node_type),
    attribute_name: nullableId(value.attribute_name),
    attribute_values: stringList(value.attribute_values),
    workflow_names: stringList(value.workflow_names),
  }
}

function normalizeNote(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const uuid = text(value.uuid, 128)
  if (!uuid) return undefined
  const content = text(value.content, MAX_CONTENT_BYTES)
  if (bytes(content) > MAX_CONTENT_BYTES) return undefined
  return {
    uuid,
    folder_uuid: nullableId(value.folder_uuid),
    content,
    format_style: value.format_style === 'markdown' ? 'markdown' : 'plaintext',
    trigger_conditions: Array.isArray(value.trigger_conditions)
      ? value.trigger_conditions.slice(0, MAX_CONDITIONS)
        .map(normalizeCondition).filter(Boolean) : [],
    pinned: value.pinned === true,
    name: text(value.name, MAX_NAME) || 'New Note',
    tags: stringList(value.tags, MAX_TAGS, 64),
  }
}

function normalizeFolder(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const uuid = text(value.uuid, 128)
  if (!uuid) return undefined
  return { uuid, parent_uuid: nullableId(value.parent_uuid),
    name: text(value.name, MAX_NAME) || 'New Folder' }
}

function normalizeState(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    return { version: 1, displayMode: 'all', notes: [], folders: [] }
  const folders = Array.isArray(value.folders)
    ? value.folders.slice(0, MAX_FOLDERS).map(normalizeFolder).filter(Boolean) : []
  const folderIds = new Set(folders.map(({ uuid }) => uuid))
  for (const folder of folders) {
    if (folder.parent_uuid === folder.uuid || !folderIds.has(folder.parent_uuid))
      folder.parent_uuid = null
  }
  const notes = Array.isArray(value.notes)
    ? value.notes.slice(0, MAX_NOTES).map(normalizeNote).filter(Boolean) : []
  for (const note of notes) {
    if (!folderIds.has(note.folder_uuid)) note.folder_uuid = null
  }
  return { version: 1,
    displayMode: value.displayMode === 'automatic' ? 'automatic' : 'all',
    notes, folders }
}

async function loadState() {
  try {
    const raw = await comfy.storage.get(STORE)
    if (!raw || bytes(raw) > MAX_STATE_BYTES) return
    state = normalizeState(JSON.parse(raw))
  } catch (_error) {
    state = { version: 1, displayMode: 'all', notes: [], folders: [] }
  }
}

async function commit(next) {
  const normalized = normalizeState(next)
  const encoded = JSON.stringify(normalized)
  if (bytes(encoded) > MAX_STATE_BYTES) throw new Error('AutoNotes storage exceeds 4 MiB')
  await comfy.storage.set(STORE, encoded)
  state = normalized
  renderSidebar()
}

function nodeAttributes(node) {
  const result = Object.create(null)
  try {
    for (const [key, value] of Object.entries(node.getProperties()))
      result[key] = value
    for (const widget of node.widgets.all()) result[widget.name] = widget.getValue()
  } catch (_error) { /* a deleted node contributes no additional context */ }
  return result
}

function context() {
  const selected = selectedNodes[0]
  const workflowNodes = Object.create(null)
  for (const node of comfy.graph.nodes()) {
    if (!own(workflowNodes, node.type)) workflowNodes[node.type] = nodeAttributes(node)
  }
  return {
    selectedType: selected?.type,
    selectedAttributes: selected ? nodeAttributes(selected) : Object.create(null),
    workflowName: comfy.workflow.current()?.name,
    workflowNodes,
  }
}

function containsAny(haystack, needles) {
  const value = String(haystack)
  return needles.some((needle) => value.includes(needle))
}

export function conditionMatches(condition, current) {
  if (condition.type === 'node_selected')
    return Boolean(current.selectedType
      && condition.node_types.includes(current.selectedType))
  if (condition.type === 'node_selected_attribute')
    return current.selectedType === condition.node_type
      && condition.attribute_name != null
      && own(current.selectedAttributes, condition.attribute_name)
      && containsAny(current.selectedAttributes[condition.attribute_name],
        condition.attribute_values)
  if (condition.type === 'node_in_workflow')
    return condition.node_types.some((type) => own(current.workflowNodes, type))
  if (condition.type === 'node_in_workflow_attribute') {
    const attributes = current.workflowNodes[condition.node_type]
    if (!attributes || condition.attribute_name == null
        || !own(attributes, condition.attribute_name)) return false
    return condition.attribute_values.length === 0
      || containsAny(attributes[condition.attribute_name], condition.attribute_values)
  }
  if (condition.type === 'workflow_name')
    return current.workflowName != null
      && containsAny(current.workflowName, condition.workflow_names)
  return false
}

export function visibleNotes(current = context()) {
  if (state.displayMode === 'all') return [...state.notes]
  return state.notes.filter((note) => note.pinned
    || note.trigger_conditions.some((condition) => conditionMatches(condition, current)))
}

function notify(severity, detail) {
  comfy.commands.notify({ severity, summary: 'AutoNotes', detail: String(detail) })
}

function button(doc, label, run, title = label) {
  const element = doc.createElement('button')
  element.type = 'button'; element.textContent = label; element.title = title
  element.addEventListener('click', run)
  return element
}

function appendInline(doc, parent, value) {
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g
  let at = 0
  for (const match of String(value).matchAll(pattern)) {
    parent.append(doc.createTextNode(value.slice(at, match.index)))
    const token = match[0]
    let element
    if (token.startsWith('`')) {
      element = doc.createElement('code'); element.textContent = token.slice(1, -1)
    } else if (token.startsWith('**')) {
      element = doc.createElement('strong'); element.textContent = token.slice(2, -2)
    } else if (token.startsWith('*')) {
      element = doc.createElement('em'); element.textContent = token.slice(1, -1)
    } else {
      const parts = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(token)
      element = doc.createElement('a'); element.textContent = parts[1]
      element.href = parts[2]; element.target = '_blank'; element.rel = 'noopener noreferrer'
    }
    parent.append(element); at = match.index + token.length
  }
  parent.append(doc.createTextNode(String(value).slice(at)))
}

function renderMarkdown(doc, root, markdown) {
  root.replaceChildren()
  let code
  for (const line of String(markdown).split(/\r?\n/)) {
    if (line.startsWith('```')) {
      if (code) { root.append(code); code = undefined }
      else code = doc.createElement('pre')
      continue
    }
    if (code) { code.textContent += `${line}\n`; continue }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line)
    const element = heading ? doc.createElement(`h${heading[1].length}`)
      : bullet ? doc.createElement('li') : doc.createElement('p')
    appendInline(doc, element, heading ? heading[2] : bullet ? bullet[1] : line)
    root.append(element)
  }
  if (code) root.append(code)
}

function option(doc, value, label = value) {
  const item = doc.createElement('option'); item.value = value; item.textContent = label
  return item
}

function folderOptions(doc, select, selected = null) {
  select.replaceChildren(option(doc, '', 'No folder'))
  const byParent = new Map()
  for (const folder of state.folders) {
    const key = folder.parent_uuid || ''
    if (!byParent.has(key)) byParent.set(key, [])
    byParent.get(key).push(folder)
  }
  const add = (parent, level, seen = new Set()) => {
    for (const folder of byParent.get(parent) || []) {
      if (seen.has(folder.uuid)) continue
      const next = new Set(seen); next.add(folder.uuid)
      select.append(option(doc, folder.uuid, `${'  '.repeat(level)}${folder.name}`))
      add(folder.uuid, level + 1, next)
    }
  }
  add('', 0); select.value = selected || ''
}

function parseList(value) {
  return String(value).split(',').map((item) => item.trim()).filter(Boolean)
}

function triggerRow(doc, condition = {}) {
  const row = doc.createElement('div'); row.className = 'autonotes-trigger'
  row.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:5px'
  const type = doc.createElement('select')
  for (const [value, label] of [
    ['node_selected', 'Node selected'],
    ['node_selected_attribute', 'Selected node + attribute'],
    ['node_in_workflow', 'Node in workflow'],
    ['node_in_workflow_attribute', 'Workflow node + attribute'],
    ['workflow_name', 'Workflow name'],
  ]) type.append(option(doc, value, label))
  type.value = condition.type || 'node_selected'
  const nodeType = doc.createElement('input'); nodeType.placeholder = 'Node type(s)'
  nodeType.value = (condition.node_types?.length
    ? condition.node_types : condition.node_type ? [condition.node_type] : []).join(', ')
  const attribute = doc.createElement('input'); attribute.placeholder = 'Attribute'
  attribute.value = condition.attribute_name || ''
  const values = doc.createElement('input'); values.placeholder = 'Value(s) / workflow name(s)'
  values.value = (condition.type === 'workflow_name'
    ? condition.workflow_names : condition.attribute_values || []).join(', ')
  const remove = button(doc, '×', () => row.remove(), 'Remove trigger')
  row.append(type, nodeType, attribute, values, remove)
  row.readValue = () => {
    const nodeTypes = parseList(nodeType.value)
    const entries = parseList(values.value)
    return normalizeCondition({
      type: type.value, node_types: nodeTypes, node_type: nodeTypes[0] || null,
      attribute_name: attribute.value.trim() || null,
      attribute_values: type.value === 'workflow_name' ? [] : entries,
      workflow_names: type.value === 'workflow_name' ? entries : [],
    })
  }
  return row
}

function openEditor(existing, seedNode) {
  const original = existing || {
    uuid: makeId(), folder_uuid: null, content: '', format_style: 'plaintext',
    trigger_conditions: seedNode ? [{ type: 'node_selected',
      node_types: [seedNode.type], node_type: seedNode.type,
      attribute_name: null, attribute_values: [], workflow_names: [] }] : [],
    pinned: false, name: seedNode ? `Note for ${seedNode.getTitle()}` : 'New Note', tags: [],
  }
  let name; let folder; let format; let pinned; let tags; let content; let triggers
  let handle
  const save = async () => {
    const conditions = [...triggers.children].map((row) => row.readValue()).filter(Boolean)
    const note = normalizeNote({ ...original, name: name.value.trim(),
      folder_uuid: folder.value || null, format_style: format.value,
      pinned: pinned.checked, tags: parseList(tags.value), content: content.value,
      trigger_conditions: conditions })
    if (!note?.name) { notify('error', 'A note name is required'); return }
    try {
      const notes = state.notes.filter(({ uuid }) => uuid !== note.uuid)
      if (notes.length >= MAX_NOTES) throw new Error('AutoNotes supports at most 500 notes')
      await commit({ ...state, notes: [...notes, note] }); handle.close()
    } catch (error) { notify('error', error) }
  }
  handle = comfy.ui.showDialog({
    key: `autonotes.editor.${original.uuid}`, title: existing ? 'Edit AutoNote' : 'Add AutoNote',
    render(container) {
      const doc = container.ownerDocument
      const shell = doc.createElement('div')
      shell.style.cssText = 'display:grid;gap:8px;min-width:min(82vw,900px);max-height:80vh;overflow:auto'
      name = doc.createElement('input'); name.value = original.name; name.placeholder = 'Name'
      folder = doc.createElement('select'); folderOptions(doc, folder, original.folder_uuid)
      format = doc.createElement('select'); format.append(option(doc, 'plaintext', 'Plain text'), option(doc, 'markdown', 'Markdown')); format.value = original.format_style
      pinned = doc.createElement('input'); pinned.type = 'checkbox'; pinned.checked = original.pinned
      const pinLabel = doc.createElement('label'); pinLabel.append(pinned, doc.createTextNode(' Always show (pinned)'))
      tags = doc.createElement('input'); tags.placeholder = 'Tags, comma separated'; tags.value = original.tags.join(', ')
      content = doc.createElement('textarea'); content.value = original.content
      content.style.cssText = 'min-height:240px;resize:vertical;font:14px/1.4 ui-monospace,monospace'
      triggers = doc.createElement('div'); triggers.style.cssText = 'display:grid;gap:5px'
      for (const condition of original.trigger_conditions) triggers.append(triggerRow(doc, condition))
      const addTrigger = button(doc, 'Add trigger', () => {
        if (triggers.children.length < MAX_CONDITIONS) triggers.append(triggerRow(doc))
      })
      const actions = doc.createElement('div'); actions.style.cssText = 'display:flex;justify-content:flex-end;gap:8px'
      actions.append(button(doc, 'Cancel', () => handle.close()), button(doc, 'Save', () => void save()))
      shell.append(name, folder, format, pinLabel, tags, content, triggers, addTrigger, actions)
      container.append(shell); name.focus()
    },
    onKeyDown(event) {
      if (!event.repeat && (event.ctrlKey || event.metaKey)
          && event.key.toLowerCase() === 's') void save()
    },
  })
}

function openFolders() {
  let list; let name; let parent; let handle
  const redraw = () => {
    if (!list) return
    const doc = list.ownerDocument; list.replaceChildren()
    for (const folder of state.folders) {
      const row = doc.createElement('div'); row.style.cssText = 'display:flex;gap:6px;align-items:center'
      const label = doc.createElement('span'); label.textContent = folder.name; label.style.flex = '1'
      row.append(label, button(doc, 'Rename', async () => {
        const renamed = name.value.trim(); if (!renamed) return
        try { await commit({ ...state, folders: state.folders.map((item) =>
          item.uuid === folder.uuid ? { ...item, name: renamed } : item) }); redraw() }
        catch (error) { notify('error', error) }
      }), button(doc, 'Delete', async () => {
        try { await commit({ ...state,
          folders: state.folders.filter(({ uuid }) => uuid !== folder.uuid)
            .map((item) => item.parent_uuid === folder.uuid ? { ...item, parent_uuid: null } : item),
          notes: state.notes.map((note) => note.folder_uuid === folder.uuid
            ? { ...note, folder_uuid: null } : note) }); redraw() }
        catch (error) { notify('error', error) }
      }))
      list.append(row)
    }
    folderOptions(doc, parent)
  }
  handle = comfy.ui.showDialog({ key: 'autonotes.folders', title: 'AutoNotes folders',
    render(container) {
      const doc = container.ownerDocument
      const shell = doc.createElement('div'); shell.style.cssText = 'display:grid;gap:8px;min-width:420px'
      name = doc.createElement('input'); name.placeholder = 'Folder name'
      parent = doc.createElement('select')
      const add = button(doc, 'Add folder', async () => {
        if (!name.value.trim()) return
        try {
          if (state.folders.length >= MAX_FOLDERS) throw new Error('AutoNotes supports at most 200 folders')
          await commit({ ...state, folders: [...state.folders, {
            uuid: makeId(), name: name.value.trim(), parent_uuid: parent.value || null,
          }] }); name.value = ''; redraw()
        } catch (error) { notify('error', error) }
      })
      list = doc.createElement('div'); list.style.cssText = 'display:grid;gap:5px;max-height:50vh;overflow:auto'
      shell.append(name, parent, add, list, button(doc, 'Close', () => handle.close()))
      container.append(shell); redraw()
    },
  })
}

async function removeNote(note) {
  try { await commit({ ...state, notes: state.notes.filter(({ uuid }) => uuid !== note.uuid) }) }
  catch (error) { notify('error', error) }
}

function noteCard(doc, note) {
  const card = doc.createElement('article')
  card.style.cssText = 'display:grid;gap:6px;padding:8px;border:1px solid #666;border-radius:6px'
  const head = doc.createElement('div'); head.style.cssText = 'display:flex;align-items:center;gap:6px'
  const title = doc.createElement('strong'); title.textContent = `${note.pinned ? '📌 ' : ''}${note.name}`; title.style.flex = '1'
  head.append(title, button(doc, 'Edit', () => openEditor(note)),
    button(doc, 'Copy', () => openEditor({ ...note, uuid: makeId(), name: `${note.name} copy` })),
    button(doc, 'Delete', () => void removeNote(note)))
  const body = doc.createElement(note.format_style === 'markdown' ? 'div' : 'pre')
  body.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;margin:0'
  if (note.format_style === 'markdown') renderMarkdown(doc, body, note.content)
  else body.textContent = note.content
  const meta = doc.createElement('small'); meta.textContent = note.tags.map((tag) => `#${tag}`).join(' ')
  card.append(head, body, meta); return card
}

function renderSidebar() {
  if (!sidebarRoot) return
  const doc = sidebarRoot.ownerDocument; sidebarRoot.replaceChildren()
  const controls = doc.createElement('div'); controls.style.cssText = 'display:flex;gap:5px;flex-wrap:wrap'
  const mode = doc.createElement('select')
  mode.append(option(doc, 'all', 'All notes'), option(doc, 'automatic', 'Automatic'))
  mode.value = state.displayMode
  mode.addEventListener('change', async () => {
    try { await commit({ ...state, displayMode: mode.value }) }
    catch (error) { notify('error', error) }
  })
  const search = doc.createElement('input'); search.placeholder = 'Filter notes or tags'; search.style.flex = '1'
  const list = doc.createElement('div'); list.style.cssText = 'display:grid;gap:8px;overflow:auto'
  const draw = () => {
    list.replaceChildren(); const query = search.value.trim().toLowerCase()
    const notes = visibleNotes().filter((note) => !query
      || `${note.name}\n${note.content}\n${note.tags.join(' ')}`.toLowerCase().includes(query))
    if (!notes.length) { const empty = doc.createElement('p'); empty.textContent = 'No notes to display'; list.append(empty) }
    for (const note of notes) list.append(noteCard(doc, note))
  }
  search.addEventListener('input', draw)
  controls.append(mode, search, button(doc, 'Add', () => openEditor()),
    button(doc, 'Add from selected', () => {
      if (!selectedNodes[0]) notify('warning', 'Select a node first')
      else openEditor(undefined, selectedNodes[0])
    }), button(doc, 'Folders', openFolders))
  sidebarRoot.append(controls, list); draw()
}

function scheduleRefresh() {
  if (refreshQueued) return
  refreshQueued = true
  queueMicrotask(() => { refreshQueued = false; renderSidebar() })
}

const ready = loadState()
comfy.onSelectionChanged((nodes) => { selectedNodes = [...nodes]; scheduleRefresh() })
comfy.onNodeChanged(() => scheduleRefresh())
comfy.onWorkflowLoaded(() => scheduleRefresh())

comfy.defs.extend(/./, (builder) => {
  builder.addMenuItem({ label: 'Create AutoNote for this node',
    run: (node) => openEditor(undefined, node) })
})

comfy.ui.addSidebarTab({
  id: 'autonotes.sidebar', icon: 'icon-[lucide--notebook-tabs]',
  title: 'AutoNotes', tooltip: 'Context-aware notes',
  async render(container) {
    sidebarRoot = container; sidebarRoot.style.cssText = 'display:grid;gap:8px;height:100%'
    await ready; renderSidebar()
  },
  destroy() { sidebarRoot = undefined },
})
