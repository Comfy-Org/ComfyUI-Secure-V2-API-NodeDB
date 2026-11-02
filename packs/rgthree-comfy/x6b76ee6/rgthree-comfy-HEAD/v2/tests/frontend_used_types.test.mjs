// rgthree-comfy to-50% repair R1: frontend unit tests on host fakes for the 9 corpus-used
// frontend-only types (Fast Muter, Fast Bypasser, Fast Actions Button, Label, Mute / Bypass
// Relay, Mute / Bypass Repeater, Node Collector, Random Unmuter, Reroute).
//
// R  register: the served v2/web entry modules evaluate in one realm against a fake
//    `/comfy/api/v2.js`; each type is defined exactly once, as `execution: 'frontend'`, with
//    the original's slots; only Reroute carries a resolver.
// L  load: each type's composed hooks (define + every matching `extend`) accept a node restored
//    from a saved workflow (onCreated restored+loading, onConfigured) without an error.
// P  prompt build: the host's own `resolution.ts` (frontend 1.53.4, unmodified, from /deps) with a
//    port of ExecutableNodeDTO.resolveInput/resolveOutput (ExecutableNodeDTO.ts 6642209731a7) and
//    graphToPrompt's per-input substitution (executionUtil.ts 27e1412d5a02, L247-312). The
//    ORIGINAL side registers the same types the way upstream did: `isVirtualNode` and no
//    resolver. The V2 side registers them as defsRegistry.ts (4c5e2eb778ef) L1117-1123 does:
//    `isVirtualNode`, plus `resolutionOwned` when the definition has `resolve`.
// M  modes: Fast Muter and Fast Bypasser, original vs v2, over the same click/action sequence.
//    The original's own BaseNodeModeChanger/MuterNode/BypasserNode code runs with a minimal
//    LiteGraph base class; v2 runs its real modules on the fake host. Repeater, Relay and Random
//    Unmuter v2 behaviour is checked against the original's documented rule (file:line cited).
//
// usage: node --experimental-vm-modules --import ./host_model/hooks.mjs frontend_used_types.test.mjs \
//          <v2 web dir> <pristine web dir> <host resolution.ts> <out.json> [negative]
import vm from 'node:vm'
import path from 'node:path'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { pathToFileURL } from 'node:url'

const [WEB, PRISTINE_WEB, RESOLUTION_TS, OUT, MODE] = process.argv.slice(2)
const NEGATIVE = MODE === 'negative'
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex')
const results = []
const check = (group, name, pass, detail, types = []) => results.push({ group, name, types, pass: !!pass, detail })
const uncaught = []
process.on('uncaughtException', (e) => uncaught.push(String(e?.stack || e).split('\n').slice(0, 3).join(' | ')))
process.on('unhandledRejection', (e) => uncaught.push('rejection: ' + String(e?.stack || e).split('\n').slice(0, 3).join(' | ')))
// A crash (an error escaping a top-level await lands in the handler above) still writes a receipt.
let written = false
process.on('exit', () => {
  if (written) return
  writeFileSync(OUT, JSON.stringify({ test: 'rgthree-comfy to-50% repair R1 (crashed)', status: 'CRASH', cases: results.length,
    failed: [...results.filter((r) => !r.pass).map((r) => `${r.group}: ${r.name}`), `CRASH: ${uncaught.at(-1) ?? 'unknown'}`],
    uncaught, per_type: {}, prompt_deviations: [], inputs_sha256: {}, results }, null, 1) + '\n')
  process.exitCode = 1
})
const tick = () => new Promise((r) => setTimeout(r, 0))
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

const TYPES = {
  FAST_MUTER: 'Fast Muter (rgthree)', FAST_BYPASSER: 'Fast Bypasser (rgthree)',
  FAST_ACTIONS_BUTTON: 'Fast Actions Button (rgthree)', LABEL: 'Label (rgthree)',
  RELAY: 'Mute / Bypass Relay (rgthree)', REPEATER: 'Mute / Bypass Repeater (rgthree)',
  NODE_COLLECTOR: 'Node Collector (rgthree)', RANDOM_UNMUTER: 'Random Unmuter (rgthree)',
  REROUTE: 'Reroute (rgthree)',
}
const USED = Object.values(TYPES)
// The original's slots, from the pristine TypeScript (file:line in each entry).
const ORIGINAL_SLOTS = {
  [TYPES.FAST_MUTER]: { inputs: ['*'], outputs: [['OPT_CONNECTION', '*']], src: 'base_any_input_connected_node.ts:49, base_node_mode_changer.ts:33' },
  [TYPES.FAST_BYPASSER]: { inputs: ['*'], outputs: [['OPT_CONNECTION', '*']], src: 'base_any_input_connected_node.ts:49, base_node_mode_changer.ts:33' },
  [TYPES.FAST_ACTIONS_BUTTON]: { inputs: ['*'], outputs: [], src: 'base_any_input_connected_node.ts:49; fast_actions_button.ts adds no output' },
  [TYPES.NODE_COLLECTOR]: { inputs: ['*'], outputs: [['Output', '*']], src: 'base_any_input_connected_node.ts:49, node_collector.ts:38' },
  [TYPES.RELAY]: { inputs: ['*'], outputs: [['REPEATER', '_NODE_REPEATER_']], src: 'base_any_input_connected_node.ts:49, node_mode_relay.ts:90' },
  [TYPES.REPEATER]: { inputs: ['*'], outputs: [['OPT_CONNECTION', '*']], src: 'base_any_input_connected_node.ts:49, node_mode_repeater.ts:38' },
  [TYPES.RANDOM_UNMUTER]: { inputs: ['*'], outputs: [], src: 'base_any_input_connected_node.ts:49; random_unmuter.ts adds no output' },
  [TYPES.REROUTE]: { inputs: ['*'], outputs: [['', '*']], src: 'reroute.ts:444-445' },
  [TYPES.LABEL]: { inputs: [], outputs: [], src: 'label.ts (RgthreeBaseVirtualNode, no slots)' },
}
const ENTRY_MODULES = ['comfyui/bypasser.js', 'comfyui/fast_actions_button.js', 'comfyui/label.js', 'comfyui/muter.js',
  'comfyui/node_collector.js', 'comfyui/node_mode_relay.js', 'comfyui/node_mode_repeater.js', 'comfyui/random_unmuter.js',
  'comfyui/reroute.js']
