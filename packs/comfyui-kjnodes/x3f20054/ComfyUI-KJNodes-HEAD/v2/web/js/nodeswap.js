import { comfy } from '/comfy/api/v2.js';
import { typesCompatible } from "./utility.js";

let swapTargetNode = null;
let swapDraggedNode = null;
let swapDragStartPos = null;
let swapKeyDown = false;
let swapLastMoveTime = 0;
// The swap animation writes positions itself, and those come back through
// onNodeMoved — guard against acting on our own writes.
let swapping = false;

// No pointerup is published, so a gap this long is what separates one drag from
// the next.
const GESTURE_IDLE_MS = 250;

/** Find the topmost node whose bounding box overlaps with draggedNode */
function getOverlappingNode(draggedNode) {
	const pos = draggedNode.getPosition();
	const size = draggedNode.getSize();
	const ax = pos.x;
	const ay = pos.y;
	const aw = size.width || 100;
	const ah = size.height || 60;

	const nodes = comfy.graph.nodes();
	for (let i = nodes.length - 1; i >= 0; i--) {
		const n = nodes[i];
		if (n.id === draggedNode.id) continue;
		const nPos = n.getPosition();
		const nSize = n.getSize();
		const bx = nPos.x;
		const by = nPos.y;
		if (ax < bx + (nSize.width || 100) && ax + aw > bx &&
			ay < by + (nSize.height || 60) && ay + ah > by) {
			return n;
		}
	}
	return null;
}


// Marks the node a release would swap with. addBadge hands back its own remover,
// so the mark is put up and taken down instead of repainted every frame.
let removeSwapTargetBadge = null;

function setSwapTarget(node) {
	if (swapTargetNode && node && swapTargetNode.id === node.id) return;
	removeSwapTargetBadge?.();
	removeSwapTargetBadge = null;
	swapTargetNode = node;
	if (!node) return;
	const pinned = node.isPinned();
	removeSwapTargetBadge = node.addBadge({
		text: pinned ? "pinned" : "swap",
		color: "#000",
		bgColor: pinned ? "#ff5050" : "#64c8ff",
	});
}

function clearSwapState() {
	setSwapTarget(null);
	swapDraggedNode = null;
	swapDragStartPos = null;
}

function snapshotConnections(node) {
	const inputs = [];
	const inputSlots = node.inputs.all();
	for (let i = 0; i < inputSlots.length; i++) {
		const inp = inputSlots[i];
		const link = inp.link();
		if (!link) continue;
		inputs.push({
			slotIndex: i,
			type: inp.type,
			name: inp.name,
			originNodeId: link.sourceNodeId,
			originSlot: link.sourceIndex,
		});
	}

	const outputs = [];
	const outputSlots = node.outputs.all();
	for (let o = 0; o < outputSlots.length; o++) {
		const out = outputSlots[o];
		const targets = out.links()
			.map((link) => ({ targetNodeId: link.targetNodeId, targetSlot: link.targetIndex }));
		if (targets.length > 0) {
			outputs.push({ slotIndex: o, type: out.type, name: out.name, targets });
		}
	}

	return { inputs, outputs };
}

function disconnectAll(node) {
	const inputs = node.inputs.all();
	for (let i = inputs.length - 1; i >= 0; i--) {
		if (inputs[i].isConnected) inputs[i].disconnect();
	}
	const outputs = node.outputs.all();
	for (let o = outputs.length - 1; o >= 0; o--) {
		if (outputs[o].isConnected) outputs[o].disconnect();
	}
}

// Map each snapshot entry → a new-node slot. Name matches win first, then sameIndex,
// then first compatible. Each slot is claimed at most once so fallbacks can't stomp matches.
function resolveAssignments(snapshots, slots, isFree) {
	const assignments = new Map();
	if (!slots || !slots.length) return assignments;
	const used = new Set();

	for (const snap of snapshots) {
		if (!snap.name) continue;
		const nameLower = String(snap.name).toLowerCase();
		for (let s = 0; s < slots.length; s++) {
			if (used.has(s) || !isFree(s)) continue;
			const slotName = slots[s].name;
			if (slotName && String(slotName).toLowerCase() === nameLower &&
				typesCompatible(snap.type, slots[s].type)) {
				assignments.set(snap, s);
				used.add(s);
				break;
			}
		}
	}

	for (const snap of snapshots) {
		if (assignments.has(snap)) continue;
		const i = snap.slotIndex;
		if (i < slots.length && !used.has(i) && isFree(i) &&
			typesCompatible(snap.type, slots[i].type)) {
			assignments.set(snap, i);
			used.add(i);
			continue;
		}
		for (let s = 0; s < slots.length; s++) {
			if (used.has(s) || !isFree(s)) continue;
			if (typesCompatible(snap.type, slots[s].type)) {
				assignments.set(snap, s);
				used.add(s);
				break;
			}
		}
	}

	return assignments;
}

