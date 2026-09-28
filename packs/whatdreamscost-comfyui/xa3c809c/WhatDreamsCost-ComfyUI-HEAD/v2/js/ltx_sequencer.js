import { comfy } from '/comfy/api/v2.js';

const TARGET = 'LTXSequencer';
const instances = new Map();

function key(node) {
    return `${node.graphId ?? ''}:${node.id}`;
}

function clampCount(value) {
    return Math.max(0, Math.min(50, Math.trunc(Number(value) || 0)));
}

function applyVisibility(instance) {
    const count = clampCount(instance.node.widgets.get('num_images')?.getValue());
    const mode = String(instance.node.widgets.get('insert_mode')?.getValue() || 'frames');
    instance.node.widgets.get('num_images')?.setLabel('images_loaded');
    for (let index = 1; index <= 50; index += 1) {
        const visible = index <= count;
        instance.node.widgets.get(`insert_frame_${index}`)?.setHidden(!visible || mode !== 'frames');
        instance.node.widgets.get(`insert_second_${index}`)?.setHidden(!visible || mode !== 'seconds');
        instance.node.widgets.get(`strength_${index}`)?.setHidden(!visible);
    }
}

function syncAll(source) {
    const names = source.node.widgets.names();
    for (const target of instances.values()) {
        if (target === source) continue;
        for (const name of names) {
            if (!/^(num_images|insert_mode|frame_rate|insert_frame_\d+|insert_second_\d+|strength_\d+)$/.test(name)) continue;
            const value = source.node.widgets.get(name)?.getValue();
            const widget = target.node.widgets.get(name);
            if (widget && widget.getValue() !== value) widget.setValue(value);
        }
        applyVisibility(target);
    }
}

comfy.defs.extend(TARGET, (builder) => {
    builder.onCreated((node) => {
        const instance = { node, unsubscribers: [] };
        instances.set(key(node), instance);
        for (const name of node.widgets.names()) {
            if (!/^(num_images|insert_mode|frame_rate|insert_frame_\d+|insert_second_\d+|strength_\d+)$/.test(name)) continue;
            const unsubscribe = node.widgets.get(name)?.on('change', () => {
                applyVisibility(instance);
                syncAll(instance);
            });
            if (unsubscribe) instance.unsubscribers.push(unsubscribe);
        }
        applyVisibility(instance);
        node.setSizeConstraints({ autoHeight: true });
    });
    builder.onConfigured((node) => {
        const instance = instances.get(key(node));
        if (instance) applyVisibility(instance);
    });
    builder.onRemoved((node) => {
        const instance = instances.get(key(node));
        if (!instance) return;
        for (const unsubscribe of instance.unsubscribers) unsubscribe();
        instances.delete(key(node));
    });
});
