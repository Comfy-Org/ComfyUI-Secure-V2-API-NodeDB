import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import { additionalBehavior } from '../tests/behavior_extra.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const ts = require('../test-dependencies/typescript.cjs');
const compiler = await import('../test-dependencies/compiler-sfc.mjs');
const candidate = join(root, 'lifecycle-r2/candidate');
let cases = 0;
const results = [];
async function check(name, fn) {
  await fn(); cases++; results.push(name);
}
const plain = (value) => JSON.parse(JSON.stringify(value));
const tick = () => new Promise((done) => setImmediate(done));

function context2d() {
  const operations = [];
  const context = { operations, font: '', textAlign: 'left', textBaseline: 'alphabetic',
    measureText(text) {
      const width = text.length * 6;
      const left = this.textAlign === 'center' ? width / 2 : this.textAlign === 'right' ? width : 0;
      return { width, actualBoundingBoxLeft: left, actualBoundingBoxRight: width - left,
        actualBoundingBoxAscent: 0, actualBoundingBoxDescent: 12 };
    },
  };
  for (const method of ['save', 'restore', 'translate', 'rotate', 'beginPath', 'roundRect', 'fill', 'fillText', 'clearRect', 'setTransform', 'drawImage']) {
    context[method] = (...args) => operations.push([method, ...args]);
  }
  for (const field of ['font', 'textAlign', 'textBaseline', 'fillStyle']) {
    let current = context[field];
    Object.defineProperty(context, field, {
      get: () => current,
      set: (value) => { current = value; operations.push([field, value]); },
      configurable: true,
    });
  }
  return context;
}

const drawing = await import(pathToFileURL(join(candidate, 'pack/web/comfyui/label_drawing.js')));
const originalPath = resolve(root, '../../../../corpus/packs/rgthree-comfy/x6b76ee6/rgthree-comfy-HEAD/web/comfyui/label.js');
const original = readFileSync(originalPath, 'utf8');
const originalContext = vm.createContext({
  app: { registerExtension() {} }, NodeTypesString: { LABEL: 'Label (rgthree)' },
  rgthree: {}, LiteGraph: { NO_TITLE: 1 },
  LGraphCanvas: class { drawNode() {} }, LGraph: class { getNodeOnPos() {} },
  RgthreeBaseVirtualNode: class { constructor(title) { this.title = title; this.properties = {}; this.size = [0, 0]; this.flags = {}; } onConstructed() {} },
});
vm.runInContext(original.replace(/^import .*;\r?\n/gm, '').replace('export class Label', 'class Label') + '\nthis.OriginalLabel = Label;', originalContext);

for (const title of ['Hello', 'first\\nsecond\n\n', '', 'Unicode Ω 漢字']) {
  for (const align of ['left', 'center', 'right']) {
    for (const angle of [0, 45, -90, 180]) {
      await check(`original-draw:${JSON.stringify(title)}:${align}:${angle}`, () => {
        const node = new originalContext.OriginalLabel(title);
        Object.assign(node.properties, { textAlign: align, angle, padding: 3, borderRadius: 4,
          fontSize: 17, fontColor: '#ffaa0088', backgroundColor: '#123456' });
        const oldContext = context2d(), newContext = context2d();
        node.draw(oldContext);
        const layout = drawing.layoutLabel(title, node.properties, context2d());
        drawing.drawLabel(newContext, layout, node.properties);
        assert.deepEqual([layout.width, layout.height], Array.from(node.size));
        assert.deepEqual(plain(newContext.operations), plain(oldContext.operations));
        assert.ok(layout.bounds.width > 0 && layout.bounds.height > 0);
        for (const [x, y] of [[0, 0], [layout.width, 0], [layout.width, layout.height], [0, layout.height]]) {
          const cx = layout.width / 2, cy = layout.height / 2;
          const rx = cx + (x - cx) * Math.cos(layout.angle) - (y - cy) * Math.sin(layout.angle);
          const ry = cy + (x - cx) * Math.sin(layout.angle) + (y - cy) * Math.cos(layout.angle);
          assert.ok(rx >= layout.bounds.x && rx <= layout.bounds.x + layout.bounds.width);
          assert.ok(ry >= layout.bounds.y && ry <= layout.bounds.y + layout.bounds.height);
        }
      });
    }
  }
}

