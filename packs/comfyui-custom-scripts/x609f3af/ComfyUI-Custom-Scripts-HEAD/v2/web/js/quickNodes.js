import { comfy } from '/comfy/api/v2.js';

// Adds a bunch of context menu entries for quickly adding common steps

function outputOf(node, slot) {
	const output = node?.outputs.at(slot);
	if (!output) {
		throw new Error(`[pysssss 🐍] no output slot ${slot} on the node to connect from`);
	}
	return output;
}

function connect(fromNode, fromSlot, toNode, toSlot) {
	return outputOf(fromNode, fromSlot).connectTo(typeof toNode === "string" ? toNode : toNode.id, {
		index: toSlot,
	});
}

function getOrAddVAELoader(node) {
	let vaeNode = comfy.graph.nodesOfType("VAELoader")[0];
	if (!vaeNode) {
		vaeNode = addNode("VAELoader", node);
	}
	return vaeNode;
}

function addNode(name, nextTo, options) {
	options = { select: true, shiftY: 0, before: false, ...(options || {}) };
	const node = comfy.graph.add(name);
	const nextToPos = nextTo.getPosition();
	node.setPosition({
		x: options.before ? nextToPos.x - node.getSize().width - 30 : nextToPos.x + nextTo.getSize().width + 30,
		y: nextToPos.y + options.shiftY,
	});
	if (options.select) comfy.graph.select([node]);
	return node;
}

comfy.defs.extend(
	(def) => def.inputs.some((input) => input.type === "VAE"),
	(b) => {
		const i = b.def.inputs.findIndex((input) => input.type === "VAE");
		b.addMenuItem({
			label: "Use VAE",
			run(node) {
				connect(getOrAddVAELoader(node), 0, node, i);
			},
		});
	}
);

comfy.defs.extend("KSampler", (b) => {
	b.addMenuItem({
		label: "Add Blank Input",
		run(node) {
			const imageNode = addNode("EmptyLatentImage", node, { before: true });
			connect(imageNode, 0, node, 3);
		},
	});
	b.addMenuItem({
		label: "Add Hi-res Fix",
		run(node) {
			const upscaleNode = addNode("LatentUpscale", node);
			connect(node, 0, upscaleNode, 0);

			const sampleNode = addNode("KSampler", upscaleNode);

			for (let i = 0; i < 3; i++) {
				const l = node.inputs.at(i)?.link();
				if (l) {
					connect(comfy.graph.node(l.sourceNodeId), l.sourceIndex, sampleNode, i);
				}
			}

			connect(upscaleNode, 0, sampleNode, 3);
		},
	});
	b.addMenuItem({
		label: "Add 2nd Pass",
		run(node) {
			const upscaleNode = addNode("LatentUpscale", node);
			connect(node, 0, upscaleNode, 0);

			const ckptNode = addNode("CheckpointLoaderSimple", node);
			const sampleNode = addNode("KSampler", ckptNode);

			const positiveLink = node.inputs.at(1)?.link();
			const negativeLink = node.inputs.at(2)?.link();
			const positiveNode = positiveLink
				? comfy.graph.duplicate(positiveLink.sourceNodeId)
				: addNode("CLIPTextEncode");
			const negativeNode = negativeLink
				? comfy.graph.duplicate(negativeLink.sourceNodeId)
				: addNode("CLIPTextEncode");

			connect(ckptNode, 0, sampleNode, 0);
			connect(ckptNode, 1, positiveNode, 0);
			connect(ckptNode, 1, negativeNode, 0);
			connect(positiveNode, 0, sampleNode, 1);
			connect(negativeNode, 0, sampleNode, 2);
			connect(upscaleNode, 0, sampleNode, 3);
		},
	});
	b.addMenuItem({
		label: "Add Save Image",
		run(node) {
			const decodeNode = addNode("VAEDecode", node);
			connect(node, 0, decodeNode, 0);

			connect(getOrAddVAELoader(decodeNode), 0, decodeNode, 1);

			const saveNode = addNode("SaveImage", decodeNode);
			connect(decodeNode, 0, saveNode, 0);
		},
	});
});

comfy.defs.extend("CheckpointLoaderSimple", (b) => {
	b.addMenuItem({
		label: "Add Clip Skip",
		run(node) {
			const clipSkipNode = addNode("CLIPSetLastLayer", node);
			const clipOutput = outputOf(node, 1);
			const clipLinks = clipOutput.links();

			clipOutput.disconnect();
			connect(node, 1, clipSkipNode, 0);

			for (const clipLink of clipLinks) {
				connect(clipSkipNode, 0, clipLink.targetNodeId, clipLink.targetIndex);
			}
		},
	});
});

comfy.defs.extend(
	["CheckpointLoaderSimple", "CheckpointLoader", "CheckpointLoader|pysssss", "LoraLoader", "LoraLoader|pysssss"],
	(b) => {
		function addLora(node, type) {
			const loraNode = addNode(type, node);

			const modelOutput = outputOf(node, 0);
			const clipOutput = outputOf(node, 1);
			const modelLinks = modelOutput.links();
			const clipLinks = clipOutput.links();

			modelOutput.disconnect();
			clipOutput.disconnect();

			connect(node, 0, loraNode, 0);
			connect(node, 1, loraNode, 1);

			for (const modelLink of modelLinks) {
				connect(loraNode, 0, modelLink.targetNodeId, modelLink.targetIndex);
			}

			for (const clipLink of clipLinks) {
				connect(loraNode, 1, clipLink.targetNodeId, clipLink.targetIndex);
			}
		}
		b.addMenuItem({
			label: "Add LoRA",
			run: (node) => addLora(node, "LoraLoader"),
		});
		b.addMenuItem({
			label: "Add 🐍 LoRA",
			run: (node) => addLora(node, "LoraLoader|pysssss"),
		});
		b.addMenuItem({
			label: "Add Prompts",
			run(node) {
				const positiveNode = addNode("CLIPTextEncode", node);
				const negativeNode = addNode("CLIPTextEncode", node, { shiftY: positiveNode.getSize().height + 30 });

				connect(node, 1, positiveNode, 0);
				connect(node, 1, negativeNode, 0);
			},
		});
	}
);
