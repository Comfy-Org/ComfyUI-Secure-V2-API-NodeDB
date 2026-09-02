import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { defineAnyInputConnectedNode, graphOf, nodeKey, setModeDeep, } from "./base_any_input_connected_node.js";
import { exposedActionsFor, handleAction } from "./base_node.js";

// Fast Actions Button — one row per connected node, each choosing what that node should
// do (Mute / Bypass / Enable, or an action the node itself declares), plus any number of
// "Comfy Action" rows that act on the application. Pressing the button, or its shortcut,
// runs every row in order.
//
// The three markers that stood here are all closed by work in other files rather than by
// new API: `exposedActions` / `handleAction` is rgthree's own convention between
// rgthree's own nodes and is a registry in base_node.js now; the base class's
// grow-an-input machinery is `defineAnyInputConnectedNode`; and the pack's `addMenuItem`
// is `b.addMenuItem`, which `defineAnyInputConnectedNode` forwards `menuItems` to.
//
// The shortcut stays plain `window` keydown/keyup, as it always was, so it needs nothing
// published — and it should stay that way rather than becoming a command: the key is a
// *property the user types on this node*, and a graph may hold several buttons with
// different keys. `comfy.commands.register` binds one combo once, at load.
//
// COSMETIC: no property metadata. `FastActionsButton["@shortcutModifier"] = {type:
//   "combo", values: ["ctrl","alt","shift"]}` and its two `{type: "string"}` siblings
//   told the properties panel which control to edit each with. All three still work and
//   still save; they are free-text fields.
// REFUSED, not a gap: `collapsible = false`, `app.canvas.dirty_canvas = true` and
//   `this.graph.change()`. Whether a node may collapse and when the canvas repaints are
//   the renderer's, and the renderer is ours to replace — see utils.js. Writes through
//   this API invalidate on their own, so the repaint requests are deleted rather than
//   translated.
//
// WIRE FORMAT: unchanged, including its own inconsistency. `widgets_values` is still
// `[buttonValue, …rows]` — the button passes `options.serialize` only, which gates the
// prompt and not the saved file, so it keeps its slot and index 0 is still skipped on
// restore. A Comfy Action row still writes `comfy_action:<value>` into the saved file and
// `comfy_app:<value>` into the prompt, which is what `onSerialize` and `serializeValue`
// did respectively; the prompt half was already dead code, since the node never reaches
// graphToPrompt. Rows are named by the id of the node they drive rather than by its
// title, because a widget's name is its identity here — names are not serialized, only
// positions are.
const MODE_ALWAYS = "always";
const MODE_MUTE = "never";
const MODE_BYPASS = "bypass";
const BUTTON_WIDGET = "rgthree_action_button";
const COMFY_ACTION_PREFIX = "comfy_action:";
const COMFY_ACTION_VALUES = ["None", "Queue Prompt", "REMOVE Comfy Action", "MOVE to end"];
// Handles hold no arbitrary properties, so `widgetToData`, the two bound key listeners
// and `executingFromShortcut` live here, keyed by node, and are dropped in onRemoved.
const stateByNode = new Map();
let comfyActionCounter = 0;
function stateFor(node) {
    let state = stateByNode.get(nodeKey(node));
    if (!state) {
        stateByNode.set(nodeKey(node), (state = {
            rows: new Map(),
            lastValues: new Map(),
            listeners: null,
            executingFromShortcut: false,
        }));
    }
    return state;
}
function addComfyActionWidget(node, slot, value = "None") {
    const state = stateFor(node);
    const name = `comfy_action_${++comfyActionCounter}`;
    const widget = node.widgets.add({
        type: "combo",
        name,
        value,
        options: { values: COMFY_ACTION_VALUES },
    });
    widget.setLabel("Comfy Action");
    state.rows.set(name, { comfy: true });
    state.lastValues.set(name, value);
    widget.on("change", (v) => {
        if (String(v).startsWith("MOVE ")) {
            node.widgets.move(name, node.widgets.length - 1);
            widget.setValue(String(state.lastValues.get(name)));
            return;
        }
        if (String(v).startsWith("REMOVE ")) {
            node.widgets.remove(name);
            state.rows.delete(name);
            state.lastValues.delete(name);
            return;
        }
        state.lastValues.set(name, widget.getValue());
    });
    widget.on("beforeSerialize", (e) => {
        e.setSerializedValue(e.context === "prompt" ? `comfy_app:${e.value}` : `${COMFY_ACTION_PREFIX}${e.value}`);
    });
    if (slot != null) {
        node.widgets.move(name, slot);
    }
    return widget;
}
async function executeConnectedNodes(node) {
    const state = stateFor(node);
    for (const widget of node.widgets.all()) {
        if (widget.name === BUTTON_WIDGET) {
            continue;
        }
        const action = widget.getValue();
        const data = state.rows.get(widget.name);
        if (data?.comfy) {
            if (action === "Queue Prompt") {
                await comfy.queue.run();
            }
            continue;
        }
        if (data?.nodeId) {
            const linked = graphOf(node).node(data.nodeId);
            if (!linked) {
                continue;
            }
            if (typeof action !== "string") {
                throw new Error("Fast Actions Button action should be a string: " + action);
            }
            // One press is one undo step, and a muted node may be a subgraph whose whole
            // contents move with it.
            comfy.graph.batch(() => {
                if (action === "Mute") {
                    setModeDeep([linked], MODE_MUTE);
                }
                else if (action === "Bypass") {
                    setModeDeep([linked], MODE_BYPASS);
                }
                else if (action === "Enable") {
                    setModeDeep([linked], MODE_ALWAYS);
                }
            });
            await handleAction(linked, action);
            continue;
        }
        console.warn("Fast Actions Button has a widget without correct data.");
    }
}
function handleLinkedNodes(node, linkedNodes) {
    const state = stateFor(node);
    const wanted = new Set(linkedNodes.map((linked) => linked.id));
    for (const name of node.widgets.names()) {
        const data = state.rows.get(name);
        if (data?.nodeId && !wanted.has(data.nodeId)) {
            node.widgets.remove(name);
            state.rows.delete(name);
        }
    }
    for (const linked of linkedNodes) {
        let widget = node.widgets.get(linked.id);
        if (!widget) {
            widget = node.widgets.add({
                type: "combo",
                name: linked.id,
                value: "None",
                options: {
                    values: ["None", "Mute", "Bypass", "Enable", ...exposedActionsFor(linked.type)],
                },
            });
            state.rows.set(linked.id, { nodeId: linked.id });
        }
        // The row was labelled with the node's title, which the original wrote into the
        // widget's `name`; a retitled upstream node relabels the row in place instead of
        // moving it.
        widget.setLabel(linked.getTitle());
    }
    // The button first, then one row per connected node in connection order — except that
    // a Comfy Action row already sitting at a position keeps it, which is what the
    // original's `indexOffset` was stepping over.
    const previous = node.widgets.names();
    const comfyNames = previous.filter((name) => state.rows.get(name)?.comfy);
    const nodeNames = linkedNodes.map((linked) => linked.id);
    const order = [BUTTON_WIDGET];
    let nextNode = 0;
    let nextComfy = 0;
    while (nextNode < nodeNames.length || nextComfy < comfyNames.length) {
        const comfyName = comfyNames[nextComfy];
        if (comfyName !== undefined && previous.indexOf(comfyName) === order.length) {
            order.push(comfyName);
            nextComfy++;
        }
        else if (nextNode < nodeNames.length) {
            order.push(nodeNames[nextNode]);
            nextNode++;
        }
        else {
            order.push(comfyNames[nextComfy]);
            nextComfy++;
        }
    }
    if (previous.length === order.length && previous.some((name, i) => name !== order[i])) {
        node.widgets.reorder(order);
    }
}
defineAnyInputConnectedNode({
    type: NodeTypesString.FAST_ACTIONS_BUTTON,
    handleLinkedNodes,
    onCreated(node) {
        node.setSerializeWidgets(true);
        node.setProperty("buttonText", "🎬 Action!");
        node.setProperty("shortcutModifier", "alt");
        node.setProperty("shortcutKey", "");
        const state = stateFor(node);
        if (!node.widgets.get(BUTTON_WIDGET)) {
            const button = node.widgets.add({
                type: "button",
                name: BUTTON_WIDGET,
                value: "",
                options: { serialize: false },
            });
            button.setLabel(String(node.getProperty("buttonText")));
            button.on("activate", () => {
                void executeConnectedNodes(node);
            });
        }
        if (state.listeners) {
            return;
        }
        // Plain `window` listeners, exactly as `onAdded` / `onRemoved` installed them.
        const onKeypress = (event) => {
            const target = event.target;
            if (state.executingFromShortcut ||
                target.localName == "input" ||
                target.localName == "textarea") {
                return;
            }
            const shortcutKey = String(node.getProperty("shortcutKey") ?? "");
            if (shortcutKey.trim() && shortcutKey.toLowerCase() === event.key.toLowerCase()) {
                const shortcutModifier = node.getProperty("shortcutModifier");
                let good = shortcutModifier === "ctrl" && event.ctrlKey;
                good = good || (shortcutModifier === "alt" && event.altKey);
                good = good || (shortcutModifier === "shift" && event.shiftKey);
                good = good || (shortcutModifier === "meta" && event.metaKey);
                if (good) {
                    setTimeout(() => {
                        void executeConnectedNodes(node);
                    }, 20);
                    state.executingFromShortcut = true;
                    event.preventDefault();
                    event.stopImmediatePropagation();
                }
            }
        };
        const onKeyup = (event) => {
            const target = event.target;
            if (target.localName == "input" || target.localName == "textarea") {
                return;
            }
            state.executingFromShortcut = false;
        };
        window.addEventListener("keydown", onKeypress);
        window.addEventListener("keyup", onKeyup);
        state.listeners = { onKeypress, onKeyup };
    },
    onConfigured(node, data) {
        // The original deferred this by 100 ms so that the connected-node rows, which the
        // base class's own stabilize creates, existed to receive the saved values. The
        // base still schedules that pass on the same 100 ms debounce, so the wait is kept
        // rather than replaced with a hook that does not exist.
        setTimeout(() => {
            if (node.isDeleted || !Array.isArray(data.widgets_values)) {
                return;
            }
            for (let [index, value] of data.widgets_values.entries()) {
                if (index === 0) {
                    continue;
                }
                if (typeof value === "string" && value.startsWith(COMFY_ACTION_PREFIX)) {
                    value = value.replace(COMFY_ACTION_PREFIX, "");
                    addComfyActionWidget(node, index, value);
                }
                const widget = node.widgets.at(index);
                if (widget) {
                    widget.setValue(value);
                }
            }
        }, 100);
    },
    onPropertyChanged(node, event) {
        if (event.name === "buttonText" && typeof event.value === "string") {
            // `buttonWidget.name = value` — the label, not the identity, so the row does
            // not move and no lookup by name breaks.
            const button = node.widgets.get(BUTTON_WIDGET);
            if (button) {
                button.setLabel(event.value);
            }
        }
        if (event.name === "shortcutKey" && typeof event.value === "string") {
            // litegraph's own callback could only veto, reverting to the previous value;
            // `setValue` corrects what the user typed instead of discarding it, which is
            // what this line was reaching for.
            event.setValue(event.value.trim()[0]?.toLowerCase() ?? "");
        }
    },
    onRemoved(node) {
        const state = stateByNode.get(nodeKey(node));
        if (state?.listeners) {
            window.removeEventListener("keydown", state.listeners.onKeypress);
            window.removeEventListener("keyup", state.listeners.onKeyup);
        }
        stateByNode.delete(nodeKey(node));
    },
    menuItems: [
        {
            label: "➕ Append a Comfy Action",
            run: (node) => {
                addComfyActionWidget(node);
            },
        },
    ],
});
