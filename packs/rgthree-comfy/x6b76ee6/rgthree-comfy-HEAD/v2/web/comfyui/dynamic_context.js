import { comfy } from '/comfy/api/v2.js';
import { connectedInputNodes, graphOf, nodeKey } from "./base_any_input_connected_node.js";
import { applyUpstreamMutation, contextInputs, dynamicInputMenuItems, ensureContextOutput, ensureTrailingContextInput, isOwnedContextInput, nextUniqueContextName, ownedInputName, prepareDynamicContextNode, releaseDynamicContextNode, removeContextPair, renameContextPair, stripOwnedPrefix, } from "./dynamic_context_base.js";
import { NodeTypesString } from "./constants.js";
import { followConnectionUntilType } from "./utils.js";
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
import { getContextOutputName, getDynamicContextInputsData, notifyContextInputsChanged, registerDynamicContext, } from "./services/context_service.js";

const TYPE = NodeTypesString.DYNAMIC_CONTEXT;
const cleanupByNode = new Map();
const pendingSync = new Set();

function ensureBaseSlots(node) {
    if (!node.inputs.byName("base_ctx")) {
        node.inputs.add("base_ctx", "RGTHREE_DYNAMIC_CONTEXT");
        node.inputs.reorder(["base_ctx", ...node.inputs.names().filter((name) => name !== "base_ctx")]);
    }
    ensureContextOutput(node);
}

function stabilizeOwnedNames(node, reserved = []) {
    const used = new Set(reserved.map((name) => getContextOutputName(name)));
    for (let index = 1; index < node.inputs.length; index++) {
        const input = node.inputs.at(index);
        if (!input || input.type === "*") {
            continue;
        }
        if (!isOwnedContextInput(input)) {
            used.add(getContextOutputName(input.name));
            const output = node.outputs.at(index);
            if (output && output.name !== getContextOutputName(input.name)) {
                output.modify({ name: getContextOutputName(input.name), label: undefined });
            }
            continue;
        }
        const root = stripOwnedPrefix(input.name).replace(/\.\d+$/, "");
        let name = root;
        let suffix = 0;
        while (used.has(getContextOutputName(name))) {
            name = `${root}.${++suffix}`;
        }
        used.add(getContextOutputName(name));
        const wanted = ownedInputName(name);
        if (input.name !== wanted || node.outputs.at(index)?.name !== getContextOutputName(wanted)) {
            renameContextPair(node, index, name, true);
        }
    }
}

function reconcileFromBase(node) {
    const upstream = connectedInputNodes(node, { slot: 0 })[0];
    if (!upstream) return;
    const desired = getDynamicContextInputsData(upstream).filter((slot) => slot.index > 0);
    stabilizeOwnedNames(node, desired.map((slot) => slot.name));

    const desiredOutputs = new Set(desired.map((slot) => getContextOutputName(slot.name)));
    for (let index = node.inputs.length - 1; index > 0; index--) {
        const input = node.inputs.at(index);
        if (!input || input.type === "*" || isOwnedContextInput(input)) {
            continue;
        }
        if (!desiredOutputs.has(getContextOutputName(input.name))) {
            removeContextPair(node, index);
        }
    }

    for (const slot of desired) {
        const existing = node.inputs
            .all()
            .find((input) => !isOwnedContextInput(input) && getContextOutputName(input.name) === getContextOutputName(slot.name));
        if (existing) {
            existing.modify({ name: slot.name, type: slot.type, label: undefined });
            node.outputs.at(existing.index)?.modify({
                name: getContextOutputName(slot.name),
                type: slot.type,
                label: undefined,
            });
        }
        else {
            const trailing = node.inputs.at(node.inputs.length - 1);
            const index = trailing?.type === "*" ? trailing.index : node.inputs.length;
            node.inputs.add(slot.name, slot.type);
            node.outputs.add(getContextOutputName(slot.name), slot.type);
            node.inputs.reorder([
                ...node.inputs.names().filter((name) => name !== slot.name).slice(0, index),
                slot.name,
                ...node.inputs.names().filter((name) => name !== slot.name).slice(index),
            ]);
        }
    }

    const inherited = desired
        .map((slot) => node.inputs.all().find((input) => !isOwnedContextInput(input) && getContextOutputName(input.name) === getContextOutputName(slot.name))?.name)
        .filter(Boolean);
    const owned = node.inputs
        .all()
        .filter((input) => input.type !== "*" && isOwnedContextInput(input))
        .map((input) => input.name);
    const trailing = node.inputs.all().filter((input) => input.type === "*").map((input) => input.name);
    const outputOrder = [
        node.outputs.at(0).name,
        ...inherited.map(getContextOutputName),
        ...owned.map(getContextOutputName),
    ];
    for (const output of node.outputs.all().slice(1)) {
        if (!outputOrder.includes(output.name)) node.outputs.remove(output.id);
    }
    node.inputs.reorder([node.inputs.at(0).name, ...inherited, ...owned, ...trailing]);
    node.outputs.reorder(outputOrder);
    notifyContextInputsChanged(node);
}

function scheduleBaseSync(node) {
    const key = nodeKey(node);
    if (pendingSync.has(key)) {
        return;
    }
    pendingSync.add(key);
    queueMicrotask(() => {
        pendingSync.delete(key);
        if (!node.isDeleted) {
            comfy.graph.batch(() => reconcileFromBase(node));
        }
    });
}

