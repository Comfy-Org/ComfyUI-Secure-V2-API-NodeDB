import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(process.env.TARGET_JS, 'utf8');
const hooks = {};
const pickDeclarations = [];
const uploadCalls = [];
const assetUrls = [];
let selector = null;
let hiddenByBuilder = null;
let uploadIndex = 0;

const builder = {
    hideWidget(name) { hiddenByBuilder = name; },
    onCreated(callback) { hooks.created = callback; },
    onConfigured(callback) { hooks.configured = callback; },
    onRemoved(callback) { hooks.removed = callback; },
};

const selectedFiles = [
    {
        name: 'quoted"image.png',
        type: 'image/png',
        bytes: new Uint8Array([1, 2, 3]),
    },
    {
        name: 'second.png',
        type: 'image/png',
        bytes: new Uint8Array([4, 5]),
    },
];

const comfy = {
    defs: {
        extend(value, apply) {
            selector = value;
            apply(builder);
        },
    },
    files: {
        async pickMany(declaration) {
            pickDeclarations.push(structuredClone(declaration));
            return selectedFiles;
        },
    },
    backend: {
        async fetch(route, init) {
            assert.equal(route, '/upload/image');
            uploadCalls.push({
                route,
                method: init.method,
                headers: { ...init.headers },
                body: Array.from(init.body),
            });
            uploadIndex += 1;
            return {
                ok: true,
                status: 200,
                async json() {
                    return uploadIndex === 1
                        ? { name: 'frame10.png', type: 'input', subfolder: 'wan' }
                        : { name: 'frame2.png', type: 'input', subfolder: 'wan' };
                },
            };
        },
        assetUrl(route) {
            assetUrls.push(route);
            return `https://host.invalid${route}`;
        },
    },
};

const context = vm.createContext({
    console,
    TextEncoder,
    Uint8Array,
    URLSearchParams,
});
const facade = new vm.SyntheticModule(
    ['comfy'],
    function initialize() { this.setExport('comfy', comfy); },
    { context, identifier: '/comfy/api/v2.js' },
);
const guestModule = new vm.SourceTextModule(source, {
    context,
    identifier: process.env.TARGET_JS,
});
await guestModule.link(async (specifier) => {
    if (specifier !== '/comfy/api/v2.js') {
        throw new Error(`unexpected import: ${specifier}`);
    }
    return facade;
});
await guestModule.evaluate();

assert.equal(selector, 'WanMultiImageLoader');
assert.equal(hiddenByBuilder, 'images_data');
for (const hook of ['created', 'configured', 'removed']) {
    assert.equal(typeof hooks[hook], 'function', `missing ${hook} hook`);
}
for (const name of [
    'window', 'document', 'parent', 'app', 'fetch', 'XMLHttpRequest',
    'WebSocket', 'setTimeout', 'setInterval', 'localStorage',
]) {
    assert.equal(
        vm.runInContext(`typeof ${name}`, context),
        'undefined',
        `${name} leaked into the guest`,
    );
}

class FakeElement {
    constructor(tagName) {
        this.tagName = String(tagName).toUpperCase();
        this.children = [];
        this.listeners = new Map();
        this.style = {};
        this.textContent = '';
        this.value = '';
        this.type = '';
        this.placeholder = '';
        this.src = '';
        this.alt = '';
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
        const fullEvent = {
            target: this,
            stopPropagation() {},
            ...event,
        };
        for (const callback of this.listeners.get(name) || []) {
            await callback(fullEvent);
        }
    }
}

const documentFactory = {
    createElement(name) { return new FakeElement(name); },
};
const container = new FakeElement('div');
container.ownerDocument = documentFactory;

function descendants(root) {
    return [root, ...root.children.flatMap(descendants)];
}

function findElement(tagName, text) {
    const found = descendants(container).find((element) => (
        element.tagName === tagName.toUpperCase()
        && (text === undefined || element.textContent === text)
    ));
    assert.ok(found, `missing ${tagName} ${text ?? ''}`);
    return found;
}

function makeWidget(name, initial) {
    let value = initial;
    let hidden = false;
    const callbacks = new Map();
    return {
        name,
        getValue() { return value; },
        setValue(next) {
            const previous = value;
            value = next;
            for (const callback of callbacks.get('change') || []) {
                callback(next, previous);
            }
        },
        setHidden(next) { hidden = Boolean(next); },
        isHidden() { return hidden; },
        on(event, callback) {
            if (!callbacks.has(event)) callbacks.set(event, new Set());
            callbacks.get(event).add(callback);
            return () => callbacks.get(event).delete(callback);
        },
        emitBeforeSerialize() {
            let serialized;
            const event = {
                setSerializedValue(next) { serialized = next; },
            };
            for (const callback of callbacks.get('beforeSerialize') || []) {
                callback(event);
            }
            return serialized;
        },
        callbackCount() {
            return [...callbacks.values()].reduce(
                (total, entries) => total + entries.size, 0,
            );
        },
    };
}

