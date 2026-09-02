import { comfy } from '/comfy/api/v2.js';
import { debounce } from "../../rgthree/common/shared_utils.js";
import { connectedInputNodes, nodeKey } from "./base_any_input_connected_node.js";
import { NodeTypesString } from "./constants.js";
import { ensureContextOutput, prepareDynamicContextNode, releaseDynamicContextNode } from "./dynamic_context_base.js";
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
import { getContextOutputName, getDynamicContextInputsData, notifyContextInputsChanged, registerDynamicContext, } from "./services/context_service.js";

const TYPE = NodeTypesString.DYNAMIC_CONTEXT_SWITCH;
const stateByNode = new Map();

function ensureFixedSlots(node) {
    if (!node.inputs.names().some((name) => name.startsWith("ctx_"))) {
        for (let index = 1; index <= 5; index++) {
            node.inputs.add(`ctx_${index}`, "RGTHREE_DYNAMIC_CONTEXT");
        }
    }
    ensureContextOutput(node);
}

function getState(node) {
    const key = nodeKey(node);
    let state = stateByNode.get(key);
    if (!state) {
        state = {
            inputs: [{ name: "base_ctx", type: "RGTHREE_DYNAMIC_CONTEXT", index: 0 }],
            signature: "",
            statusText: "",
        };
        stateByNode.set(key, state);
    }
    return state;
}

function refresh(node) {
    const state = getState(node);
    const merged = new Map([
        ["CONTEXT", { name: "base_ctx", type: "RGTHREE_DYNAMIC_CONTEXT", count: 0 }],
    ]);
    let connected = 0;
    for (let index = 0; index < node.inputs.length; index++) {
        const source = connectedInputNodes(node, { slot: index })[0];
        if (!source) {
            continue;
        }
        connected++;
        for (const slot of getDynamicContextInputsData(source)) {
            const key = getContextOutputName(slot.name);
            const existing = merged.get(key);
            if (existing) {
                existing.count++;
            }
            else {
                merged.set(key, { name: slot.name, type: slot.type, count: 1 });
            }
        }
    }

    const desired = [...merged.entries()];
    const desiredNames = new Set(desired.map(([name]) => name));
    for (const [name, data] of desired) {
        let output = node.outputs.byName(name);
        if (!output) {
            output = node.outputs.add(name, data.type);
        }
        output.modify({ name, type: data.type });
    }

    const orphans = [];
    for (let index = node.outputs.length - 1; index >= 0; index--) {
        const output = node.outputs.at(index);
        if (!output || desiredNames.has(output.name)) {
            continue;
        }
        if (output.isConnected) {
            orphans.unshift(output.name);
        }
        else {
            node.outputs.remove(output.id);
        }
    }
    node.outputs.reorder([...desired.map(([name]) => name), ...orphans]);

    const warnings = desired.filter(([, data]) => connected > 0 && data.count !== connected).map(([name]) => name);
    state.statusText = [...warnings.map((name) => `⚠️ ${name}`), ...orphans.map((name) => `🛑 ${name}`)].join("  ");
    if (state.statusText && !state.removeBadge) {
        state.removeBadge = node.addBadge(() => ({ text: state.statusText }));
    }
    else if (!state.statusText && state.removeBadge) {
        state.removeBadge();
        delete state.removeBadge;
    }

    state.inputs = desired.map(([, data], index) => ({
        name: data.name,
        type: data.type,
        index,
    }));
    const signature = JSON.stringify(state.inputs.map(({ name, type }) => [name, type]));
    if (signature !== state.signature) {
        state.signature = signature;
        notifyContextInputsChanged(node);
    }
}

function scheduleRefresh(node, ms = 64) {
    const state = getState(node);
    state.refresh ??= () => {
        if (!node.isDeleted) {
            comfy.graph.batch(() => refresh(node));
        }
    };
    debounce(state.refresh, ms);
}

function cleanup(node) {
    const key = nodeKey(node);
    const state = stateByNode.get(key);
    state?.unregister?.();
    state?.removeBadge?.();
    stateByNode.delete(key);
    releaseDynamicContextNode(node);
}

if (CONFIG_SERVICE.getConfigValue("unreleased.dynamic_context.enabled")) {
    comfy.defs.extend(TYPE, (builder) => {
        builder.onCreated((node) => {
            cleanup(node);
            ensureFixedSlots(node);
            prepareDynamicContextNode(node);
            const state = getState(node);
            state.unregister = registerDynamicContext(node, {
                inputs: () => state.inputs,
                upstreamChanged: () => scheduleRefresh(node),
            });
            scheduleRefresh(node, 0);
        });
        builder.onConfigured((node) => {
            ensureFixedSlots(node);
            scheduleRefresh(node, 0);
        });
        builder.onConnectionsChanged((node, event) => {
            if (event.side === "input") {
                scheduleRefresh(node);
            }
        });
        builder.onRemoved(cleanup);
    });
}

// The old shadow inputs and rgthree_status fields are pack state now, not fake
// entity fields. COSMETIC: exact warning keys appear in a title badge rather
// than beside each slot, so the status survives both renderers without adding
// serialized slot metadata. Output names, types, order, links, and labels stay
// unchanged.
