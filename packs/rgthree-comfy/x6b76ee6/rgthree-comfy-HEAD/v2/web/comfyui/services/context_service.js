import { connectedOutputNodes, nodeKey } from "../base_any_input_connected_node.js";

const REGEX_PREFIX = /^[+⚠️🛑]\s*/;
const registrations = new Map();

export const InputMutationOperation = Object.freeze({
    ADDED: "added",
    REMOVED: "removed",
    RENAMED: "renamed",
});

export function stripContextInputPrefixes(name) {
    return name.replace(REGEX_PREFIX, "");
}

export function getContextOutputName(inputName) {
    return inputName === "base_ctx"
        ? "CONTEXT"
        : stripContextInputPrefixes(inputName).toUpperCase();
}

function slotData(slot, index) {
    return {
        name: stripContextInputPrefixes(slot.name),
        type: String(slot.type),
        index,
    };
}

export function registerDynamicContext(node, registration) {
    const key = nodeKey(node);
    registrations.set(key, registration);
    return () => registrations.delete(key);
}

export function getDynamicContextInputsData(node) {
    const supplied = registrations.get(nodeKey(node))?.inputs();
    if (supplied) {
        return supplied.map((slot, index) => slotData(slot, slot.index ?? index)).filter((slot) => slot.type !== "*");
    }
    return node.inputs
        .all()
        .map(slotData)
        .filter((slot) => slot.type !== "*");
}

export function getDynamicContextOutputsData(node) {
    return node.outputs.all().map(slotData);
}

export function notifyContextInputsChanged(node, mutation) {
    for (const downstream of connectedOutputNodes(node, { slot: 0 })) {
        registrations.get(nodeKey(downstream))?.upstreamChanged?.(mutation);
    }
}

export const SERVICE = {
    getDynamicContextInputsData,
    getDynamicContextOutputsData,
    onInputChanges: notifyContextInputsChanged,
};