// Imports the 9 types do not exercise here: the every-node menu registrations, the drop import
// feature (pulls in the Power Lora Loader), and the F01 layout pass (out of scope; PARTIAL).
const STUBS = {
  'comfyui/menu_queue_node.js': {},
  'comfyui/feature_import_individual_nodes.js': {},
  'comfyui/connection_layout.js': { applyConnectionLayout: () => {} },
  'comfyui/services/config_service.js': { SERVICE: { getConfigValue: (key, def) => def, getFeatureValue: (key, def) => def, setConfigValue: () => {} } },
}

// ---------------------------------------------------------------- fake host (/comfy/api/v2.js)
const MODE_NAMES = ['always', 'on-event', 'never', 'on-trigger', 'bypass']
function makeHost() {
  const defined = new Map(), defineCount = new Map(), extensions = [], readyCbs = [], nodeChanged = []
  const beforeRun = [], afterRun = [], nodes = new Map(), links = new Map(), settings = new Map()
  let linkSeq = 0
  const host = { defined, defineCount, extensions, readyCbs, nodeChanged, beforeRun, afterRun, nodes, links, notes: [], batches: 0, windowListeners: [] }
  const graph = {
    get id() { return 'root' },
    node: (id) => nodes.get(String(id)),
    nodes: () => [...nodes.values()],
    nodesOfType: (t) => [...nodes.values()].filter((n) => n.type === t),
    root: () => graph, subgraphs: () => [], groups: () => [], selection: () => [], select() {},
    batch(fn) { host.batches++; return fn() },
    add() { throw new Error('graph.add not modelled') }, replace() { throw new Error('graph.replace not modelled') },
  }
  host.connect = (src, srcSlot, dst, dstSlot) => {
    const id = String(++linkSeq)
    links.set(id, { id, sourceNodeId: src.id, sourceSlot: srcSlot, targetNodeId: dst.id, targetSlot: dstSlot })
    dst.__inputs[dstSlot].linkId = id
    src.__outputs[srcSlot].linkIds.push(id)
    return id
  }
  host.comfy = {
    defs: {
      define(def) { defined.set(def.type, def); defineCount.set(def.type, (defineCount.get(def.type) ?? 0) + 1); return () => {} },
      extend(selector, apply) { extensions.push({ selector, apply }); return () => {} },
      get: (t) => defined.get(t), has: (t) => defined.has(t), all: () => [...defined.values()],
      onRefreshed: () => () => {}, typeColor: () => '#888', nodeColor: () => undefined, defineWidgetType: () => () => {},
      isTypeCompatible: (a, b) => a === b || a === '*' || b === '*',
    },
    onReady(cb) { readyCbs.push(cb); return () => {} },
    onNodeChanged(cb) { nodeChanged.push(cb); return () => {} },
    onViewportChanged: () => () => {},
    graph,
    commands: { register: () => () => {}, notify: (n) => host.notes.push(n) },
    settings: { declare: () => () => {}, get: (k) => settings.get(k), set: (k, v) => settings.set(k, v), onChange: () => () => {} },
    ui: { showDialog: () => {}, showMenu: () => {} },
    queue: { onBeforeRun(cb) { beforeRun.push(cb); return () => {} }, onAfterRun(cb) { afterRun.push(cb); return () => {} }, run: async () => {} },
  }
  return host
}

