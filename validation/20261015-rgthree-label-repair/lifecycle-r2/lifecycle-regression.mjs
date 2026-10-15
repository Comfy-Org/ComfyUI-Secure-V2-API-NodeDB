import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const lane = resolve(here, '..');
const workspace = resolve(lane, '../../../..');
const require = createRequire(import.meta.url);
const ts = require('../test-dependencies/typescript.cjs');
const base = join(lane, 'integration-r1/successor-candidate');
const candidate = join(here, 'candidate');
const actual = join(lane, 'integration-r1/frontend');
const constantsPath = join(workspace, 'corpus/packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/v2/web/comfyui/constants.js');
const fixturePath = join(lane, 'integration-r1/handoff-r2/label-acceptance-workflow.json');
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8'));
const TYPE = fixture.nodes[1].type;
const { SecureExtensionHost } = await import(pathToFileURL(join(base, 'extension-host/host-entry.mjs')));
const drawing = await import(pathToFileURL(join(base, 'pack/web/comfyui/label_drawing.js')));
const clone = (value) => structuredClone(value);
const plain = (value) => JSON.parse(JSON.stringify(value));
const tick = () => new Promise((done) => setImmediate(done));
const reports = [];
const cases = [];
const check = (name, run) => { run(); cases.push(name); };
const digest = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');

function context2d() {
  const ctx = { font: '', textAlign: 'left', textBaseline: 'alphabetic' };
  ctx.measureText = (text) => {
    const width = text.length * 6;
    const left = ctx.textAlign === 'center' ? width / 2 : ctx.textAlign === 'right' ? width : 0;
    return { width, actualBoundingBoxLeft: left, actualBoundingBoxRight: width - left, actualBoundingBoxAscent: 0, actualBoundingBoxDescent: 12 };
  };
  for (const name of ['save', 'restore', 'translate', 'rotate', 'beginPath', 'roundRect', 'fill', 'fillText', 'clearRect', 'setTransform', 'drawImage']) ctx[name] = () => {};
  return ctx;
}
class Bitmap {
  constructor(width, height) { Object.assign(this, { width, height, closed: false }); }
  close() { this.closed = true; }
}
globalThis.ImageBitmap = Bitmap;

