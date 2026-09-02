import { PassThroughFollowing, connectedInputNodes, defineAnyInputConnectedNode, graphOf, shouldPassThrough, } from "./base_any_input_connected_node.js";

// `BaseCollectorNode` — the "don't connect the same node twice" rule shared by Node
// Collector, Mute/Bypass Repeater and Mute/Bypass Relay. It was a class; here it is the
// extra `beforeConnect` veto layered onto `defineAnyInputConnectedNode`.
//
// The same node reaching a second slot is refused, and so is a reroute whose own source
// is already connected — the case that made a node fed through a reroute count twice.
// Reconnecting a node to the slot it already occupies is allowed, as before.
//
// DROPPED: the two `logger.debugParts(...)` lines that explained a refusal in the
//   console. They went through `rgthree.newLogSession`, punted with rgthree.js; the
//   refusal itself is unchanged. Cosmetic.
export function defineCollectorNode(config) {
    const { beforeConnect } = config;
    return defineAnyInputConnectedNode({
        ...config,
        beforeConnect(node, event) {
            if (event.peerNodeId && isDuplicateConnection(node, event)) {
                return false;
            }
            return beforeConnect ? beforeConnect(node, event) : true;
        },
    });
}
function isDuplicateConnection(node, event) {
    const connected = connectedInputNodes(node, { filtered: false });
    const inThisSlot = connectedInputNodes(node, { slot: event.index, filtered: false });
    const isDuplicate = (id) => connected.some((n) => n.id === id) && !inThisSlot.some((n) => n.id === id);
    if (isDuplicate(event.peerNodeId)) {
        return true;
    }
    // The node being connected is not wired yet, so `shouldPassThrough(outputNode)` is
    // resolved from `event.peerNodeId` against the graph that holds this node.
    const peer = graphOf(node).node(event.peerNodeId);
    if (!peer || !shouldPassThrough(peer, PassThroughFollowing.REROUTE_ONLY)) {
        return false;
    }
    const behindTheReroute = connectedInputNodes(peer, {
        following: PassThroughFollowing.REROUTE_ONLY,
    })[0];
    return !!behindTheReroute && isDuplicate(behindTheReroute.id);
}
