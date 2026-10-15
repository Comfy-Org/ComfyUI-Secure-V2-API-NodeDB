import { app } from "../../scripts/app.js";

// Filters the "preset" combo of the "CAS Empty Latent Aspect Ratio Preset" node down to
// entries matching the selected "model" widget. The model is parsed from each preset's
// label ("WxH - label - model"), so presets.py stays the single source of truth.
app.registerExtension({
    name: "ComfyUI.AspectRatioPresets.ModelFilter",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "CAS Empty Latent Aspect Ratio Preset") return;

        const allPresets = nodeData.input.required.preset[0];
        const presetsByModel = (model) =>
            allPresets.filter((p) => p.endsWith(` - ${model}`));

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            const modelWidget = this.widgets.find((w) => w.name === "model");
            const presetWidget = this.widgets.find((w) => w.name === "preset");
            if (!modelWidget || !presetWidget) return;

            const applyFilter = () => {
                const filtered = presetsByModel(modelWidget.value);
                presetWidget.options.values = filtered;
                if (!filtered.includes(presetWidget.value)) {
                    presetWidget.value = filtered[0];
                }
            };

            const origCallback = modelWidget.callback;
            modelWidget.callback = (...args) => {
                origCallback?.apply(modelWidget, args);
                applyFilter();
            };

            applyFilter();
        };
    },
});
