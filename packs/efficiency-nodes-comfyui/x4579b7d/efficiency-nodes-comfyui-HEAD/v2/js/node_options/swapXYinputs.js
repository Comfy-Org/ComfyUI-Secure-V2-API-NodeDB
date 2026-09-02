import { comfy } from '/comfy/api/v2.js';

function replaceNode(oldNode, newNodeName) {
    const newNode = comfy.graph.add(newNodeName);

    newNode.setPosition(oldNode.getPosition());

    // Handle the special nodes with two outputs
    const nodesWithTwoOutputs = ["XY Input: LoRA Plot", "XY Input: Control Net Plot", "XY Input: Manual XY Entry"];
    let outputCount = nodesWithTwoOutputs.includes(oldNode.type) ? 2 : 1;

    // Transfer output connections from old node to new node
    // WIRE FORMAT: re-homing a link onto a DIFFERENT node allocates a new link id,
    // exactly as the original did. moveLinksTo() preserves ids only between two
    // outputs of one node, so there is nothing to preserve identity with here.
    oldNode.outputs.all().slice(0, outputCount).forEach((output, index) => {
        output.links().forEach(link => {
            const newOutput = newNode.outputs.at(index);
            if (newOutput) {
                newOutput.connectTo(link.targetNodeId, { index: link.targetIndex });
            }
        });
    });

    // Remove old node
    oldNode.remove();
}

const xyInputNodes = [
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

// Extension Definition
// One registration per type: a submenu's items are fixed at registration, so the
// "every XY Input except this one" list the old callback built per node is worked
// out here instead. That also narrows the selector from `startsWith("XY Input:")`
// to this list — an XY Input type added later gets no entry until it is added
// here, where before it would have been offered every other type but itself.
for (const nodeType of xyInputNodes) {
    comfy.defs.extend(nodeType, (b) => {
        b.addMenuItem({
            label: "🔄 Swap with...",
            order: 0,
            items: xyInputNodes.filter(n => n !== nodeType).map(n => ({
                label: n,
                run: (node) => replaceNode(node, n)
            }))
        });
    });
}
