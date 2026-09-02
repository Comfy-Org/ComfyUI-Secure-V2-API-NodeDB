import { comfy } from '/comfy/api/v2.js';
import { findWidgetByName } from "./common/utils.js";

function replaceNode(oldNode, newNodeName) {
    const newNode = comfy.graph.add(newNodeName);

    newNode.setPosition(oldNode.getPosition());
    newNode.setSize(oldNode.getSize());

    // Transfer widget values
    const widgetMapping = {
        "ckpt_name": "base_ckpt_name",
        "vae_name": "vae_name",
        "clip_skip": "base_clip_skip",
        "positive": "positive",
        "negative": "negative",
        "prompt_style": "prompt_style",
        "empty_latent_width": "empty_latent_width",
        "empty_latent_height": "empty_latent_height",
        "batch_size": "batch_size"
    };

    let effectiveWidgetMapping = widgetMapping;

    // Invert the mapping when going from "Eff. Loader SDXL" to "Efficient Loader"
    if (oldNode.type === "Eff. Loader SDXL" && newNodeName === "Efficient Loader") {
        effectiveWidgetMapping = {};
        for (const [key, value] of Object.entries(widgetMapping)) {
            effectiveWidgetMapping[value] = key;
        }
    }

    oldNode.widgets.all().forEach(widget => {
        const newName = effectiveWidgetMapping[widget.name];
        if (newName) {
            const newWidget = findWidgetByName(newNode, newName);
            if (newWidget) {
                newWidget.setValue(widget.getValue());
            }
        }
    });

    // Hardcoded transfer for specific outputs based on the output names from the nodes in the image
    const outputMapping = {
        "MODEL": null,           // Not present in "Eff. Loader SDXL"
        "CONDITIONING+": null,   // Not present in "Eff. Loader SDXL"
        "CONDITIONING-": null,   // Not present in "Eff. Loader SDXL"
        "LATENT": "LATENT",
        "VAE": "VAE",
        "CLIP": null,            // Not present in "Eff. Loader SDXL"
        "DEPENDENCIES": "DEPENDENCIES"
    };

    // Transfer connections from old node outputs to new node outputs based on the outputMapping
    // WIRE FORMAT: re-homing a link onto a DIFFERENT node allocates a new link id,
    // exactly as the original did. moveLinksTo() preserves ids only between two
    // outputs of one node, so there is nothing to preserve identity with here.
    oldNode.outputs.all().forEach((output) => {
        const links = output.links();
        if (links.length && outputMapping[output.name]) {
            const newOutputName = outputMapping[output.name];

            // If the new node does not have this output, skip
            if (newOutputName === null) {
                return;
            }

            const newOutput = newNode.outputs.byName(newOutputName);
            if (newOutput) {
                links.forEach(link => {
                    newOutput.connectTo(link.targetNodeId, { index: link.targetIndex });
                });
            }
        }
    });

    // Remove old node
    oldNode.remove();
}

// Extension Definition
// Registered per type rather than for both at once: a submenu's items are fixed
// at registration, and the entry each loader offers is the OTHER loader — which
// is what the `node.type !== …` tests worked out when the menu opened.
comfy.defs.extend("Efficient Loader", (b) => {
    b.addMenuItem({
        label: "🔄 Swap with...",
        order: 0,
        items: [
            { label: "Eff. Loader SDXL", run: (node) => replaceNode(node, "Eff. Loader SDXL") }
        ]
    });
});

comfy.defs.extend("Eff. Loader SDXL", (b) => {
    b.addMenuItem({
        label: "🔄 Swap with...",
        order: 0,
        items: [
            { label: "Efficient Loader", run: (node) => replaceNode(node, "Efficient Loader") }
        ]
    });
});
