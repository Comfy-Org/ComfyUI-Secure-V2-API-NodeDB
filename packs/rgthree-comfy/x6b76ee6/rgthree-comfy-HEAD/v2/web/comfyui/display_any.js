import { comfy } from '/comfy/api/v2.js';
let hasShownAlertForUpdatingInt = false;
comfy.defs.extend(["Display Any (rgthree)", "Display Int (rgthree)"], (b) => {
    b.onCreated((node) => {
        // onCreated fires when the node joins a graph, which can happen more than
        // once for one node; mount() throws on a duplicate name.
        if (node.widgets.get("output")) {
            return;
        }
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
    });
    // REFUSED, not a gap: `addConnectionLayoutSupport` put the input and output on
    // chosen sides of the node by patching `getConnectionPos` on the node class and
    // recomputing positions from `LiteGraph.NODE_SLOT_HEIGHT`. Deciding where the
    // renderer draws a socket is refused rather than pending — see utils.js. The
    // "Connections Layout" menu entry and the saved `connections_layout` property go
    // with it; existing workflows keep the property and it no longer does anything.
    b.onExecuted((node, result) => {
        const showValueWidget = node.widgets.get("output");
        if (!showValueWidget) {
            throw new Error(`[rgthree.DisplayAny] node ${node.id} has no "output" widget to write to.`);
        }
        showValueWidget.setValue(result.text[0]);
    });
});