// Only browser/graph storage and drawing are fixtures. The complete production
// defsRegistry, guest bootstrap, host dispatch, snapshots and nodeop table run
// unchanged. Queue delivery is deliberately delayed across host configure.
async function harness(packRoot, bootDefs) {
  const nodes = new Map(), handles = new Map(), types = Object.create(null);
  const warnings = [], outgoing = [], incoming = [], trace = [], errors = [], dialogs = [];
  let loading = false, receive;
  class FixtureNode {
    constructor(title) { Object.assign(this, { title, id: -1, type: TYPE, properties: {}, size: [100, 60], pos: [0, 0], flags: {}, widgets: [] }); }
    setProperty(name, value) { const old = this.properties[name]; this.properties[name] = value; this.onPropertyChanged?.(name, value, old); }
    setDirtyCanvas() {}
    addInput() { assert.fail('Label must remain slotless'); }
    addOutput() { assert.fail('Label must remain slotless'); }
  }
  const litegraph = {
    registered_node_types: types, NO_TITLE: 4,
    registerNodeType(type, Class) { types[type] = Class; },
    unregisterNodeType(type) { delete types[type]; },
  };
  const modules = new Map();
  function loadTS(file) {
    if (modules.has(file)) return modules.get(file);
    const source = readFileSync(join(actual, 'src/platform/nodeApi', file + '.ts'), 'utf8');
    const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }, reportDiagnostics: true });
    assert.equal((compiled.diagnostics || []).filter((d) => d.category === ts.DiagnosticCategory.Error).length, 0);
    const module = { exports: {} };
    modules.set(file, module.exports);
    const dependencies = {
      '@/lib/litegraph/src/LGraphNode': { LGraphNode: FixtureNode },
      '@/lib/litegraph/src/litegraph': { LiteGraph: litegraph, LGraphCanvas: { node_colors: {}, link_type_colors: {} } },
      '@/utils/litegraphUtil': { getLinkTypeColor: () => '#fff' },
      '@/i18n': { st: (_key, fallback) => fallback },
      '@/utils/formatUtil': { normalizeI18nKey: (value) => value },
      './nodeCanvas': { removeNodeCanvas() {} },
      './slotHandle': { slotShapeOf: (shape) => shape },
      './widgetHandle': { addDeclaredWidget() { assert.fail('Label has no widgets'); } },
      './widgetTypes': { createWidgetTypeRegistrar: () => () => { assert.fail('No widget registration'); } },
    };
    vm.runInNewContext(compiled.outputText, {
      exports: module.exports, module,
      console: { error: (...args) => warnings.push(args.join(' ')), warn: (...args) => warnings.push(args.join(' ')) },
      require(specifier) {
        if (Object.hasOwn(dependencies, specifier)) return dependencies[specifier];
        if (specifier === './errors' || specifier === './nodePresentation') return loadTS(specifier.slice(2));
        throw new Error(`Unexpected production dependency ${specifier}`);
      },
    }, { filename: file + '.ts' });
    return module.exports;
  }
  const registryModule = loadTS('defsRegistry');
  registryModule.provideGraphLoadingState(() => loading);
  function handleFor(id) {
    const node = nodes.get(String(id));
    if (!node) return undefined;
    if (handles.has(String(id))) return handles.get(String(id));
    const handle = {
      id: String(id), type: TYPE, graphId: 'root',
      snapshot: () => ({ id: String(id), type: TYPE, graphId: 'root', title: node.title, position: { x: node.pos[0], y: node.pos[1] }, size: { width: node.size[0], height: node.size[1] }, pinned: !!node.flags.pinned, collapsed: !!node.flags.collapsed }),
      getProperties: () => ({ ...node.properties }),
      getProperty: (name) => node.properties[name],
      setProperty: (name, value) => node.setProperty(name, value),
      getTitle: () => node.title, setTitle: (title) => { node.title = title; },
      getSize: () => ({ width: node.size[0], height: node.size[1] }),
      setSize: ({ width, height }) => { node.size = [width, height]; },
      setCollapsed: (value) => { node.flags.collapsed = value; },
      widgets: { all: () => [] }, inputs: { all: () => [] }, outputs: { all: () => [] },
      canvas(def) {
        const surface = { bounds: def.bounds, removed: false, setBounds(bounds) { this.bounds = bounds; }, remove() { this.removed = true; } };
        return surface;
      },
    };
    handles.set(String(id), handle);
    return handle;
  }
  const host = Object.create(SecureExtensionHost.prototype);
  host.comfy = {
    defs: registryModule.createDefRegistry().forMajor(handleFor),
    graph: { id: 'root', node: handleFor, root() { return this; }, subgraphs: () => [], pointerPosition: () => undefined, selection: () => [] },
    onNodeChanged() { return () => {}; },
  };
  host._definitionOwners = new Map(); host._definitionDisposers = new Set(); host._nodeCanvases = new Map();
  host._host = { send(_pack, message) { incoming.push(clone(message)); } };
  const context = vm.createContext({
    console: { error: (...args) => errors.push(args.join(' ')), warn: (...args) => warnings.push(args.join(' ')), log() {} },
    URL, Blob, ArrayBuffer, TextEncoder, TextDecoder, structuredClone, performance,
    setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
    location: { href: 'https://fixture.invalid/guest' }, navigator: {},
    OffscreenCanvas: class { constructor(width, height) { Object.assign(this, { width, height }); } getContext() { return context2d(); } },
    createImageBitmap: async (canvas) => new Bitmap(canvas.width, canvas.height),
    postMessage(message) {
      // ImageBitmap is a fixture, while every other transport field crosses an
      // actual structuredClone boundary, as it does in the worker.
      const copied = message.bitmap ? { ...clone({ ...message, bitmap: undefined }), bitmap: message.bitmap } : clone(message);
      outgoing.push(copied);
      trace.push({ direction: 'guest-host', t: message.t, op: message.op, args: message.args, hook: message.hook, nodeId: message.nodeId });
    },
    addEventListener(name, fn) { assert.equal(name, 'message'); assert.equal(receive, undefined); receive = fn; },
  });
  context.self = context;
  const moduleCache = new Map();
  async function makeModule(id) {
    if (moduleCache.has(id)) return moduleCache.get(id);
    let module;
    if (id === '/comfy/api/v2.js') {
      module = new vm.SyntheticModule(['comfy'], function () { this.setExport('comfy', context.comfy); }, { context, identifier: id });
    } else if (id === 'config-fixture') {
      module = new vm.SyntheticModule(['SERVICE'], function () { this.setExport('SERVICE', { getConfigValue() { assert.fail('Label does not read config'); } }); }, { context, identifier: id });
    } else {
      const path = id === 'constants' ? constantsPath : join(packRoot, 'pack/web/comfyui', id);
      module = new vm.SourceTextModule(readFileSync(path, 'utf8'), { context, identifier: path });
    }
    moduleCache.set(id, module);
    await module.link((specifier) => makeModule(specifier === './constants.js' ? 'constants' : specifier === './services/config_service.js' ? 'config-fixture' : specifier.replace(/^\.\//, '')));
    return module;
  }
  const guestSource = readFileSync(join(base, 'extension-host/guest.mjs'), 'utf8');
  vm.runInContext(guestSource, context, {
    filename: 'actual-guest.mjs',
    importModuleDynamically: async (specifier) => {
      assert.equal(specifier, 'label-fixture');
      const module = await makeModule('label.js'); await module.evaluate(); return module;
    },
  });
  async function pump(limit = 1000) {
    for (let step = 0; step < limit; step++) {
      while (outgoing.length) {
        const message = outgoing.shift();
        if (message.t === 'loaderror' || message.t === 'packerror') errors.push(message.error);
        await host._onPackMessage('rgthree-comfy', message);
      }
      while (incoming.length) {
        const message = incoming.shift();
        if (message.t === 'ret' && !message.ok) errors.push(message.error);
        await receive({ data: message });
      }
      await tick();
      if (!outgoing.length && !incoming.length) return;
    }
    throw new Error('Protocol queue did not settle within finite test steps');
  }
  let initialized = false;
  const init = receive({ data: { t: 'init', name: 'rgthree-comfy', packUrl: 'label-fixture', boot: { defs: bootDefs } } }).then(() => { initialized = true; });
  for (let i = 0; !initialized && i < 100; i++) { await pump(); await tick(); }
  assert.equal(initialized, true, 'actual guest module registration settles');
  await init;
  assert.ok(types[TYPE], 'actual defsRegistry registers Label');
  assert.deepEqual(errors, [], 'pack registers without protocol errors');
  function make(id, title = TYPE) {
    const node = new types[TYPE](); node.id = id; node.title = title; nodes.set(String(id), node); return node;
  }
  function configure(node, saved) {
    Object.assign(node, { title: saved.title, properties: clone(saved.properties || {}), size: clone(saved.size || [100, 60]), pos: clone(saved.pos || [0, 0]), flags: clone(saved.flags || {}) });
    node.onConfigure?.(clone(saved));
  }
  function add(node) { node.onAdded?.({}); }
  return { nodes, warnings, errors, trace, incoming, outgoing, dialogs, host, make, configure, add, pump, setLoading(value) { loading = value; } };
}

const catalogues = [[], [{ type: 'CLIPTextEncode', title: 'CLIP Text Encode', inputs: [], outputs: [] }]];
for (const [index, catalogue] of catalogues.entries()) {
  for (const [name, root] of [['frozen-r3', base], ['lifecycle-r2', candidate]]) {
    const h = await harness(root, catalogue);
    const registered = h.trace.filter((m) => m.t === 'extend' || m.t === 'define').map((m) => m.t);
    check(`${name}/${index}: actual registration ordering evidence`, () => assert.deepEqual(registered, name === 'frozen-r3' ? ['define', 'extend'] : ['extend', 'define']));
    const before = h.trace.length;
    h.setLoading(true);
    // Exactly the production LGraph.configure order: all onAdded callbacks are
    // queued before each node receives its saved configure state.
    const loaded = fixture.nodes.filter((n) => n.type === TYPE).map((saved) => h.make(saved.id, saved.title));
    loaded.forEach(h.add);
    loaded.forEach((node, i) => h.configure(node, fixture.nodes[i + 1]));
    h.setLoading(false);
    const created = h.incoming.filter((m) => m.t === 'hook' && m.hook === 'onCreated');
    check(`${name}/${index}: actual onCreated captures pre-configure properties and loading flag`, () => {
      assert.equal(created.length, 2);
      for (const m of created) { assert.deepEqual(m.snapshot.properties, {}); assert.deepEqual(m.arg, { loading: true, restored: false }); }
    });
    await h.pump();
    assert.deepEqual(h.errors, []);
    const final = loaded.map((node) => ({ id: node.id, title: node.title, properties: clone(node.properties), size: clone(node.size), flags: clone(node.flags) }));
    reports.push({ source: name, catalogue: index, registration: registered, final, warnings: h.warnings, trace: h.trace.slice(before) });
    if (name === 'frozen-r3') {
      for (const [i, node] of loaded.entries()) {
        check(`${name}/${index}/node${node.id}: saved-property assertion fails against actual old lifecycle`, () => {
          assert.throws(() => assert.deepEqual(node.properties, fixture.nodes[i + 1].properties), assert.AssertionError);
          assert.deepEqual(node.properties, plain(drawing.LABEL_DEFAULTS));
        });
      }
      check(`${name}/${index}: production registry reports ignored late edit extension`, () => {
        assert.ok(h.warnings.some((w) => w.includes('will not be applied')));
        assert.equal(typeof loaded[0].onDblClick, 'undefined');
      });
      continue;
    }
    for (const [i, node] of loaded.entries()) {
      const saved = fixture.nodes[i + 1];
      check(`${name}/${index}/node${node.id}: all eight saved properties, title, pin and layout preserved`, () => {
        assert.equal(Object.keys(node.properties).length, 8);
        assert.deepEqual(node.properties, saved.properties);
        assert.equal(node.title, saved.title); assert.equal(node.flags.pinned, saved.flags.pinned);
        const layout = drawing.layoutLabel(saved.title, saved.properties, context2d());
        assert.deepEqual(node.size, [layout.width, layout.height]);
      });
    }
    check(`${name}/${index}: no creation defaults return to configured host nodes`, () => assert.equal(h.trace.slice(before).filter((m) => m.t === 'nodeop' && m.op === 'setProperty').length, 0));
    check(`${name}/${index}: edit hooks installed by actual registry`, () => {
      assert.equal(h.warnings.length, 0);
      assert.equal(typeof loaded[0].onDblClick, 'function');
      const items = []; loaded[0].getExtraMenuOptions({}, items);
      assert.ok(items.some((item) => item.content === 'Edit label' && typeof item.callback === 'function'));
      loaded[0].onDblClick();
      assert.equal(h.incoming.at(-1).hook, 'onDoubleClick');
      // Confirm the callback dispatch without opening a browser dialog in this
      // source test. Actual field editing remains in original111 + browser gate.
      h.incoming.pop();
    });
    const fresh = h.make(4); h.add(fresh); await h.pump();
    check(`${name}/${index}: fresh creation initializes all original defaults`, () => {
      assert.deepEqual(fresh.properties, plain(drawing.LABEL_DEFAULTS));
      assert.equal(fresh.flags.collapsed, false);
      assert.ok(h.host._nodeCanvases.size >= 3);
    });
    const pasted = h.make(5); h.configure(pasted, { ...fixture.nodes[1], id: 5 }); h.add(pasted);
    const pastedCreated = h.incoming.find((m) => m.t === 'hook' && m.hook === 'onCreated');
    check(`${name}/${index}: pasted node has restored true and loading false`, () => assert.deepEqual(pastedCreated.arg, { restored: true, loading: false }));
    await h.pump();
    check(`${name}/${index}: pasted properties and title are retained`, () => { assert.deepEqual(pasted.properties, fixture.nodes[1].properties); assert.equal(pasted.title, fixture.nodes[1].title); });
    const partial = h.make(6); h.setLoading(true); h.add(partial); h.configure(partial, { ...fixture.nodes[2], id: 6, properties: { fontSize: 27, angle: 45 } }); h.setLoading(false); await h.pump();
    check(`${name}/${index}: configured partial legacy properties fill only missing defaults`, () => assert.deepEqual(partial.properties, { ...plain(drawing.LABEL_DEFAULTS), fontSize: 27, angle: 45 }));
    const reloaded = { ...fixture.nodes[1], properties: { ...fixture.nodes[1].properties, fontSize: 31, textAlign: 'right', angle: -25 } };
    h.configure(loaded[0], reloaded); await h.pump();
    check(`${name}/${index}: subsequent configure keeps newly saved values`, () => assert.deepEqual(loaded[0].properties, reloaded.properties));
    check(`${name}/${index}: complete source replay has no host or guest protocol errors`, () => assert.deepEqual(h.errors, []));
  }
}

const sources = {};
for (const path of [join(base, 'pack/web/comfyui/label.js'), join(candidate, 'pack/web/comfyui/label.js'), join(base, 'pack/web/comfyui/label_drawing.js'), join(base, 'extension-host/guest.mjs'), join(base, 'extension-host/host-entry.mjs'), join(actual, 'src/platform/nodeApi/defsRegistry.ts'), join(actual, 'src/lib/litegraph/src/LGraph.ts'), join(actual, 'src/scripts/app.ts'), constantsPath, fixturePath, fileURLToPath(import.meta.url)]) sources[path.replace(workspace + '\\', '').replaceAll('\\', '/')] = digest(path);
writeFileSync(join(here, 'evidence/lifecycle-regression.json'), JSON.stringify({ status: 'PASS', checks: cases.length, cases, sources, boundaries: ['Production defsRegistry transpiled without changing implementation; external LGraphNode storage, graph handles, canvas pixels and UI are fixtures.', 'Complete production guest bootstrap and host-entry dispatch/snapshot/nodeop methods execute unchanged with structured-cloned delayed messages.', 'Actual browser save/load, rendering and editing still require operator acceptance.'], reports }, null, 2) + '\n');
console.log(JSON.stringify({ lifecycle: 'PASS', checks: cases.length, old_source_negative_controls: 4, source_delta: 'pack/web/comfyui/label.js only' }));
