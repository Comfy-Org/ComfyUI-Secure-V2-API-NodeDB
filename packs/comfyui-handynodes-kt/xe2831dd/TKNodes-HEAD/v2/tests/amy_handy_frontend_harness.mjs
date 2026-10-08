import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const v2 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pristine = path.dirname(v2);
let checks = 0;
function check(fn) { fn(); checks++; }
const clone = value => JSON.parse(JSON.stringify(value));
class Element {
    constructor(tag, ownerDocument) {
        this.tagName = tag.toUpperCase(); this.ownerDocument = ownerDocument;
        this.children = []; this.listeners = new Map(); this.style = {}; this.value = ''; this.disabled = false;
    }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.children.push(child); return child; }
    addEventListener(type, listener) { const set = this.listeners.get(type) || new Set(); set.add(listener); this.listeners.set(type, set); }
    removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
    async fire(type) { if (this.disabled) return; for (const fn of [...(this.listeners.get(type) || [])]) await fn({ target: this }); }
    all(tag) { return [this, ...this.children.flatMap(child => child.all(tag))].filter(el => el.tagName === tag.toUpperCase()); }
}
const doc = { createElement(tag) { return new Element(tag, doc); } };
class Widget {
    constructor(name, value = 0) { this.name = name; this.value = value; this.listeners = new Set(); this.commits = 0; }
    getValue() { return this.value; }
    setValue(value) {
        if (Object.is(value, this.value)) return;
        this.value = value; this.commits++;
        for (const listener of [...this.listeners]) listener(value);
    }
    setHidden(value) { this.hidden = value; }
    on(event, fn) { assert.equal(event, 'change'); this.listeners.add(fn); return () => this.listeners.delete(fn); }
}
function makeNode(tracks, saved = {}) {
    const items = Array.from({ length: tracks }, (_, index) => [
        new Widget('track_start_' + (index + 1), saved['track_start_' + (index + 1)] ?? 0),
        new Widget('track_end_' + (index + 1), saved['track_end_' + (index + 1)] ?? 0),
    ]).flat();
    if (tracks === 14) items.push(new Widget('track_state', saved.track_state ?? 'DataUnchanged'),
        new Widget('speaker_times', saved.speaker_times ?? ''), new Widget('silence_threshold', 1));
    const mounts = [], properties = { ...(saved.properties || {}) };
    const node = {
        items, mounts, properties, constraints: [],
        inputs: { byName(name) { assert.equal(name, 'fullaudio'); return { source: () => ({ nodeId: 'audio', outputIndex: 0 }) }; } },
        widgets: {
            get(name) { return items.find(widget => widget.name === name); },
            all() { return items; },
            mount(def) { const container = new Element('div', doc); mounts.push({ def, container }); def.render(container); return {}; },
            canvas(def) { node.canvas = def; return { redraw() { node.redraws = (node.redraws || 0) + 1; } }; },
        },
        getProperty(key) { return properties[key]; },
        setProperty(key, value) { properties[key] = value; },
        setSerializeWidgets(value) { node.serialize = value; },
        setSizeConstraints(value) { node.constraints.push(value); },
        save() { return { ...Object.fromEntries(items.map(w => [w.name, w.value])), properties: clone(properties) }; },
        destroy() { for (const mount of mounts) mount.def.destroy?.(); },
    };
    return node;
}
const definitions = [];
let response = { speaker_times: [], duration: 10 };
let respond = async () => ({ ok: true, json: async () => clone(response) });
const facade = {
    defs: { extend(type, apply) {
        const hooks = {}; apply({
            onCreated(fn) { hooks.created = fn; }, onConfigured(fn) { hooks.configured = fn; },
            onExecuted(fn) { hooks.executed = fn; }, onRemoved(fn) { hooks.removed = fn; },
        }); definitions.push({ type, hooks });
    } },
    graph: { node() { return { widgets: { get: () => ({ getValue: () => 'voice.wav' }) } }; } },
    backend: { ownFetch(route, init) {
        assert.equal(route, '/tk/detect_speakers'); assert.deepEqual(JSON.parse(init.body), { audio: 'voice.wav', silence_threshold: 1 });
        return respond();
    } },
};
const context = vm.createContext({ console, TextEncoder, Number, Math, JSON, String, Array, Object, Promise, WeakMap, Map, Set, parseFloat, parseInt, isNaN });
const cache = new Map();
async function load(filename) {
    if (cache.has(filename)) return cache.get(filename);
    const module = new vm.SourceTextModule(fs.readFileSync(filename, 'utf8'), { context, identifier: filename });
    cache.set(filename, module);
    await module.link(async spec => {
        if (spec === '/comfy/api/v2.js') {
            const api = new vm.SyntheticModule(['comfy'], function() { this.setExport('comfy', facade); }, { context });
            await api.link(() => {}); return api;
        }
        assert.ok(spec.startsWith('./')); return load(path.resolve(path.dirname(filename), spec));
    });
    return module;
}
for (const name of ['TKAudioSpeakerTalkTime..js', 'TKLocateSpeakersUsingSilenceBreaks.js']) {
    const module = await load(path.join(v2, 'web', name)); await module.evaluate();
}
const talk = definitions.find(d => d.type === 'TKAudioSpeakerTalkTime').hooks;
const speaker = definitions.find(d => d.type === 'TKLocateSpeakersUsingSilenceBreaks').hooks;
const nativeCode = fs.readFileSync(path.join(pristine, 'js/TKLocateSpeakersUsingSilenceBreaks.js'), 'utf8').replace(/^import .*;\s*/m, '');
function nativeNode() {
    const shell = makeNode(14);
    const widgets = shell.items.map(w => ({ name: w.name, value: w.value }));
    const type = { prototype: {} };
    const ctx = vm.createContext({
        console: { log() {}, error() {} }, document: doc, setTimeout(fn) { fn(); },
        app: { registerExtension(def) { def.beforeRegisterNodeDef(type, { name: 'TKLocateSpeakersUsingSilenceBreaks' }); }, graph: {} },
    });
    vm.runInContext(nativeCode, ctx, { timeout: 2000 });
    const node = {
        widgets, size: [400, 480], flags: {}, properties: {},
        addDOMWidget(name, kind, element) { widgets.push({ name, element }); },
        setDirtyCanvas() {}, setProperty(key, value) { this.properties[key] = value; },
        setSize(value) { this.size = value; },
    };
    type.prototype.onNodeCreated.call(node);
    return node;
}
function trackValues(node, native = false) {
    const widgets = native ? node.widgets : node.items;
    return Object.fromEntries(widgets.filter(w => /^track_(start|end)_/.test(w.name) || w.name === 'track_state').map(w => [w.name, w.value]));
}
function draw(node) {
    const calls = [];
    const ctx = new Proxy({}, { get(target, key) { return (...args) => calls.push([key, ...args]); }, set() { return true; } });
    node.canvas.draw(ctx, [400, 65]); return calls;
}
const talkNode = makeNode(10); talk.created(talkNode);
check(() => assert.equal(talkNode.mounts.length, 10));
check(() => assert.ok(talkNode.items.every(w => w.hidden)));
for (const [index, raw] of ['1.25', '', 'abc', '-2.125', '0', '12.5tail'].entries()) {
    const input = talkNode.mounts[0].container.all('input')[index % 2];
    input.value = raw; await input.fire('input');
    check(() => assert.equal(talkNode.items[index % 2].value, parseFloat(raw) || 0));
}
talkNode.widgets.get('track_start_1').setValue(19.75);
check(() => assert.equal(talkNode.mounts[0].container.all('input')[0].value, 19.75));
const talkSaved = talkNode.save(), talkReload = makeNode(10, talkSaved); talk.created(talkReload);
check(() => assert.deepEqual(talkReload.save(), talkSaved));
const oldInput = talkNode.mounts[0].container.all('input')[0]; talkNode.destroy(); talkNode.destroy();
oldInput.value = 999; await oldInput.fire('input');
check(() => assert.equal(talkNode.items[0].value, 19.75));
check(() => assert.ok(talkNode.items.every(w => w.listeners.size === 0)));

