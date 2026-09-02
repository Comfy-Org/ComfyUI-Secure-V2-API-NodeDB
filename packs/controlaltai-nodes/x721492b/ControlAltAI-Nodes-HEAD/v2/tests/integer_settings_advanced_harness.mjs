import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION = path.resolve(HERE, '../web/js/integer_settings_advanced.js');

function assert(condition, message) {
    if (!condition) throw new Error(`ASSERT: ${message}`);
}

const registration = {};
const comfy = {
    defs: {
        extend(nodeType, configure) {
            registration.nodeType = nodeType;
            configure({
                onCreated(callback) { registration.created = callback; },
                onConfigured(callback) { registration.configured = callback; },
                onRemoved(callback) { registration.removed = callback; },
            });
        },
    },
};

const context = vm.createContext({ console });
for (const name of [
    'window', 'document', 'parent', 'top', 'app', 'comfyAPI', 'LiteGraph',
    'fetch', 'XMLHttpRequest', 'WebSocket', 'setTimeout',
]) {
    assert(context[name] === undefined, `${name} leaked into the worker realm`);
}

const module = new vm.SourceTextModule(readFileSync(EXTENSION, 'utf8'), {
    context,
    identifier: EXTENSION,
});
await module.link((specifier) => {
    assert(specifier === '/comfy/api/v2.js', `forbidden import ${specifier}`);
    return new vm.SyntheticModule(
        ['comfy'],
        function () { this.setExport('comfy', comfy); },
        { context, identifier: specifier },
    );
});
await module.evaluate();

class Widget {
    constructor(name, value) {
        this.name = name;
        this.value = value;
        this.listeners = new Set();
    }
    getValue() { return this.value; }
    setValue(value) {
        this.value = value;
        for (const callback of [...this.listeners]) callback({ value });
    }
    on(event, callback) {
        assert(event === 'change', `unexpected widget event ${event}`);
        this.listeners.add(callback);
        return () => this.listeners.delete(callback);
    }
}

const widgets = [
    new Widget('setting_1', false),
    new Widget('setting_2', false),
    new Widget('setting_3', false),
];
const node = {
    id: 'node-1',
    graphId: 'graph-1',
    widgets: { get(name) { return widgets.find((item) => item.name === name); } },
};

assert(registration.nodeType === 'IntegerSettingsAdvanced', 'wrong node target');
registration.created(node);
assert(widgets[0].getValue() === true, 'created node did not keep one setting');
widgets[1].setValue(true);
assert(
    widgets.map((item) => item.getValue()).join(',') === 'false,true,false',
    'setting_2 did not exclude the other settings',
);
widgets[1].setValue(false);
assert(
    widgets.map((item) => item.getValue()).join(',') === 'true,false,false',
    'disabling the only setting did not restore setting_1',
);
widgets[0].value = true;
widgets[1].value = true;
widgets[2].value = true;
registration.configured(node);
assert(
    widgets.map((item) => item.getValue()).join(',') === 'false,false,true',
    'configured node did not normalize to backend priority',
);
registration.removed(node);
widgets[0].setValue(true);
assert(widgets[2].getValue() === true, 'removed node retained guest listeners');

console.log('PASS: ControlAltAI mutual exclusion uses only secure widget hooks');
