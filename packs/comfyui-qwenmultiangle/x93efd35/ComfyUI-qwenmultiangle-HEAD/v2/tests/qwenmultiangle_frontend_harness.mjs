import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(process.env.TARGET_JS, 'utf8');
const hooks = {};
let selector = null;
let backendRoute = null;

const builder = {
    onCreated(callback) { hooks.created = callback; },
    onConfigured(callback) { hooks.configured = callback; },
    onConnectionsChanged(callback) { hooks.connections = callback; },
    onExecuted(callback) { hooks.executed = callback; },
    onRemoved(callback) { hooks.removed = callback; },
};
const comfy = {
    backend: {
        url(route) {
            backendRoute = route;
            return `https://host.invalid/api${route}`;
        },
    },
    defs: {
        extend(value, apply) {
            selector = value;
            apply(builder);
        },
    },
};

class FakeImage {
    constructor() {
        this.naturalWidth = 640;
        this.naturalHeight = 480;
        this.width = 640;
        this.height = 480;
        this._src = '';
    }

    set src(value) {
        this._src = value;
        this.onload?.();
    }

    get src() { return this._src; }
}

const context = vm.createContext({
    console,
    Image: FakeImage,
    URLSearchParams,
});
const guestModule = new vm.SourceTextModule(source, { context });
await guestModule.link(async (specifier) => {
    if (specifier !== '/comfy/api/v2.js') {
        throw new Error(`unexpected import: ${specifier}`);
    }
    return new vm.SyntheticModule(
        ['comfy'],
        function initialize() { this.setExport('comfy', comfy); },
        { context },
    );
});
await guestModule.evaluate();

function check(condition, message) {
    if (!condition) throw new Error(message);
}

check(selector === 'QwenMultiangleCameraNode', 'wrong definition selector');
for (const hook of [
    'created', 'configured', 'connections', 'executed', 'removed',
]) {
    check(typeof hooks[hook] === 'function', `missing ${hook} hook`);
}
for (const name of [
    'window', 'document', 'parent', 'app', 'fetch', 'XMLHttpRequest',
    'WebSocket', 'setTimeout', 'requestAnimationFrame',
]) {
    check(vm.runInContext(`typeof ${name}`, context) === 'undefined',
        `${name} leaked into guest context`);
}

const drawing = { calls: [], text: [], images: 0 };
const gradient = { addColorStop() {} };
const context2d = new Proxy({}, {
    get(_target, property) {
        if (property === 'createLinearGradient') return () => gradient;
        if (property === 'drawImage') {
            return (...args) => {
                drawing.images += 1;
                drawing.calls.push([property, ...args]);
            };
        }
        if (property === 'fillText') {
            return (value, ...args) => {
                drawing.text.push(String(value));
                drawing.calls.push([property, value, ...args]);
            };
        }
        return (...args) => drawing.calls.push([String(property), ...args]);
    },
    set(target, property, value) {
        target[property] = value;
        return true;
    },
});

const listeners = new Map();
const attributes = new Map();
const canvas = {
    width: 0,
    height: 0,
    style: {},
    addEventListener(name, callback) { listeners.set(name, callback); },
    getContext(kind) { return kind === '2d' ? context2d : null; },
    setAttribute(name, value) { attributes.set(name, String(value)); },
};
let replaced = 0;
const container = {
    style: {},
    ownerDocument: {
        createElement(name) {
            check(name === 'canvas', 'unexpected element type');
            return canvas;
        },
    },
    appendChild(child) { check(child === canvas, 'wrong mounted child'); },
    replaceChildren() { replaced += 1; },
};

function makeWidget(initial) {
    let value = initial;
    const callbacks = new Set();
    return {
        getValue() { return value; },
        setValue(next) {
            const old = value;
            value = next;
            for (const callback of callbacks) callback(next, old);
        },
        on(event, callback) {
            check(event === 'change', 'unexpected widget event');
            callbacks.add(callback);
            return () => callbacks.delete(callback);
        },
        callbackCount() { return callbacks.size; },
    };
}

const widgetMap = new Map([
    ['horizontal_angle', makeWidget(0)],
    ['vertical_angle', makeWidget(0)],
    ['zoom', makeWidget(5)],
    ['camera_view', makeWidget(false)],
]);
let mountDef = null;
let size = { width: 180, height: 200 };
let constraints = null;
const node = {
    id: '17',
    graphId: 'root',
    getSize() { return size; },
    setSize(next) { size = next; },
    setSizeConstraints(next) { constraints = next; },
    widgets: {
        get(name) { return widgetMap.get(name); },
        mount(definition) {
            mountDef = definition;
            definition.render(container);
            return {};
        },
    },
};

hooks.created(node, { restored: false, loading: false });
check(size.width === 350 && size.height === 520, 'node was not enlarged');
check(constraints.minWidth === 350 && constraints.minHeight === 520,
    'node constraints are wrong');
check(mountDef.name === 'camera_preview' && mountDef.height === 370,
    'mounted widget allocation is wrong');
check(canvas.width === 340 && canvas.height === 370, 'canvas size is wrong');
check(attributes.get('title') ===
    '<sks> front view eye-level shot medium shot', 'initial prompt is wrong');
check([...widgetMap.values()].every((widget) => widget.callbackCount() === 1),
    'widget subscriptions were not installed');

listeners.get('pointerdown')({ offsetX: 100, offsetY: 100 });
listeners.get('pointermove')({ offsetX: 150, offsetY: 80 });
listeners.get('pointerup')({});
check(widgetMap.get('horizontal_angle').getValue() === 60,
    'horizontal drag did not update its widget');
check(widgetMap.get('vertical_angle').getValue() === 10,
    'vertical drag did not update its widget');
listeners.get('wheel')({ deltaY: -1 });
check(widgetMap.get('zoom').getValue() === 5.4, 'wheel zoom failed');
check(attributes.get('title').includes('front-right quarter view'),
    'interactive prompt classification did not update');

drawing.text.length = 0;
widgetMap.get('camera_view').setValue(true);
check(drawing.text.includes('CAMERA VIEW'), 'camera-view rendering did not run');
hooks.configured(node);

listeners.get('pointerdown')({ offsetX: 330, offsetY: 340 });
check(widgetMap.get('horizontal_angle').getValue() === 0,
    'reset did not restore horizontal angle');
check(widgetMap.get('vertical_angle').getValue() === 0,
    'reset did not restore vertical angle');
check(widgetMap.get('zoom').getValue() === 5, 'reset did not restore zoom');

hooks.executed(node, {
    raw: {
        preview_images: [{
            filename: 'frame 1.png',
            subfolder: 'demo/sub',
            type: 'temp',
        }],
    },
});
check(backendRoute ===
    '/view?filename=frame+1.png&subfolder=demo%2Fsub&type=temp',
    'preview URL was not routed through the facade');
check(drawing.images > 0, 'preview image was not rendered');

hooks.connections(node, { side: 'input', index: 0, connected: false });
const callsBeforeRemoval = drawing.calls.length;
hooks.removed(node);
check(replaced === 1, 'mounted content was not removed');
check([...widgetMap.values()].every((widget) => widget.callbackCount() === 0),
    'widget subscriptions leaked');
widgetMap.get('zoom').setValue(7);
check(drawing.calls.length === callsBeforeRemoval,
    'removed instance continued to render');

console.log('qwenmultiangle frontend harness: PASS');
