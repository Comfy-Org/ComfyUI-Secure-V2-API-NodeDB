import { comfy } from '/comfy/api/v2.js';
import { typesCompatible } from "./utility.js";

// Max age of the last keydown for it to count as the command's trigger.
// Beyond this, treat the command as menu-fired (no release tracking).
const KEYDOWN_MAX_AGE_MS = 100;

// No pointerup is published, so a gap this long is what separates one drag from
// the next.
const GESTURE_IDLE_MS = 250;

const state = {
	insertKeyDown: false,
	activationKey: null,
	draggedNode: null,
	insertTargetLink: null,
	lastScanTime: 0,
	lastMoveTime: 0,
};

let lastKeyDown = null;
let lastKeyDownTime = 0;

function bezierAt(p0, p1, p2, p3, t) {
	const u = 1 - t;
	const uu = u * u, uuu = uu * u;
	const tt = t * t, ttt = tt * t;
	return [
		uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0],
		uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1],
	];
}

// Horizontal control-point offset for the link bezier; must match what the
// renderer draws so the hit-test region matches the visible curve.
const bezierOffsetX = (from, to) => Math.max(Math.abs(to[0] - from[0]) * 0.5, 50);

// The renderer's own slot position, so it is right for collapsed nodes,
// widget-backed inputs and layouts other than the default vertical stack.
function slotPos(node, isInput, slotIdx) {
	const pos = node.getSlotPosition(isInput ? "input" : "output", slotIdx);
	return pos ? [pos.x, pos.y] : null;
}

function findLinkUnderNode(draggedNode) {
	// The node's rectangle, title bar included — the renderer's own answer.
	const bounds = draggedNode.getBounds();
	const nodeX = bounds.x;
	const nodeY = bounds.y;
	const nodeW = bounds.width;
	const nodeH = bounds.height;
	const nodeCx = nodeX + nodeW / 2;
	const nodeCy = nodeY + nodeH / 2;

	let bestLink = null;
	let bestDist = Infinity;

	for (const link of comfy.graph.links()) {
		if (link.sourceNodeId === draggedNode.id || link.targetNodeId === draggedNode.id) continue;

		const originNode = comfy.graph.node(link.sourceNodeId);
		const targetNode = comfy.graph.node(link.targetNodeId);
		if (!originNode || !targetNode) continue;

		// Reject on node bounds before resolving slot positions.
		const oPos = originNode.getPosition(), oSize = originNode.getSize();
		const tPos = targetNode.getPosition(), tSize = targetNode.getSize();
		const oW = oSize.width || 100, oH = oSize.height || 60;
		const tW = tSize.width || 100, tH = tSize.height || 60;
		const cMinX = Math.min(oPos.x, tPos.x);
		const cMaxX = Math.max(oPos.x + oW, tPos.x + tW);
		const cMinY = Math.min(oPos.y, tPos.y) - 50;
		const cMaxY = Math.max(oPos.y + oH, tPos.y + tH) + 50;
		if (cMaxX < nodeX || cMinX > nodeX + nodeW || cMaxY < nodeY || cMinY > nodeY + nodeH) continue;

		const outPos = slotPos(originNode, false, link.sourceIndex);
		const inPos = slotPos(targetNode, true, link.targetIndex);
		// A slot the renderer cannot place (removed mid-drag) is not a target.
		if (!outPos || !inPos) continue;

		const lMinX = Math.min(outPos[0], inPos[0]);
		const lMaxX = Math.max(outPos[0], inPos[0]);
		const lMinY = Math.min(outPos[1], inPos[1]) - 50; // bezier can sag
		const lMaxY = Math.max(outPos[1], inPos[1]) + 50;
		if (lMaxX < nodeX || lMinX > nodeX + nodeW || lMaxY < nodeY || lMinY > nodeY + nodeH) continue;

		const offsetX = bezierOffsetX(outPos, inPos);
		const p0 = outPos;
		const p1 = [outPos[0] + offsetX, outPos[1]];
		const p2 = [inPos[0] - offsetX, inPos[1]];
		const p3 = inPos;

		for (let i = 0; i <= 20; i++) {
			const pt = bezierAt(p0, p1, p2, p3, i / 20);
			if (pt[0] >= nodeX && pt[0] <= nodeX + nodeW && pt[1] >= nodeY && pt[1] <= nodeY + nodeH) {
				const d = Math.hypot(pt[0] - nodeCx, pt[1] - nodeCy);
				if (d < bestDist) {
					bestDist = d;
					bestLink = link;
				}
				break;
			}
		}
	}
	return bestLink;
}

