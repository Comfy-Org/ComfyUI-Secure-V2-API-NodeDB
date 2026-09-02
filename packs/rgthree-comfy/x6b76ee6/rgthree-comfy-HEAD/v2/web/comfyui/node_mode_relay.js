import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString, stripRgthree } from "./constants.js";
import { PassThroughFollowing, connectedOutputNodes, graphOf, nodeKey, setModeDeep, shouldPassThrough, } from "./base_any_input_connected_node.js";
import { defineCollectorNode } from "./base_node_collector.js";
import { helpMenuItem } from "./base_node.js";

// Mute / Bypass Relay — watches the modes of everything wired into it and pushes a
// configurable resulting mode ("all muted" / "all bypassed" / "any active" → mute /
// bypass / active / no change) into a connected Mute/Bypass Repeater.
//
// The mode observation was the reason for the two worst things in this file, and both
// are deleted rather than translated: the self-rescheduling `setTimeout(…, 500)` that
// re-read every input node's `mode`, and the `defineProperty(node, "mode", {set})` trap
// in base_node.js that drove `onModeChange`. `comfy.onNodeChanged` reports a mode change
// on any node, so the recompute below runs from that stream (via the shared stabilizer
// in base_any_input_connected_node.js) and the relay's *own* mode is the one case it
// filters by id for.
//
// The readout under the node is a badge now — `node.addBadge(() => ({text}))` draws in
// the title bar under both renderers — so the hand-painted `onDrawForeground` line and
// the `computeSize` +17 px that reserved room for it are both gone.
//
// Two markers here named destinations that already existed, and both are converted:
// `onConnectOutput` — refusing any output link whose far end, through pass-throughs, is
// not a Mute/Bypass Repeater — is `b.onBeforeConnect` with `event.side === 'output'`,
// which is installed; and the output's `LiteGraph.ARROW_SHAPE` is `shape: 'directional'`
// on the definition's output, so the arrow and the bytes it writes are both kept.
//
// COSMETIC: no property metadata. The three `@on_*_inputs` declarations gave the
//   properties panel a dropdown of MUTE / ACTIVE / BYPASS / NOTHING. The properties
//   still work and still save; they are free-text fields now.
// NOT REPRODUCED: `OPTION_TO_MODE.get(propertyVal)` returns undefined for a property the
//   user has typed something else into, and the original's `newMode !== null` test let
//   that undefined through to `changeModeOfNodes(outputNode, undefined)`. An unmapped
//   option now dispatches nothing.
const MODE_ALWAYS = "always";
const MODE_MUTE = "never";
const MODE_BYPASS = "bypass";
const MODE_REPEATS = [MODE_MUTE, MODE_BYPASS];
const MODE_NOTHING = "__nothing__";
const OPTION_TO_MODE = new Map([
    ["ACTIVE", MODE_ALWAYS],
    ["MUTE", MODE_MUTE],
    ["BYPASS", MODE_BYPASS],
    ["NOTHING", MODE_NOTHING],
]);
const MODE_TO_PROPERTY = new Map([
    [MODE_MUTE, "on_muted_inputs"],
    [MODE_BYPASS, "on_bypassed_inputs"],
    [MODE_ALWAYS, "on_any_active_inputs"],
]);
const DEFAULTS = {
    on_muted_inputs: "MUTE",
    on_bypassed_inputs: "BYPASS",
    on_any_active_inputs: "ACTIVE",
};
const HELP = `
      <p>
        This node will relay its input nodes' modes (Mute, Bypass, or Active) to a connected
        ${stripRgthree(NodeTypesString.NODE_MODE_REPEATER)} (which would then repeat that mode
        change to all of its inputs).
      </p>
      <ul>
          <li><p>
            When all connected input nodes are muted, the relay will set a connected repeater to
            mute (by default).
          </p></li>
          <li><p>
            When all connected input nodes are bypassed, the relay will set a connected repeater to
            bypass (by default).
          </p></li>
          <li><p>
            When any connected input nodes are active, the relay will set a connected repeater to
            active (by default).
          </p></li>
          <li><p>
            If no inputs are connected, the relay will set a connected repeater to its mode <i>when
            its own mode is changed</i>. <b>Note</b>, if any inputs are connected, then the above
            will occur and the Relay's mode does not matter.
          </p></li>
      </ul>
      <p>
        Note, you can change which signals get sent on the above in the <code>Properties</code>.
        For instance, you could configure an inverse relay which will send a MUTE when any of its
        inputs are active (instead of sending an ACTIVE signal), and send an ACTIVE signal when all
        of its inputs are muted (instead of sending a MUTE signal), etc.
      </p>
    `;
