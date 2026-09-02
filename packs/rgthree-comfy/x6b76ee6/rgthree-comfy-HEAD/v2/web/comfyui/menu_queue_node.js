import { comfy } from '/comfy/api/v2.js';
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
// Adds "Queue Selected Output Nodes" to a node's context menu — run only the
// selected output nodes and whatever feeds them.
//
// COSMETIC: (8) an entry cannot be positioned among core's own items. The node half
//   spliced itself in by string-matching "Outputs" or "Align"; `b.addMenuItem` appends
//   after every core entry, so both entries are present and sit lower.
//
// The canvas-wide half — `LGraphCanvas.prototype.getCanvasMenuOptions`, so the two
// entries were also reachable by right-clicking empty canvas — is a command instead.
// That is the published action layer: it puts both in the command palette, lets the user
// bind a key to either, and is reachable with nothing under the pointer, which is the
// whole of what the canvas menu was giving them. `scope: 'canvas'` keeps a binding from
// firing while the user is typing in a widget.
//
// COSMETIC: the original greyed the entries out when nothing qualified; `when` hides
//   them instead, which is the published shape. A command is always listed and does
//   nothing when there is nothing to queue, as the greyed entry did.
function isOutputNode(node) {
    var _a;
    return node.getMode() !== "never" && ((_a = comfy.defs.get(node.type)) === null || _a === void 0 ? void 0 : _a.isOutputNode);
}
function isEnabled() {
    return CONFIG_SERVICE.getConfigValue("features.menu_queue_selected_nodes") !== false;
}
function getSelectedOutputNodes() {
    if (!isEnabled()) {
        return [];
    }
    return comfy.graph.selection().filter(isOutputNode);
}
// Never cached: membership is derived from what the rectangle overlaps right now,
// and a node dragged out of the group leaves it with no event.
//
// `graph.getGroupOnPos()` against rgthree's `lastCanvasMouseEvent` is
// `comfy.graph.pointerPosition()` plus a bounds test. The pointer sits over the
// open menu rather than the canvas by the time an entry runs, so the reading is
// still where the user right-clicked; the node stands in only before the first
// frame, when there is no canvas to measure against.
function getGroupOutputNodes(node) {
    if (!isEnabled()) {
        return [];
    }
    const pos = comfy.graph.pointerPosition() ?? node?.getPosition();
    if (!pos) {
        return [];
    }
    const group = comfy.graph.groups().find((g) => {
        const bounds = g.getBounds();
        return (pos.x >= bounds.x &&
            pos.x < bounds.x + bounds.width &&
            pos.y >= bounds.y &&
            pos.y < bounds.y + bounds.height);
    });
    return group ? group.nodes().filter(isOutputNode) : [];
}
function queueSelectedOutputNodes() {
    const nodes = getSelectedOutputNodes();
    if (!nodes.length) {
        return;
    }
    void comfy.queue.run({ nodes });
}
// `node` stands in for the pointer only before the first frame, when there is no canvas
// to measure against; from the command there is no node, and the pointer reading is the
// only one there ever was.
function queueGroupOutputNodes(node) {
    const nodes = getGroupOutputNodes(node);
    if (!nodes.length) {
        return;
    }
    void comfy.queue.run({ nodes });
}
comfy.commands.register({
    id: "rgthree.queueSelectedOutputNodes",
    label: "Queue Selected Output Nodes (rgthree)",
    scope: "canvas",
    run: queueSelectedOutputNodes,
});
comfy.commands.register({
    id: "rgthree.queueGroupOutputNodes",
    label: "Queue Group Output Nodes (rgthree)",
    scope: "canvas",
    run: () => queueGroupOutputNodes(undefined),
});
comfy.defs.extend(/./, (b) => {
    b.addMenuItem({
        label: "Queue Selected Output Nodes (rgthree)",
        when: () => getSelectedOutputNodes().length > 0,
        run: queueSelectedOutputNodes,
    });
    b.addMenuItem({
        label: "Queue Group Output Nodes (rgthree)",
        when: (node) => getGroupOutputNodes(node).length > 0,
        run: queueGroupOutputNodes,
    });
});
