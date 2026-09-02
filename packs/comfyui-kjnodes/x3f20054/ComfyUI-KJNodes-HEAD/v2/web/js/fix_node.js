import { comfy } from '/comfy/api/v2.js';

/** Put every widget the definition declares back to the default it declares. */
function resetWidgetValues(newNode) {
    const def = comfy.defs.get(newNode.type);
    if (!def) return;
    for (const input of def.inputs) {
        const fallback = input.options.default;
        if (fallback === undefined) continue;
        const w = newNode.widgets.get(input.name);
        if (!w) continue;
        try { w.setValue(fallback); } catch {}
    }
}

function fixNode(oldNode, comfyClass, { resetValues = false } = {}) {
    if (!comfy.defs.has(comfyClass)) {
        console.error(`[KJNodes.FixNode] Unknown node type: ${comfyClass}`);
        return null;
    }

    try {
        // Rebuilds the node in place as one undo step, carrying position, title,
        // colour, mode, properties, widget values and every link that still fits.
        const newNode = comfy.graph.replace(oldNode.id, comfyClass) ?? null;
        if (newNode && resetValues) resetWidgetValues(newNode);
        return newNode;
    } catch (err) {
        console.error("[KJNodes.FixNode] Aborting:", err);
        return null;
    }
}

window.kjNodes = window.kjNodes || {};
window.kjNodes.recreateNode = fixNode;