const indexWidget = makeWidget('index', 0);
const dataWidget = makeWidget('images_data', '');
const widgetMap = new Map([
    ['index', indexWidget],
    ['images_data', dataWidget],
]);
let mountDefinition = null;
let constraints = null;
let size = { width: 180, height: 160 };
const node = {
    id: 'wan-loader-1',
    getSize() { return size; },
    setSize(next) { size = next; },
    setSizeConstraints(next) { constraints = next; },
    widgets: {
        get(name) { return widgetMap.get(name); },
        mount(definition) {
            mountDefinition = definition;
            definition.render(container);
            return {};
        },
    },
};

hooks.created(node, { restored: false, loading: false });
assert.equal(dataWidget.isHidden(), true);
assert.equal(mountDefinition.name, 'wan_multi_image_gallery');
assert.equal(constraints.minWidth, 420);
assert.equal(constraints.autoHeight, true);
assert.equal(size.width, 420);
assert.equal(size.height, 160);

await findElement('button', '📁 Select').dispatch('click');
for (let attempt = 0; attempt < 100 && uploadCalls.length < 2; attempt += 1) {
    await new Promise((resolve) => setImmediate(resolve));
}
assert.equal(uploadCalls.length, 2, 'selected images were not uploaded');
assert.deepEqual(pickDeclarations, [{
    extensions: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'],
    mimeTypes: [
        'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp',
    ],
    maxBytes: 16 * 1024 * 1024,
    maxFiles: 50,
    maxTotalBytes: 256 * 1024 * 1024,
}]);
assert.equal(uploadCalls[0].method, 'POST');
assert.match(
    uploadCalls[0].headers['Content-Type'],
    /^multipart\/form-data; boundary=----secure-wan22fmlf-1$/,
);
const firstBody = new TextDecoder().decode(new Uint8Array(uploadCalls[0].body));
assert.match(firstBody, /filename="quoted_image\.png"/);
assert.ok(!firstBody.includes('quoted"image.png'));

let identities = JSON.parse(dataWidget.getValue());
assert.deepEqual(identities.map((item) => item.name), [
    'frame10.png', 'frame2.png',
]);
assert.ok(assetUrls.some((route) => route.includes('filename=frame10.png')));
assert.ok(assetUrls.every((route) => route.startsWith('/view?')));

const orderInputs = descendants(container).filter((element) => (
    element.tagName === 'INPUT' && element.type === 'number'
));
assert.equal(orderInputs.length, 2);
orderInputs[0].value = '2';
orderInputs[1].value = '1';
await orderInputs[0].dispatch('input');
await orderInputs[1].dispatch('input');
await findElement('button', '🔃 Sort').dispatch('click');
identities = JSON.parse(dataWidget.getValue());
assert.deepEqual(identities.map((item) => item.name), [
    'frame2.png', 'frame10.png',
]);

const thumbnailButtons = descendants(container).filter((element) => (
    element.tagName === 'BUTTON'
    && element.children.some((child) => child.tagName === 'IMG')
));
assert.equal(thumbnailButtons.length, 2);
await thumbnailButtons[1].dispatch('click');
assert.equal(indexWidget.getValue(), 1);
const removeButtons = descendants(container).filter((element) => (
    element.tagName === 'BUTTON' && element.textContent === '×'
));
await removeButtons[0].dispatch('click');
assert.equal(JSON.parse(dataWidget.getValue()).length, 1);
assert.equal(indexWidget.getValue(), 0);

await findElement('button', '🗑️ Clear').dispatch('click');
assert.equal(JSON.parse(dataWidget.getValue()).length, 1);
await findElement('button', 'Confirm clear').dispatch('click');
assert.deepEqual(JSON.parse(dataWidget.getValue()), []);

dataWidget.setValue(JSON.stringify([
    { name: 'restored.png', type: 'temp', subfolder: 'preview' },
]));
hooks.configured(node, { restored: true, loading: false });
assert.ok(assetUrls.some((route) => (
    route.includes('filename=restored.png') && route.includes('type=temp')
)));
assert.deepEqual(JSON.parse(dataWidget.emitBeforeSerialize()), [
    { name: 'restored.png', type: 'temp', subfolder: 'preview' },
]);

assert.equal(indexWidget.callbackCount(), 1);
assert.equal(dataWidget.callbackCount(), 1);
hooks.removed(node);
assert.equal(indexWidget.callbackCount(), 0);
assert.equal(dataWidget.callbackCount(), 0);
assert.equal(container.children.length, 0);

console.log('wan22fmlf frontend harness: PASS');
