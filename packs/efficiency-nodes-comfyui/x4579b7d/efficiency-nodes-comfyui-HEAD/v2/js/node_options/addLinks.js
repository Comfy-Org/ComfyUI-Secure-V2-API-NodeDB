import { comfy } from '/comfy/api/v2.js';
import { addNode } from "./common/utils.js";

function createKSamplerEntry(samplerType, subNodeType = null, isSDXL = false) {
    const samplerLabelMap = {
        "Eff": "KSampler (Efficient)",
        "Adv": "KSampler Adv. (Efficient)",
        "SDXL": "KSampler SDXL (Eff.)"
    };

    const subNodeLabelMap = {
        "XYPlot": "XY Plot",
        "NoiseControl": "Noise Control Script",
        "HiResFix": "HighRes-Fix Script",
        "TiledUpscale": "Tiled Upscaler Script"
    };

    const nicknameMap = {
        "KSampler (Efficient)": "KSampler",
        "KSampler Adv. (Efficient)": "KSampler(Adv)",
        "KSampler SDXL (Eff.)": "KSampler",
        "XY Plot": "XY Plot",
        "Noise Control Script": "NoiseControl",
        "HighRes-Fix Script": "HiResFix",
        "Tiled Upscaler Script": "TiledUpscale"
    };

    const kSamplerLabel = samplerLabelMap[samplerType];
    const subNodeLabel = subNodeLabelMap[subNodeType];

    const kSamplerNickname = nicknameMap[kSamplerLabel];
    const subNodeNickname = nicknameMap[subNodeLabel];

    const contentLabel = subNodeNickname ? `${kSamplerNickname} + ${subNodeNickname}` : kSamplerNickname;

    return {
        label: contentLabel,
        run: function(node) {
            const kSamplerNode = addNode(kSamplerLabel, node, { shiftX: node.getSize().width + 50 });

            // Standard connections for all samplers
            node.outputs.at(0).connectTo(kSamplerNode.id, { index: 0 });  // MODEL
            node.outputs.at(1).connectTo(kSamplerNode.id, { index: 1 });  // CONDITIONING+
            node.outputs.at(2).connectTo(kSamplerNode.id, { index: 2 });  // CONDITIONING-

            // Additional connections for non-SDXL
            if (!isSDXL) {
                node.outputs.at(3).connectTo(kSamplerNode.id, { index: 3 });  // LATENT
                node.outputs.at(4).connectTo(kSamplerNode.id, { index: 4 });  // VAE
            }

            if (subNodeLabel) {
                const subNode = addNode(subNodeLabel, node, { shiftX: 50, shiftY: node.getSize().height + 50 });
                const dependencyIndex = isSDXL ? 3 : 5;
                node.outputs.at(dependencyIndex).connectTo(subNode.id, { index: 0 });
                subNode.outputs.at(0).connectTo(kSamplerNode.id, { index: dependencyIndex });
            }
        },
    };
}

function createStackerNode(type) {
    const stackerLabelMap = {
        "LoRA": "LoRA Stacker",
        "ControlNet": "Control Net Stacker"
    };

    const contentLabel = stackerLabelMap[type];

    return {
        label: contentLabel,
        run: function(node) {
            const stackerNode = addNode(contentLabel, node);

            // Calculate the left shift based on the width of the new node
            const shiftX = -(stackerNode.getSize().width + 25);

            // Introduce a Y offset of 200 for ControlNet Stacker node
            const pos = stackerNode.getPosition();
            stackerNode.setPosition({
                x: pos.x + shiftX,
                y: pos.y + (type === "ControlNet" ? 300 : 0)
            });

            // Connect outputs to the Efficient Loader based on type
            if (type === "LoRA") {
                stackerNode.outputs.at(0).connectTo(node.id, { index: 0 });
            } else if (type === "ControlNet") {
                stackerNode.outputs.at(0).connectTo(node.id, { index: 1 });
            }
        },
    };
}

function createXYPlotNode(type) {
    const contentLabel = "XY Plot";

    return {
        label: contentLabel,
        run: function(node) {
            const xyPlotNode = addNode(contentLabel, node);

            // Center the X coordinate of the XY Plot node, and adjust the Y
            // position to place it below the loader node
            const centerXShift = (node.getSize().width - xyPlotNode.getSize().width) / 2;
            const pos = xyPlotNode.getPosition();
            xyPlotNode.setPosition({
                x: pos.x + centerXShift,
                y: pos.y + node.getSize().height + 60
            });

            // Depending on the node type, connect the appropriate output to the XY Plot node
            if (type === "Efficient") {
                node.outputs.at(6).connectTo(xyPlotNode.id, { index: 0 });
            } else if (type === "SDXL") {
                node.outputs.at(3).connectTo(xyPlotNode.id, { index: 0 });
            }
        },
    };
}

function getMenuValues(type) {
    const subNodeTypes = [null, "XYPlot", "NoiseControl", "HiResFix", "TiledUpscale"];
    const excludedSubNodeTypes = ["NoiseControl", "HiResFix", "TiledUpscale"];  // Nodes to exclude from the menu

    const menuValues = [];

    // Add the new node types to the menu first for the correct order
    menuValues.push(createStackerNode("LoRA"));
    menuValues.push(createStackerNode("ControlNet"));

    for (const subNodeType of subNodeTypes) {
        // Skip adding submenu items that are in the excludedSubNodeTypes array
        if (!excludedSubNodeTypes.includes(subNodeType)) {
            const menuEntry = createKSamplerEntry(type === "Efficient" ? "Eff" : "SDXL", subNodeType, type === "SDXL");
            menuValues.push(menuEntry);
        }
    }

    // Insert the standalone XY Plot option after the KSampler without any subNodeTypes and before any other KSamplers with subNodeTypes
    menuValues.splice(3, 0, createXYPlotNode(type));

    return menuValues;
}

// Extension Definition
// The entry builders no longer take the node: a submenu's items are fixed at
// registration and `run` is handed the node the menu was opened on, which is the
// only thing they used it for.
const linkTypes = {
    "Efficient Loader": "Efficient",
    "Eff. Loader SDXL": "SDXL"
};

for (const [nodeType, linkType] of Object.entries(linkTypes)) {
    comfy.defs.extend(nodeType, (b) => {
        b.addMenuItem({
            label: "⛓ Add link...",
            order: 1,
            items: getMenuValues(linkType)
        });
    });
}
