import { comfy } from '/comfy/api/v2.js';

const TARGET = 'IntegerSettingsAdvanced';
const NAMES = ['setting_1', 'setting_2', 'setting_3'];
const subscriptions = new Map();

function enforce(node, activeName = '') {
    const widgets = NAMES.map((name) => node.widgets.get(name)).filter(Boolean);
    const requested = widgets.find(
        (widget) => widget.name === activeName && widget.getValue() === true,
    );
    const selected = requested
        ?? [...widgets].reverse().find((widget) => widget.getValue() === true)
        ?? widgets.find((widget) => widget.name === 'setting_1');
    for (const widget of widgets) {
        if (widget !== selected && widget.getValue() !== false) {
            widget.setValue(false);
        }
    }
    if (selected && selected.getValue() !== true) {
        selected.setValue(true);
    }
}

function bind(node) {
    subscriptions.get(node)?.forEach((unsubscribe) => unsubscribe());
    const removers = [];
    for (const name of NAMES) {
        const widget = node.widgets.get(name);
        if (!widget) continue;
        const unsubscribe = widget.on('change', () => enforce(node, name));
        if (typeof unsubscribe === 'function') removers.push(unsubscribe);
    }
    subscriptions.set(node, removers);
    enforce(node);
}

comfy.defs.extend(TARGET, (builder) => {
    builder.onCreated((node) => bind(node));
    builder.onConfigured((node) => enforce(node));
    builder.onRemoved((node) => {
        subscriptions.get(node)?.forEach((unsubscribe) => unsubscribe());
        subscriptions.delete(node);
    });
});