// A node handle modelled on the published NodeHandle/SlotHandle/WidgetHandle members these
// modules call (comfy-api.d.ts in this v2 tree). Modes are the published names.
function makeNode(host, { id, type, mode = 'always', title = type, properties = {}, inputs = [], outputs = [] }) {
  const props = structuredClone(properties)
  const node = { id: String(id), type, graphId: 'root', isDeleted: false, modeLog: [], __inputs: [], __outputs: [] }
  let currentMode = mode, currentTitle = title, size = { width: 200, height: 100 }
  const slotHandle = (side, data) => ({
    get index() { return node[side === 'in' ? '__inputs' : '__outputs'].indexOf(data) },
    get name() { return data.name }, get type() { return data.type }, get label() { return data.label },
    get isConnected() { return side === 'in' ? data.linkId != null : data.linkIds.length > 0 },
    link() { const l = data.linkId != null && host.links.get(data.linkId); return l || undefined },
    links() { return data.linkIds.map((i) => host.links.get(i)).filter(Boolean) },
    modify(patch) { Object.assign(data, patch); return this },
    disconnect() { if (side === 'in') data.linkId = null; else data.linkIds = [] },
    snapshot() { return { ...data } },
  })
  const collection = (side) => {
    const list = node[side === 'in' ? '__inputs' : '__outputs']
    return {
      get length() { return list.length },
      at: (i) => (list.at(i) ? slotHandle(side, list.at(i)) : undefined),
      all: () => list.map((d) => slotHandle(side, d)),
      get: (name) => { const d = list.find((x) => x.name === name); return d ? slotHandle(side, d) : undefined },
      add(name, type) { const d = side === 'in' ? { name, type, linkId: null } : { name, type, linkIds: [] }; list.push(d); return slotHandle(side, d) },
      remove({ index }) { list.splice(index, 1) },
    }
  }
  for (const s of inputs) node.__inputs.push({ name: s.name ?? '', type: s.type ?? '*', linkId: null })
  for (const s of outputs) node.__outputs.push({ name: s.name ?? '', type: s.type ?? '*', linkIds: [] })
  const widgetList = []
  node.inputs = collection('in'); node.outputs = collection('out')
  node.widgets = {
    add(def) {
      const listeners = []
      const w = { name: def.name, type: def.type, value: def.value, label: undefined, options: def.options,
        getValue: () => w.value, setValue(v) { w.value = v; for (const fn of listeners) fn(v) }, on(evt, fn) { if (evt === 'change') listeners.push(fn) },
        setLabel(l) { w.label = l }, click() { w.value = !w.value; for (const fn of listeners) fn(w.value) } }
      widgetList.push(w); return w
    },
    get: (name) => widgetList.find((w) => w.name === name), at: (i) => widgetList.at(i), all: () => [...widgetList],
    names: () => widgetList.map((w) => w.name), remove(name) { const i = widgetList.findIndex((w) => w.name === name); if (i > -1) widgetList.splice(i, 1) },
    reorder(order) { widgetList.sort((a, b) => order.indexOf(a.name) - order.indexOf(b.name)) },
    move() {},
  }
  Object.assign(node, {
    getMode: () => currentMode, setMode(m) { currentMode = m; node.modeLog.push(m) },
    getTitle: () => currentTitle, setTitle(t) { currentTitle = t },
    getProperty: (k) => props[k], setProperty(k, v) { props[k] = v }, getProperties: () => ({ ...props }),
    getSize: () => ({ ...size }), setSize(s) { size = { ...size, ...s } },
    setSerializeWidgets() {}, setCollapsed() {}, setColor() {}, redraw() {}, getBounds: undefined,
  })
  // Published NodeHandle members this fake does not model answer as inert no-ops (the guest
  // implements them; nothing here reads their effect). Anything unpublished stays undefined.
  const handle = new Proxy(node, { get: (t, p) => (p in t ? t[p] : PUBLISHED_NODE_MEMBERS.has(p) ? () => undefined : undefined) })
  host.nodes.set(node.id, handle)
  return handle
}
// comfy-api.d.ts `interface NodeHandle` (L1355) members not modelled above.
const PUBLISHED_NODE_MEMBERS = new Set(['addBadge', 'canvas', 'getBgColor', 'getColor', 'getDisplayedImageIndex', 'getOutputImages',
  'getPosition', 'getShape', 'getSizeConstraints', 'getSlotPosition', 'isCollapsed', 'isPinned', 'isSerializingWidgets', 'remove',
  'setBgColor', 'setPinned', 'setPosition', 'setResizable', 'setShape', 'setSizeConstraints', 'snapshot'])

// Hooks the host would run for `type`: every matching `extend` builder first, then the define's own.
function hooksFor(host, type) {
  const hooks = {}
  const add = (k, fn) => (hooks[k] ??= []).push(fn)
  // Every published `on*` builder hook records its callback (NodeDefBuilder, comfy-api.d.ts L498);
  // other builder members are inert. The four synchronous hooks the guest refuses still throw.
  const base = { get def() { return host.defined.get(type) } }
  for (const h of ['onBeforeConnect', 'onUnplacedLink', 'onDragOver', 'onDrop']) base[h] = () => { throw new Error(`refused: ${h}`) }
  const builder = new Proxy(base, { get: (t, p) => (p in t ? t[p] : typeof p === 'string' && /^on[A-Z]/.test(p) ? (fn) => add(p, fn) : () => {}) })
  for (const { selector, apply } of host.extensions) {
    const sel = typeof selector === 'string' ? [selector] : selector
    const match = Array.isArray(sel) ? sel.includes(type) : selector instanceof RegExp ? selector.test(type)
      : typeof selector === 'object' && selector?.category ? false : false
    if (match) apply(builder)
  }
  const def = host.defined.get(type)
  for (const [k, v] of Object.entries(def ?? {})) if (k.startsWith('on') && typeof v === 'function') add(k, v)
  return hooks
}
const fire = (hooks, name, ...args) => { for (const fn of hooks[name] ?? []) fn(...args) }

