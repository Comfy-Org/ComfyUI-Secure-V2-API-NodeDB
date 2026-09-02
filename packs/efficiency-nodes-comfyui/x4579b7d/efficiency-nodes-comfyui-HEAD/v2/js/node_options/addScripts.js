import { comfy } from '/comfy/api/v2.js';
import { addNode } from "./common/utils.js";

const connectionMap = {
    "KSampler (Efficient)": ["input", 5],
    "KSampler Adv. (Efficient)": ["input", 5],
    "KSampler SDXL (Eff.)": ["input", 3],
    "XY Plot": ["output", 0],
    "Noise Control Script": ["input & output", 0],
    "HighRes-Fix Script": ["input & output", 0],
    "Tiled Upscaler Script": ["input & output", 0]
};

function addAndConnectScriptNode(scriptType, selectedNode) {
    const selectedNodeType = connectionMap[selectedNode.type];
    const newNodeType = connectionMap[scriptType];

    // 1. Create the new node without position adjustments
    const newNode = addNode(scriptType, selectedNode, { shiftX: 0, shiftY: 0 });

    // 2. Adjust position of the new node based on conditions
    const newNodePos = newNode.getPosition();
    if (newNodeType[0].includes("input") && selectedNodeType[0].includes("output")) {
        newNode.setPosition({ x: newNodePos.x + selectedNode.getSize().width + 50, y: newNodePos.y });
    } else if (newNodeType[0].includes("output") && selectedNodeType[0].includes("input")) {
        newNode.setPosition({ x: newNodePos.x - (newNode.getSize().width + 50), y: newNodePos.y });
    }

    // 3. Logic for connecting the nodes
    switch (selectedNodeType[0]) {
        case "output":
            if (newNodeType[0] === "input & output") {
                // For every node that was previously connected to the selectedNode's output
                const selectedOutput = selectedNode.outputs.at(selectedNodeType[1]);
                const connectedNodes = selectedOutput.targets().map(target => comfy.graph.node(target.nodeId)).filter(Boolean);
                if (connectedNodes.length) {
                    for (let connectedNode of connectedNodes) {
                        // Disconnect the node from selectedNode's output
                        selectedOutput.disconnect();
                        // Connect the newNode's output to the previously connected node,
                        // using the appropriate slot based on the type of the connectedNode
                        const targetSlot = (connectedNode.type in connectionMap) ? connectionMap[connectedNode.type][1] : 0;
                        newNode.outputs.at(0).connectTo(connectedNode.id, { index: targetSlot });
                    }
                }
                // Connect selectedNode's output to newNode's input
                selectedOutput.connectTo(newNode.id, { index: newNodeType[1] });
            }
            break;

        case "input":
            if (newNodeType[0] === "output") {
                newNode.outputs.at(0).connectTo(selectedNode.id, { index: selectedNodeType[1] });
            } else if (newNodeType[0] === "input & output") {
                const ogInput = selectedNode.inputs.at(selectedNodeType[1]).source();
                const ogInputNode = ogInput ? comfy.graph.node(ogInput.nodeId) : undefined;
                if (ogInputNode) {
                    ogInputNode.outputs.at(0).connectTo(newNode.id, { index: 0 });
                }
                newNode.outputs.at(0).connectTo(selectedNode.id, { index: selectedNodeType[1] });
            }
            break;
        case "input & output":
            if (newNodeType[0] === "output") {
                newNode.outputs.at(0).connectTo(selectedNode.id, { index: 0 });
            } else if (newNodeType[0] === "input & output") {

                const selectedOutput = selectedNode.outputs.at(0);
                const connectedNodes = selectedOutput.targets().map(target => comfy.graph.node(target.nodeId)).filter(Boolean);
                if (connectedNodes.length) {
                    for (let connectedNode of connectedNodes) {
                        selectedOutput.disconnect();
                        newNode.outputs.at(0).connectTo(connectedNode.id, { index: connectedNode.type in connectionMap ? connectionMap[connectedNode.type][1] : 0 });
                    }
                }
                // Connect selectedNode's output to newNode's input
                selectedNode.outputs.at(selectedNodeType[1]).connectTo(newNode.id, { index: newNodeType[1] });
            }
            break;
    }

    return newNode;
}

function createScriptEntry(scriptType) {
    return {
        label: scriptType,
        run: function(node) {
            addAndConnectScriptNode(scriptType, node);
        },
    };
}

function getScriptOptions(nodeType) {
    const allScriptTypes = [
        "XY Plot",
        "Noise Control Script",
        "HighRes-Fix Script",
        "Tiled Upscaler Script"
    ];

    // Filter script types based on node type
    const scriptTypes = allScriptTypes.filter(scriptType => {
        const scriptBehavior = connectionMap[scriptType][0];

        if (connectionMap[nodeType][0] === "output") {
            return scriptBehavior.includes("input");  // Includes nodes that are "input" or "input & output"
        } else {
            return true;
        }
    });

    return scriptTypes.map(script => createScriptEntry(script));
}

// Extension Definition
// The filter only ever depended on the node's TYPE, which a per-type
// registration knows outright — a submenu's items are fixed at registration.
for (const nodeType of Object.keys(connectionMap)) {
    comfy.defs.extend(nodeType, (b) => {
        b.addMenuItem({
            label: "📜 Add script...",
            order: 2,
            items: getScriptOptions(nodeType)
        });
    });
}
