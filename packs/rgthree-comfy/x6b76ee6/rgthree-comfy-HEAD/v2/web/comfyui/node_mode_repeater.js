import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString, stripRgthree } from "./constants.js";
import { PassThroughFollowing, connectedInputNodes, connectedOutputNodes, graphOf, nodeKey, setModeDeep, shouldPassThrough, } from "./base_any_input_connected_node.js";
import { defineCollectorNode } from "./base_node_collector.js";
import { helpMenuItem } from "./base_node.js";

// Mute / Bypass Repeater — when this node's own mode changes it repeats that mode onto
// every node wired into its inputs, or, if nothing is wired in and the node sits inside a
// group, onto every node in that group.
//
// `onModeChange(from, to)` only ever fired because base_node.js installed a
// `defineProperty(this, "mode", {set})` trap on every rgthree node.
// `comfy.onNodeChanged` filtered on `e.property === 'mode' && e.node.id === …` is that
// signal, published, carrying the same two values. The trap is deleted rather than
// converted. `onNodeChanged` does not say a *person* made the change, so the repeater
// will see its own writes to other nodes come back — it only ever acts on its own id.
//
// The slot colouring is not decoration: `color_on` / `color_off` sit on `INodeSlot` and
// are serialized, so a repeater that stopped writing them would save different bytes.
// They are `slot.modify({color, colorWhenUnconnected})`.
//
// `onConnectOutput` refused any output link unless the far end — through pass-throughs —
// was a Fast Muter, Fast Bypasser, Node Collector, Fast Actions Button, Reroute or
// Random Unmuter, and refused everything once a Relay was wired in. Both rules are back:
// `b.onBeforeConnect` installs the output side too, and `event.side` distinguishes it,
// which the marker here said it could not.
//
// `getGroupNodes(group)` reading `group._children` is `group.nodes()`, and a subgraph's
// own groups are `subgraph.groups()`, so the group fallback is whole. Which groups a node
// is *in* is derived rather than asked for — the test below walks the graph's groups and
// keeps the ones holding this node — because membership is geometric and recomputed, so
// there is no stored answer to read. That is the same derivation `group.nodes()` performs
// internally, run once per mode change rather than per frame.
const TOGGLER_TYPES = [NodeTypesString.FAST_MUTER, NodeTypesString.FAST_BYPASSER];
const OUTPUT_TARGET_TYPES = [
    NodeTypesString.FAST_MUTER,
    NodeTypesString.FAST_BYPASSER,
    NodeTypesString.NODE_COLLECTOR,
    NodeTypesString.FAST_ACTIONS_BUTTON,
    NodeTypesString.REROUTE,
    NodeTypesString.RANDOM_UNMUTER,
];
const OUTPUT_COLORS = { color: "#Fc0", colorWhenUnconnected: "#a80" };
const HELP = `
      <p>
        When this node's mode (Mute, Bypass, Active) changes, it will "repeat" that mode to all
        connected input nodes, or, if there are no connected nodes AND it is overlapping a group,
        "repeat" it's mode to all nodes in that group.
      </p>
      <ul>
        <li><p>
          Optionally, connect this mode's output to a ${stripRgthree(NodeTypesString.FAST_MUTER)}
          or ${stripRgthree(NodeTypesString.FAST_BYPASSER)} for a single toggle to quickly
          mute/bypass all its connected nodes.
        </p></li>
        <li><p>
          Optionally, connect a ${stripRgthree(NodeTypesString.NODE_MODE_RELAY)} to this nodes
          inputs to have it automatically toggle its mode. If connected, this will always take
          precedence (and disconnect any connected fast togglers).
        </p></li>
      </ul>
    `;
