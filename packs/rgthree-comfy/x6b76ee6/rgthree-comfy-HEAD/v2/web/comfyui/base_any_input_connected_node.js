import { comfy } from '/comfy/api/v2.js';
import { debounce } from "../../rgthree/common/shared_utils.js";

// The shared body of every rgthree node that grows an input as the last one fills:
// Fast Muter, Fast Bypasser, Node Collector, Random Unmuter, Mute/Bypass Repeater and
// Relay. The class hierarchy it used to be — RgthreeBaseVirtualNode →
// BaseAnyInputConnectedNode → BaseCollectorNode → the node — is gone; what the base
// classes actually provided was composition, so this file provides it as functions and
// `defineAnyInputConnectedNode` assembles a definition from them.
//
// Two of the base class's mechanisms are deleted rather than converted, because what
// they compensated for is published now:
//   - `scheduleStabilizeWidgets(500)` re-scheduled itself forever so a node would
//     notice a linked node's `mode` or `title` changing. `comfy.onNodeChanged` reports
//     both, so the poll is gone and stabilization is event-driven.
//   - `defineProperty(this, "mode", {get, set})` in base_node.js existed so a node
//     could hear its own mode change. Same signal, filtered on `e.node.id`.
//
// `_tempWidth` is not a gap after all: it captured `size[0]` before every slot or
// widget mutation and fed it back through a `computeSize()` override so the node did
// not resize while its input list churned. `node.getSize()` / `node.setSize()` say
// exactly that, which is what `pinWidth` below does — and it makes the
// `loadedGraphNode` hook that seeded `_tempWidth` unnecessary rather than lost.
//
// The output-side veto is not a gap after all: `b.onBeforeConnect` installs
// `onConnectOutput` as well as `onConnectInput`, and `event.side` distinguishes them.
// The loop guard below ("a situation that could create a time paradox") refuses in both
// directions again, and the Relay and Repeater state their output restrictions the same
// way.
//
// REFUSED, not a gap: replacing core's connection routing for the whole document.
//   `LGraphNode.prototype.connectByType` was patched at module load so that dropping
//   *any* link on *any* node — every other pack's included — preferred a free `*`
//   input, and `connectByTypeOutput` was overridden for the same reason in reverse. A
//   pack cannot be allowed to decide where other packs' links land; it is invisible to
//   the user, order-dependent between packs, and unattributable when it goes wrong.
//   The capability survives where it belongs. These nodes declare exactly one input and
//   its type is `*`, which core's own `connectByType` already matches and already
//   prefers when free, so a link dropped on one of rgthree's collectors lands where it
//   always did. `b.onUnplacedLink` is the published seat for a node that wants to place
//   a drop itself — context.js uses it — and it is scoped to the node type that asked.
// `clone()` is not a gap either. It trimmed a copy's inputs back to one unless
//   rgthree's clipboard flag said several nodes were copied together — that is, unless
//   the upstream feeding those inputs came along too. `b.onCreated`'s event carries
//   `restored` and `loading`, which is the same question asked in published terms: a
//   node that arrives restored but not loading came from a paste or a duplicate. The
//   flag itself was a global on the `rgthree` singleton set from a canvas callback, and
//   goes with it.
// REFUSED, not a gap: the `collapse_connections` property subtracted
//   `LiteGraph.NODE_SLOT_HEIGHT` per row inside `computeSize` so every slot drew at one
//   point. It is the other half of `addConnectionLayoutSupport` — renderer geometry
//   recomputed from renderer constants — so the property and its "Collapse Connections"
//   menu entry go with it. See utils.js.
export const PassThroughFollowing = {
    ALL: 0,
    NONE: 1,
    REROUTE_ONLY: 2,
};
const TIME_PARADOX = `Whoa, whoa, whoa. You've just tried to create a connection that loops back on itself, ` +
    `a situation that could create a time paradox, the results of which could cause a ` +
    `chain reaction that would unravel the very fabric of the space time continuum, ` +
    `and destroy the entire universe!`;
