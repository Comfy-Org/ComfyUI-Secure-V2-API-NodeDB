import { comfy } from "/comfy/api/v2.js";

const COLOR_THEMES = Object.freeze({
    QwenVL: Object.freeze({
        nodeColor: "#28403f",
        nodeBgColor: "#374539",
        width: 340,
    }),
    QwenVLGGUF: Object.freeze({
        nodeColor: "#474539",
        nodeBgColor: "#2c4045",
        width: 340,
    }),
    Enhancer: Object.freeze({
        nodeColor: "#374445",
        nodeBgColor: "#474539",
        width: 340,
    }),
});

const NODE_THEMES = Object.freeze({
    AILab_QwenVL: "QwenVL",
    AILab_QwenVL_Advanced: "QwenVL",
    AILab_QwenVL_PromptEnhancer: "Enhancer",
    AILab_QwenVL_GGUF: "QwenVLGGUF",
    AILab_QwenVL_GGUF_Advanced: "QwenVLGGUF",
    AILab_QwenVL_GGUF_PromptEnhancer: "Enhancer",
});

comfy.defs.extend(Object.keys(NODE_THEMES), (builder) => {
    builder.onCreated((node) => {
        const theme = COLOR_THEMES[NODE_THEMES[node.comfyClass]];
        if (!theme) return;

        node.setColor(theme.nodeColor);
        node.setBgColor(theme.nodeBgColor);
        node.setSize({ ...node.getSize(), width: theme.width });
    });
});