// Reconnect external connections from a snapshot onto newNode.
// moveLinksTo preserves link ids but only re-homes within one node's own outputs,
// so a swap between two nodes stays disconnect-and-reconnect. The original did the
// same (disconnectInput/disconnectOutput then connect), so the ids a swap allocates
// are the ids it always allocated and the saved workflow is unchanged by this port.
function reconnectExternal(snapshot, newNode, otherNodeId) {
	const newInputs = newNode.inputs.all();
	const inputAssignments = resolveAssignments(
		snapshot.inputs, newInputs,
		(s) => !newInputs[s].isConnected,
	);
	for (const inp of snapshot.inputs) {
		if (inp.originNodeId === otherNodeId) continue;
		if (!inputAssignments.has(inp)) continue;
		const originNode = comfy.graph.node(inp.originNodeId);
		const originOutput = originNode?.outputs.at(inp.originSlot);
		if (!originOutput) continue;
		originOutput.connectTo(newNode.id, { index: inputAssignments.get(inp) });
	}

	const newOutputs = newNode.outputs.all();
	const outputAssignments = resolveAssignments(
		snapshot.outputs, newOutputs,
		() => true,
	);
	for (const out of snapshot.outputs) {
		if (!outputAssignments.has(out)) continue;
		const bestSlot = outputAssignments.get(out);
		for (const tgt of out.targets) {
			if (tgt.targetNodeId === otherNodeId) continue;
			const targetNode = comfy.graph.node(tgt.targetNodeId);
			if (!targetNode) continue;
			newOutputs[bestSlot].connectTo(targetNode.id, { index: tgt.targetSlot });
		}
	}
}

// Reconnect links that were between the two swapped nodes in one direction.
// A→B becomes B→A, if slot types are compatible.
function reconnectInternalOneDirection(snap, fromNodeId, srcNode, dstNode) {
	const srcOutputs = srcNode.outputs.all();
	const dstInputs = dstNode.inputs.all();
	for (const out of snap.outputs) {
		for (const tgt of out.targets) {
			if (tgt.targetNodeId !== fromNodeId) continue;
			if (out.slotIndex >= srcOutputs.length) continue;
			if (tgt.targetSlot >= dstInputs.length) continue;
			if (!typesCompatible(srcOutputs[out.slotIndex].type, dstInputs[tgt.targetSlot].type)) continue;
			srcOutputs[out.slotIndex].connectTo(dstNode.id, { index: tgt.targetSlot });
		}
	}
}

// The swap animation is renderer-neutral: it moves the nodes over time and
// whichever renderer is active follows. A CSS-transition variant used to be
// selected by asking which renderer was running and reaching for the node's
// DOM element; neither is published, and the rAF path is correct under both.

function animateSwapCanvas(nodeA, fromA, toA, nodeB, fromB, toB, duration) {
	const start = performance.now();

	function ease(t) {
		return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
	}

	function frame(now) {
		const t = Math.min((now - start) / duration, 1);
		const e = ease(t);
		nodeA.setPosition({
			x: fromA[0] + (toA[0] - fromA[0]) * e,
			y: fromA[1] + (toA[1] - fromA[1]) * e,
		});
		nodeB.setPosition({
			x: fromB[0] + (toB[0] - fromB[0]) * e,
			y: fromB[1] + (toB[1] - fromB[1]) * e,
		});
		if (t < 1) requestAnimationFrame(frame);
		else swapping = false;
	}

	requestAnimationFrame(frame);
}

