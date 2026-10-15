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
const base = join(here, 'baseline');
const candidate = base;
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
  const ctx = { operations: [], font: '', textAlign: 'left', textBaseline: 'alphabetic' };
  ctx.measureText = (text) => {
    const width = text.length * 6;
    const left = ctx.textAlign === 'center' ? width / 2 : ctx.textAlign === 'right' ? width : 0;
    return { width, actualBoundingBoxLeft: left, actualBoundingBoxRight: width - left, actualBoundingBoxAscent: 0, actualBoundingBoxDescent: 12 };
  };
  for (const name of ['save', 'restore', 'translate', 'rotate', 'beginPath', 'roundRect', 'fill', 'fillText', 'clearRect', 'setTransform', 'drawImage']) ctx[name] = (...args) => ctx.operations.push([name, ...args]);
  for (const name of ['font', 'textAlign', 'textBaseline', 'fillStyle']) {
    let value = ctx[name];
    Object.defineProperty(ctx, name, { get() { return value; }, set(next) { value = next; ctx.operations.push(['set', name, next]); } });
  }
  return ctx;
}
class Bitmap {
  constructor(width, height, operations) { Object.assign(this, { width, height, operations, closed: false }); }
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
  const guestIntervals = new Set();
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
  host._host = { send(_pack, message) { incoming.push(clone(message)); trace.push({ direction: 'host-guest', message: clone(message) }); } };
  const context = vm.createContext({
    console: { error: (...args) => errors.push(args.join(' ')), warn: (...args) => warnings.push(args.join(' ')), log() {} },
    URL, Blob, ArrayBuffer, TextEncoder, TextDecoder, structuredClone, performance,
    setTimeout, clearTimeout, queueMicrotask,
    setInterval(...args) { const timer = setInterval(...args); guestIntervals.add(timer); return timer; },
    clearInterval(timer) { clearInterval(timer); guestIntervals.delete(timer); },
    location: { href: 'https://fixture.invalid/guest' }, navigator: {},
    OffscreenCanvas: class {
      constructor(width, height) { this.context = context2d(); this.width = width; this.height = height; }
      set width(value) { this.w = value; this.context.operations = []; } get width() { return this.w; }
      set height(value) { this.h = value; this.context.operations = []; } get height() { return this.h; }
      getContext() { return this.context; }
    },
    createImageBitmap: async (canvas) => new Bitmap(canvas.width, canvas.height, clone(canvas.context.operations)),
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
  return { nodes, warnings, errors, trace, incoming, outgoing, dialogs, host, make, configure, add, pump, guestNode: (id) => context.comfy.graph.node(String(id)), setLoading(value) { loading = value; }, close() { for (const timer of guestIntervals) clearInterval(timer); guestIntervals.clear(); } };
}

const h = await harness(base, []);
const saved = fixture.nodes[1];
try {
  const node = h.make(saved.id, saved.title);
  h.setLoading(true); h.add(node); h.configure(node, saved); h.setLoading(false);
  await h.pump();
  const accepted = () => h.host._nodeCanvases.get(JSON.stringify(['rgthree-comfy', 'root', String(node.id)]));
  const drawFor = (properties) => {
    const layout = drawing.layoutLabel(node.title, properties, context2d());
    const context = context2d();
    context.setTransform(1, 0, 0, 1, -layout.bounds.x, -layout.bounds.y);
    drawing.drawLabel(context, layout, properties);
    return { operations: context.operations, bounds: layout.bounds, width: layout.width, height: layout.height };
  };
  check('loaded fixture creates an accepted bitmap with exact current draw commands', () => {
    assert.deepEqual(accepted().bitmap.operations, drawFor(node.properties).operations);
    assert.equal(accepted().bitmap.closed, false);
  });
  for (const [route, property, value] of [
    ['host', 'angle', -20], ['guest', 'angle', 35], ['host', 'angle', 0],
    ['guest', 'fontSize', 31], ['host', 'textAlign', 'right'], ['guest', 'fontColor', '#eeddcc'],
  ]) {
    const before = clone(node.properties), start = h.trace.length;
    const previousBitmap = accepted().bitmap;
    if (route === 'host') node.setProperty(property, value);
    else h.guestNode(node.id).setProperty(property, value);
    await h.pump();
    const after = clone(node.properties), surface = accepted();
    const hook = h.trace.slice(start).find((entry) => entry.direction === 'host-guest' && entry.message.t === 'hook' && entry.message.hook === 'onPropertyChanged');
    assert.ok(hook, 'actual property callback was transported');
    check(`${route}/${property}: host commits the requested new property`, () => assert.equal(after[property], value));
    check(`${route}/${property}: actual hook snapshot precedes property commit`, () => {
      assert.equal(hook.message.arg.value, value);
      assert.equal(hook.message.arg.previous, before[property]);
      assert.equal(hook.message.snapshot.properties[property], before[property]);
    });
    const actualDraw = clone(surface.bitmap.operations);
    const wanted = drawFor(after), previous = drawFor(before);
    check(`${route}/${property}: final accepted draw commands lag one property mutation`, () => {
      assert.deepEqual(actualDraw, previous.operations);
      assert.throws(() => assert.deepEqual(actualDraw, wanted.operations), assert.AssertionError);
      assert.deepEqual(surface.bounds, previous.bounds);
      assert.equal(surface.bitmap.closed, false);
      assert.equal(previousBitmap.closed, true);
    });
    reports.push({ route, property, value, previous: before[property], final_graph: after, event: hook.message.arg, event_snapshot: hook.message.snapshot.properties, accepted_revision: surface.revision, accepted_bounds: surface.bounds, actual_draw_commands: actualDraw, required_draw_commands: wanted.operations });
  }
  check('no actual host or guest protocol errors occurred', () => assert.deepEqual(h.errors, []));
} finally { h.close(); }
const sources = {};
for (const path of [join(base, 'pack/web/comfyui/label.js'), join(base, 'pack/web/comfyui/label_drawing.js'), join(base, 'extension-host/guest.mjs'), join(base, 'extension-host/host-entry.mjs'), join(base, 'extension-host/ui-renderer.mjs'), join(actual, 'src/platform/nodeApi/defsRegistry.ts'), join(actual, 'src/platform/nodeApi/nodeHandle.ts'), fileURLToPath(import.meta.url)]) sources[path.replace(workspace + '\\', '').replaceAll('\\', '/')] = digest(path);
writeFileSync(join(here, 'evidence/run1/PROPERTY_DRAW_DIAGNOSTIC.json'), JSON.stringify({ status: 'DIAGNOSTIC_CONFIRMED', checks: cases.length, expected_property_draw_failures: reports.length, cases, source_sha256: sources, reports, boundary: 'Production registry, complete guest, Label source/layout/draw, host callback snapshots, nodeop and accepted frame lifecycle run unchanged. Canvas records exact drawing operations in an ImageBitmap fixture; it is not a browser pixel/raster acceptance result. No properties or graph state are restored between mutations.' }, null, 2) + '\n');
console.log(JSON.stringify({ status: 'DIAGNOSTIC_CONFIRMED', checks: cases.length, stale_accepted_frames: reports.length }));
