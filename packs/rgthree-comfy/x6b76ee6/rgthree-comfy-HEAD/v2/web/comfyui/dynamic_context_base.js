import { nodeKey } from "./base_any_input_connected_node.js";
import {
    InputMutationOperation,
    getContextOutputName,
    notifyContextInputsChanged,
    stripContextInputPrefixes,
} from "./services/context_service.js";

const OWNED_PREFIX = /^\+\s*/;
const outputKeyListeners = new Map();

export function isOwnedContextInput(inputOrName) {
    const name = typeof inputOrName === "string" ? inputOrName : inputOrName?.name ?? "";
    return OWNED_PREFIX.test(name);
}

export function stripOwnedPrefix(name) {
    return name.replace(OWNED_PREFIX, "");
}

export function ownedInputName(name) {
    return `+ ${stripOwnedPrefix(name)}`;
}

export function contextInputs(node) {
    return node.inputs
        .all()
        .map((slot, index) => ({ name: slot.name, type: slot.type, index }))
        .filter((slot) => slot.type !== "*");
}

export function ensureContextOutput(node) {
    if (!node.outputs.byName("CONTEXT")) {
        node.outputs.add("CONTEXT", "RGTHREE_DYNAMIC_CONTEXT");
        node.outputs.reorder(["CONTEXT", ...node.outputs.names().filter((name) => name !== "CONTEXT")]);
    }
}

export function ensureTrailingContextInput(node) {
    const empty = node.inputs.all().filter((input) => input.name === "+" && input.type === "*" && !input.isConnected);
    for (const extra of empty.slice(1))
        node.inputs.remove(extra.id);
    const last = node.inputs.at(node.inputs.length - 1);
    if (!last || last.name !== "+" || last.type !== "*" || last.isConnected)
        node.inputs.add("+", "*");
}

export function ensureOutputKeysWidget(node) {
    let widget = node.widgets.get("output_keys");
    if (!widget) {
        widget = node.widgets.add({
            type: "text",
            name: "output_keys",
            value: "",
            hidden: true,
            serialize: true,
        });
    }
    const key = nodeKey(node);
    outputKeyListeners.get(key)?.();
    outputKeyListeners.set(key, widget.on("beforeSerialize", (event) => {
        if (event.context === "prompt") {
            event.setSerializedValue(node.outputs.names().slice(1).join(","));
        }
    }));
}

export function releaseDynamicContextNode(node) {
    const key = nodeKey(node);
    outputKeyListeners.get(key)?.();
    outputKeyListeners.delete(key);
}

function insertName(names, name, index) {
    const next = names.filter((candidate) => candidate !== name);
    next.splice(Math.min(Math.max(index, 0), next.length), 0, name);
    return next;
}

export function addContextPair(node, name, type, index = node.inputs.length, owned = false) {
    const inputName = owned ? ownedInputName(name) : stripOwnedPrefix(name);
    const outputName = getContextOutputName(inputName);
    node.inputs.add(inputName, type);
    node.outputs.add(outputName, type);
    node.inputs.reorder(insertName(node.inputs.names(), inputName, index));
    node.outputs.reorder(insertName(node.outputs.names(), outputName, index));
    const slot = node.inputs.at(index);
    const mutation = {
        operation: InputMutationOperation.ADDED,
        slotIndex: index,
        slot: slot ? { name: slot.name, type: slot.type } : { name: inputName, type },
    };
    notifyContextInputsChanged(node, mutation);
    return slot;
}

export function removeContextPair(node, index) {
    const input = node.inputs.at(index);
    if (!input) {
        return false;
    }
    const slot = { name: input.name, type: input.type };
    node.inputs.remove({ index });
    if (node.outputs.at(index)) {
        node.outputs.remove({ index });
    }
    notifyContextInputsChanged(node, {
        operation: InputMutationOperation.REMOVED,
        slotIndex: index,
        slot,
    });
    return true;
}

export function renameContextPair(node, index, name, owned) {
    const input = node.inputs.at(index);
    const output = node.outputs.at(index);
    if (!input || !output) {
        return false;
    }
    const stripped = stripOwnedPrefix(name.trim() || input.name).toLowerCase();
    const inputName = owned ? ownedInputName(stripped) : stripped;
    input.modify({ name: inputName, label: undefined });
    output.modify({ name: getContextOutputName(inputName), label: undefined });
    notifyContextInputsChanged(node, {
        operation: InputMutationOperation.RENAMED,
        slotIndex: index,
        slot: { name: inputName, type: input.type },
    });
    return true;
}

export function applyUpstreamMutation(node, mutation) {
    if (mutation.operation === InputMutationOperation.ADDED) {
        addContextPair(node, mutation.slot.name, mutation.slot.type, mutation.slotIndex);
        return;
    }
    if (mutation.operation === InputMutationOperation.REMOVED) {
        removeContextPair(node, mutation.slotIndex);
        return;
    }
    if (mutation.operation === InputMutationOperation.RENAMED) {
        renameContextPair(node, mutation.slotIndex, mutation.slot.name, false);
    }
}

export function nextUniqueContextName(node, desiredName) {
    const existing = new Set(node.inputs.names().map((name) => stripOwnedPrefix(name).toUpperCase()));
    const root = stripOwnedPrefix(desiredName);
    let candidate = root;
    let suffix = 0;
    while (existing.has(candidate.toUpperCase())) {
        candidate = `${root}.${++suffix}`;
    }
    return candidate;
}

export function dynamicInputMenuItems(node, action) {
    return node.inputs
        .all()
        .filter((input) => isOwnedContextInput(input))
        .map((input) => ({
        label: stripContextInputPrefixes(input.name),
        run: () => action(input.index),
    }));
}

export function prepareDynamicContextNode(node) {
    ensureOutputKeysWidget(node);
    node.setSizeConstraints({ autoHeight: true });
}

// REFUSED: writing this type into LiteGraph.slot_types_default_out. Core builds
// link-release suggestions from registered definitions; a pack does not reorder
// the global suggestions table.
// LIMITATION: the legacy renderer's generic slot menu can still rename a paired
// output directly. Nodes 2.0 exposes the pack's paired rename/delete node menu,
// which keeps both sides consistent without publishing renderer menu flags.
