import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
const PROPERTY_HIDE_TYPE_SELECTOR = "hideTypeSelector";
const PRIMITIVES = {
    STRING: "STRING",
    INT: "INT",
    FLOAT: "FLOAT",
    BOOLEAN: "BOOLEAN",
};
const TYPE_WIDGET = "type";
const VALUE_WIDGET = "value";
// Handles hold no arbitrary properties, so the "what shape is the value widget in
// right now" guard lives here, keyed by node id and dropped in onRemoved.
const typeStateByNode = new Map();
function typeWidgetOf(node) {
    const typeWidget = node.widgets.get(TYPE_WIDGET);
    if (!typeWidget) {
        throw new Error(`[rgthree.PowerPrimitive] node ${node.id} has no "${TYPE_WIDGET}" widget.`);
    }
    return typeWidget;
}
// The multiline case was `ComfyWidgets["STRING"](…, {multiline: true})`, which is
// a DOM widget holding a textarea. `mount` is that, owned by the pack: a native
// 'textarea' widget draws a "Vue only" warning under the legacy renderer, which
// the original did not.
function mountMultilineValue(node, initialValue) {
    let stopWatching = null;
    node.widgets.mount({
        name: VALUE_WIDGET,
        defaultValue: initialValue,
        serialize: true,
        render(container, value) {
            const inputEl = document.createElement("textarea");
            inputEl.style.width = "100%";
            inputEl.style.height = "100%";
            inputEl.value = String(value.get());
            inputEl.addEventListener("input", () => {
                value.set(inputEl.value);
            });
            container.appendChild(inputEl);
            stopWatching = value.onChange((v) => {
                inputEl.value = String(v);
            });
        },
        destroy() {
            stopWatching === null || stopWatching === void 0 ? void 0 : stopWatching();
            stopWatching = null;
        },
    });
}
function setTypedData(node) {
    const type = typeWidgetOf(node).getValue();
    const firstInput = node.inputs.at(0);
    const linked = !!(firstInput && firstInput.isConnected);
    const newTypeState = `${type}|${linked}`;
    if (typeStateByNode.get(node.id) === newTypeState)
        return;
    typeStateByNode.set(node.id, newTypeState);
    const previous = node.widgets.get(VALUE_WIDGET);
    const value = previous ? previous.getValue() : null;
    if (previous) {
        node.widgets.remove(VALUE_WIDGET);
    }
    if (linked) {
        node.widgets.add({ type: "text", name: VALUE_WIDGET, value: "" });
    }
    else if (type === "STRING") {
        mountMultilineValue(node, value ? "" : String(value));
    }
    else if (type === "INT" || type === "FLOAT") {
        const isFloat = type === "FLOAT";
        const numeric = isNaN(Number(value)) ? 0 : Number(value);
        node.widgets.add({
            type: "number",
            name: VALUE_WIDGET,
            value: numeric,
            options: { precision: isFloat ? 1 : 0, step2: isFloat ? 0.1 : 0 },
        });
    }
    else if (type === "BOOLEAN") {
        let bool = value;
        if (typeof bool === "string") {
            bool = !["false", "null", "None", "", "0"].includes(bool.toLowerCase());
        }
        node.widgets.add({
            type: "toggle",
            name: VALUE_WIDGET,
            value: !!bool,
            options: { on: "true", off: "false" },
        });
    }
    else {
        throw new Error(`Unsupported type "${type}".`);
    }
    node.widgets.move(VALUE_WIDGET, 1);
    if (!node.inputs.length) {
        node.inputs.add(VALUE_WIDGET, "*", { widget: VALUE_WIDGET });
    }
    const output = node.outputs.at(0);
    if (output) {
        const label = output.label === "*" || output.label === output.type ? null : output.label;
        output.modify({ type, label: label || type });
    }
}
comfy.defs.extend(NodeTypesString.POWER_PRIMITIVE, (b) => {
    b.onCreated((node) => {
        // onCreated fires whenever the node joins a graph, which can happen more
        // than once; the old constructor and onNodeCreated each ran once, and
        // widgets.add() throws on a duplicate name.
        if (node.widgets.get(TYPE_WIDGET)) {
            return;
        }
        if (node.getProperty(PROPERTY_HIDE_TYPE_SELECTOR) === undefined) {
            node.setProperty(PROPERTY_HIDE_TYPE_SELECTOR, false);
        }
        const typeWidget = node.widgets.add({
            type: "combo",
            name: TYPE_WIDGET,
            value: "STRING",
            options: { values: Object.keys(PRIMITIVES) },
        });
        typeWidget.on("change", () => {
            setTypedData(node);
        });
        typeWidget.setHidden(!!node.getProperty(PROPERTY_HIDE_TYPE_SELECTOR));
        setTypedData(node);
    });
    b.onConfigured((node) => {
        const typeWidget = typeWidgetOf(node);
        if (typeWidget.getValue() === "BOOL") {
            typeWidget.setValue("BOOLEAN");
        }
        setTypedData(node);
    });
    b.onConnectionsChanged((node, event) => {
        if (event.side === "input") {
            setTypedData(node);
        }
    });
    b.onPropertyChanged((node, event) => {
        if (event.name !== PROPERTY_HIDE_TYPE_SELECTOR) {
            return;
        }
        const typeWidget = node.widgets.get(TYPE_WIDGET);
        if (!typeWidget) {
            return;
        }
        // `setHidden` is the whole of what the original did: it set `hidden` and
        // then replaced computeLayoutSize with one returning zeros, because
        // `hidden` alone used to leave a gap. `LGraphNode.isWidgetVisible` now
        // skips a hidden widget in computeSize, so the second half is core's.
        typeWidget.setHidden(!!event.value);
    });
    b.onRemoved((node) => {
        typeStateByNode.delete(node.id);
    });
    b.addMenuItem({
        label: (node) => `${node.getProperty(PROPERTY_HIDE_TYPE_SELECTOR) ? "Show" : "Hide"} Type Selector Widget`,
        run: (node) => {
            node.setProperty(PROPERTY_HIDE_TYPE_SELECTOR, !node.getProperty(PROPERTY_HIDE_TYPE_SELECTOR));
        },
    });
    b.addMenuItem({
        label: "Set type",
        items: Object.keys(PRIMITIVES).map((primitive) => ({
            label: primitive,
            run: (node) => {
                typeWidgetOf(node).setValue(primitive);
                setTypedData(node);
            },
        })),
    });
});
// COSMETIC: no property metadata — `RgthreePowerPrimitive["@hideTypeSelector"] =
//   {type: "boolean"}` told the properties panel to edit that property as a
//   checkbox rather than a text field. It still works and still saves.
// COSMETIC: (8) the two entries were spliced in at position 0, above core's own,
//   with a separator after them. Both entries are present; pack entries are appended,
//   so they now sit below core's rather than above.
// WIRE FORMAT: unchanged. The widget list is still [type, value] — the value
//   widget is removed and re-added rather than swapped in place, then moved back
//   to index 1, so `widgets_values` keeps the same length and order. The `value`
//   input is added with `{widget: 'value'}`, which serialises as
//   `{widget: {name}}` exactly as the original's `addInput(…, {widget})` did.
//   One intermediate state is now observable that was not: between the remove and
//   the add, a pack watching this node sees the value widget missing.