// ---------------------------------------------------------------- module loader (one realm)
async function loadRealm(host, overrides = {}) {
  const context = vm.createContext({
    console: { log() {}, warn() {}, error() {}, info() {}, debug() {} }, setTimeout, clearTimeout, setInterval, clearInterval,
    queueMicrotask, structuredClone, URL, Math, Date, JSON, Promise,
    // Standard globals of the dedicated worker the guest evaluates pack modules in. No fetch.
    EventTarget, Event, CustomEvent, AbortController, AbortSignal, TextEncoder, TextDecoder, performance, atob, btoa,
    // The guest's scoped stubs (guest.mjs c6b97a15 / 16924bbe L332-378: `self.window = windowStub`,
    // `self.document = documentStub`): listeners are recorded, nothing reaches the host page.
    window: { addEventListener: (t, fn) => host.windowListeners.push([t, fn]), removeEventListener() {}, dispatchEvent: () => false,
      devicePixelRatio: 1, innerWidth: 1920, innerHeight: 1080 },
    document: { addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false },
    OffscreenCanvas: class { getContext() { return { font: '', measureText: (t) => ({ width: 7 * String(t).length }) } } },
  })
  const cache = new Map()
  const get = (rel) => {
    if (cache.has(rel)) return cache.get(rel)
    let mod
    if (rel === '/comfy/api/v2.js') {
      mod = new vm.SyntheticModule(['comfy'], function () { this.setExport('comfy', host.comfy) }, { context, identifier: rel })
    } else if (Object.hasOwn(STUBS, rel)) {
      const ex = STUBS[rel]
      mod = new vm.SyntheticModule(Object.keys(ex), function () { for (const [k, v] of Object.entries(ex)) this.setExport(k, v) }, { context, identifier: rel })
    } else {
      const source = overrides[rel] ?? readFileSync(path.join(WEB, rel), 'utf8')
      mod = new vm.SourceTextModule(source, { context, identifier: rel })
    }
    cache.set(rel, mod)
    return mod
  }
  const linker = async (specifier, referencing) => specifier === '/comfy/api/v2.js' ? get(specifier)
    : get(path.posix.normalize(path.posix.join(path.posix.dirname(referencing.identifier), specifier)))
  const namespaces = {}
  for (const entry of ENTRY_MODULES) {
    const mod = get(entry)
    await mod.link(linker)
    await mod.evaluate()
    namespaces[entry] = mod.namespace
  }
  for (const cb of host.readyCbs) cb()
  const ns = (rel) => cache.get(rel)?.namespace
  return { namespaces, ns, loaded: [...cache.keys()].filter((k) => k.endsWith('.js') && !Object.hasOwn(STUBS, k) && k !== '/comfy/api/v2.js').sort() }
}

// The negative control perturbs one converted output: the Fast Muter's off mode becomes 'bypass'.
const overrides = {}
if (NEGATIVE) {
  const src = readFileSync(path.join(WEB, 'comfyui/muter.js'), 'utf8')
  overrides['comfyui/muter.js'] = src.replace('modeOff: "never"', 'modeOff: "bypass"')
  if (overrides['comfyui/muter.js'] === src) throw new Error('negative control did not apply')
}

const host = makeHost()
const realm = await loadRealm(host, overrides)

// ---------------------------------------------------------------- R: register
for (const type of USED) {
  const def = host.defined.get(type)
  check('R register', `${type}: defined exactly once`, host.defineCount.get(type) === 1, { count: host.defineCount.get(type) ?? 0 }, [type])
  check('R register', `${type}: execution 'frontend'`, def?.execution === 'frontend', { execution: def?.execution }, [type])
  const want = ORIGINAL_SLOTS[type]
  const gotIn = (def?.inputs ?? []).map((s) => s.type)
  const gotOut = (def?.outputs ?? []).map((s) => [s.name, s.type])
  check('R register', `${type}: slots equal the original's (${want.src})`,
    JSON.stringify(gotIn) === JSON.stringify(want.inputs) && JSON.stringify(gotOut) === JSON.stringify(want.outputs), { inputs: gotIn, outputs: gotOut, original: want }, [type])
  check('R register', `${type}: ${type === TYPES.REROUTE ? 'has' : 'has no'} resolver`, (typeof def?.resolve === 'function') === (type === TYPES.REROUTE), {}, [type])
}
const rerouteDef = host.defined.get(TYPES.REROUTE)
const rr = rerouteDef?.resolve?.({ self: { id: '7', input: (i) => ({ nodeId: '7', input: i }) }, nodesOfType: () => [] })
check('R register', 'Reroute resolver: output 0 forwards to its own input 0', JSON.stringify(rr) === JSON.stringify({ 0: { forwardTo: { nodeId: '7', input: 0 } } }), rr, [TYPES.REROUTE])

// ---------------------------------------------------------------- L: load from a saved workflow
const SAVED = {
  [TYPES.FAST_MUTER]: { properties: { toggleRestriction: 'default' } },
  [TYPES.FAST_BYPASSER]: { properties: { toggleRestriction: 'max one' } },
  [TYPES.FAST_ACTIONS_BUTTON]: { properties: { buttonText: '🎬 Action!', shortcutModifier: 'alt', shortcutKey: '' }, widgets_values: ['🎬 Action!', 'None', 'Mute all'] },
  [TYPES.NODE_COLLECTOR]: { properties: {} },
  [TYPES.RELAY]: { properties: { on_muted_inputs: 'MUTE', on_bypassed_inputs: 'BYPASS', on_any_active_inputs: 'ACTIVE' } },
  [TYPES.REPEATER]: { properties: {} },
  [TYPES.RANDOM_UNMUTER]: { properties: {} },
  [TYPES.REROUTE]: { properties: { resizable: false, size: [40, 30], showLabel: true } },
  [TYPES.LABEL]: { properties: { fontSize: 12, fontFamily: 'Arial', fontColor: '#ffffff', textAlign: 'left', backgroundColor: 'transparent', padding: 0, borderRadius: 0 } },
}
let seq = 100
for (const type of USED) {
  const before = uncaught.length
  let error
  try {
    const def = host.defined.get(type)
    const node = makeNode(host, { id: ++seq, type, title: type, properties: SAVED[type].properties,
      inputs: (def?.inputs ?? []).map((s) => ({ ...s })), outputs: (def?.outputs ?? []).map((s) => ({ ...s })) })
    const hooks = hooksFor(host, type)
    fire(hooks, 'onCreated', node, { restored: true, loading: true })
    fire(hooks, 'onConfigured', node, { id: Number(node.id), type, properties: SAVED[type].properties, widgets_values: SAVED[type].widgets_values })
    await wait(150)
  } catch (e) { error = String(e?.stack || e).split('\n').slice(0, 2).join(' | ') }
  check('L load', `${type}: restored node runs onCreated/onConfigured and its debounced pass without an error`,
    !error && uncaught.length === before, { error, uncaught: uncaught.slice(before) }, [type])
}