for (let count = 0; count < 41; count++) {
    const segments = Array.from({ length: count }, (_, i) => ({ start: (count - i) / 7, end: (count - i) / 7 + .25, speaker: i % 2 }));
    const original = nativeNode(), converted = makeNode(14); speaker.created(converted);
    const wrapped = count % 2 === 0;
    const payload = { duration: [10], speaker_times: wrapped ? [segments] : segments };
    original.onExecuted(clone(payload)); speaker.executed(converted, { raw: clone(payload) });
    check(() => assert.deepEqual(clone(trackValues(converted)), clone(trackValues(original, true))));
    check(() => assert.equal(JSON.parse(converted.widgets.get('speaker_times').value).length, count));
    check(() => assert.equal(draw(converted).filter(call => call[0] === 'roundRect').length, wrapped ? 1 : count + 1));
    const saved = converted.save(), reconstructed = makeNode(14, saved); speaker.created(reconstructed); speaker.configured(reconstructed);
    check(() => assert.deepEqual(clone(reconstructed.save()), clone(saved)));
    speaker.removed(converted); converted.destroy(); reconstructed.destroy();
}

const manual = makeNode(14); speaker.created(manual);
check(() => assert.equal(manual.widgets.get('track_state').value, 'DataUnchanged'));
const detectButton = manual.mounts.at(-1).container.all('button')[0];
const clearButton = manual.mounts.at(-1).container.all('button')[1];
response = { duration: 10, speaker_times: Array.from({ length: 20 }, (_, i) => ({ start: i / 3, end: i / 3 + .25, speaker: i % 2 })) };
await detectButton.fire('click');
check(() => assert.equal(manual.widgets.get('track_state').value, 'DataChange'));
check(() => assert.equal(JSON.parse(manual.widgets.get('speaker_times').value).length, 20));
check(() => assert.equal(manual.items.filter(w => /^track_end_/.test(w.name) && w.value > 0).length, 14));
const other = makeNode(14); speaker.created(other);
check(() => assert.equal(other.widgets.get('speaker_times').value, ''));
await clearButton.fire('click');
check(() => assert.equal(manual.widgets.get('track_state').value, 'DataChange'));
check(() => assert.equal(manual.widgets.get('speaker_times').value, '[]'));
check(() => assert.ok(manual.items.filter(w => /^track_(start|end)_/.test(w.name)).every(w => w.value === 0)));

