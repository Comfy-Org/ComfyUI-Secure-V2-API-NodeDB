import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
const v2 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), pristine = path.dirname(v2);
let passed = 0;
const check = fn => { fn(); passed++; };
const clone = x => JSON.parse(JSON.stringify(x));
const facade = { defs: { extend(kind, apply) { apply({ onCreated() {}, onConfigured() {}, onRemoved() {} }); } } };
const context = vm.createContext({ console, Math, Number, JSON, String, Object, Array, WeakMap, parseFloat, parseInt });
const modules = new Map();
async function load(file) {
    if (modules.has(file)) return modules.get(file);
    const module = new vm.SourceTextModule(fs.readFileSync(file, 'utf8'), { context, identifier: file });
    modules.set(file, module);
    await module.link(async spec => {
        if (spec === '/comfy/api/v2.js') {
            const api = new vm.SyntheticModule(['comfy'], function() { this.setExport('comfy', facade); }, { context });
            await api.link(() => {}); return api;
        }
        return load(path.resolve(path.dirname(file), spec));
    });
    return module;
}
const module = await load(path.join(v2, 'web/secureDimensionControl.js')); await module.evaluate();
const { pointerDimensions, canvasBounds, validateCanvasWork, createDimensionController } = module.namespace;
const defaults = modules.get(path.join(v2, 'web/secureDimensionDefaults.js')).namespace.DIMENSION_DEFAULTS;
function recording() {
    const calls = [];
    const ctx = new Proxy({}, { get: (obj, key) => (...args) => calls.push([key, ...args]),
        set(obj, key, value) { calls.push(['set', key, value]); return true; } });
    return { ctx, calls };
}
function fixture(kind) {
    const widgets = [
        ['width', 640], ['height', 480], ['fps', 30], ['length_selector', 'Use # Frames'],
        ['total_frames', 120], ['num_seconds', 4],
    ].map(([name, value]) => ({
        name, value, listeners: new Set(), getValue() { return this.value; },
        setValue(next) { if (Object.is(next, this.value)) return; this.value = next; for (const fn of [...this.listeners]) fn(next); },
        setHidden(value) { this.hidden = value; },
        on(event, fn) { assert.equal(event, 'change'); this.listeners.add(fn); return () => this.listeners.delete(fn); },
    }));
    const properties = {};
    const node = { id: '1', graphId: 'workflow', type: kind, properties,
        widgets: { get: name => widgets.find(w => w.name === name), all: () => widgets,
            canvas(def) { node.canvas = def; return { redraw() {} }; } },
        getSize: () => ({ width: 400, height: 305 }),
        getProperty: key => properties[key], getProperties: () => clone(properties),
        setProperty(key, value) { properties[key] = value; }, setSizeConstraints() {},
    };
    return node;
}
for (const kind of ['TKVideoUserInputs', 'TKPhotoUserInputs', 'TKVideoUserInputsBasic']) {
    let code = fs.readFileSync(path.join(pristine, 'js', kind + '.js'), 'utf8').replace(/^import .*;\s*/gm, '');
    const className = code.match(/class (\w+)/)[1];
    const originalContext = vm.createContext({ console: { log() {}, debug() {} },
        app: { registerExtension() {}, graph: { setDirtyCanvas() {} } },
        createModuleLogger: () => ({ debug() {} }), Math });
    vm.runInContext(code + '\n globalThis.Native = ' + className + ';', originalContext, { timeout: 1000 });
    const native = Object.create(originalContext.Native.prototype);
    native.node = { properties: {}, intpos: { x: .5, y: .5 } }; native.initializeProperties();
    check(() => assert.deepEqual(clone(defaults[kind]), clone(native.node.properties)));
    native.widthWidget = { value: 640 }; native.heightWidget = { value: 480 };
    let observed;
    native.setDimensions = (w, h) => { observed = [w, h]; };
    for (let i = 0; i < 121; i++) for (const [shift, ctrl] of [[false, false], [true, false], [false, true], [true, true]]) {
        const x = i * 3.7 - 19, y = (i % 17) * 13.1 - 9;
        native.updateCanvasValue(x, y, 250, 180, shift, ctrl);
        const converted = pointerDimensions(defaults[kind], 640, 480, x, y, 250, 180, shift, ctrl);
        check(() => assert.deepEqual(clone(converted), clone(observed)));
    }
    const node = fixture(kind), controller = createDimensionController(node, kind, facade);
    const actual = recording(); node.canvas.draw(actual.ctx, [400, 305]);
    const bounds = canvasBounds(defaults[kind], 10, 60, 380, 200);
    native.controls = {};
    native.node.properties.valueX = 640; native.node.properties.valueY = 480;
    native.node.intpos = {
        x: Math.max(0, Math.min(1, (640 - defaults[kind].canvas_min_x) / (defaults[kind].canvas_max_x - defaults[kind].canvas_min_x))),
        y: Math.max(0, Math.min(1, (480 - defaults[kind].canvas_min_y) / (defaults[kind].canvas_max_y - defaults[kind].canvas_min_y))),
    };
    const expected = recording(); native.draw2DCanvas(expected.ctx, 10, 60, 380, 200);
    check(() => assert.deepEqual(clone(native.controls.canvas2d), clone(bounds)));
    check(() => assert.deepEqual(clone(actual.calls.slice(0, expected.calls.length)), clone(expected.calls)));
    // Live modifier drag/release commits through original authoritative widgets.
    const event = { button: 0, buttons: 1, shiftKey: true, ctrlKey: false };
    const target = { x: bounds.x + bounds.w * .8, y: bounds.y + bounds.h * .3, event };
    const selected = pointerDimensions(defaults[kind], 640, 480, bounds.w * .8, bounds.h * .3, bounds.w, bounds.h, true, false);
    node.canvas.onPointerDown(target);
    check(() => assert.deepEqual([node.widgets.get('width').value, node.widgets.get('height').value], clone(selected)));
    node.canvas.onPointerUp({ ...target, event: { buttons: 0 } });
    check(() => assert.equal(node.properties.valueX, node.widgets.get('width').value));
    node.widgets.get('width').setValue(999); controller.configured();
    check(() => assert.equal(node.widgets.get('width').value, 999));
    controller.dispose(); controller.dispose();
    check(() => assert.ok(node.widgets.all().every(w => w.listeners.size === 0)));
    const before = [node.widgets.get('width').value, node.widgets.get('height').value];
    node.canvas.onPointerDown(target);
    check(() => assert.deepEqual([node.widgets.get('width').value, node.widgets.get('height').value], before));
    check(() => assert.equal(typeof originalContext.Native.prototype.drawInfoMessage, 'undefined'));
}
for (const settings of [
    { ...clone(defaults.TKVideoUserInputs), canvas_step_x: 0 },
    { ...clone(defaults.TKVideoUserInputs), canvas_max_y: 200 },
    { ...clone(defaults.TKVideoUserInputs), canvas_step_x: .00001 },
    { ...clone(defaults.TKVideoUserInputs), canvas_decimals_x: 1000 },
    { ...clone(defaults.TKVideoUserInputs), canvas_min_x: Infinity },
]) check(() => assert.throws(() => validateCanvasWork(settings)));
console.log(JSON.stringify({ passed, failed: 0, tier: 'source-differential/frontend-facade-double',
    qualification: 'Three exact pinned classes; defaults, all modifier math, exact canvas drawing commands at shared geometry, widget edits/lifetime and work bounds. Not actual pointer-capture host/iframe, dialog, backend or whole pack proof.' }));