export function shouldPassThrough(node, following = PassThroughFollowing.ALL) {
    const type = node?.type;
    if (!type || following === PassThroughFollowing.NONE) {
        return false;
    }
    if (following === PassThroughFollowing.REROUTE_ONLY) {
        return type.includes("Reroute");
    }
    return type.includes("Reroute") || type.includes("Node Combiner") || type.includes("Node Collector");
}
// `comfy.graph` addresses the graph on screen; a node inside a subgraph must resolve
// its peers against the graph that holds it, which is what `currentNode.graph` did.
export function graphOf(node) {
    const graphId = node.graphId;
    if (!graphId || graphId === comfy.graph.id) {
        return comfy.graph;
    }
    return comfy.graph.subgraphs().find((subgraph) => subgraph.id === graphId) ?? comfy.graph;
}
function linksOf(slot, isOutput) {
    if (isOutput) {
        return slot.links();
    }
    const link = slot.link();
    return link ? [link] : [];
}
function walk(scope, startId, isOutput, current, slotIndex, following) {
    const found = [];
    if (current.id !== startId && !shouldPassThrough(current, following)) {
        return found;
    }
    const slots = isOutput ? current.outputs : current.inputs;
    const links = [];
    if (slotIndex != null && slotIndex > -1) {
        const slot = slots.at(slotIndex);
        if (slot) {
            links.push(...linksOf(slot, isOutput));
        }
    }
    else {
        for (const slot of slots.all()) {
            links.push(...linksOf(slot, isOutput));
        }
    }
    for (const link of links) {
        const peer = scope.node(isOutput ? link.targetNodeId : link.sourceNodeId);
        if (!peer || found.some((node) => node.id === peer.id)) {
            continue;
        }
        found.push(peer);
        if (!shouldPassThrough(peer, following)) {
            continue;
        }
        // The original widened the follow mode to ALL past the first hop, by passing
        // `undefined` on the recursive call. Kept: a REROUTE_ONLY walk resolves
        // differently otherwise.
        for (const deeper of walk(scope, startId, isOutput, peer, undefined, PassThroughFollowing.ALL)) {
            if (!found.some((node) => node.id === deeper.id)) {
                found.push(deeper);
            }
        }
    }
    return found;
}
export function connectedInputNodes(node, { slot, following = PassThroughFollowing.ALL, filtered = true } = {}) {
    const nodes = walk(graphOf(node), node.id, false, node, slot, following);
    return filtered ? nodes.filter((n) => !shouldPassThrough(n, following)) : nodes;
}
export function connectedOutputNodes(node, { slot, following = PassThroughFollowing.ALL, filtered = true } = {}) {
    const nodes = walk(graphOf(node), node.id, true, node, slot, following);
    return filtered ? nodes.filter((n) => !shouldPassThrough(n, following)) : nodes;
}
// `changeModeOfNodes` set the node's own mode and descended into a subgraph node's
// children. A subgraph node's `type` is its definition's id, which is what
// `comfy.graph.subgraphs()` is keyed on, so the descent is expressible.
export function setModeDeep(nodes, mode) {
    const definitions = new Map(comfy.graph.subgraphs().map((s) => [s.id, s]));
    const stack = [...nodes];
    const entered = new Set();
    while (stack.length) {
        const node = stack.pop();
        node.setMode(mode);
        if (entered.has(node.type)) {
            continue;
        }
        const subgraph = definitions.get(node.type);
        if (subgraph) {
            entered.add(node.type);
            stack.push(...subgraph.nodes());
        }
    }
}
// `_tempWidth`: hold the node's width across a mutation that would otherwise grow it.
export function pinWidth(node, mutate) {
    const { width } = node.getSize();
    mutate();
    const size = node.getSize();
    if (size.width !== width) {
        node.setSize({ width, height: size.height });
    }
}
// Node ids are unique per graph, not per document, so a pack's own record keyed by id
// alone collides the moment the same id exists in a subgraph.
export function nodeKey(node) {
    return `${node.graphId ?? ""}:${node.id}`;
}
// Handles hold no arbitrary properties, so the per-node stabilizer lives here.
const stabilizersByNode = new Map();
/**
 * `onConnectionsChainChange()` — rgthree's own duck-typed call on every node downstream
 * of one whose connections changed, so a chain of them settles together. A handle
 * carries none of the pack's own methods, so the intent becomes a registry a node opts
 * into.
 *
 * Deliberately separate from `stabilizersByNode`, which the mode/title stream below also
 * drives. Any Switch implements the chain method and is not of this family; folding the
 * two registries together would restabilize it on every retitle anywhere in the graph,
 * which it never did.
 */