function findInsertSlots(node, linkType) {
	const inputSlot = node.inputs.all().findIndex(i => !i.isConnected && typesCompatible(linkType, i.type));
	const outputSlot = node.outputs.all().findIndex(o => typesCompatible(linkType, o.type));
	if (inputSlot === -1 || outputSlot === -1) return null;
	return { inputSlot, outputSlot };
}

function executeNodeInsert(node, link) {
	const originNode = comfy.graph.node(link.sourceNodeId);
	const targetNode = comfy.graph.node(link.targetNodeId);
	if (!originNode || !targetNode) return;

	const slots = findInsertSlots(node, link.type);
	if (!slots) return;

	const originSlot = link.sourceIndex;
	const targetSlot = link.targetIndex;

	const originOutput = originNode.outputs.at(originSlot);
	const insertOutput = node.outputs.at(slots.outputSlot);
	if (!originOutput || !insertOutput) return;

	// The link may have gone (undo, another edit) since it was picked. The old
	// code caught that by watching its own `_dragging` flag on the live link.
	const targetInput = targetNode.inputs.at(targetSlot);
	if (targetInput?.link()?.id !== link.id) return;

	// moveLinksTo re-homes only within one node's own outputs, so splicing a
	// third node into a wire stays disconnect-and-reconnect, as it was before.
	targetInput.disconnect();
	originOutput.connectTo(node.id, { index: slots.inputSlot });
	insertOutput.connectTo(targetNode.id, { index: targetSlot });
}

// Previously the pending insertion was previewed by chaining lgCanvas.onDrawForeground
// and painting two animated dashed bezier segments in the link's type colour, driven by
// a requestAnimationFrame loop calling lgCanvas.setDirty(true, false); the link being
// replaced was hidden by writing `link._dragging = true` on the live LLink.
//
// REFUSED, not a pending gap: painting into the host canvas's own foreground pass, and
// asking it to repaint. onDrawForeground is the renderer's and is winner-takes-all
// across every pack that claims it; setDirty has no published equivalent by design,
// because handle writes invalidate on their own.
//
// REFUSED, not a pending gap: writing a private field on a core link object to change
// how the renderer draws it. `_dragging` is not the pack's field, not documented, and
// not a value any other reader expects a node pack to have set — which is why the
// original had to remember to `delete` it again on every exit path, including undo.
//
// The capability is not refused and is not lost: the point of the preview is telling
// the user that releasing now will splice this node into a wire. That belongs on the
// node being dragged, and addBadge is core's own per-node extension point, which both
// renderers draw. The link's type colour is kept — defs.typeColor is the published read
// of the same table the ghost sampled.
//
// COSMETIC: a badge on the dragged node rather than two animated ghost curves, and the
// link being replaced stays visible underneath instead of being hidden.

// Puts the "insert" mark up and takes it down, rather than repainting it per frame.
let removeInsertBadge = null;

function setInsertTarget(link) {
	if (state.insertTargetLink?.id === link?.id) return;
	removeInsertBadge?.();
	removeInsertBadge = null;
	state.insertTargetLink = link ?? null;
	if (!link || !state.draggedNode) return;
	removeInsertBadge = state.draggedNode.addBadge({
		text: "insert",
		color: "#000",
		bgColor: comfy.defs.typeColor(link.type),
	});
}

function clearState() {
	setInsertTarget(null);
	state.draggedNode = null;
}

comfy.settings.declare({
	id: "KJNodes.nodeInsertMode",
	name: "Node insert activation",
	category: ["KJNodes", "Node Insert", "Activation mode"],
	tooltip: "Always: dragging a compatible node onto a link previews insertion. Hotkey: only while the hotkey (default: D) is held. Disabled: feature off.",
	type: "combo",
	defaultValue: "hotkey",
	options: ["always", "hotkey", "disabled"],
});

