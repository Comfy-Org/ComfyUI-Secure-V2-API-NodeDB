import { comfy } from '/comfy/api/v2.js';

const TARGET = 'LTXKeyframer';
const instances = new Map();

function key(node) {
    return `${node.graphId ?? ''}:${node.id}`;
}

function clampCount(value) {
    return Math.max(0, Math.min(50, Math.trunc(Number(value) || 0)));
}

function applyCount(instance, value) {
    const count = clampCount(value);
    instance.count = count;
    if (Number(instance.countWidget?.getValue()) !== count) instance.countWidget?.setValue(count);
    for (let index = 1; index <= 50; index += 1) {
        const visible = index <= count;
        instance.node.widgets.get(`insert_frame_${index}`)?.setHidden(!visible);
        instance.node.widgets.get(`strength_${index}`)?.setHidden(!visible);
    }
}

function sync(source, name, value) {
    for (const instance of instances.values()) {
        if (instance === source) continue;
        const widget = instance.node.widgets.get(name);
        if (widget && widget.getValue() !== value) widget.setValue(value);
    }
}

comfy.defs.extend(TARGET, (builder) => {
    builder.onCreated((node) => {
        const instance = {
            node,
            count: -1,
            countWidget: node.widgets.get('num_images'),
            unsubscribers: [],
        };
        instances.set(key(node), instance);
        instance.countWidget?.setLabel('images_loaded');
        instance.unsubscribers.push(instance.countWidget?.on('change', (value) => {
            applyCount(instance, value);
            sync(instance, 'num_images', clampCount(value));
        }));
        for (let index = 1; index <= 50; index += 1) {
            for (const prefix of ['insert_frame', 'strength']) {
                const name = `${prefix}_${index}`;
                const widget = node.widgets.get(name);
                instance.unsubscribers.push(widget?.on('change', (value) => sync(instance, name, value)));
            }
        }
        applyCount(instance, instance.countWidget?.getValue());
        node.setSizeConstraints({ autoHeight: true });
    });
    builder.onConfigured((node) => {
        const instance = instances.get(key(node));
        if (instance) applyCount(instance, instance.countWidget?.getValue());
    });
    builder.onRemoved((node) => {
        const instance = instances.get(key(node));
        if (!instance) return;
        for (const unsubscribe of instance.unsubscribers) unsubscribe?.();
        instances.delete(key(node));
    });
});