function handleNewInput(node, index) {
    const input = node.inputs.at(index);
    if (!input || input.name !== "+" || input.type !== "*" || !input.isConnected) {
        return;
    }
    const source = followConnectionUntilType(node, false, true, index);
    if (!source?.type || !source.name) {
        return;
    }
    let name = nextUniqueContextName(node, source.name);
    if (/^[A-Z_]+(?:\.\d+)?$/.test(name)) {
        name = name.toLowerCase();
    }
    input.modify({ name: ownedInputName(name), type: source.type, label: undefined });
    node.outputs.add(getContextOutputName(name), source.type);
    node.outputs.reorder([
        ...node.outputs.names().filter((outputName) => outputName !== getContextOutputName(name)).slice(0, index),
        getContextOutputName(name),
        ...node.outputs.names().filter((outputName) => outputName !== getContextOutputName(name)).slice(index),
    ]);
    notifyContextInputsChanged(node, {
        operation: "added",
        slotIndex: index,
        slot: { name: input.name, type: input.type },
    });
    stabilizeOwnedNames(node);
    ensureTrailingContextInput(node);
}

function handleBaseDisconnected(node) {
    for (let index = node.inputs.length - 1; index > 0; index--) {
        const input = node.inputs.at(index);
        if (!input || input.type === "*" || isOwnedContextInput(input)) {
            continue;
        }
        const output = node.outputs.at(index);
        if (input.isConnected || output?.isConnected) {
            renameContextPair(node, index, input.name, true);
        }
        else {
            removeContextPair(node, index);
        }
    }
    ensureTrailingContextInput(node);
}

function trimUnfedClone(node) {
    for (let index = node.inputs.length - 1; index > 0; index--) {
        const input = node.inputs.at(index);
        const output = node.outputs.at(index);
        if (input?.type !== "*" && !input.isConnected && !output?.isConnected) {
            removeContextPair(node, index);
        }
    }
    ensureTrailingContextInput(node);
}

function cleanupNode(node) {
    const key = nodeKey(node);
    cleanupByNode.get(key)?.();
    cleanupByNode.delete(key);
    pendingSync.delete(key);
    releaseDynamicContextNode(node);
}

if (CONFIG_SERVICE.getConfigValue("unreleased.dynamic_context.enabled")) {
    comfy.defs.extend(TYPE, (builder) => {
        builder.onCreated((node, event) => {
            cleanupNode(node);
            ensureBaseSlots(node);
            ensureTrailingContextInput(node);
            prepareDynamicContextNode(node);
            cleanupByNode.set(nodeKey(node), registerDynamicContext(node, {
                inputs: () => contextInputs(node),
                upstreamChanged: (mutation) => {
                    if (mutation) {
                        comfy.graph.batch(() => {
                            if (mutation.operation !== "removed")
                                stabilizeOwnedNames(node, [mutation.slot.name]);
                            applyUpstreamMutation(node, mutation);
                            stabilizeOwnedNames(node);
                            ensureTrailingContextInput(node);
                        });
                    }
                    else {
                        scheduleBaseSync(node);
                    }
                },
            }));
            if (event.restored && !event.loading) {
                setTimeout(() => {
                    if (!node.isDeleted) {
                        comfy.graph.batch(() => trimUnfedClone(node));
                    }
                }, 0);
            }
            scheduleBaseSync(node);
        });
        builder.onConfigured((node) => {
            ensureBaseSlots(node);
            ensureTrailingContextInput(node);
            stabilizeOwnedNames(node);
            scheduleBaseSync(node);
        });
        builder.onBeforeConnect((node, event) => {
            if (event.side !== "input" || event.index === 0 || event.peerIndex !== 0 || !event.peerNodeId) {
                return;
            }
            return graphOf(node).node(event.peerNodeId)?.type === TYPE ? false : undefined;
        });
        builder.onConnectionsChanged((node, event) => {
            if (event.side !== "input") {
                return;
            }
            comfy.graph.batch(() => {
                if (event.index === 0) {
                    if (event.connected) {
                        scheduleBaseSync(node);
                    }
                    else {
                        handleBaseDisconnected(node);
                    }
                }
                else if (event.connected) {
                    handleNewInput(node, event.index);
                }
            });
        });
        builder.onRemoved(cleanupNode);
        builder.addMenuItem({
            label: "Rename input",
            when: (node) => dynamicInputMenuItems(node, () => {}).length > 0,
            items: (node) => dynamicInputMenuItems(node, (index) => {
                const input = node.inputs.at(index);
                if (!input) {
                    return;
                }
                comfy.ui.prompt({ label: "Input name", value: stripOwnedPrefix(input.name) }).then((name) => {
                    if (name !== undefined) {
                        comfy.graph.batch(() => {
                            renameContextPair(node, index, name, true);
                            stabilizeOwnedNames(node);
                        });
                    }
                });
            }),
        });
        builder.addMenuItem({
            label: "Delete input",
            when: (node) => dynamicInputMenuItems(node, () => {}).length > 0,
            items: (node) => dynamicInputMenuItems(node, (index) => {
                comfy.graph.batch(() => {
                    removeContextPair(node, index);
                    ensureTrailingContextInput(node);
                    stabilizeOwnedNames(node);
                });
            }),
        });
    });
}

// REFUSED: overriding renderer connection geometry to force inputs left and
// outputs right. The node keeps its behavior with host-owned slot placement.
