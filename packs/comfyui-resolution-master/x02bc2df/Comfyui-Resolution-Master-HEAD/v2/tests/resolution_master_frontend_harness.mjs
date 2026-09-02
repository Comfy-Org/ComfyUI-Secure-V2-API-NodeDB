import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';


function check(condition, message) {
    if (!condition) throw new Error(message);
}

const hooks = {};
let selector = null;
const builder = {
    onCreated(callback) { hooks.created = callback; },
    onConfigured(callback) { hooks.configured = callback; },
    onConnectionsChanged(callback) { hooks.connections = callback; },
    onExecuted(callback) { hooks.executed = callback; },
    onRemoved(callback) { hooks.removed = callback; },
};
const stored = new Map();
const storageCalls = [];
const comfy = {
    defs: {
        extend(value, apply) {
            selector = value;
            apply(builder);
        },
    },
    storage: {
        async get(name) {
            storageCalls.push(['get', name]);
            return stored.get(name) ?? null;
        },
        async set(name, value) {
            storageCalls.push(['set', name, value]);
            stored.set(name, value);
        },
    },
};

const context = vm.createContext({ console });
const moduleCache = new Map();
const facade = new vm.SyntheticModule(
    ['comfy'],
    function initialize() { this.setExport('comfy', comfy); },
    { context, identifier: '/comfy/api/v2.js' },
);

async function loadModule(filename) {
    const resolved = path.resolve(filename);
    if (moduleCache.has(resolved)) return moduleCache.get(resolved);
    const source = fs.readFileSync(resolved, 'utf8');
    const module = new vm.SourceTextModule(source, {
        context,
        identifier: resolved,
    });
    moduleCache.set(resolved, module);
    await module.link(async (specifier, referencing) => {
        if (specifier === '/comfy/api/v2.js') return facade;
        if (!specifier.startsWith('.')) {
            throw new Error(`unexpected import: ${specifier}`);
        }
        return loadModule(path.resolve(path.dirname(referencing.identifier), specifier));
    });
    return module;
}

const guestModule = await loadModule(process.env.TARGET_JS);
await guestModule.evaluate();

check(selector === 'ResolutionMaster', 'wrong definition selector');
for (const hook of [
    'created', 'configured', 'connections', 'executed', 'removed',
]) {
    check(typeof hooks[hook] === 'function', `missing ${hook} hook`);
}
for (const name of [
    'window', 'document', 'parent', 'app', 'fetch', 'XMLHttpRequest',
    'WebSocket', 'setTimeout', 'setInterval', 'requestAnimationFrame',
    'localStorage',
]) {
    check(
        vm.runInContext(`typeof ${name}`, context) === 'undefined',
        `${name} leaked into guest context`,
    );
}

const drawing = { calls: [], labels: [] };
const context2d = new Proxy({}, {
    get(target, property) {
        if (property === 'fillText') {
            return (value, ...args) => {
                drawing.labels.push(String(value));
                drawing.calls.push([String(property), value, ...args]);
            };
        }
        if (property in target) return target[property];
        return (...args) => drawing.calls.push([String(property), ...args]);
    },
    set(target, property, value) {
        target[property] = value;
        return true;
    },
});

