import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const root = new URL('../', import.meta.url);
const source = fs.readFileSync(new URL('web/aspect_ratio_filter.js', root), 'utf8');
const oldSource = fs.readFileSync(new URL('../web/aspect_ratio_filter.js', root), 'utf8');
const manifest = JSON.parse(fs.readFileSync(new URL('secure-nodes.json', root), 'utf8'));
const inputs = manifest.nodes['CAS Empty Latent Aspect Ratio Preset'].schema.inputs;
const presets = inputs.find((x) => x.attrs.id === 'preset').attrs.options;
const models = inputs.find((x) => x.attrs.id === 'model').attrs.options;
assert.ok(Array.isArray(presets) && presets.length > 30);

let doc = 'doc-a';
let hooks, closeDocument;
const comfy = {
    sameEntity: (a, b) => a.entity === b.entity,
    workflow: { current: () => ({ id: doc }) },
    onDocumentClosed: (callback) => { closeDocument = callback; return () => {}; },
    defs: { extend(type, callback) {
        assert.equal(type, 'CAS Empty Latent Aspect Ratio Preset');
        hooks = {};
        callback({ def: { inputs: [{ name: 'preset', values: presets }] },
            onCreated: (cb) => { hooks.created = cb; },
            onConfigured: (cb) => { hooks.configured = cb; } });
        return () => {};
    } },
};
const context = vm.createContext({}); // No window, document, fetch or Node globals.
const module = new vm.SourceTextModule(source, { context });
await module.link(async (specifier) => {
    assert.equal(specifier, '/comfy/api/v2.js');
    const api = new vm.SyntheticModule(['comfy'], function () { this.setExport('comfy', comfy); }, { context });
    return api;
});
await module.evaluate();

let extension;
const oldContext = vm.createContext({});
const oldModule = new vm.SourceTextModule(oldSource, { context: oldContext });
await oldModule.link(async (specifier) => {
    assert.equal(specifier, '../../scripts/app.js');
    return new vm.SyntheticModule(['app'], function () {
        this.setExport('app', { registerExtension: (def) => { extension = def; } });
    }, { context: oldContext });
});
await oldModule.evaluate();

function widget(value) {
    const listeners = { change: new Set(), removed: new Set() };
    return { value, options: {}, writes: 0, listeners,
        getValue() { return this.value; },
        setValue(next) {
            if (Object.is(next, this.value)) return;
            this.value = next; this.writes++;
            for (const listener of [...listeners.change]) listener(next);
        },
        setOption(key, next) { this.options[key] = next; },
        on(event, listener) { listeners[event].add(listener); return () => listeners[event].delete(listener); },
        remove() { for (const listener of [...listeners.removed]) listener(); },
    };
}
function node(model, preset, id = '1', graphId = 'graph-a') {
    const widgets = { model: widget(model), preset: widget(preset) };
    return { id, graphId, entity: {}, values: widgets, widgets: { get: (key) => widgets[key] } };
}
function legacy(model, preset) {
    function Type() { this.widgets = [{ name: 'model', value: model }, { name: 'preset', value: preset, options: {} }]; }
    extension.beforeRegisterNodeDef(Type, { name: 'CAS Empty Latent Aspect Ratio Preset', input: { required: { preset: [presets] } } });
    const n = new Type(); n.onNodeCreated(); return n;
}

for (const model of [...models, 'not-a-model']) {
    const n = node(model, 'invalid');
    const old = legacy(model, 'invalid');
    hooks.created(n);
    assert.deepEqual([...n.values.preset.options.values], [...old.widgets[1].options.values]);
    assert.equal(n.values.preset.value, old.widgets[1].value);
    for (const choice of presets.filter((p) => p.endsWith(` - ${model}`))) {
        n.values.preset.setValue(choice);
        hooks.configured(n);
        assert.equal(n.values.preset.value, choice);
        assert.equal(n.values.model.listeners.change.size, 1);
    }
    n.values.model.remove();
    assert.equal(n.values.model.listeners.change.size, 0);
    assert.equal(n.values.model.listeners.removed.size, 0);
}

doc = 'doc-a';
const first = node(models[0], 'invalid'); hooks.created(first);
const subgraph = node(models[1], 'invalid', '1', 'subgraph'); hooks.created(subgraph);
doc = 'doc-b';
const second = node(models[2], 'invalid'); hooks.created(second);
first.values.model.setValue(models[3]);
assert.ok(first.values.preset.value.endsWith(` - ${models[3]}`));
assert.ok(second.values.preset.value.endsWith(` - ${models[2]}`));
assert.ok(subgraph.values.preset.value.endsWith(` - ${models[1]}`));
closeDocument({ id: 'doc-a' });
assert.equal(first.values.model.listeners.change.size, 0);
assert.equal(subgraph.values.model.listeners.change.size, 0);
assert.equal(second.values.model.listeners.change.size, 1);
hooks.configured({ ...second }); // Host-issued replacement node handle.
assert.equal(second.values.model.listeners.change.size, 1);
closeDocument({ id: 'doc-b' });
assert.equal(second.values.model.listeners.change.size, 0);

hooks.created({ id: 'missing', graphId: 'g', widgets: { get: () => undefined } });
assert.ok(!/\b(window|document|localStorage|indexedDB|fetch)\./.test(source));
assert.ok(!source.includes('prototype'));
console.log(`Frontend passed: ${models.length} models, ${presets.length} preset selections, lifecycle/document/subgraph isolation; opaque realm.`);
