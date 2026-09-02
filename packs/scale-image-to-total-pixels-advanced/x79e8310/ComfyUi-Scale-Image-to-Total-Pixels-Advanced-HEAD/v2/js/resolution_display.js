import { comfy } from '/comfy/api/v2.js';

const TARGET_CLASS = "ImageScaleToTotalPixelsX";
const labels = new Map();

function nodeKey(node) {
    return `${String(node.graphId ?? "")}:${node.id}`;
}

comfy.defs.extend(TARGET_CLASS, (builder) => {
    builder.onCreated((node) => {
        const state = { text: "" };
        labels.set(nodeKey(node), state);
        state.removeBadge = node.addBadge(() => ({ text: state.text }));
    });

    builder.onExecuted((node, result) => {
        const state = labels.get(nodeKey(node));
        const text = result?.text;
        if (state && Array.isArray(text) && text.length > 0) {
            state.text = String(text[0] ?? "");
        }
    });

    builder.onRemoved((node) => {
        const key = nodeKey(node);
        labels.get(key)?.removeBadge?.();
        labels.delete(key);
    });
});