// ---------------------------------------------------------------- P: prompt build (host model)
const { resolveFrontendNodesAsync } = await import(pathToFileURL(RESOLUTION_TS).href)
const NEVER = 2, BYPASS = 4
const isValidConnection = (a, b) => {
  if (!a || !b || a === b || a === '*' || b === '*') return true
  const la = String(a).toLowerCase().split(','), lb = String(b).toLowerCase().split(',')
  return la.some((x) => lb.includes(x))
}
// Backend types for the fixtures, and the frontend types' slots from the v2 definitions.
const BACKEND = {
  Ckpt: { inputs: [], outputs: [['MODEL', 'MODEL'], ['CLIP', 'CLIP']] },
  Lora: { inputs: [['model', 'MODEL'], ['clip', 'CLIP']], outputs: [['MODEL', 'MODEL'], ['CLIP', 'CLIP']] },
  KSampler: { inputs: [['model', 'MODEL']], outputs: [['LATENT', 'LATENT']] },
}
function buildGraph(spec, side) {
  // spec: { nodes: [[id, type, mode?]], links: [[srcId, srcSlot, dstId, dstSlot]] }
  const nodes = new Map(), links = new Map()
  for (const [id, type, mode = 0] of spec.nodes) {
    const frontend = USED.includes(type)
    const def = frontend ? host.defined.get(type) : null
    const shape = frontend ? { inputs: (def.inputs ?? []).map((s) => [s.name, s.type]), outputs: (def.outputs ?? []).map((s) => [s.name, s.type]) } : BACKEND[type]
    nodes.set(String(id), {
      id: String(id), type, mode, properties: {}, color: undefined, widgets: [],
      inputs: shape.inputs.map(([name, t]) => ({ name, type: t, link: null })),
      outputs: shape.outputs.map(([name, t]) => ({ name, type: t, links: [] })),
      isVirtualNode: frontend,
      resolutionOwned: frontend && side === 'v2' && typeof def.resolve === 'function',
    })
  }
  let seqL = 0
  for (const [s, ss, d, ds] of spec.links) {
    const id = String(++seqL), src = nodes.get(String(s)), dst = nodes.get(String(d))
    links.set(id, { id, origin_id: src.id, origin_slot: ss, target_id: dst.id, target_slot: ds, type: src.outputs[ss].type, originIsIoNode: false, resolve: () => ({}) })
    dst.inputs[ds].link = id; src.outputs[ss].links.push(id)
  }
  const graph = {
    nodes: [...nodes.values()], _groups: [],
    getNodeById: (id) => nodes.get(String(id)) ?? null,
    getLink: (id) => links.get(String(id)),
    inputLink: (nodeId, slot) => { const n = nodes.get(String(nodeId)); const l = n?.inputs[slot]?.link; return l != null ? links.get(l) : undefined },
  }
  return graph
}
// Port of ExecutableNodeDTO.resolveInput / resolveOutput / _getBypassSlotIndex (subgraphs and
// widget inputs are out of scope for these fixtures).
function resolveInput(graph, node, slot, visited, type) {
  const key = `${node.id}[I]${slot}`
  if (visited.has(key)) throw new Error(`recursion at ${key}`)
  visited.add(key)
  const input = node.inputs[slot]
  if (!input) throw new Error(`no input ${node.id}:${slot}`)
  if (input.link == null) return undefined
  const link = graph.getLink(input.link)
  const outputNode = graph.getNodeById(link.origin_id)
  return resolveOutput(graph, outputNode, link.origin_slot, type ?? input.type, visited)
}
function bypassSlotIndex(node, slot, type) {
  const inputs = node.inputs, opposite = inputs[slot], outputType = node.outputs[slot].type
  if (type === '*' || type === '') return inputs.length > slot ? slot : 0
  if (opposite && isValidConnection(opposite.type, outputType) && isValidConnection(opposite.type, type)) return slot
  const exact = inputs.findIndex((i) => i.type === type)
  if (exact !== -1) return exact
  return inputs.findIndex((i) => isValidConnection(i.type, outputType) && isValidConnection(i.type, type))
}
function resolveOutput(graph, node, slot, type, visited) {
  const key = `${node.id}[O]${slot}`
  if (visited.has(key)) throw new Error(`recursion at ${key}`)
  visited.add(key)
  if (node.mode === NEVER) return undefined
  if (node.mode === BYPASS) {
    const index = bypassSlotIndex(node, slot, type)
    if (index === -1) return undefined
    return resolveInput(graph, node, index, visited)
  }
  if (node.isVirtualNode) {
    if (node.resolutionOwned) return { origin_id: node.id, origin_slot: slot }
    const virtualLink = node.inputs[slot]?.link
    if (virtualLink != null) return resolveInput(graph, node, slot, visited, type)
    return undefined
  }
  return { origin_id: node.id, origin_slot: slot }
}
async function graphToPrompt(spec, side) {
  const graph = buildGraph(spec, side)
  const resolvers = new Map()
  if (side === 'v2') for (const type of USED) { const r = host.defined.get(type)?.resolve; if (r) resolvers.set(type, r) }
  const resolutions = await resolveFrontendNodesAsync(graph, resolvers)
  const output = {}
  for (const node of graph.nodes) {
    if (node.isVirtualNode || node.mode === NEVER || node.mode === BYPASS) continue
    const inputs = {}
    for (const [i, input] of node.inputs.entries()) {
      const r = resolveInput(graph, node, i, new Set())
      if (!r) continue
      const resolved = resolutions.get(`${r.origin_id}:${Number(r.origin_slot)}`)
      if (resolved?.kind === 'omitted') continue
      if (resolved?.kind === 'literal') { inputs[input.name] = resolved.value; continue }
      if (resolved?.kind === 'output') { inputs[input.name] = [resolved.nodeId, resolved.output]; continue }
      inputs[input.name] = [String(r.origin_id), Number(r.origin_slot)]
    }
    output[node.id] = { inputs, class_type: node.type }
  }
  for (const { inputs } of Object.values(output)) {
    for (const [k, v] of Object.entries(inputs)) if (Array.isArray(v) && v.length === 2 && !output[v[0]]) delete inputs[k]
  }
  return output
}
const R = TYPES.REROUTE
const FIXTURES = [
  ['P1 reroute pass-through', { nodes: [[1, 'Ckpt'], [2, R], [3, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0]] }],
  ['P2 reroute chain', { nodes: [[1, 'Ckpt'], [2, R], [3, R], [4, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0], [3, 0, 4, 0]] }],
  ['P3 reroute fan-out to two consumers', { nodes: [[1, 'Ckpt'], [2, R], [3, 'KSampler'], [4, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0], [2, 0, 4, 0]] }],
  ['P4 reroute with nothing connected', { nodes: [[2, R], [3, 'KSampler']], links: [[2, 0, 3, 0]] }],
  ['P5 muted source behind a reroute', { nodes: [[1, 'Ckpt', NEVER], [2, R], [3, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0]] }],
  ['P6 muted reroute', { nodes: [[1, 'Ckpt'], [2, R, NEVER], [3, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0]] }],
  ['P7 bypassed reroute', { nodes: [[1, 'Ckpt'], [2, R, BYPASS], [3, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0]] }],
  ['P8 control: bypassed LoRA, no reroute', { nodes: [[1, 'Ckpt'], [2, 'Lora', BYPASS], [3, 'KSampler']], links: [[1, 0, 2, 0], [1, 1, 2, 1], [2, 0, 3, 0]] }],
  ['P9 bypassed LoRA feeding a reroute', { nodes: [[1, 'Ckpt'], [2, 'Lora', BYPASS], [3, R], [4, 'KSampler']], links: [[1, 0, 2, 0], [1, 1, 2, 1], [2, 0, 3, 0], [3, 0, 4, 0]] }],
  ['P10 reroute, bypassed LoRA, reroute', { nodes: [[1, 'Ckpt'], [2, R], [3, 'Lora', BYPASS], [4, R], [5, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0], [1, 1, 3, 1], [3, 0, 4, 0], [4, 0, 5, 0]] }],
  ['P11 active LoRA feeding a reroute', { nodes: [[1, 'Ckpt'], [2, 'Lora'], [3, R], [4, 'KSampler']], links: [[1, 0, 2, 0], [1, 1, 2, 1], [2, 0, 3, 0], [3, 0, 4, 0]] }],
]
// Every resolver-less frontend type with an output, wired from a source and into a backend input.
for (const type of [TYPES.FAST_MUTER, TYPES.FAST_BYPASSER, TYPES.NODE_COLLECTOR, TYPES.REPEATER]) {
  FIXTURES.push([`P-${type} output into a backend input`, { nodes: [[1, 'Ckpt'], [2, type], [3, 'KSampler']], links: [[1, 0, 2, 0], [2, 0, 3, 0]] }])
}
// The same nodes in the usual wiring: backend outputs into their inputs only.
FIXTURES.push(['P-usual wiring: muter/bypasser/collector/repeater/relay/unmuter/button/label beside a pipeline', {
  nodes: [[1, 'Ckpt'], [2, 'Lora'], [3, 'KSampler'], [10, TYPES.FAST_MUTER], [11, TYPES.FAST_BYPASSER], [12, TYPES.NODE_COLLECTOR],
    [13, TYPES.REPEATER], [14, TYPES.RELAY], [15, TYPES.RANDOM_UNMUTER], [16, TYPES.FAST_ACTIONS_BUTTON], [17, TYPES.LABEL]],
  links: [[1, 0, 2, 0], [1, 1, 2, 1], [2, 0, 3, 0], [2, 0, 10, 0], [2, 0, 11, 0], [2, 0, 12, 0], [2, 0, 13, 0], [2, 0, 15, 0], [2, 0, 16, 0], [14, 0, 13, 0]],
}])
const deviations = []
for (const [name, spec] of FIXTURES) {
  let original, v2, error
  try { original = await graphToPrompt(spec, 'original'); v2 = await graphToPrompt(spec, 'v2') } catch (e) { error = String(e?.message ?? e) }
  const same = !error && JSON.stringify(original) === JSON.stringify(v2)
  if (!same) deviations.push(name)
  check('P prompt build', `${name}: v2 prompt equals the original's`, same, { original, v2, error }, [...new Set(spec.nodes.map((n) => n[1]).filter((t) => USED.includes(t)))])
}