let release;
respond = () => new Promise(resolve => { release = resolve; });
const pending = detectButton.fire('click');
await Promise.resolve();
check(() => assert.equal(detectButton.disabled, true));
await clearButton.fire('click');
release({ ok: true, json: async () => clone(response) }); await pending;
check(() => assert.equal(manual.widgets.get('speaker_times').value, '[]'));
check(() => assert.equal(detectButton.disabled, false));
const removed = detectButton.fire('click'); await Promise.resolve();
speaker.removed(manual); manual.destroy();
release({ ok: true, json: async () => clone(response) }); await removed;
check(() => assert.equal(manual.widgets.get('speaker_times').value, '[]'));
check(() => assert.ok(manual.items.every(w => w.listeners.size === 0)));

const helper = cache.get(path.join(v2, 'web/secureSpeakerState.js')).namespace;
for (const value of ['{', 'x'.repeat(65537), '[{"start":1,"end":null,"speaker":0}]']) {
    check(() => assert.throws(() => helper.readCarrier(value)));
}
check(() => assert.throws(() => helper.checkedSegments(Array(4097).fill({ start: 0, end: 1, speaker: 0 }))));
const invalid = makeNode(14, { speaker_times: '{' });
check(() => assert.throws(() => speaker.created(invalid)));
const extreme = makeNode(14, { properties: { tk_speaker_duration: 10001 } });
check(() => assert.throws(() => speaker.created(extreme)));
console.log(JSON.stringify({ passed: checks, failed: 0, tier: 'source-differential/frontend-facade-double',
    qualifications: 'Exact legacy execution callback controls and current widget commit contract double. Not actual opaque worker, host renderer, route, backend or whole-pack proof.' }));