// Handles hold no arbitrary properties, so the live relays and their badge subscriptions
// live here, keyed by node id and dropped in onRemoved.
const relayNodes = new Map();
// `onPropertyChanged` runs *before* the write commits, so the value being set is passed
// in rather than read back — otherwise the badge appears and disappears one edit late.
function isCustomised(node, pendingName, pendingValue) {
    return Object.entries(DEFAULTS).some(([property, value]) => (property === pendingName ? pendingValue : node.getProperty(property)) !== value);
}
function refreshBadge(node, pendingName, pendingValue) {
    const state = relayNodes.get(nodeKey(node));
    if (!state) {
        return;
    }
    if (!isCustomised(node, pendingName, pendingValue)) {
        state.removeBadge?.();
        state.removeBadge = null;
        return;
    }
    state.removeBadge ??= node.addBadge(() => ({
        text: `*(MUTE > ${node.getProperty("on_muted_inputs")},  ` +
            `BYPASS > ${node.getProperty("on_bypassed_inputs")},  ` +
            `ACTIVE > ${node.getProperty("on_any_active_inputs")})`,
    }));
}
function dispatchModeToRepeater(node, mode) {
    if (mode == null) {
        return;
    }
    const option = node.getProperty(MODE_TO_PROPERTY.get(mode) ?? "");
    const mapped = OPTION_TO_MODE.get(String(option));
    if (mapped === undefined || mapped === MODE_NOTHING) {
        return;
    }
    const outputNodes = connectedOutputNodes(node);
    if (!outputNodes.length) {
        return;
    }
    comfy.graph.batch(() => setModeDeep(outputNodes, mapped));
}
// The relay's own mode only matters when nothing is wired into it.
comfy.onReady(() => {
    comfy.onNodeChanged((event) => {
        if (event.property !== "mode" || !relayNodes.has(nodeKey(event.node))) {
            return;
        }
        const node = event.node;
        if (node.inputs.length <= 1 && !node.inputs.at(0)?.isConnected && node.outputs.all().some((o) => o.isConnected)) {
            dispatchModeToRepeater(node, node.getMode());
        }
    }, { scope: "document" });
});
defineCollectorNode({
    type: NodeTypesString.NODE_MODE_RELAY,
    following: PassThroughFollowing.ALL,
    outputs: [{ name: "REPEATER", type: "_NODE_REPEATER_", shape: "directional" }],
    beforeConnect(node, event) {
        if (event.side !== "output") {
            return true;
        }
        // `onConnectOutput`: this output only means anything to a Repeater, reached
        // through whatever pass-throughs sit in between.
        const peer = event.peerNodeId && graphOf(node).node(event.peerNodeId);
        if (!peer) {
            return true;
        }
        const beyond = shouldPassThrough(peer, PassThroughFollowing.ALL)
            ? (connectedOutputNodes(peer)[0] ?? peer)
            : peer;
        return beyond.type === NodeTypesString.NODE_MODE_REPEATER;
    },
    handleLinkedNodes(node, linkedNodes) {
        if (!node.outputs.all().some((output) => output.isConnected) || !node.inputs.at(0)?.isConnected) {
            return;
        }
        let mode;
        for (const inputNode of linkedNodes) {
            const inputMode = inputNode.getMode();
            if (mode === undefined) {
                mode = inputMode;
            }
            else if (mode === inputMode && MODE_REPEATS.includes(mode)) {
                continue;
            }
            else if (inputMode === MODE_ALWAYS || mode === MODE_ALWAYS) {
                mode = MODE_ALWAYS;
            }
            else {
                mode = undefined;
            }
        }
        dispatchModeToRepeater(node, mode);
    },
    onCreated(node) {
        relayNodes.set(nodeKey(node), { removeBadge: null });
        for (const [property, value] of Object.entries(DEFAULTS)) {
            node.setProperty(property, value);
        }
        // Serialized fields, so a missing slot is a real failure rather than a skip.
        const output = node.outputs.at(0);
        if (!output) {
            throw new Error(`[rgthree.NodeModeRelay] node ${node.id} has no REPEATER output.`);
        }
        output.modify({ color: "#Fc0", colorWhenUnconnected: "#a80" });
        refreshBadge(node);
    },
    onConfigured(node) {
        refreshBadge(node);
    },
    onPropertyChanged(node, event) {
        refreshBadge(node, event.name, event.value);
    },
    onRemoved(node) {
        relayNodes.get(nodeKey(node))?.removeBadge?.();
        relayNodes.delete(nodeKey(node));
    },
    menuItems: [helpMenuItem(NodeTypesString.NODE_MODE_RELAY, HELP)],
});
