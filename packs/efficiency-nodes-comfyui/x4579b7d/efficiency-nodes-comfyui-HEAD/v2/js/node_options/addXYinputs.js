import { comfy } from '/comfy/api/v2.js';
import { addNode } from "./common/utils.js";

const nodePxOffsets = 80;

function getXYInputNodes() {
    return [
        "XY Input: Seeds++ Batch",
        "XY Input: Add/Return Noise",
        "XY Input: Steps",
        "XY Input: CFG Scale",
        "XY Input: Sampler/Scheduler",
        "XY Input: Denoise",
        "XY Input: VAE",
        "XY Input: Prompt S/R",
        "XY Input: Aesthetic Score",
        "XY Input: Refiner On/Off",
        "XY Input: Checkpoint",
        "XY Input: Clip Skip",
        "XY Input: LoRA",
        "XY Input: LoRA Plot",
        "XY Input: LoRA Stacks",
        "XY Input: Control Net",
        "XY Input: Control Net Plot",
        "XY Input: Manual XY Entry"
    ];
}

function getAddXYInputItems(type) {
    const specialNodes = [
        "XY Input: LoRA Plot",
        "XY Input: Control Net Plot",
        "XY Input: Manual XY Entry"
    ];

    return getXYInputNodes().map(nodeType => {
        return {
            label: nodeType,
            run: function(node) {
                const newNode = addNode(nodeType, node);

                // Calculate the left shift based on the width of the new node
                const shiftX = -(newNode.getSize().width + 35);
                const pos = newNode.getPosition();

                if (specialNodes.includes(nodeType)) {
                    newNode.setPosition({ x: pos.x + shiftX, y: pos.y + 20 });
                    // Connect both outputs to the XY Plot's 2nd and 3rd input.
                    newNode.outputs.at(0).connectTo(node.id, { index: 1 });
                    newNode.outputs.at(1).connectTo(node.id, { index: 2 });
                } else if (type === 'X') {
                    newNode.setPosition({ x: pos.x + shiftX, y: pos.y + 20 });
                    newNode.outputs.at(0).connectTo(node.id, { index: 1 });  // Connect to 2nd input
                } else {
                    newNode.setPosition({ x: pos.x + shiftX, y: pos.y + node.getSize().height + 45 });
                    newNode.outputs.at(0).connectTo(node.id, { index: 2 });  // Connect to 3rd input
                }
            }
        };
    });
}

comfy.defs.extend("XY Plot", (b) => {
    b.addMenuItem({
        label: "✏️ Add 𝚇 input...",
        order: 6,
        items: getAddXYInputItems('X')
    });
    b.addMenuItem({
        label: "✏️ Add 𝚈 input...",
        order: 7,
        items: getAddXYInputItems('Y')
    });
});
