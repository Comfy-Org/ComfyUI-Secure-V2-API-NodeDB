import { comfy } from '/comfy/api/v2.js';

function addNode(name, nextTo, options) {
	options = { side: "left", select: true, shiftY: 0, shiftX: 0, ...(options || {}) };
	const node = comfy.graph.add(name);

	node.setPosition({
		x: options.side === "left" ? nextTo.getPosition().x - (node.getSize().width + options.offset): nextTo.getPosition().x + nextTo.getSize().width + options.offset,
		y: nextTo.getPosition().y + options.shiftY,
	});

	// Automatically connect nodes
	if (options.side === "left") {
		// New node on left: connect new node's first output to nextTo's first free input
		if (node.outputs.length > 0 && nextTo.inputs.length > 0) {
			for (let i = 0; i < nextTo.inputs.length; i++) {
				if (!nextTo.inputs.at(i).isConnected) {
					node.setPosition({ x: node.getPosition().x, y: node.getPosition().y + i * (node.getSize().height + 32) });
					node.outputs.at(0).connectTo(nextTo.id, { index: i });
					break;
				}
			}
		}
	} else {
		// New node on right: connect nextTo's first free output to new node's first free input
		if (nextTo.outputs.length > 0 && node.inputs.length > 0) {
			for (let o = 0; o < nextTo.outputs.length; o++) {
				if (!nextTo.outputs.at(o).isConnected) {
					// Offset vertically by slot index so multiple Set nodes don't overlap
					node.setPosition({ x: node.getPosition().x, y: node.getPosition().y + o * (node.getSize().height + 32) });
					for (let i = 0; i < node.inputs.length; i++) {
						if (!node.inputs.at(i).isConnected) {
							nextTo.outputs.at(o).connectTo(node.id, { index: i });
							break;
						}
					}
					break;
				}
			}
		}
	}

	if (options.select) {
		comfy.graph.select([node]);
	}
	return node;
}

// Expose addNode for use in setgetnodes.js
window.kjNodes = window.kjNodes || {};
window.kjNodes.addNode = addNode;

comfy.settings.declare({
	id: "KJNodes.helpPopup",
	name: "Help popups",
	category: ["KJNodes", "General", "Help popups"],
	tooltip: "Show help popups when hovering over KJNodes",
	defaultValue: true,
	type: "boolean",
});

const hasInputs = (node) => node.inputs.length > 0;

comfy.defs.extend(/.*/, (b) => {
	b.addMenuItem({
		label: "Add GetNode",
		when: hasInputs,
		run: (node) => { addNode("GetNode", node, { side: "left", offset: 30 }); }
	});
	b.addMenuItem({
		label: "Add SetNode",
		when: hasInputs,
		run: (node) => { addNode("SetNode", node, { side: "right", offset: 30 }); }
	});
	b.addMenuItem({
		label: "Add PreviewAsTextNode",
		when: hasInputs,
		run: (node) => { addNode("PreviewAny", node, { side: "right", offset: 30 }); }
	});
	b.addMenuItem({
		label: "Convert all outputs to Set/Get",
		when: hasInputs,
		run: (node) => {
			for (const n of window.kjNodes.snapshotSelectedNodes(node)) window.kjNodes.convertOutputsToSetGet(n);
		}
	});

	b.addMenuItem({
		label: "Recreate node",
		when: () => !!window.kjNodes?.recreateNode,
		items: [
			{ label: "Keep widget values", run: (node) => window.kjNodes.recreateNode(node, node.type, { resetValues: false }) },
			{ label: "Reset widget values", run: (node) => window.kjNodes.recreateNode(node, node.type, { resetValues: true }) },
		]
	});
});

// Previously injected "Add SetNode" / "Add GetNode" next to "Add Reroute" in the
// menu shown when a link is dropped on empty canvas, by replacing
// app.canvas.showConnectionMenu and — for the duration of that one call —
// swapping the global LiteGraph.ContextMenu constructor for a stand-in that
// spliced a string into the options array another component had already built.
//
// REFUSED, not a pending gap: replacing a live LGraphCanvas method.
// showConnectionMenu is the renderer's, and the renderer is ours to replace.
//
// REFUSED, not a pending gap: swapping a global constructor to edit somebody
// else's menu mid-construction. LiteGraph.ContextMenu is reassigned, its
// prototype re-pointed, and restored on the way out, so every menu opened in
// that window — core's, another pack's — is built by this pack's function. The
// file carries an `interceptActive` latch and a restore in two places precisely
// because the window is not actually bounded. A pack editing an options array
// it did not build cannot be given a published equivalent: the correct shape is
// contributing an entry, which is what addMenuItem above does.
//
// The capability is not refused and is not lost. "Add SetNode" and "Add GetNode"
// are contributed to every node's own context menu above, do the same work —
// create the node beside this one and wire it to the first free slot — and reach
// it in the same number of clicks from the node the user would have dragged
// from. What is lost is the placement, not the feature, so KJNodes.helpPopup
// stays and KJNodes.showSetGetInConnectionMenu is no longer declared: it gated
// nothing but the refused injection, and a setting that toggles nothing is worse
// than no setting.
//
// COSMETIC: the entries no longer appear in the dropped-link menu.
//
// No node in ComfyUI-KJNodes is made inoperable by this refusal.
