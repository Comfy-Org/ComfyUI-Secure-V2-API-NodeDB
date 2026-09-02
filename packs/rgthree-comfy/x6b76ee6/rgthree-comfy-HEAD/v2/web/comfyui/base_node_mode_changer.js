import { comfy } from '/comfy/api/v2.js';
import { PassThroughFollowing, defineAnyInputConnectedNode, graphOf, setModeDeep, } from "./base_any_input_connected_node.js";
import { exposeActions } from "./base_node.js";

// `BaseNodeModeChanger` — the body of Fast Muter and Fast Bypasser: one toggle per
// connected node, labelled after that node's title, which flips the node's mode and
// honours a "max one" / "always one" restriction.
//
// The original renamed a live widget in place (`widget.name = "Enable " + title`) and
// truncated the array (`this.widgets.length = n`) to drop extras. A widget's name is
// identity here, so a row is keyed by the id of the node it drives and the title goes in
// `setLabel` — which is also what makes a retitled upstream node cheap: the label
// changes and the widget does not move. Nothing is serialized either way, because these
// nodes never set `serialize_widgets`.
//
// `exposedActions` / `handleAction` — "Mute all"/"Bypass all", "Enable all", "Toggle
// all" — is not a gap: it is rgthree's own convention, declared on the class and read by
// rgthree's own Fast Actions Button, so the pack was only ever talking to itself. The
// table moves to `exposeActions` in base_node.js, keyed by node type, because a handle
// has no `constructor` to hang it on.
//
// COSMETIC: no property metadata. `BaseNodeModeChanger["@toggleRestriction"] = {type:
//   "combo", values: ["default", "max one", "always one"]}` told the properties panel to
//   edit that property with a dropdown. The property still works and still saves; it is
//   a free-text field now. Cosmetic.
const PROPERTY_RESTRICTION = "toggleRestriction";
// `widget.setValue` fans out to `on('change')` listeners, where the original assigned
// `widget.callback` directly and its own writes were silent. Without this guard the
// "always one" branch, which answers a click with the opposite value, re-enters forever.
let writingToggle = false;
function setToggle(widget, value) {
    if (widget.getValue() === value) {
        return;
    }
    writingToggle = true;
    try {
        widget.setValue(value);
    }
    finally {
        writingToggle = false;
    }
}
export function defineModeChangerNode({ type, modeOn, modeOff, offAction }) {
    function doModeChange(node, linkedId, force, skipOtherNodeCheck) {
        const linked = graphOf(node).node(linkedId);
        if (!linked) {
            return;
        }
        let newValue = force == null ? linked.getMode() === modeOff : force;
        if (skipOtherNodeCheck !== true) {
            const restriction = String(node.getProperty(PROPERTY_RESTRICTION) ?? "default");
            if (newValue && restriction.includes(" one")) {
                for (const name of node.widgets.names()) {
                    doModeChange(node, name, false, true);
                }
            }
            else if (!newValue && restriction === "always one") {
                newValue = node.widgets.all().every((w) => !w.getValue() || w.name === linkedId);
            }
        }
        setModeDeep([linked], newValue ? modeOn : modeOff);
        const widget = node.widgets.get(linkedId);
        if (widget) {
            setToggle(widget, newValue);
        }
    }
    function handleLinkedNodes(node, linkedNodes) {
        const wanted = new Set(linkedNodes.map((linked) => linked.id));
        for (const name of node.widgets.names()) {
            if (!wanted.has(name)) {
                node.widgets.remove(name);
            }
        }
        for (const linked of linkedNodes) {
            let widget = node.widgets.get(linked.id);
            if (!widget) {
                widget = node.widgets.add({
                    type: "toggle",
                    name: linked.id,
                    value: linked.getMode() === modeOn,
                    options: { on: "yes", off: "no" },
                });
                widget.on("change", () => {
                    if (writingToggle) {
                        return;
                    }
                    // One click can flip several nodes under the "max one" / "always
                    // one" restriction, and a muted node may be a subgraph whose whole
                    // contents move with it; `batch` makes that one undo step.
                    comfy.graph.batch(() => doModeChange(node, linked.id));
                });
            }
            widget.setLabel(`Enable ${linked.getTitle()}`);
            setToggle(widget, linked.getMode() === modeOn);
        }
        const order = linkedNodes.map((linked) => linked.id);
        const names = node.widgets.names();
        if (names.length === order.length && names.some((name, i) => name !== order[i])) {
            node.widgets.reorder(order);
        }
    }
    // Each entry passes `skipOtherNodeCheck` so "max one" / "always one" does not fight
    // a deliberate all-at-once change, exactly as `forceWidget*(widget, true)` did.
    exposeActions(type, [offAction, "Enable all", "Toggle all"], (node, action) => {
        comfy.graph.batch(() => {
            for (const widget of node.widgets.all()) {
                const force = action === offAction
                    ? false
                    : action === "Enable all"
                        ? true
                        : !widget.getValue();
                doModeChange(node, widget.name, force, true);
            }
        });
    });
    return defineAnyInputConnectedNode({
        type,
        following: PassThroughFollowing.ALL,
        outputs: [{ name: "OPT_CONNECTION", type: "*" }],
        handleLinkedNodes,
        onCreated(node) {
            node.setProperty(PROPERTY_RESTRICTION, "default");
        },
    });
}