function executeNodeSwap(nodeA, nodeB, originalPosA) {
	const snapA = snapshotConnections(nodeA);
	const snapB = snapshotConnections(nodeB);

	const fromA = nodeA.getPosition();
	const fromB = nodeB.getPosition();
	const posA = originalPosA || [fromA.x, fromA.y];
	const posB = [fromB.x, fromB.y];

	disconnectAll(nodeA);
	disconnectAll(nodeB);

	reconnectExternal(snapA, nodeB, nodeA.id);
	reconnectExternal(snapB, nodeA, nodeB.id);

	reconnectInternalOneDirection(snapA, nodeB.id, nodeB, nodeA);
	reconnectInternalOneDirection(snapB, nodeA.id, nodeA, nodeB);

	swapping = true;
	animateSwapCanvas(nodeA, [fromA.x, fromA.y], posB,
		nodeB, [fromB.x, fromB.y], posA, 200);
}

comfy.settings.declare({
	id: "KJNodes.nodeSwapEnabled",
	name: "Enable node swap on drag",
	category: ["KJNodes", "Node Swap", "Enable"],
	tooltip: "Hold swap key (default: S, rebindable in Keybindings) and drag a node onto another to swap their positions and reconnect links",
	type: "boolean",
	defaultValue: true,
});

// A function label carries the toggle's state, which is what `active` showed here.
comfy.commands.register({
	id: "KJNodes.ToggleNodeSwap",
	label: () => comfy.settings.get("KJNodes.nodeSwapEnabled")
		? "Disable node swap on drag"
		: "Enable node swap on drag",
	run: () => {
		const cur = comfy.settings.get("KJNodes.nodeSwapEnabled");
		void comfy.settings.set("KJNodes.nodeSwapEnabled", !cur);
	},
});

comfy.commands.register({
	id: "KJNodes.NodeSwapMode",
	label: "Node swap mode (hold to activate)",
	keybinding: { key: "s" },
	scope: 'canvas',
	run: () => {
		swapKeyDown = true;
		// If already dragging a node, check for overlap immediately
		// (handles case where node is already on top of another when key is pressed)
		if (swapDraggedNode) {
			setSwapTarget(getOverlappingNode(swapDraggedNode));
		}
	},
});

// The command system handles keydown (sets swapKeyDown = true).
// Any keyup clears it since the user must hold the key.
document.addEventListener("keyup", () => {
	if (swapKeyDown) {
		swapKeyDown = false;
		setSwapTarget(null);
	}
});

comfy.onNodeMoved(({ node, position }) => {
	if (swapping) return;
	// The editor is already mid-gesture — dragging a link, resizing a node,
	// dragging a widget.
	if (comfy.isInteracting()) return;
	if (!comfy.settings.get("KJNodes.nodeSwapEnabled")) return;

	const now = performance.now();
	if (now - swapLastMoveTime > GESTURE_IDLE_MS) clearSwapState();
	swapLastMoveTime = now;

	if (!swapDraggedNode) {
		swapDraggedNode = node;
		// The old code captured pos at pointerdown; the first reported move is
		// the earliest position this API offers, so the swapped node lands a
		// pointer-tick short of where the drag actually began.
		swapDragStartPos = [position.x, position.y];
	}
	// Multi-node drags report every node they move; follow the first only.
	if (node.id !== swapDraggedNode.id) return;

	if (!swapKeyDown) {
		setSwapTarget(null);
		return;
	}

	setSwapTarget(getOverlappingNode(swapDraggedNode));
});

// Previously the swap target was marked by replacing lgCanvas.onDrawBackground and
// painting a pulsing, shadowed roundRect around the node, red if it was pinned.
//
// REFUSED, not a pending gap: painting into the host canvas's own background pass.
// onDrawBackground is the renderer's, it is winner-takes-all across every pack that
// claims it, and it is a method on the renderer Nodes 2.0 replaces. widgets.canvas
// is deliberately per node — a pack draws on what it owns.
//
// The capability is not refused and is not lost: the mark belongs on the node being
// marked, and addBadge is core's own per-node extension point, which both renderers
// draw. Pinned is still called out, because a pinned target refuses the swap and the
// user needs to know that before releasing.
//
// COSMETIC: a badge on the title bar rather than a pulsing outline around the node.

// Nodes 2.0 only: the legacy canvas renderer publishes no drag lifecycle, so
// onNodeDragEnd never fires there and the swap never commits under it.
comfy.onNodeDragEnd(() => {
	const targetNode = swapTargetNode;
	const draggedNode = swapDraggedNode;
	const startPos = swapDragStartPos;
	clearSwapState();

	if (!targetNode || !draggedNode || !swapKeyDown) return;

	if (!targetNode.isPinned() && !draggedNode.isPinned()) {
		executeNodeSwap(draggedNode, targetNode, startPos);
	}
});
