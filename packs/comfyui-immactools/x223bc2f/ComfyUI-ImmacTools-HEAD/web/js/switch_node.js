import { app } from "../../scripts/app.js";

/**
 * SwitchImmacTools — dynamic slot visibility driven by the `num_inputs` widget.
 *
 * All 20 input slots are declared statically in the Python schema (so their
 * positional indices are fixed and never scrambled by autogrow). The JS layer
 * adds/removes them to match `num_inputs`, using the widget value as the
 * single source of truth rather than counting serialised slots.
 *
 * On reload / paste / subgraph creation `widgets_values[0]` (num_inputs) is
 * always restored correctly before link re-wiring happens, so slots are in the
 * right positions when LiteGraph reconnects links.
 */

const MAX_INPUTS = 20;

function applySlotCount(node, count) {
    // Current autogrow-style input slots
    const currentSlots = (node.inputs ?? []).filter((inp) =>
        /^input_\d+$/.test(inp.name)
    );
    const current = currentSlots.length;

    if (current < count) {
        // Add missing slots in order — mark optional so they don't appear required
        for (let i = current; i < count; i++) {
            node.addInput(`input_${i}`, "*", { optional: true });
        }
    } else if (current > count) {
        // Remove excess slots from the tail (reverse to avoid index shifting)
        for (let i = (node.inputs ?? []).length - 1; i >= 0; i--) {
            const m = node.inputs[i]?.name.match(/^input_(\d+)$/);
            if (m && parseInt(m[1]) >= count) {
                node.removeInput(i);
            }
        }
    }

    node.setSize(node.computeSize());
}

app.registerExtension({
    name: "immac.switch_node",

    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "SwitchImmacTools") return;

        const origOnConfigure = nodeType.prototype.onConfigure;
        const origOnNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onConfigure = function (data) {
            // Let upstream restore widget values first (num_inputs, index, one_indexed, …).
            origOnConfigure?.call(this, data);

            // Read num_inputs from the restored widget — robust even if a widget
            // was converted to a link input (widgets_values index would shift).
            const widget = this.widgets?.find((w) => w.name === "num_inputs");
            const count = Math.max(1, Math.min(MAX_INPUTS, widget?.value ?? 5));
            applySlotCount(this, count);
        };

        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.call(this);

            // Hook the num_inputs widget so changing it live updates slot count.
            const widget = this.widgets?.find((w) => w.name === "num_inputs");
            if (widget) {
                const origCallback = widget.callback;
                widget.callback = (value, ...args) => {
                    origCallback?.call(widget, value, ...args);
                    applySlotCount(this, Math.max(1, Math.min(MAX_INPUTS, value)));
                };

                // Apply on first creation (fresh node, not configure path).
                applySlotCount(this, Math.max(1, Math.min(MAX_INPUTS, widget.value ?? 5)));
            }
        };
    },
});