// ---------------------------------------------------------------- M: modes
// Original side: the pristine compiled modules run with a minimal LiteGraph base class. The mode
// logic under test (BaseNodeModeChanger.setWidget/doModeChange, MuterNode/BypasserNode.handleAction,
// utils.changeModeOfNodes) is the original's own code.
async function originalModeChanger(typeFile) {
  const context = vm.createContext({ console: { log() {}, warn() {}, error() {} }, setTimeout, Promise })
  const registered = []
  const app = { registerExtension(ext) { registered.push(ext) } }
  class BaseAnyInputConnectedNode {
    constructor(title) { this.title = title; this.properties = {}; this.widgets = []; this.outputs = []; this.inputs = []; this.size = [200, 100] }
    addOutput(name, type) { this.outputs.push({ name, type }) }
    addWidget(type, name, value, callback, options) { const w = { type, name, value, callback, options }; this.widgets.push(w); return w }
    onConstructed() {}
    static setUp() { registered.push(this) }
  }
  const utilsSrc = readFileSync(path.join(PRISTINE_WEB, 'comfyui/utils.js'), 'utf8')
  const pick = (name) => { const s = utilsSrc.indexOf(`export function ${name}(`); const e = utilsSrc.indexOf('\nexport ', s + 10); return utilsSrc.slice(s, e) }
  const stubs = {
    '../../scripts/app.js': { app },
    './base_any_input_connected_node.js': { BaseAnyInputConnectedNode },
    '../../rgthree/common/shared_utils.js': { wait: () => Promise.resolve() },
    './constants.js': { NodeTypesString: { FAST_MUTER: TYPES.FAST_MUTER, FAST_BYPASSER: TYPES.FAST_BYPASSER } },
  }
  const cache = new Map()
  const get = (spec) => {
    if (cache.has(spec)) return cache.get(spec)
    let mod
    if (Object.hasOwn(stubs, spec)) {
      const ex = stubs[spec]
      mod = new vm.SyntheticModule(Object.keys(ex), function () { for (const [k, v] of Object.entries(ex)) this.setExport(k, v) }, { context, identifier: spec })
    } else if (spec === './utils.js') {
      const src = pick('changeModeOfNodes') + '\n' + pick('reduceNodesDepthFirst') + '\nexport const PassThroughFollowing = { ALL: 0, NONE: 1, REROUTE_ONLY: 2 };\n'
      mod = new vm.SourceTextModule(src, { context, identifier: spec })
    } else if (spec === './base_node_mode_changer.js' || spec === typeFile) {
      mod = new vm.SourceTextModule(readFileSync(path.join(PRISTINE_WEB, 'comfyui', spec.replace('./', '')), 'utf8'), { context, identifier: spec })
    } else throw new Error(`original: refusing to link ${spec}`)
    cache.set(spec, mod)
    return mod
  }
  const mod = get(typeFile)
  await mod.link(async (s) => get(s))
  await mod.evaluate()
  for (const ext of registered.filter((r) => typeof r.registerCustomNodes === 'function')) ext.registerCustomNodes()
  const Clazz = registered.find((r) => typeof r === 'function')
  return Clazz
}
const NUM = { always: 0, never: 2, bypass: 4 }
const SEQUENCE = [['click', 'A'], ['click', 'A'], ['click', 'B'], ['action', 'OFF'], ['action', 'Enable all'], ['action', 'Toggle all'],
  ['action', 'Toggle all'], ['click', 'B'], ['restrict', 'max one'], ['click', 'A'], ['click', 'B'], ['click', 'B'], ['restrict', 'always one'],
  ['click', 'A'], ['click', 'A'], ['click', 'B'], ['action', 'OFF'], ['action', 'Enable all']]
