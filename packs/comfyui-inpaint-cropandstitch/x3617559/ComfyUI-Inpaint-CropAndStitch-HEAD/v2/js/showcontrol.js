import { comfy } from '/comfy/api/v2.js';

const TARGET_CLASS = "InpaintCropImproved";
const subscriptions = new Map();

const nodeKey = (node) => `${String(node.graphId ?? "")}:${String(node.id)}`;

function widget(node, name) {
    return node.widgets.get(name);
}

function setEnabled(node, name, enabled) {
    widget(node, name)?.setDisabled(!enabled);
}

function applyControlState(node) {
    const preresize = widget(node, "preresize")?.getValue() === true;
    const preresizeMode = widget(node, "preresize_mode")?.getValue();

    setEnabled(node, "preresize_mode", preresize);
    setEnabled(
        node,
        "preresize_min_width",
        preresize && preresizeMode !== "ensure maximum resolution",
    );
    setEnabled(
        node,
        "preresize_min_height",
        preresize && preresizeMode !== "ensure maximum resolution",
    );
    setEnabled(
        node,
        "preresize_max_width",
        preresize && preresizeMode !== "ensure minimum resolution",
    );
    setEnabled(
        node,
        "preresize_max_height",
        preresize && preresizeMode !== "ensure minimum resolution",
    );

    const extend = widget(node, "extend_for_outpainting")?.getValue() === true;
    for (const name of [
        "extend_up_factor",
        "extend_down_factor",
        "extend_left_factor",
        "extend_right_factor",
    ]) {
        setEnabled(node, name, extend);
    }

    const resize =
        widget(node, "output_resize_to_target_size")?.getValue() === true;
    setEnabled(node, "output_target_width", resize);
    setEnabled(node, "output_target_height", resize);
}

function bindControlState(node) {
    const key = nodeKey(node);
    subscriptions.get(key)?.forEach((unsubscribe) => unsubscribe());

    const unsubscriptions = [];
    for (const name of [
        "preresize",
        "preresize_mode",
        "extend_for_outpainting",
        "output_resize_to_target_size",
    ]) {
        const handle = widget(node, name);
        if (handle) {
            unsubscriptions.push(handle.on("change", () => applyControlState(node)));
        }
    }
    subscriptions.set(key, unsubscriptions);
    applyControlState(node);
}

comfy.defs.extend(TARGET_CLASS, (builder) => {
    builder.onCreated((node) => bindControlState(node));
    builder.onConfigured((node) => applyControlState(node));
    builder.onRemoved((node) => {
        const key = nodeKey(node);
        subscriptions.get(key)?.forEach((unsubscribe) => unsubscribe());
        subscriptions.delete(key);
    });
});