const compiledModules = new Map();
const domCanvases = [];
const documentStub = { createElement(name) {
  assert.equal(name, 'canvas');
  const context = context2d();
  const canvas = { width: 0, height: 0, style: {}, getContext: () => context };
  domCanvases.push(canvas); return canvas;
} };
function loadTS(relative) {
  if (compiledModules.has(relative)) return compiledModules.get(relative);
  const source = readFileSync(relative === 'errors.ts' ? join(root, 'integration-r1/frontend/src/platform/nodeApi/errors.ts') : join(candidate, 'frontend/src/platform/nodeApi', relative), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }, reportDiagnostics: true });
  assert.equal((compiled.diagnostics || []).filter((d) => d.category === ts.DiagnosticCategory.Error).length, 0);
  const module = { exports: {} };
  compiledModules.set(relative, module.exports);
  const sandbox = { module, exports: module.exports, document: documentStub,
    require(specifier) { if (specifier === '@/platform/telemetry/reportError') return { reportError() {} }; return loadTS(`${specifier.replace('./', '')}.ts`); } };
  vm.runInNewContext(compiled.outputText, sandbox, { filename: relative });
  return module.exports;
}
const presentation = loadTS('nodePresentation.ts');
const canvasAPI = loadTS('nodeCanvas.ts');

await check('presentation validation and pinned hit behavior', () => {
  assert.throws(() => presentation.validateNodePresentation({ chrome: 'none', arbitrary: true }));
  assert.throws(() => presentation.validateNodePresentation({ resizable: 0 }));
  const remove = presentation.registerNodePresentation('owned', { chrome: 'none', resizable: false, collapsible: false, pinnedInteraction: 'pass-through' });
  const node = { type: 'owned', flags: { pinned: true } };
  assert.equal(presentation.passesPinnedPrimaryClick(node, 0, false), true);
  assert.equal(presentation.passesPinnedPrimaryClick(node, 0, true), false);
  assert.equal(presentation.passesPinnedPrimaryClick(node, 2, false), false);
  remove();
  assert.equal(presentation.passesPinnedPrimaryClick(node, 0, false), false);
});
const valid = { x: -20, y: -10, width: 80, height: 40 };
const invalidBounds = [null, [], {}, { ...valid, width: Infinity }, { ...valid, x: NaN },
  { ...valid, width: 0 }, { ...valid, width: 8193 }, { ...valid, x: -8193 },
  { ...valid, width: 4097, height: 4097 }, { ...valid, html: '<script>' }];
for (const bounds of invalidBounds) await check(`frontend-invalid-bounds:${cases}`, () => assert.throws(() => canvasAPI.validateNodeCanvasBounds(bounds)));
await check('canvas local origin, unchanged layout, replacement and removal', () => {
  presentation.registerNodePresentation('surface-owner', { chrome: 'none' });
  const node = { type: 'surface-owner', size: [23, 7], setDirtyCanvas() {} };
  const handle = canvasAPI.createNodeCanvas(node, { bounds: valid, draw(ctx) { ctx.fillText('hello', 0, 0); } });
  assert.deepEqual(node.size, [23, 7]);
  assert.deepEqual(plain(domCanvases.at(-1).getContext().operations[0]), ['setTransform', 1, 0, 0, 1, 20, 10]);
  const draw = context2d(); canvasAPI.drawNodeCanvas(node, draw);
  assert.deepEqual(draw.operations[0].slice(2), [-20, -10]);
  handle.setBounds({ ...valid, x: -33 });
  assert.equal(canvasAPI.nodeCanvasBounds(node).x, -33);
  const previous = domCanvases.at(-1);
  canvasAPI.createNodeCanvas(node, { bounds: valid, draw() {} });
  assert.equal(previous.width, 0);
  handle.remove();
  assert.ok(canvasAPI.nodeCanvasBounds(node));
  canvasAPI.removeNodeCanvas(node);
  assert.equal(canvasAPI.nodeCanvasBounds(node), undefined);
});

