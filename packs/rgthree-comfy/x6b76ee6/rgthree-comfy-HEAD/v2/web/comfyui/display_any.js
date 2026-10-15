import { comfy } from '/comfy/api/v2.js';
const serializationListeners = new Map();
const keyOf = (node) => JSON.stringify([node.graphId ?? '', node.id]);
comfy.defs.extend(["Display Any (rgthree)", "Display Int (rgthree)"], (b) => {
    b.onCreated((node) => {
        // onCreated fires when the node joins a graph, which can happen more than
        // once for one node; mount() throws on a duplicate name.
        if (!node.widgets.get("output")) {
            let stopWatching = null;
            node.widgets.mount({
                name: "output",
                defaultValue: "",
                serialize: true,
                render(container, value) {
                    const textarea = document.createElement("textarea");
                    textarea.readOnly = true;
                    textarea.style.width = "100%";
                    textarea.style.height = "100%";
                    textarea.value = String(value.get());
                    container.appendChild(textarea);
                    stopWatching = value.onChange((v) => {
                        textarea.value = String(v);
                    });
                },
                destroy() {
                    stopWatching === null || stopWatching === void 0 ? void 0 : stopWatching();
                    stopWatching = null;
                },
            });
        }
        const key = keyOf(node);
        serializationListeners.get(key)?.();
        // The original serializer returned an empty string and cleared the
        // embedded workflow's matching value. Public serialization contexts
        // let us express both without touching another node or the built prompt.
        serializationListeners.set(key, node.widgets.get('output').on('beforeSerialize', (event) => {
            event.setSerializedValue('');
        }));
    });
    b.onRemoved((node) => {
        const key = keyOf(node); serializationListeners.get(key)?.(); serializationListeners.delete(key);
    });
    b.onExecuted((node, result) => {
        const showValueWidget = node.widgets.get("output");
        if (!showValueWidget) {
            throw new Error(`[rgthree.DisplayAny] node ${node.id} has no "output" widget to write to.`);
        }
        showValueWidget.setValue(result.text[0]);
    });
});
