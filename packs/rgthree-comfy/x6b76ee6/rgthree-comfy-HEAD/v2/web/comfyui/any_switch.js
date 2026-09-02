import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { debounce } from "../../rgthree/common/shared_utils.js";
import { followConnectionUntilType } from "./utils.js";
import { onConnectionsChainChange } from "./base_any_input_connected_node.js";
import { removeUnusedInputsFromEnd } from "./utils_inputs_outputs.js";
// HANDLED: Any Switch (rgthree)
// Handles hold no arbitrary properties, so what the old class kept on the
// instance lives here, keyed by node id and dropped in onRemoved. `debounce`
// keys by function identity, so each node needs its own stabilizer.
const stabilizersByNode = new Map();
const resolvedTypeByNode = new Map();
const unwatchChainByNode = new Map();
function addAnyInput(node, num = 1) {
    for (let i = 0; i < num; i++) {
        node.inputs.add(`any_${String(node.inputs.length + 1).padStart(2, "0")}`, resolvedTypeByNode.get(node.id) || "*");
    }
}
function stabilize(node) {
    if (node.isDeleted)
        return;
    removeUnusedInputsFromEnd(node, 4);
    addAnyInput(node);
    let connectedType = followConnectionUntilType(node, false, true);
    if (!connectedType) {
        connectedType = followConnectionUntilType(node, true, true);
    }
    const nodeType = (connectedType === null || connectedType === void 0 ? void 0 : connectedType.type) || "*";
    resolvedTypeByNode.set(node.id, nodeType);
    for (const input of node.inputs) {
        input.modify({ type: nodeType });
    }
    for (const output of node.outputs) {
        output.modify({
            type: nodeType,
            label: nodeType === "RGTHREE_CONTEXT"
                ? "CONTEXT"
                : nodeType.includes(",")
                    ? (connectedType === null || connectedType === void 0 ? void 0 : connectedType.label) || nodeType
                    : nodeType,
        });
    }
}
comfy.defs.extend(NodeTypesString.ANY_SWITCH, (b) => {
    function scheduleStabilize(node, ms = 64) {
        let stabilizer = stabilizersByNode.get(node.id);
        if (!stabilizer) {
            stabilizer = () => stabilize(node);
            stabilizersByNode.set(node.id, stabilizer);
        }
        return debounce(stabilizer, ms);
    }
    b.onCreated((node) => {
        // onCreated fires whenever the node joins a graph, which can happen more
        // than once; the old constructor ran only at construction, and a second
        // pass would append five more any_XX inputs to the serialized node.
        if (!node.inputs.names().some((name) => name.startsWith("any_"))) {
            addAnyInput(node, 5);
        }
        // `onConnectionsChainChange()`, which this node implemented and the collector
        // family called on it when their own connections changed. It is a registry
        // now — see base_any_input_connected_node.js — because a handle carries none
        // of the pack's own methods for a neighbour to duck-type against.
        unwatchChainByNode.set(node.id, onConnectionsChainChange(node, () => scheduleStabilize(node, 100)));
    });
    b.onConnectionsChanged((node) => {
        scheduleStabilize(node);
    });
    b.onRemoved((node) => {
        stabilizersByNode.delete(node.id);
        resolvedTypeByNode.delete(node.id);
        unwatchChainByNode.get(node.id)?.();
        unwatchChainByNode.delete(node.id);
    });
});
// REFUSED, not a gap: `addConnectionLayoutSupport` put the input on the left and the
//   output on the right by patching `getConnectionPos` on the node class. Deciding
//   where the renderer draws a socket is refused, not pending — see utils.js. The node
//   works; its sockets sit where the renderer puts them.
// WIRE FORMAT: unchanged. Five `any_XX` inputs are appended after the
//   definition's own, exactly as the old constructor did, and the growth/trim
//   rule is the same. The resolved type is held in a module Map rather than on
//   the instance, so nothing new is serialized.