const chainListenersByNode = new Map();
export function onConnectionsChainChange(node, listener) {
    const key = nodeKey(node);
    chainListenersByNode.set(key, listener);
    return () => chainListenersByNode.delete(key);
}
function scheduleStabilize(node, ms = 100) {
    const stabilizer = stabilizersByNode.get(nodeKey(node));
    if (stabilizer) {
        // `debounce` keys on function identity, so each node needs its own.
        debounce(stabilizer, ms);
    }
}
function notifyConnectionsChain(node) {
    for (const downstream of connectedOutputNodes(node)) {
        const listener = chainListenersByNode.get(nodeKey(downstream));
        if (listener) {
            debounce(listener, 100);
        }
    }
}
// One stream for every node of this family rather than a watched-id set per node:
// `onNodeChanged` is deliberately not a per-node subscription, and a stale watch set is
// a silent wrong answer. A graph holds a handful of these nodes, and this replaces a
// 500 ms poll in each of them.
comfy.onReady(() => {
    comfy.onNodeChanged((event) => {
        if (event.property !== "mode" && event.property !== "title") {
            return;
        }
        for (const stabilizer of stabilizersByNode.values()) {
            debounce(stabilizer, 100);
        }
        // `'document'` rather than the default: these nodes read the titles and modes of
        // whatever is wired into them, and a collector inside a subgraph the user has
        // navigated away from would otherwise stop hearing and keep asserting a stale
        // list. The 500 ms poll this replaces did not care which graph was on screen.
    }, { scope: "document" });
});
function stabilizeInputs(node, following) {
    const last = node.inputs.at(node.inputs.length - 1);
    if (!last || last.isConnected) {
        node.inputs.add("", "*");
    }
    for (let index = node.inputs.length - 2; index >= 0; index--) {
        const input = node.inputs.at(index);
        if (!input) {
            continue;
        }
        if (!input.isConnected) {
            node.inputs.remove({ index });
            continue;
        }
        const name = connectedInputNodes(node, { slot: index, following })[0]?.getTitle() || "";
        if (input.name !== name) {
            input.modify({ name });
        }
    }
}
/**
 * Assembles a node definition with the base class's behaviour: one trailing `*` input
 * that grows as it fills, names taken from the connected nodes, the cycle guard, and a
 * stabilization pass driven by connection and mode/title changes instead of a poll.
 */
export function defineAnyInputConnectedNode(config) {
    const { type, title = type, outputs = [], following = PassThroughFollowing.NONE, handleLinkedNodes, beforeConnect, onCreated, onConfigured, onConnectionsChanged, onPropertyChanged, onRemoved, menuItems = [], } = config;
    function stabilize(node) {
        if (node.isDeleted) {
            return;
        }
        pinWidth(node, () => {
            stabilizeInputs(node, following);
            handleLinkedNodes?.(node, connectedInputNodes(node, { following }));
        });
    }
    // Registered before `define`, which is the point at which extensions are applied.
    comfy.defs.extend(type, (b) => {
        for (const item of menuItems) {
            b.addMenuItem(item);
        }
        b.onBeforeConnect((node, event) => {
            // `onConnectInput` refused a link from something already downstream;
            // `onConnectOutput` refused one into something already upstream. Same loop
            // from either end, and `event.side` says which end this is.
            const wouldLoop = event.side === "input"
                ? connectedOutputNodes(node, { filtered: false })
                : connectedInputNodes(node, { filtered: false });
            if (event.peerNodeId && wouldLoop.some((n) => n.id === event.peerNodeId)) {
                alert(TIME_PARADOX);
                return false;
            }
            return beforeConnect ? beforeConnect(node, event) : true;
        });
    });
    return comfy.defs.define({
        type,
        title,
        category: "rgthree",
        // Drives other nodes and must never reach graphToPrompt. No `resolve`: the
        // original was `isVirtualNode` with no `applyToGraph`, so its outputs resolved
        // to nothing and the node was simply left out of the prompt.
        execution: 'frontend',
        inputs: [{ name: "", type: "*" }],
        outputs,
        onCreated(node, event) {
            // `defs.define` turns widget serialization on, matching the host's own node
            // class; these nodes never had it, so no toggle reaches `widgets_values`
            // and the saved bytes are unchanged.
            node.setSerializeWidgets(false);
            const stabilizer = () => stabilize(node);
            stabilizersByNode.set(nodeKey(node), stabilizer);
            onConnectionsChainChange(node, stabilizer);
            // `clone()` trimmed a copy's inputs back to one unless the nodes feeding
            // them were copied too. A node that arrives restored but not loading is a
            // paste or a duplicate; links are not copied with it, so `stabilize` drops
            // the now-unfed inputs and leaves the single empty one — which is what the
            // clipboard flag was standing in for.
            if (event.restored && !event.loading) {
                stabilize(node);
            }
            onCreated?.(node);
        },
        onConfigured(node, data) {
            onConfigured?.(node, data);
            scheduleStabilize(node);
        },
        // Only when asked for: registering it wraps `setProperty` on the type.
        ...(onPropertyChanged ? { onPropertyChanged } : {}),
        onConnectionsChanged(node, event) {
            notifyConnectionsChain(node);
            scheduleStabilize(node);
            onConnectionsChanged?.(node, event);
        },
        onRemoved(node) {
            stabilizersByNode.delete(nodeKey(node));
            chainListenersByNode.delete(nodeKey(node));
            onRemoved?.(node);
        },
    });
}