// COSMETIC: `active: () => state.insertKeyDown` rendered a toggle indicator on the
// entry. CommandDef has no `active`, but its label may be a function, so the state is
// still shown — as words rather than as a check.
comfy.commands.register({
	id: "KJNodes.NodeInsertMode",
	label: () => state.insertKeyDown
		? "Node insert mode (holding)"
		: "Node insert mode (hold to activate)",
	// Default only — release detection captures the actually-triggering
	// key at command-fire time, so user rebinds work.
	keybinding: { key: "d" },
	scope: 'canvas',
	run: () => {
		state.insertKeyDown = true;
		// Snapshot the key that triggered this so any rebind works.
		state.activationKey = (performance.now() - lastKeyDownTime < KEYDOWN_MAX_AGE_MS)
			? lastKeyDown
			: null;
		if (state.draggedNode) {
			const link = findLinkUnderNode(state.draggedNode);
			if (link && findInsertSlots(state.draggedNode, link.type)) {
				setInsertTarget(link);
			}
		}
	},
});

// Capture phase so `lastKeyDown` is set before ComfyUI fires the command.
document.addEventListener("keydown", (e) => {
	if (e.repeat) return;
	lastKeyDown = e.key?.toLowerCase() ?? null;
	lastKeyDownTime = performance.now();
}, true);

document.addEventListener("keyup", (e) => {
	const key = e.key?.toLowerCase() ?? null;
	// Released key can't be a future trigger — invalidate so a stale
	// keydown can't be picked up by a later menu activation.
	if (key && key === lastKeyDown) lastKeyDownTime = 0;

	if (!state.insertKeyDown) return;
	// No activation key (menu-fired) → blur/pointercancel will clean up.
	if (!state.activationKey || key !== state.activationKey) return;
	state.insertKeyDown = false;
	state.activationKey = null;
	setInsertTarget(null);
});

// Releases outside the window never reach our keyup listener, so without these
// the hotkey state can stick.
const dropTransient = () => {
	state.insertKeyDown = false;
	state.activationKey = null;
	clearState();
};
window.addEventListener("blur", dropTransient);
document.addEventListener("visibilitychange", () => {
	if (document.hidden) dropTransient();
});
document.addEventListener("pointercancel", dropTransient, true);

comfy.onNodeMoved(({ node }) => {
	// The editor is already mid-gesture — dragging a link, resizing a node,
	// dragging a widget. This also covers the widget drags that used to reach
	// this handler as bare document pointermoves.
	if (comfy.isInteracting()) return;

	const mode = comfy.settings.get("KJNodes.nodeInsertMode") ?? "always";
	if (mode === "disabled") return;

	const now = performance.now();
	if (now - state.lastMoveTime > GESTURE_IDLE_MS) clearState();
	state.lastMoveTime = now;
	// Multi-node drags report every node they move; follow the first only.
	state.draggedNode ??= node;
	if (node.id !== state.draggedNode.id) return;

	const active = mode === "always" || state.insertKeyDown;
	if (!active) {
		setInsertTarget(null);
		return;
	}

	// Multi-node drags move several nodes together — inserting one of
	// them into a link is almost never what the user wants.
	if (comfy.graph.selection().length > 1) {
		setInsertTarget(null);
		return;
	}

	const nodeCount = comfy.graph.nodes().length;
	const throttle = nodeCount > 200 ? 50 : nodeCount > 100 ? 32 : 16;
	if (now - state.lastScanTime < throttle) return;
	state.lastScanTime = now;

	const link = findLinkUnderNode(state.draggedNode);
	const slots = link ? findInsertSlots(state.draggedNode, link.type) : null;
	setInsertTarget(slots ? link : null);
});

// Nodes 2.0 only: the legacy canvas renderer publishes no drag lifecycle, so
// onNodeDragEnd never fires there and the insert never commits under it.
comfy.onNodeDragEnd(() => {
	const link = state.insertTargetLink;
	const node = state.draggedNode;
	clearState();

	if (link && node && !node.isPinned()) {
		executeNodeInsert(node, link);
	}
});