class Bitmap { constructor(width, height) { this.width = width; this.height = height; this.closed = 0; } close() { this.closed++; } }
globalThis.ImageBitmap = Bitmap;
const { SecureExtensionHost, nodeCanvasBoundsData } = await import(pathToFileURL(join(candidate, 'extension-host/host-entry.mjs')));
for (const bounds of invalidBounds) await check(`host-invalid-bounds:${cases}`, () => assert.throws(() => nodeCanvasBoundsData(bounds)));
const messages = [];
const host = Object.create(SecureExtensionHost.prototype);
const liveNodes = new Map();
const surfaces = [];
const mockNode = (id, graphId, type) => ({ id, graphId, type,
  canvas(def) { const record = { def, removed: false, bounds: def.bounds, setBounds(bounds) { this.bounds = bounds; }, remove() { this.removed = true; } }; surfaces.push(record); return record; },
});
liveNodes.set('g:1', mockNode('1', 'g', 'owned'));
liveNodes.set('sub:1', mockNode('1', 'sub', 'owned'));
host.comfy = { graph: { id: 'g', node(id) { return liveNodes.get(`g:${id}`); }, root() { return this; }, subgraphs() { return [{ id: 'sub', node(id) { return liveNodes.get(`sub:${id}`); } }]; } } };
host._definitionOwners = new Map([['owned', 'pack-a']]);
host._nodeCanvases = new Map();
host._host = { send(pack, value) { messages.push({ pack, value }); } };
const mount = (pack, nodeId, graphId, surfaceId = 'nc-1') => host._onPackMessage(pack, { t: 'nodecanvasmount', id: `req-${messages.length}`, nodeId, graphId, surfaceId, bounds: valid });
await check('canvas rejects a different pack owner', async () => {
  await mount('pack-b', '1', 'g');
  assert.equal(host._nodeCanvases.size, 0);
});
await check('canvas keys include graph scope', async () => {
  await mount('pack-a', '1', 'g'); await mount('pack-a', '1', 'sub');
  assert.equal(host._nodeCanvases.size, 2);
});
await check('bitmap replacement, stale revision and mismatch disposal', async () => {
  const frame = (bitmap, revision, bounds = valid) => host._onPackMessage('pack-a', { t: 'nodecanvasframe', nodeId: '1', graphId: 'g', surfaceId: 'nc-1', bitmap, revision, bounds });
  const a = new Bitmap(80, 40), b = new Bitmap(80, 40), stale = new Bitmap(80, 40), wrong = new Bitmap(81, 40);
  await frame(a, 1); await frame(b, 2); await frame(stale, 1); await frame(wrong, 3);
  assert.equal(a.closed, 1); assert.equal(stale.closed, 1); assert.equal(wrong.closed, 1); assert.equal(b.closed, 0);
  await host._onPackMessage('pack-a', { t: 'nodecanvasremove', id: 'remove', nodeId: '1', graphId: 'g', surfaceId: 'nc-1' });
  assert.equal(b.closed, 1); assert.equal(host._nodeCanvases.size, 1);
  assert.equal(surfaces[0].removed, true);
});
await check('canvas per-pack pixel budget', () => {
  const key = 'other';
  host._nodeCanvases.set(key, { pack: 'pack-a', bounds: { x: 0, y: 0, width: 8192, height: 8192 } });
  assert.throws(() => host._checkNodeCanvasBudget('pack-a', 'new', valid));
  host._nodeCanvases.delete(key);
});

