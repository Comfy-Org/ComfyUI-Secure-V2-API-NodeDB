import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
const v2 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), pristine = path.dirname(v2);
const clone = value => JSON.parse(JSON.stringify(value));
let checks = 0;
function check(fn) { fn(); checks++; }
class Element {
    constructor(tag, ownerDocument) { this.tagName = tag.toUpperCase(); this.ownerDocument = ownerDocument;
        this.children = []; this.style = {}; this.listeners = new Map(); this.value = ''; }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.children.push(child); return child; }
    addEventListener(type, fn) { const set = this.listeners.get(type) || new Set(); set.add(fn); this.listeners.set(type, set); }
    removeEventListener(type, fn) { this.listeners.get(type)?.delete(fn); }
    async fire(type, event = {}) { for (const fn of [...(this.listeners.get(type) || [])]) await fn(event); if (this['on' + type]) await this['on' + type](event); }
    all(tag) { return [this, ...this.children.flatMap(child => child.all(tag))].filter(el => el.tagName === tag.toUpperCase()); }
}
const doc = { createElement(tag) { return new Element(tag, doc); } };
class Widget {
    constructor(name, value = '') { this.name = name; this.value = value; this.options = { values: ['', 'existing.png'] }; this.listeners = new Set(); }
    getValue() { return this.value; }
    setValue(next) { if (this.value === next) return; this.value = next; for (const fn of [...this.listeners]) fn(next); }
    getOptions() { return this.options; }
    setOption(key, value) { this.options[key] = value; }
    setHidden(value) { this.hidden = value; }
    on(event, fn) { assert.equal(event, 'change'); this.listeners.add(fn); return () => this.listeners.delete(fn); }
}
function fixture(prompts, saved = {}) {
    const widgets = [];
    for (let i = 1; i <= (prompts ? 4 : 12); i++) {
        widgets.push(new Widget('image_' + i, saved['image_' + i] || 'existing.png'));
        if (prompts) widgets.push(new Widget('prompt_' + i, saved['prompt_' + i] || 'initial ' + i));
    }
    const node = { items: widgets, mounts: [], constraints: [],
        widgets: { get: name => widgets.find(w => w.name === name),
            mount(def) { const container = new Element('div', doc); node.mounts.push({ def, container }); def.render(container); return {}; } },
        setSizeConstraints(def) { node.constraints.push(def); },
        save() { return Object.fromEntries(widgets.map(w => [w.name, w.value])); },
        destroy() { for (const mount of node.mounts) mount.def.destroy?.(); },
    };
    return node;
}
let selected = { name: 'new.png', type: 'image/png', bytes: new Uint8Array([1, 2, 3]) };
let pick = async () => selected;
let upload = async file => ({ path: 'managed/' + file.name, name: file.name, subfolder: 'managed' });
const uploads = [], definitions = [];
const facade = { files: {
    pick(options) { assert.equal(options.maxBytes, 16 * 1024 * 1024); return pick(); },
    upload(file) { uploads.push({ name: file.name, size: file.size }); return upload(file); },
}, backend: { url: value => 'https://managed.example/api' + value }, defs: {
    extend(kind, apply) { const hooks = {}; apply({
        onCreated(fn) { hooks.created = fn; }, onConfigured(fn) { hooks.configured = fn; },
        onRemoved(fn) { hooks.removed = fn; }, onDragDrop(fn) { hooks.drop = fn; },
    }); definitions.push({ kind, hooks }); },
} };
const context = vm.createContext({ console, File, Uint8Array, TextEncoder, Object, Array, JSON, String, Number, WeakMap });
const cache = new Map();
async function load(file) {
    if (cache.has(file)) return cache.get(file);
    const module = new vm.SourceTextModule(fs.readFileSync(file, 'utf8'), { context, identifier: file }); cache.set(file, module);
    await module.link(async spec => {
        if (spec === '/comfy/api/v2.js') {
            const api = new vm.SyntheticModule(['comfy'], function() { this.setExport('comfy', facade); }, { context }); await api.link(() => {}); return api;
        }
        return load(path.resolve(path.dirname(file), spec));
    });
    return module;
}
for (const name of ['extTKMultiImagePrompt.js', 'extTKMultiImageSelect.js']) { const module = await load(path.join(v2, 'web', name)); await module.evaluate(); }
function native(prompts) {
    const kind = prompts ? 'TKMultiImagePrompt' : 'TKMultiImageSelect';
    const raw = fixture(prompts), type = { prototype: {} };
    const code = fs.readFileSync(path.join(pristine, 'js', 'ext' + kind + '.js'), 'utf8').replace(/^import .*;\s*/gm, '');
    const context = vm.createContext({ console: { log() {}, error() {} }, document: doc,
        app: { registerExtension(def) { def.beforeRegisterNodeDef(type, { name: kind }); } },
        api: { apiURL: value => 'https://managed.example/api' + value },
        setTimeout(fn) { fn(); }, encodeURIComponent, Math });
    vm.runInContext(code, context, { timeout: 2000 });
    const node = { widgets: raw.items, size: [200, 300], mounts: [],
        addDOMWidget(name, type, element) { this.mounts.push({ name, container: element }); },
        setSize(value) { this.size = value; }, computeSize: () => [200, 300], setDirtyCanvas() {} };
    type.prototype.onNodeCreated.call(node); return node;
}
for (const prompts of [true, false]) {
    const kind = prompts ? 'TKMultiImagePrompt' : 'TKMultiImageSelect', hooks = definitions.find(d => d.kind === kind).hooks;
    const node = fixture(prompts), original = native(prompts); hooks.created(node);
    check(() => assert.equal(node.mounts.length, original.mounts.length));
    check(() => assert.equal(node.mounts.slice(0, 4).flatMap(m => m.container.all('img')).length, prompts ? 4 : 12));
    check(() => assert.deepEqual(clone(node.save()), clone(Object.fromEntries(original.widgets.map(w => [w.name, w.value])))));
    check(() => assert.ok(node.items.every(w => w.hidden)));
    check(() => assert.equal(hooks.drop(), true));
    const row = node.mounts[0].container;
    if (prompts) {
        const text = row.all('textarea')[0]; text.value = 'edited\nline'; await text.fire('input');
        check(() => assert.equal(node.widgets.get('prompt_1').value, 'edited\nline'));
        node.widgets.get('prompt_1').setValue('external');
        check(() => assert.equal(text.value, 'external'));
    }
    await row.all('button')[0].fire('click');
    check(() => assert.equal(node.widgets.get('image_1').value, 'managed/new.png'));
    check(() => assert.equal(row.all('img')[0].src, 'https://managed.example/api/view?filename=new.png&type=input&subfolder=managed'));
    check(() => assert.ok(node.widgets.get('image_1').options.values.includes('managed/new.png')));
    const saved = node.save(), reconstructed = fixture(prompts, saved); hooks.created(reconstructed); hooks.configured(reconstructed);
    check(() => assert.deepEqual(clone(reconstructed.save()), clone(saved)));
    check(() => assert.equal(reconstructed.mounts[0].container.all('img')[0].src, row.all('img')[0].src));
    node.widgets.get('image_1').setValue('folder/native.jpg');
    check(() => assert.ok(row.all('img')[0].src.endsWith('filename=native.jpg&type=input&subfolder=folder')));
    const clear = node.mounts.at(-1).container.all('button')[0]; await clear.fire('click');
    await original.mounts.at(-1).container.fire('click');
    check(() => assert.deepEqual(clone(node.save()), clone(Object.fromEntries(original.widgets.map(w => [w.name, w.value])))));
    check(() => assert.ok(node.mounts.slice(0, 4).flatMap(m => m.container.all('img')).every(img => img.style.display === 'none')));
    let release;
    let began;
    const entered = new Promise(resolve => { began = resolve; });
    upload = () => new Promise(resolve => { release = resolve; began(); });
    const pending = row.all('button')[0].fire('click'); await entered;
    await clear.fire('click');
    release({ path: 'late.png' }); await pending;
    check(() => assert.equal(node.widgets.get('image_1').value, ''));
    pick = () => new Promise(resolve => { release = resolve; });
    const pendingPicker = row.all('button')[0].fire('click'); await Promise.resolve();
    hooks.removed(node); node.destroy();
    release(selected); await pendingPicker;
    check(() => assert.equal(node.widgets.get('image_1').value, ''));
    check(() => assert.ok(node.items.every(w => w.listeners.size === 0)));
    reconstructed.destroy(); pick = async () => selected; upload = async file => ({ path: 'managed/' + file.name });
}
const preview = cache.get(path.join(v2, 'web/secureImageGrid.js')).namespace.imagePreview;
for (const value of ['/absolute', '../escape', 'C:\\escape', 'https://host/file', 'x'.repeat(1025), '\0'])
    check(() => assert.throws(() => preview(facade, value)));
console.log(JSON.stringify({ passed: checks, failed: 0, tier: 'source-differential/frontend-facade-double',
    qualification: 'Exact native4+12 grids/clear/serialization, managed path preview, edits/picker/upload lifetime and denial controls. No actual picker/upload broker/opaque renderer/backend/whole29 proof.' }));
