import { comfy } from '/comfy/api/v2.js';

const state = {
	lastDelta: [0, 0],
	lastPos: null,
	reversalTimes: [],
	lastScanTime: 0,
	lastMoveTime: 0,
	trackedNodeId: null,
	triggered: false,
};

// Cached from each setting's onChange to avoid per-move lookups.
const settings = {
	enabled: true,
	reversalsNeeded: 3,
};

// Movement arrives once per layout write; sampling at the old pointermove rate
// keeps the reversal thresholds calibrated.
const SAMPLE_INTERVAL_MS = 16;
// No pointerup is published, so a gap this long is what separates one drag from
// the next.
const GESTURE_IDLE_MS = 250;

function nodeHasLinks(node) {
	if (node.inputs.all().some(i => i.isConnected)) return true;
	if (node.outputs.all().some(o => o.isConnected)) return true;
	return false;
}

// Same end result as deleting all selected nodes except internal links between selected nodes are preserved.
function executeShakeBreak(draggedNodes) {
	if (draggedNodes.length === 0) return;

	const selectedIds = new Set(draggedNodes.map(n => n.id));

	// One undo step for the shake, not one per link rewired.
	comfy.graph.batch(() => {
		for (const node of draggedNodes) bypassExternal(node, selectedIds);
		for (const node of draggedNodes) disconnectExternal(node, selectedIds);
	});

	state.triggered = true;
	state.reversalTimes = [];
}

function bypassExternal(node, selectedIds) {
	const inputs = node.inputs.all();
	for (let i = 0; i < inputs.length; i++) {
		const inLink = inputs[i].link();
		if (!inLink || selectedIds.has(inLink.sourceNodeId)) continue;
		const inNode = comfy.graph.node(inLink.sourceNodeId);
		if (!inNode) continue;

		traceAndBypass(node, i, inNode, inLink, selectedIds, new Set());
	}
}

// At each step, follows output[slot] (matching the input slot we arrived on).
// Internal targets recurse; external targets get a direct upstream → target link.
function traceAndBypass(currentNode, slot, inNode, inLink, selectedIds, visited) {
	const key = `${currentNode.id}:${slot}`;
	if (visited.has(key)) return;
	visited.add(key);

	// links() is already a frozen snapshot, so connecting while iterating is safe.
	const outLinks = currentNode.outputs.at(slot)?.links() ?? [];
	if (!outLinks.length) return;

	for (const outLink of outLinks) {
		if (selectedIds.has(outLink.targetNodeId)) {
			const nextNode = comfy.graph.node(outLink.targetNodeId);
			if (nextNode) {
				traceAndBypass(nextNode, outLink.targetIndex, inNode, inLink, selectedIds, visited);
			}
		} else {
			const outNode = comfy.graph.node(outLink.targetNodeId);
			const upstream = inNode.outputs.at(inLink.sourceIndex);
			if (outNode && upstream) {
				// DROPPED: the old call passed inLink.parentId as a fourth argument so
				// the bypass re-threaded the reroute points the incoming link ran
				// through. connectTo takes no reroute parent, and a reroute's identity
				// is not published, so a bypass across a rerouted link now lands as a
				// straight one. The connection itself is unchanged.
				upstream.connectTo(outNode.id, { index: outLink.targetIndex });
			}
		}
	}
}

function disconnectExternal(node, selectedIds) {
	for (const input of node.inputs.all()) {
		const link = input.link();
		if (!link || selectedIds.has(link.sourceNodeId)) continue;
		// DROPPED: disconnectInput(i, true) kept the link's reroute points in place
		// for whatever was wired next. disconnect() takes no such flag, so a shake
		// takes the reroutes with the links it breaks.
		input.disconnect();
	}
	for (const output of node.outputs.all()) {
		for (const link of output.links()) {
			if (selectedIds.has(link.targetNodeId)) continue;
			const targetNode = comfy.graph.node(link.targetNodeId);
			if (targetNode) targetNode.inputs.at(link.targetIndex).disconnect();
		}
	}
}

// The zoom factor is not published on its own: getScreenRect() already accounts
// for it, so the ratio against the same node's graph-space bounds is the scale.
function screenScale(node) {
	const rect = node.getScreenRect();
	const bounds = node.getBounds();
	if (!rect || !bounds?.width) return 1;
	return rect.width / bounds.width;
}

function clearState() {
	state.lastDelta = [0, 0];
	state.lastPos = null;
	state.reversalTimes = [];
	state.lastScanTime = 0;
	state.trackedNodeId = null;
	state.triggered = false;
}

comfy.settings.declare({
	id: "KJNodes.shakeToDisconnect",
	name: "Enable shake to disconnect",
	category: ["KJNodes", "Shake to Disconnect", "Enabled"],
	tooltip: "Shake a selected node back and forth quickly to remove its links. Pass-through bypass is applied (same as deleting the node); when multiple nodes are selected, links between them are preserved and bypass propagates through the chain.",
	type: "boolean",
	defaultValue: false,
	onChange: (v) => { settings.enabled = !!v; },
});

comfy.settings.declare({
	id: "KJNodes.shakeReversals",
	name: "Reversals required",
	category: ["KJNodes", "Shake to Disconnect", "Reversals required"],
	tooltip: "Number of back-and-forth direction reversals needed to trigger disconnect. Lower = more sensitive (triggers from a small wiggle), higher = needs a more deliberate shake.",
	type: "slider",
	defaultValue: 3,
	attrs: { min: 2, max: 6, step: 1 },
	onChange: (v) => { settings.reversalsNeeded = Number(v) || 3; },
});

comfy.onNodeMoved(({ node, position }) => {
	if (!settings.enabled) return;
	// The editor is already mid-gesture — dragging a link, resizing a node,
	// dragging a widget.
	if (comfy.isInteracting()) return;

	const now = performance.now();
	if (now - state.lastMoveTime > GESTURE_IDLE_MS) clearState();
	state.lastMoveTime = now;

	// Multi-node drags report every node they move; follow the first, as the
	// old code followed selectedItems[0].
	state.trackedNodeId ??= node.id;
	if (node.id !== state.trackedNodeId) return;
	if (state.triggered) return;

	if (now - state.lastScanTime < SAMPLE_INTERVAL_MS) return;
	state.lastScanTime = now;

	// Top-left, not center: center shifts during resize, this only moves on drag.
	const curPos = [position.x, position.y];
	if (state.lastPos) {
		// Thresholds are in screen-pixels; deltas are in graph-coords, so scale.
		const scale = screenScale(node);
		const sdx = (curPos[0] - state.lastPos[0]) * scale;
		const sdy = (curPos[1] - state.lastPos[1]) * scale;
		const dot = sdx * state.lastDelta[0] + sdy * state.lastDelta[1];
		const magnitude = Math.sqrt(sdx * sdx + sdy * sdy);
		if (dot < 0 && magnitude > 5) state.reversalTimes.push(now);
		if (magnitude > 2) state.lastDelta = [sdx, sdy];
	}
	state.lastPos = curPos;
	const cutoff = now - 600;
	while (state.reversalTimes.length && state.reversalTimes[0] < cutoff) state.reversalTimes.shift();

	if (state.reversalTimes.length < settings.reversalsNeeded) return;

	const draggedNodes = comfy.graph.selection();
	if (draggedNodes.some(nodeHasLinks)) executeShakeBreak(draggedNodes);
});