async function runOriginal(typeFile, offAction) {
  const Clazz = await originalModeChanger(typeFile)
  const node = new Clazz()
  const A = { mode: 0, title: 'Node A' }, B = { mode: 0, title: 'Node B' }
  const linked = { A, B }
  node.handleLinkedNodesStabilization([A, B])
  const trace = []
  for (const [op, arg] of SEQUENCE) {
    if (op === 'click') { const w = node.widgets[arg === 'A' ? 0 : 1]; w.value = !w.value; w.callback() }
    else if (op === 'action') await node.handleAction(arg === 'OFF' ? offAction : arg)
    else node.properties.toggleRestriction = arg
    node.handleLinkedNodesStabilization([A, B])
    trace.push([linked.A.mode, linked.B.mode])
  }
  return trace
}
async function runV2(type, offAction) {
  const { handleAction } = realm.ns('comfyui/base_node.js')
  const A = makeNode(host, { id: ++seq, type: 'KSampler', title: 'Node A', outputs: [{ name: 'LATENT', type: 'LATENT' }] })
  const B = makeNode(host, { id: ++seq, type: 'KSampler', title: 'Node B', outputs: [{ name: 'LATENT', type: 'LATENT' }] })
  const def = host.defined.get(type)
  const node = makeNode(host, { id: ++seq, type, inputs: [{ name: '', type: '*' }], outputs: (def.outputs ?? []).map((s) => ({ ...s })) })
  const hooks = hooksFor(host, type)
  fire(hooks, 'onCreated', node, { restored: false, loading: false })
  host.connect(A, 0, node, 0)
  node.inputs.add('', '*')
  host.connect(B, 0, node, 1)
  fire(hooks, 'onConnectionsChanged', node, { side: 'input' })
  await wait(150)
  const trace = []
  for (const [op, arg] of SEQUENCE) {
    if (op === 'click') node.widgets.get(arg === 'A' ? A.id : B.id).click()
    else if (op === 'action') await handleAction(node, arg === 'OFF' ? offAction : arg)
    else node.setProperty('toggleRestriction', arg)
    trace.push([NUM[A.getMode()], NUM[B.getMode()]])
  }
  return { trace, widgets: node.widgets.names().length }
}
for (const [type, file, offAction] of [[TYPES.FAST_MUTER, './muter.js', 'Mute all'], [TYPES.FAST_BYPASSER, './bypasser.js', 'Bypass all']]) {
  let original, v2, error
  try { original = await runOriginal(file, offAction); v2 = await runV2(type, offAction) } catch (e) { error = String(e?.stack ?? e).split('\n').slice(0, 3).join(' | ') }
  check('M modes', `${type}: ${SEQUENCE.length}-step click/action/restriction sequence leaves the same modes as the original`,
    !error && JSON.stringify(original) === JSON.stringify(v2?.trace), { sequence: SEQUENCE, original, v2: v2?.trace, error }, [type])
}
// Repeater: its own mode change repeats onto the nodes wired into it (node_mode_repeater.ts
// onModeChange, via base_node.ts's mode setter); the v2 listener is node_mode_repeater.js:114-142.
{
  const A = makeNode(host, { id: ++seq, type: 'KSampler', title: 'A', outputs: [{ name: 'LATENT', type: 'LATENT' }] })
  const B = makeNode(host, { id: ++seq, type: 'KSampler', title: 'B', outputs: [{ name: 'LATENT', type: 'LATENT' }] })
  const def = host.defined.get(TYPES.REPEATER)
  const rep = makeNode(host, { id: ++seq, type: TYPES.REPEATER, inputs: [{ name: '', type: '*' }], outputs: (def.outputs ?? []).map((s) => ({ ...s })) })
  const hooks = hooksFor(host, TYPES.REPEATER)
  fire(hooks, 'onCreated', rep, { restored: false, loading: false })
  host.connect(A, 0, rep, 0); rep.inputs.add('', '*'); host.connect(B, 0, rep, 1)
  fire(hooks, 'onConnectionsChanged', rep, { side: 'input' })
  await wait(150)
  const seen = []
  for (const to of [2, 4, 0]) {
    rep.setMode(MODE_NAMES[to])
    for (const cb of host.nodeChanged) cb({ property: 'mode', node: rep, graphId: 'root', from: 0, to })
    seen.push([NUM[A.getMode()], NUM[B.getMode()]])
  }
  check('M modes', 'Mute / Bypass Repeater: its mode (mute, bypass, active) is repeated onto both wired nodes',
    JSON.stringify(seen) === JSON.stringify([[2, 2], [4, 4], [0, 0]]), { seen }, [TYPES.REPEATER])
}
// Random Unmuter: with every wired node muted, one is unmuted for the run and muted again after
// (random_unmuter.ts; v2 random_unmuter.js:58-84).
{
  const A = makeNode(host, { id: ++seq, type: 'KSampler', title: 'A', mode: 'never', outputs: [{ name: 'LATENT', type: 'LATENT' }] })
  const B = makeNode(host, { id: ++seq, type: 'KSampler', title: 'B', mode: 'never', outputs: [{ name: 'LATENT', type: 'LATENT' }] })
  const un = makeNode(host, { id: ++seq, type: TYPES.RANDOM_UNMUTER, inputs: [{ name: '', type: '*' }] })
  const hooks = hooksFor(host, TYPES.RANDOM_UNMUTER)
  fire(hooks, 'onCreated', un, { restored: false, loading: false })
  host.connect(A, 0, un, 0); un.inputs.add('', '*'); host.connect(B, 0, un, 1)
  const during = [], after = []
  for (let run = 0; run < 20; run++) {
    for (const cb of host.beforeRun) cb()
    during.push([A.getMode(), B.getMode()].filter((m) => m === 'always').length)
    for (const cb of host.afterRun) cb()
    after.push([A.getMode(), B.getMode()].every((m) => m === 'never'))
  }
  check('M modes', 'Random Unmuter: exactly one of two muted inputs runs per queue, and both are muted again after (20 runs)',
    during.every((n) => n === 1) && after.every(Boolean), { during, after }, [TYPES.RANDOM_UNMUTER])
}

