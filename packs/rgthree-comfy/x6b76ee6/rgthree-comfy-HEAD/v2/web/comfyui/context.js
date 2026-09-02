import { comfy } from '/comfy/api/v2.js';
import { debounce } from "../../rgthree/common/shared_utils.js";
import { NodeTypesString } from "./constants.js";
import { removeUnusedInputsFromEnd } from "./utils_inputs_outputs.js";
import { matchLocalSlotsToServer } from "./utils.js";
// Handles hold no arbitrary properties, so the per-node debounce target lives
// here. `debounce` keys by function identity, so each node needs its own.
const stabilizersByNode = new Map();
const CONVERT_TO = {
    [NodeTypesString.CONTEXT]: {
        label: "Convert To Context Big",
        type: NodeTypesString.CONTEXT_BIG,
    },
    [NodeTypesString.CONTEXT_BIG]: {
        label: "Convert To Context (Original)",
        type: NodeTypesString.CONTEXT,
    },
    [NodeTypesString.CONTEXT_SWITCH]: {
        label: "Convert To Context Switch Big",
        type: NodeTypesString.CONTEXT_SWITCH_BIG,
    },
    [NodeTypesString.CONTEXT_SWITCH_BIG]: {
        label: "Convert To Context Switch",
        type: NodeTypesString.CONTEXT_SWITCH,
    },
    [NodeTypesString.CONTEXT_MERGE]: {
        label: "Convert To Context Merge Big",
        type: NodeTypesString.CONTEXT_MERGE_BIG,
    },
    [NodeTypesString.CONTEXT_MERGE_BIG]: {
        label: "Convert To Context Switch",
        type: NodeTypesString.CONTEXT_MERGE,
    },
};
const MULTI_CTX_INPUT_TYPES = [
    NodeTypesString.CONTEXT_SWITCH,
    NodeTypesString.CONTEXT_SWITCH_BIG,
    NodeTypesString.CONTEXT_MERGE,
    NodeTypesString.CONTEXT_MERGE_BIG,
];
function addContextInput(node, num = 1) {
    for (let i = 0; i < num; i++) {
        node.inputs.add(`ctx_${String(node.inputs.length + 1).padStart(2, "0")}`, "RGTHREE_CONTEXT");
    }
}
function stabilize(node) {
    if (node.isDeleted)
        return;
    removeUnusedInputsFromEnd(node, 4);
    addContextInput(node);
}
// An early build shipped this output misspelled, so saved workflows still carry
// it. The author's note says the rename lives here in perpetuity.
function fixBadConfigs(node) {
    const wrongName = node.outputs.byName("CLIP_HEIGTH");
    if (wrongName) {
        wrongName.modify({ name: "CLIP_HEIGHT" });
    }
}
// rgthree's own matching rules, unchanged: which of a context's slots feeds a
// given slot on some other node. The heuristics — SEED matching anything with
// SEED in the name, STEP_REFINER matching AT_STEP, POSITIVE/NEGATIVE inferred
// from the peer node's type or title — are domain knowledge about ComfyUI's
// conventions and belong to the pack. The API publishes the moment, not the
// match.
const COMBO = "COMBO";
const NAMED_MATCH_TYPES = ["CONDITIONING", "INT", "STRING", "FLOAT", COMBO];
function normalizeType(type) {
    return Array.isArray(type) || String(type).includes(",") ? COMBO : type;
}
function normalizeName(name) {
    return name.toUpperCase().replace("OPT_", "").replace("_NAME", "");
}
function findMatchingIndexByTypeOrName(peer, peerSlot, ctxSlots) {
    const peerType = (peer.type || "").toUpperCase();
    const peerTitle = peer.getTitle().toUpperCase();
    const slotType = normalizeType(peerSlot.type);
    const slotName = normalizeName(peerSlot.name);
    if (!NAMED_MATCH_TYPES.includes(slotType)) {
        return ctxSlots.findIndex((ctx) => normalizeType(ctx.type) === slotType);
    }
    return ctxSlots.findIndex((ctx) => {
        if (normalizeType(ctx.type) !== slotType)
            return false;
        const ctxName = normalizeName(ctx.name);
        if (ctxName === slotName ||
            (ctxName === "SEED" && slotName.includes("SEED")) ||
            (ctxName === "STEP_REFINER" && slotName.includes("AT_STEP")) ||
            (ctxName === "STEP_REFINER" && slotName.includes("REFINER_STEP"))) {
            return true;
        }
        const says = (word) => peerType.includes(word) || peerTitle.includes(word);
        if (says("POSITIVE") &&
            ((ctxName === "POSITIVE" && slotType === "CONDITIONING") ||
                (ctxName === "TEXT_POS_G" && slotName.includes("TEXT_G")) ||
                (ctxName === "TEXT_POS_L" && slotName.includes("TEXT_L")))) {
            return true;
        }
        if (says("NEGATIVE") &&
            ((ctxName === "NEGATIVE" && slotType === "CONDITIONING") ||
                (ctxName === "TEXT_NEG_G" && slotName.includes("TEXT_G")) ||
                (ctxName === "TEXT_NEG_L" && slotName.includes("TEXT_L")))) {
            return true;
        }
        return false;
    });
}
/**
 * Unpacks a context onto every slot of the peer that one of ours matches.
 *
 * The original replaced `connectByType` on LGraphNode.prototype to do this,
 * which changed link routing for every node in the document. `onUnplacedLink`
 * fires at the same moment — a link dropped on a node body that no single slot
 * fits — and only for these types.
 */