const guestSource = readFileSync(join(candidate, 'extension-host/guest.mjs'), 'utf8');
const guestAST = ts.createSourceFile('guest.mjs', guestSource, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
const declarations = new Map();
function findFunctions(node) { if (ts.isFunctionDeclaration(node) && node.name) declarations.set(node.name.text, node.getText(guestAST)); ts.forEachChild(node, findFunctions); }
findFunctions(guestAST);
const sent = [], rpcCalls = [], pendingBitmaps = [];
const guestContext = vm.createContext({
  seq: 1, nodeCanvasSurfaces: new Map(), wrapContext: (ctx) => ctx,
  OffscreenCanvas: class { constructor(width, height) { this.width = width; this.height = height; this.context = context2d(); } getContext() { return this.context; } },
  createImageBitmap(canvas) { return new Promise((resolve) => pendingBitmaps.push(() => { const bitmap = new Bitmap(canvas.width, canvas.height); resolve(bitmap); return bitmap; })); },
  self: { postMessage(message) { sent.push(message); } },
  rpc(kind, message) { rpcCalls.push({ kind, message }); return Promise.resolve(null); },
});
vm.runInContext(`${declarations.get('checkedNodeCanvasBounds')}\n${declarations.get('makeNodeCanvas')}\nthis.makeSurface = makeNodeCanvas;`, guestContext);
await check('guest frames remain ordered and removed frames close', async () => {
  const ref = { id: '1', snap: { graphId: 'g' }, whenReal(fn) { fn(); } };
  const surface = guestContext.makeSurface(ref, { bounds: valid, draw(ctx) { ctx.fillText('hello', 0, 0); } });
  await tick();
  assert.equal(rpcCalls[0].kind, 'nodecanvasmount');
  surface.redraw();
  surface.redraw();
  assert.equal(pendingBitmaps.length, 1, 'only one bitmap snapshot is in flight');
  const obsolete = pendingBitmaps.shift()();
  await tick();
  const current = pendingBitmaps.shift()();
  await tick();
  assert.equal(obsolete.closed, 1); assert.equal(current.closed, 0);
  assert.equal(sent.filter((m) => m.t === 'nodecanvasframe').length, 1);
  surface.redraw(); await tick(); surface.remove();
  const removed = pendingBitmaps.shift()(); await tick();
  assert.equal(removed.closed, 1);
  assert.throws(() => surface.setBounds(valid));
});

function filesBelow(directory) { return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? filesBelow(join(directory, entry.name)) : [join(directory, entry.name)]); }
await additionalBehavior({ check, candidate, drawing, context2d, ts, originalContext, host, liveNodes, valid, Bitmap, tick });
await check('generated public declarations type-check valid calls and reject forbidden shapes', () => {
  const options = { noEmit: true, strict: true, skipLibCheck: true, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, types: [] };
  const program = ts.createProgram([join(candidate, 'pack/comfy-api.d.ts'), join(root, 'integration-r1/public_consumer.ts')], options);
  const diagnostics = ts.getPreEmitDiagnostics(program);
  assert.equal(diagnostics.length, 0, ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: (name) => name, getCurrentDirectory: () => root, getNewLine: () => '\n'
  }));
});
for (const path of filesBelow(join(candidate, 'frontend')).filter((path) => path.endsWith('.ts') || path.endsWith('.vue'))) {
  await check(`parse:${path.slice(candidate.length + 1)}`, () => {
    const source = readFileSync(path, 'utf8');
    if (path.endsWith('.vue')) {
      const parsed = compiler.parse(source, { filename: path });
      assert.deepEqual(parsed.errors, []);
      const result = compiler.compileTemplate({ source: parsed.descriptor.template.content, filename: path, id: 'label-test' });
      assert.deepEqual(result.errors, []);
      const script = ts.createSourceFile(path, parsed.descriptor.scriptSetup.content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
      assert.equal(script.parseDiagnostics.length, 0);
    } else {
      const script = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
      assert.equal(script.parseDiagnostics.length, 0);
    }
  });
}
console.log(JSON.stringify({ status: 'PASS', cases, results,
  scope: 'Original draw-operation parity; Label registration, property/dialog/lifecycle behavior; bounded API; actual transport and pointer routing methods; source parsing.',
  not_proven: ['Browser raster/font parity', 'Real worker/iframe transport and workflow reload', 'Vue pointer and renderer integration', 'Whole repository typecheck/lint/build', 'Complete rgthree pack acceptance'] }, null, 2));
