import { comfy } from "/comfy/api/v2.js";

const READOUT = "ShowText_output";

function outSet(node, texts) {
    // Preserve the original ordered trim/filter/join, including its nonempty
    // array condition. The backend's exact UI key remains `string`.
    if (texts.length > 0) {
        if (Array.isArray(texts)) {
            texts = texts.filter((word) => word.trim() !== "")
                .map((word) => word.trim()).join(" ");
        }
        node.widgets.get(READOUT).setValue(texts);
    }
}

comfy.defs.extend("ShowText", (builder) => {
    if (builder.def.category !== "MK/text") return;
    builder.addWidget({ type: "text", name: READOUT, value: "",
        disabled: true, serialize: true,
        options: { multiline: true, placeholder: "Text output...", serialize: false } });
    builder.onExecuted((node, result) => outSet(node, result.raw.string));
    builder.onConfigured((node, data) => {
        if (data?.widgets_values?.length) outSet(node, data.widgets_values);
    });
});