class FakeElement {
    constructor(tagName, factory) {
        this.tagName = String(tagName).toUpperCase();
        this.factory = factory;
        this.children = [];
        this.listeners = new Map();
        this.style = {};
        this.textContent = '';
        this.value = '';
        this.checked = false;
        this.type = '';
        this.placeholder = '';
        this.width = 0;
        this.height = 0;
        this.min = '';
        this.max = '';
        this.step = '';
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    replaceChildren(...children) {
        this.children = [...children];
    }

    addEventListener(name, callback) {
        if (!this.listeners.has(name)) this.listeners.set(name, []);
        this.listeners.get(name).push(callback);
    }

    async dispatch(name, event = {}) {
        for (const callback of this.listeners.get(name) || []) {
            await callback({ target: this, ...event });
        }
    }

    getContext(kind) {
        return this.tagName === 'CANVAS' && kind === '2d' ? context2d : null;
    }
}

const factory = {
    created: [],
    createElement(name) {
        const item = new FakeElement(name, this);
        this.created.push(item);
        return item;
    },
};
let replaced = 0;
const container = new FakeElement('div', factory);
container.ownerDocument = factory;
container.replaceChildren = (...children) => {
    replaced += 1;
    container.children = [...children];
};

function makeWidget(name, initial) {
    let value = initial;
    let hidden = false;
    const callbacks = new Set();
    return {
        name,
        widgetType: 'test',
        getValue() { return value; },
        setValue(next) {
            const previous = value;
            if (Object.is(previous, next)) return;
            value = next;
            for (const callback of callbacks) callback(next, previous);
        },
        on(event, callback) {
            check(event === 'change', `unexpected widget event: ${event}`);
            callbacks.add(callback);
            return () => callbacks.delete(callback);
        },
        setHidden(next) { hidden = Boolean(next); },
        isHidden() { return hidden; },
        callbackCount() { return callbacks.size; },
    };
}

const initialValues = {
    mode: 'Manual',
    latent_type: 'latent_4x8',
    width: 512,
    height: 512,
    auto_detect: false,
    auto_detect_source: 'backend',
    auto_detect_width: 0,
    auto_detect_height: 0,
    auto_fit_on_change: false,
    auto_resize_on_change: false,
    auto_snap_on_change: false,
    smart_fit: false,
    use_custom_calc: false,
    preserve_scaling_ratio: false,
    selected_category: '',
    snap_value: 64,
    upscale_value: 1,
    target_resolution: 1080,
    target_megapixels: 2,
    auto_detect_presets_json: '{}',
    rescale_mode: 'resolution',
    rescale_value: 1,
    batch_size: 1,
    input_image: null,
};
const widgetMap = new Map(
    Object.entries(initialValues).map(([name, value]) => [
        name, makeWidget(name, value),
    ]),
);
let mountDefinition = null;
let size = { width: 180, height: 200 };
let constraints = null;
const node = {
    id: '23',
    graphId: 'root',
    getSize() { return size; },
    setSize(next) { size = next; },
    setSizeConstraints(next) { constraints = next; },
    widgets: {
        get(name) { return widgetMap.get(name); },
        all() { return [...widgetMap.values()]; },
        mount(definition) {
            mountDefinition = definition;
            definition.render(container);
            return {};
        },
    },
};

await hooks.created(node, { restored: false, loading: false });
check(size.width === 390 && size.height === 670, 'node was not enlarged');
check(
    constraints.minWidth === 390 && constraints.minHeight === 670,
    'node constraints are wrong',
);
check(
    mountDefinition.name === 'resolution_master_controls'
        && mountDefinition.height === 610,
    'mounted control allocation is wrong',
);
check(
    [...widgetMap.values()].every((item) => item.isHidden()),
    'legacy widgets were not safely hidden',
);
check(
    storageCalls.some(([action, name]) => (
        action === 'get' && name === 'ResolutionMaster/custom-presets-v2.json'
    )),
    'custom preset storage was not loaded through the facade',
);
const canvas = factory.created.find((item) => item.tagName === 'CANVAS');
check(canvas.width === 350 && canvas.height === 190, 'canvas size is wrong');
check(drawing.labels.includes('512 × 512'), 'initial resolution was not drawn');

function controlForLabel(labelText) {
    const label = factory.created.find((item) => (
        item.tagName === 'LABEL'
        && item.children[0]?.textContent === labelText
    ));
    check(label, `missing label: ${labelText}`);
    return label.children[1];
}

function button(labelText) {
    const item = factory.created.find((candidate) => (
        candidate.tagName === 'BUTTON'
        && candidate.textContent === labelText
    ));
    check(item, `missing button: ${labelText}`);
    return item;
}

const preset = controlForLabel('Preset');
preset.value = '16:9 Widescreen';
await preset.dispatch('change');
check(widgetMap.get('width').getValue() === 768, 'preset width was not applied');
check(widgetMap.get('height').getValue() === 432, 'preset height was not applied');
await button('Swap').dispatch('click');
check(widgetMap.get('width').getValue() === 432, 'swap width failed');
check(widgetMap.get('height').getValue() === 768, 'swap height failed');

const widthInput = controlForLabel('Width');
const heightInput = controlForLabel('Height');
widthInput.value = '777';
heightInput.value = '511';
await widthInput.dispatch('change');
await button('Snap').dispatch('click');
check(widgetMap.get('width').getValue() % 64 === 0, 'snap width failed');
check(widgetMap.get('height').getValue() % 64 === 0, 'snap height failed');

widgetMap.get('width').setValue(800);
widgetMap.get('height').setValue(600);
await canvas.dispatch('pointerdown', {
    offsetX: 210, offsetY: 70, shiftKey: true, ctrlKey: true,
});
await canvas.dispatch('pointermove', {
    offsetX: 260, offsetY: 45, shiftKey: true, ctrlKey: true,
});
await canvas.dispatch('pointerup');
const draggedWidth = widgetMap.get('width').getValue();
const draggedHeight = widgetMap.get('height').getValue();
check(
    draggedWidth * 3 === draggedHeight * 4,
    'Shift+Ctrl drag did not preserve the exact aspect ratio',
);

const scaleMode = controlForLabel('Scale by');
const scaleValue = controlForLabel('Target / multiplier');
widgetMap.get('width').setValue(512);
widgetMap.get('height').setValue(384);
scaleMode.value = 'manual';
await scaleMode.dispatch('change');
scaleValue.value = '2';
await scaleValue.dispatch('change');
await button('Apply scale').dispatch('click');
check(widgetMap.get('width').getValue() === 1024, 'manual scale width failed');
check(widgetMap.get('height').getValue() === 768, 'manual scale height failed');

const category = controlForLabel('Category / model');
category.value = 'Flux';
await category.dispatch('change');
widgetMap.get('width').setValue(5000);
widgetMap.get('height').setValue(1000);
await button('Model calc').dispatch('click');
check(widgetMap.get('width').getValue() <= 2560, 'Flux max edge was ignored');
check(widgetMap.get('height').getValue() >= 320, 'Flux min edge was ignored');
check(widgetMap.get('width').getValue() % 32 === 0, 'Flux width was not rounded');
check(widgetMap.get('height').getValue() % 32 === 0, 'Flux height was not rounded');

category.value = 'Standard';
await category.dispatch('change');
widgetMap.get('width').setValue(640);
widgetMap.get('height').setValue(960);
const customName = factory.created.find((item) => (
    item.tagName === 'INPUT' && item.placeholder === 'Custom preset name'
));
customName.value = 'My Portrait';
await button('Save preset').dispatch('click');
const saved = JSON.parse(stored.get('ResolutionMaster/custom-presets-v2.json'));
check(
    saved.Standard['My Portrait'].width === 640
        && saved.Standard['My Portrait'].height === 960,
    'custom preset was not persisted',
);
check(preset.value === 'My Portrait', 'saved preset was not selected');
await button('Delete preset').dispatch('click');
const afterDelete = JSON.parse(stored.get(
    'ResolutionMaster/custom-presets-v2.json',
));
check(!afterDelete.Standard, 'custom preset was not deleted');

const autoDetectLabel = factory.created.find((item) => (
    item.tagName === 'LABEL'
    && item.children[1]?.textContent === 'Auto-detect'
));
const autoDetect = autoDetectLabel.children[0];
autoDetect.checked = true;
await autoDetect.dispatch('change');
check(widgetMap.get('auto_detect').getValue() === true, 'auto-detect toggle failed');

hooks.executed(node, {
    raw: {
        resolution_master: {
            detected_width: 1280,
            detected_height: 720,
            width: 1024,
            height: 576,
            rescale_factor: 1.5,
            source_empty: false,
        },
    },
});
check(widgetMap.get('auto_detect_source').getValue() === 'frontend',
    'executed auto-detect source was not acknowledged');
check(widgetMap.get('auto_detect_width').getValue() === 1280,
    'detected width was not synchronized');
check(widgetMap.get('auto_detect_height').getValue() === 720,
    'detected height was not synchronized');
check(widgetMap.get('width').getValue() === 1024, 'executed width was not applied');
check(widgetMap.get('height').getValue() === 576, 'executed height was not applied');

hooks.connections(node, {
    side: 'input', name: 'input_image', connected: false,
});
check(widgetMap.get('auto_detect_source').getValue() === 'frontend-empty',
    'disconnected source was not marked empty');
check(widgetMap.get('auto_detect_width').getValue() === 0,
    'disconnected width was not cleared');
hooks.connections(node, {
    side: 'input', name: 'input_image', connected: true,
});
check(widgetMap.get('auto_detect_source').getValue() === 'backend',
    'connected source did not arm backend detection');
hooks.configured(node);

const callsBeforeRemoval = drawing.calls.length;
hooks.removed(node);
check(replaced === 1, 'mounted content was not removed');
check(
    [...widgetMap.values()].every((item) => item.callbackCount() === 0),
    'widget subscriptions leaked',
);
widgetMap.get('width').setValue(2048);
check(
    drawing.calls.length === callsBeforeRemoval,
    'removed instance continued to draw',
);

console.log('resolution master frontend harness: PASS');
