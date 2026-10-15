import { comfy } from "/comfy/api/v2.js";

const TYPE = "CAS Empty Latent Aspect Ratio Preset";
const bindings = new Set();

/**
 * @param {import('../comfy-api.d.ts').NodeHandle} node
 * @param {string[]} allPresets
 */
function bind(node, allPresets) {
    const documentId = comfy.workflow.current()?.id;
    // Entity equality also distinguishes two opens of the same workflow,
    // whose graph and node IDs can be identical.
    for (const binding of [...bindings]) {
        if (comfy.sameEntity(binding.node, node)) binding.dispose();
    }
    const model = node.widgets.get("model");
    const preset = node.widgets.get("preset");
    if (!model || !preset) return;
    const apply = () => {
        const filtered = allPresets.filter((value) => value.endsWith(` - ${model.getValue()}`));
        preset.setOption("values", filtered);
        if (!filtered.includes(preset.getValue())) preset.setValue(filtered[0]);
    };
    const offChange = model.on("change", apply);
    const dispose = () => {
        offChange();
        offRemoved();
        bindings.delete(binding);
    };
    const offRemoved = model.on("removed", dispose);
    const binding = { node, documentId, dispose };
    bindings.add(binding);
    apply();
}

comfy.onDocumentClosed((closed) => {
    for (const binding of [...bindings]) {
        if (binding.documentId === closed.id) binding.dispose();
    }
});

comfy.defs.extend(TYPE, (builder) => {
    const choices = builder.def.inputs.find((input) => input.name === "preset")?.values;
    const allPresets = Array.isArray(choices) ? choices.filter((value) => typeof value === "string") : [];
    builder.onCreated((node) => bind(node, allPresets));
    builder.onConfigured((node) => bind(node, allPresets));
});
