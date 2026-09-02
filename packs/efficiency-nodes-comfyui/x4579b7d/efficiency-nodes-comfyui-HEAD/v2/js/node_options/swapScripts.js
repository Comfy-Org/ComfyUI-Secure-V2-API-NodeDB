import { comfy } from '/comfy/api/v2.js';

function replaceNode(oldNode, newNodeName) {
    const newNode = comfy.graph.add(newNodeName);

    newNode.setPosition(oldNode.getPosition());

    // Transfer connections from old node to new node
    // WIRE FORMAT: re-homing a link onto a DIFFERENT node allocates a new link id,
    // exactly as the original did. moveLinksTo() preserves ids only between two
    // outputs of one node, so there is nothing to preserve identity with here.
    // XY Plot has only one output.
    if(oldNode.type === "XY Plot") {
        const oldOutput = oldNode.outputs.at(0);
        if (oldOutput) {
            oldOutput.links().forEach(link => {
                const newOutput = newNode.outputs.at(0);
                if (newOutput) {
                    newOutput.connectTo(link.targetNodeId, { index: link.targetIndex });
                }
            });
        }
    } else {
        // Noise Control Script, HighRes-Fix Script, and Tiled Upscaler Script have 1 input and 1 output at index 0
        const source = oldNode.inputs.at(0)?.source();
        if (source) {
            const originNode = comfy.graph.node(source.nodeId);
            if (originNode) {
                const originOutput = originNode.outputs.at(source.outputIndex);
                if (originOutput) {
                    originOutput.connectTo(newNode.id, { index: 0 });
                }
            }
        }

        const oldOutput = oldNode.outputs.at(0);
        if (oldOutput) {
            oldOutput.links().forEach(link => {
                const newOutput = newNode.outputs.at(0);
                if (newOutput) {
                    newOutput.connectTo(link.targetNodeId, { index: link.targetIndex });
                }
            });
        }
    }

    // Remove old node
    oldNode.remove();
}

// Extension Definition
// One registration per type: a submenu's items are fixed at registration, so the
// "every script except this one" list the old callback built per node is worked
// out here instead.
const scriptNodes = [
    "XY Plot",
    "Noise Control Script",
    "HighRes-Fix Script",
    "Tiled Upscaler Script"
];

for (const nodeType of scriptNodes) {
    comfy.defs.extend(nodeType, (b) => {
        b.addMenuItem({
            label: "🔄 Swap with...",
            order: 0,
            items: scriptNodes.filter(n => n !== nodeType).map(n => ({
                label: n,
                run: (node) => replaceNode(node, n)
            }))
        });
    });
}