// ---------------------------------------------------------------- receipt
const failed = results.filter((r) => !r.pass).map((r) => `${r.group}: ${r.name}`)
const perType = Object.fromEntries(USED.map((t) => { const rs = results.filter((r) => r.types.includes(t)); return [t, { cases: rs.length, failed: rs.filter((r) => !r.pass).map((r) => r.name) }] }))
const receipt = {
  test: 'rgthree-comfy to-50% repair R1: frontend used types on host fakes', mode: NEGATIVE ? 'negative-control' : 'normal',
  node: process.version, status: failed.length ? 'FAIL' : 'PASS', cases: results.length, failed, uncaught,
  prompt_deviations: deviations,
  inputs_sha256: {
    resolution_ts: sha(RESOLUTION_TS),
    v2_modules: Object.fromEntries(realm.loaded.map((rel) => [rel, sha(path.join(WEB, rel))])),
    original_modules: Object.fromEntries(['comfyui/muter.js', 'comfyui/bypasser.js', 'comfyui/base_node_mode_changer.js', 'comfyui/utils.js'].map((rel) => [rel, sha(path.join(PRISTINE_WEB, rel))])),
  },
  per_type: perType,
  results,
}
writeFileSync(OUT, JSON.stringify(receipt, null, 1) + '\n')
written = true
console.log(JSON.stringify({ status: receipt.status, cases: receipt.cases, failed: receipt.failed.length, deviations }))
process.exit(0)