function fanOut(node, event) {
    const peer = comfy.graph.node(event.peerNodeId);
    if (!peer)
        return false;
    const feeding = event.side === "output";
    const ours = feeding ? node.outputs.all() : node.inputs.all();
    const theirs = feeding ? peer.inputs.all() : peer.outputs.all();
    return comfy.graph.batch(() => {
        let wired = false;
        for (const peerSlot of theirs) {
            // Without the modifier, an already-wired slot is left alone; the
            // original read ctrl from the pack's own key service, and the host
            // now says which modifier means overwrite.
            if (peerSlot.isConnected && !event.replaceExisting)
                continue;
            const index = findMatchingIndexByTypeOrName(peer, peerSlot, ours);
            if (index === -1)
                continue;
            const source = feeding ? ours[index] : peerSlot;
            const targetId = feeding ? peer.id : node.id;
            const targetIndex = feeding ? peerSlot.index : ours[index].index;
            source.connectTo(targetId, { index: targetIndex });
            wired = true;
        }
        return wired;
    });
}
comfy.defs.extend(Object.keys(CONVERT_TO), (b) => {
    // The original read `nodeData.input.optional` for the input side. `b.def.inputs`
    // merges required and optional in the order core itself builds the node's slots,
    // which is the list the node should match; for these types, whose Python declares
    // every input optional, the two are the same list.
    function reconcileWithServerDef(node) {
        matchLocalSlotsToServer(node.outputs, b.def.outputs);
        if (!node.type.includes("Switch") && !node.type.includes("Merge")) {
            matchLocalSlotsToServer(node.inputs, b.def.inputs);
        }
    }
    b.onCreated((node) => {
        fixBadConfigs(node);
        reconcileWithServerDef(node);
        // onCreated fires whenever the node joins a graph, which can happen more
        // than once; the old constructor ran only at construction, and a second
        // pass would append five more ctx_XX inputs to the serialized node.
        if (MULTI_CTX_INPUT_TYPES.includes(node.type) &&
            !node.inputs.names().some((name) => name.startsWith("ctx_"))) {
            addContextInput(node, 5);
        }
    });
    b.onConfigured((node) => {
        fixBadConfigs(node);
        reconcileWithServerDef(node);
    });
    b.onConnectionsChanged((node, event) => {
        if (event.side !== "input" || !MULTI_CTX_INPUT_TYPES.includes(node.type)) {
            return;
        }
        let stabilizer = stabilizersByNode.get(node.id);
        if (!stabilizer) {
            stabilizer = () => stabilize(node);
            stabilizersByNode.set(node.id, stabilizer);
        }
        debounce(stabilizer, 64);
    });
    b.onRemoved((node) => {
        stabilizersByNode.delete(node.id);
    });
    b.onUnplacedLink((node, event) => fanOut(node, event));
    b.addMenuItem({
        label: (node) => CONVERT_TO[node.type].label,
        when: (node) => !!CONVERT_TO[node.type],
        run: (node) => {
            // `comfy.graph.replace` is the original's whole routine: it carries the
            // title the user gave the node, its position, properties and widget
            // values, sizes the replacement to whichever of the two is larger, and
            // re-makes every link by slot name — in one undo step, and without the
            // original's ten-frame retry loop, which existed only because the
            // server-node setup it waited on filled the node in asynchronously.
            comfy.graph.replace(node.id, CONVERT_TO[node.type].type);
        },
    });
});
// `matchLocalSlotsToServer` is converted (see utils.js) and called from both hooks
//   above, which are the original's `nodeCreated` and `loadedGraphNode`. The marker
//   it carried here — "no published way to insert or permute a slot, and none at all
//   for inputs" — named a destination that already existed: `reorder(names)` on either
//   slot collection permutes and re-points every affected link in one batch, so link
//   ids survive and the saved `links` array is unchanged. `fixBadConfigs`, the other
//   half of that migration, was already converted.
// REFUSED, not a gap: writing into core's global slot-default tables.
//   `LiteGraph.slot_types_default_out["RGTHREE_CONTEXT"].push(...)` — and the matching
//   `_in` — decide what *every* pack's link drop offers for a type, from a table the
//   pack reaches into by name at module load. Which nodes a dropped link suggests is
//   the host's answer to give, and a pack pushing itself to the front of a shared list
//   is exactly the invisible, order-dependent global write this migration deletes.
//   The capability survives and needs nothing from the pack: core's own
//   `slotDefaults` extension fills both tables from every registered definition, so a
//   context link dropped on empty canvas already offers the nodes that declare
//   `RGTHREE_CONTEXT` — which is these. What is lost is putting them *first*.
// REFUSED, not a gap: `addConnectionLayoutSupport` put the inputs on the left and the
//   outputs on the right by patching `getConnectionPos` on the node class. Deciding
//   where the renderer draws a socket is refused, not pending — see utils.js. The
//   nodes work; their sockets sit where the renderer puts them.
// NO LONGER A GAP: dropping a context link on a node and having EVERY matching
//   slot wire at once is `b.onUnplacedLink`, converted above. The original got
//   there by replacing `connectByType` on LGraphNode.prototype, which changed
//   link routing for every node in the document; the hook fires at the same
//   moment — a link dropped on a body that no single slot fits — and only for
//   these types. `replaceExisting` replaces the ctrl read from the pack's own
//   key service. `findMatchingIndexByTypeOrName` stays: which context slot feeds
//   which peer slot is rgthree's domain knowledge, not the host's.
// REFUSED, not a gap: `_collapsed_width` measured the node title in the canvas's
//   own `title_text_font` to size the collapsed node. Renderer text metrics are
//   the renderer's.
// WIRE FORMAT: unchanged. Five `ctx_XX` inputs are appended after the
//   definition's own on the four multi-input types, exactly as the old
//   constructor did, and the growth/trim rule is the same. `graph.replace`
//   allocates new link ids, as the original's own routine did — it also rebuilt
//   every link on a freshly created node.
