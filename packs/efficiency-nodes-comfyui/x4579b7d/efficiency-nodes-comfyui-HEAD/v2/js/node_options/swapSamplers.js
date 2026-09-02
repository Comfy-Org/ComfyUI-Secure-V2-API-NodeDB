import { comfy } from '/comfy/api/v2.js';
import { findWidgetByName } from "./common/utils.js";

function replaceNode(oldNode, newNodeName) {
    // Create new node
    const newNode = comfy.graph.add(newNodeName);

    // Position new node at the same position as the old node
    newNode.setPosition(oldNode.getPosition());

    // Define widget mappings
    const mappings = {
        "KSampler (Efficient) <-> KSampler Adv. (Efficient)": {
            seed: "noise_seed",
            cfg: "cfg",
            sampler_name: "sampler_name",
            scheduler: "scheduler",
            preview_method: "preview_method",
            vae_decode: "vae_decode"
        },
        "KSampler (Efficient) <-> KSampler SDXL (Eff.)": {
            seed: "noise_seed",
            cfg: "cfg",
            sampler_name: "sampler_name",
            scheduler: "scheduler",
            preview_method: "preview_method",
            vae_decode: "vae_decode"
        },
        "KSampler Adv. (Efficient) <-> KSampler SDXL (Eff.)": {
            noise_seed: "noise_seed",
            steps: "steps",
            cfg: "cfg",
            sampler_name: "sampler_name",
            scheduler: "scheduler",
            start_at_step: "start_at_step",
            preview_method: "preview_method",
            vae_decode: "vae_decode"}
    };

    const swapKey = `${oldNode.type} <-> ${newNodeName}`;

    let widgetMapping = {};

    // Check if a reverse mapping is needed
    if (!mappings[swapKey]) {
        const reverseKey = `${newNodeName} <-> ${oldNode.type}`;
        const reverseMapping = mappings[reverseKey];
        if (reverseMapping) {
            widgetMapping = Object.entries(reverseMapping).reduce((acc, [key, value]) => {
                acc[value] = key;
                return acc;
            }, {});
        }
    } else {
        widgetMapping = mappings[swapKey];
    }

    if (oldNode.type === "KSampler (Efficient)" && (newNodeName === "KSampler Adv. (Efficient)" || newNodeName === "KSampler SDXL (Eff.)")) {
        const denoise = Math.min(Math.max(findWidgetByName(oldNode, "denoise").getValue(), 0), 1); // Ensure denoise is between 0 and 1
        const steps = Math.min(Math.max(findWidgetByName(oldNode, "steps").getValue(), 0), 10000); // Ensure steps is between 0 and 10000

        const total_steps = Math.floor(steps / denoise);
        const start_at_step = total_steps - steps;

        findWidgetByName(newNode, "steps").setValue(Math.min(Math.max(total_steps, 0), 10000)); // Ensure total_steps is between 0 and 10000
        findWidgetByName(newNode, "start_at_step").setValue(Math.min(Math.max(start_at_step, 0), 10000)); // Ensure start_at_step is between 0 and 10000
    }
    else if ((oldNode.type === "KSampler Adv. (Efficient)" || oldNode.type === "KSampler SDXL (Eff.)") && newNodeName === "KSampler (Efficient)") {
        const stepsAdv = Math.min(Math.max(findWidgetByName(oldNode, "steps").getValue(), 0), 10000); // Ensure stepsAdv is between 0 and 10000
        const start_at_step = Math.min(Math.max(findWidgetByName(oldNode, "start_at_step").getValue(), 0), 10000); // Ensure start_at_step is between 0 and 10000

        const denoise = Math.min(Math.max((stepsAdv - start_at_step) / stepsAdv, 0), 1); // Ensure denoise is between 0 and 1
        const stepsTotal = stepsAdv - start_at_step;

        findWidgetByName(newNode, "denoise").setValue(denoise);
        findWidgetByName(newNode, "steps").setValue(Math.min(Math.max(stepsTotal, 0), 10000)); // Ensure stepsTotal is between 0 and 10000
    }

    // Transfer widget values from old node to new node
    oldNode.widgets.all().forEach(widget => {
        const newName = widgetMapping[widget.name];
        if (newName) {
            const newWidget = findWidgetByName(newNode, newName);
            if (newWidget) {
                newWidget.setValue(widget.getValue());
            }
        }
    });

    // Determine the starting indices based on the node types
    let oldNodeInputStartIndex = 0;
    let newNodeInputStartIndex = 0;
    let oldNodeOutputStartIndex = 0;
    let newNodeOutputStartIndex = 0;

    if (oldNode.type === "KSampler SDXL (Eff.)" || newNodeName === "KSampler SDXL (Eff.)") {
        oldNodeInputStartIndex = (oldNode.type === "KSampler SDXL (Eff.)") ? 1 : 3;
        newNodeInputStartIndex = (newNodeName === "KSampler SDXL (Eff.)") ? 1 : 3;
        oldNodeOutputStartIndex = (oldNode.type === "KSampler SDXL (Eff.)") ? 1 : 3;
        newNodeOutputStartIndex = (newNodeName === "KSampler SDXL (Eff.)") ? 1 : 3;
    }

    // Transfer connections from old node to new node
    // WIRE FORMAT: re-homing a link onto a DIFFERENT node allocates a new link id,
    // exactly as the original did. moveLinksTo() preserves ids only between two
    // outputs of one node, so there is nothing to preserve identity with here.
    oldNode.inputs.all().slice(oldNodeInputStartIndex).forEach((input, index) => {
        const source = input.source();
        if (source) {
            const originNode = comfy.graph.node(source.nodeId);
            if (originNode) {
                const originOutput = originNode.outputs.at(source.outputIndex);
                if (originOutput) {
                    originOutput.connectTo(newNode.id, { index: index + newNodeInputStartIndex });
                }
            }
        }
    });

    oldNode.outputs.all().slice(oldNodeOutputStartIndex).forEach((output, index) => {
        output.links().forEach(link => {
            const newOutput = newNode.outputs.at(index + newNodeOutputStartIndex);
            if (newOutput) {
                newOutput.connectTo(link.targetNodeId, { index: link.targetIndex });
            }
        });
    });

    // Remove old node
    oldNode.remove();
}

// Extension Definition
// One registration per type: a submenu's items are fixed at registration, so the
// "every sampler except this one" list the old callback built per node is worked
// out here instead.
const samplerNodes = [
    "KSampler (Efficient)",
    "KSampler Adv. (Efficient)",
    "KSampler SDXL (Eff.)"
];

for (const nodeType of samplerNodes) {
    comfy.defs.extend(nodeType, (b) => {
        b.addMenuItem({
            label: "🔄 Swap with...",
            order: 0,
            items: samplerNodes.filter(n => n !== nodeType).map(n => ({
                label: n,
                run: (node) => replaceNode(node, n)
            }))
        });
    });
}