// `hasRelayInput` / `hasTogglerOutput` were instance fields; handles hold no arbitrary
// properties, so they live here keyed by node id and are dropped in onRemoved.
const stateByNode = new Map();
// The node being connected is not wired yet, so the original resolved "what is really on
// the other side" by walking the peer's own links when the peer is a pass-through.
function beyondPassThrough(peer) {
    if (!shouldPassThrough(peer, PassThroughFollowing.ALL)) {
        return peer;
    }
    return connectedOutputNodes(peer)[0] ?? peer;
}
function recompute(node) {
    const hasTogglerOutput = connectedOutputNodes(node).some((n) => TOGGLER_TYPES.includes(n.type));
    let hasRelayInput = false;
    // Per input slot rather than per entry of the filtered node list. The original used
    // the list index as a slot index, which only agrees with itself while every input
    // resolves to exactly one node in order — i.e. until a reroute is involved.
    for (const input of node.inputs.all()) {
        const inputNode = connectedInputNodes(node, { slot: input.index })[0];
        if (!inputNode) {
            continue;
        }
        if (inputNode.type !== NodeTypesString.NODE_MODE_RELAY) {
            setModeDeep([inputNode], node.getMode());
            continue;
        }
        if (hasTogglerOutput) {
            console.log(`Can't be connected to a Relay if also output to a toggler.`);
            input.disconnect();
        }
        else {
            hasRelayInput = true;
            input.modify({ color: "#FC0", colorWhenUnconnected: "#a80" });
        }
    }
    stateByNode.set(nodeKey(node), { hasRelayInput, hasTogglerOutput });
    // A repeater driven by a relay has nothing to offer a toggler, so it loses the slot.
    if (hasRelayInput) {
        if (node.outputs.length) {
            node.outputs.remove({ index: 0 });
        }
    }
    else if (!node.outputs.length) {
        node.outputs.add("OPT_CONNECTION", "*").modify(OUTPUT_COLORS);
    }
}
// A mode change on this node repeats outwards; one press is one undo step.
comfy.onReady(() => {
    comfy.onNodeChanged((event) => {
        if (event.property !== "mode" || !stateByNode.has(nodeKey(event.node))) {
            return;
        }
        const node = event.node;
        const mode = node.getMode();
        const linkedNodes = connectedInputNodes(node).filter((n) => n.type !== NodeTypesString.NODE_MODE_RELAY);
        if (linkedNodes.length) {
            comfy.graph.batch(() => setModeDeep(linkedNodes, mode));
            return;
        }
        const groups = graphOf(node).groups();
        const containing = groups.filter((group) => group.nodes().some((n) => n.id === node.id));
        if (!containing.length) {
            return;
        }
        comfy.graph.batch(() => {
            for (const group of containing) {
                setModeDeep(group.nodes().filter((n) => n.id !== node.id), mode);
            }
        });
    }, { scope: "document" });
});
defineCollectorNode({
    type: NodeTypesString.NODE_MODE_REPEATER,
    following: PassThroughFollowing.ALL,
    outputs: [{ name: "OPT_CONNECTION", type: "*" }],
    beforeConnect(node, event) {
        const peer = event.peerNodeId && graphOf(node).node(event.peerNodeId);
        if (!peer) {
            return true;
        }
        const beyond = beyondPassThrough(peer);
        if (event.side === "output") {
            // `onConnectOutput`: the output only means something to a node that reads
            // it, and means nothing at all once a Relay drives this repeater.
            return (!stateByNode.get(nodeKey(node))?.hasRelayInput &&
                OUTPUT_TARGET_TYPES.includes(beyond.type));
        }
        const isRelay = beyond.type === NodeTypesString.NODE_MODE_RELAY;
        return !isRelay || !stateByNode.get(nodeKey(node))?.hasTogglerOutput;
    },
    onCreated(node) {
        stateByNode.set(nodeKey(node), { hasRelayInput: false, hasTogglerOutput: false });
        // Serialized fields, so a missing slot is a real failure rather than a skip.
        const output = node.outputs.at(0);
        if (!output) {
            throw new Error(`[rgthree.NodeModeRepeater] node ${node.id} has no OPT_CONNECTION output.`);
        }
        output.modify(OUTPUT_COLORS);
    },
    onConnectionsChanged(node) {
        recompute(node);
    },
    onRemoved(node) {
        stateByNode.delete(nodeKey(node));
    },
    menuItems: [helpMenuItem(NodeTypesString.NODE_MODE_REPEATER, HELP)],
});
