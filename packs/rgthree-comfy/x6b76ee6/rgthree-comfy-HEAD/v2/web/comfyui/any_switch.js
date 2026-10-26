import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { debounce } from "../common/shared_utils.js";
import { followConnectionUntilType } from "./utils.js";
import { nodeKey, onConnectionsChainChange } from "./base_any_input_connected_node.js";
import { removeUnusedInputsFromEnd } from "./utils_inputs_outputs.js";
import { applyConnectionLayout } from './connection_layout.js';
// HANDLED: Any Switch (rgthree)
// Handles hold no arbitrary properties, so what the old class kept on the
// instance lives here, keyed by graph and node id and dropped in onRemoved. `debounce`
// keys by function identity, so each node needs its own stabilizer.
const stabilizersByNode = new Map();
const resolvedTypeByNode = new Map();
const unwatchChainByNode = new Map();
function addAnyInput(node, num = 1) {
    for (let i = 0; i < num; i++) {
        node.inputs.add(`any_${String(node.inputs.length + 1).padStart(2, "0")}`, resolvedTypeByNode.get(nodeKey(node)) || "*");
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
    resolvedTypeByNode.set(nodeKey(node), nodeType);
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
    applyConnectionLayout(node);
}
comfy.defs.extend(NodeTypesString.ANY_SWITCH, (b) => {
    function scheduleStabilize(node, ms = 64) {
        let stabilizer = stabilizersByNode.get(nodeKey(node));
        if (!stabilizer) {
            stabilizer = () => stabilize(node);
            stabilizersByNode.set(nodeKey(node), stabilizer);
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
        unwatchChainByNode.get(nodeKey(node))?.();
        unwatchChainByNode.set(nodeKey(node), onConnectionsChainChange(node, () => scheduleStabilize(node, 100)));
    });
    b.onConnectionsChanged((node) => {
        scheduleStabilize(node);
    });
    b.onRemoved((node) => {
        stabilizersByNode.delete(nodeKey(node));
        resolvedTypeByNode.delete(nodeKey(node));
        unwatchChainByNode.get(nodeKey(node))?.();
        unwatchChainByNode.delete(nodeKey(node));
    });
});
// CONVERTED (revision 9, F01): connection_layout.js restores the saved Left/Right
//   layout with public slot patches. It is reapplied after the delayed input/type
//   stabilization above, not before those slots exist.
// WIRE FORMAT: unchanged. Five `any_XX` inputs are appended after the
//   definition's own, exactly as the old constructor did, and the growth/trim
//   rule is the same. The resolved type is held in a module Map rather than on
//   the instance, so nothing new is serialized.
