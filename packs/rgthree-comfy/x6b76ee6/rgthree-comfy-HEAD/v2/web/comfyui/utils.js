import { comfy } from '/comfy/api/v2.js';
import { graphOf } from "./base_any_input_connected_node.js";

// MOST OF THE OLD TOOLKIT WAS DELIBERATELY NOT RESTORED — 748 lines in, two exports out.
//
// The pack's shared graph/menu/geometry toolkit, imported by 28 of its 48 files.
// Its renderer geometry and its prototype patches have no destination and are
// listed below. Its link walking does, and the type walk in this file
// is that half converted — the routine that resolves what a `*` slot really carries
// by following its links until it meets a concrete type. Any Switch and Dynamic
// Context both need that answer, so it is shared from here. While this file exported
// nothing its helpers were being copied into consumers instead, and the copies had
// already drifted.
//
// `matchLocalSlotsToServer` is converted below. The marker it carried — "no published
// way to insert or permute a slot, and none at all for inputs" — named a destination
// that already existed: `SlotCollection.reorder(names)` permutes and re-points every
// affected link in one batch, and `add`/`remove` are on the same collection for inputs
// and outputs alike.
//
// REFUSED, not a gap: deciding where the renderer draws a slot.
//   `addConnectionLayoutSupport` / `getConnectionPosForLayout` /
//   `setConnectionsLayout` / `setConnectionsCollapse` are the pack's
//   "Connections Layout" feature, and they work by patching `getConnectionPos`,
//   `getInputPos` and `getOutputPos` on a node class and recomputing socket
//   positions from `LiteGraph.NODE_SLOT_HEIGHT`, `NODE_TITLE_HEIGHT` and
//   `NODE_COLLAPSED_WIDTH`. Where a socket sits, how tall a slot row is and how wide
//   a collapsed node draws are the renderer's, and the renderer is ours to replace —
//   a pack that hardcodes today's layout constants breaks on the day we change them,
//   silently and for its users rather than for its author. `node.getSlotPosition()`
//   *reads* where the renderer put a slot, which is what a pack anchoring something
//   to a socket actually needs; choosing the position is not published and is not
//   waiting on anything.
//   Two riders go with it. `toggleConnectionLabel` blanks a slot's label by writing
//   `cxn.label = " "` from inside that position callback — a per-frame write to
//   serialized state, which `slot.modify({label})` replaces for any pack that wants
//   the effect on its own terms. The disabled-slot recolouring is also inside the
//   callback: writing the grey is `slot.modify({color, colorWhenUnconnected})`, but
//   restoring it is not, because the routine stashes `cxn.color_on` in `_color_on_org`
//   first and nothing published reads a slot's colour back — `SlotSnapshot` is
//   `{id,index,name,type,label,isConnected}`.
// COSMETIC: (8) an entry cannot be positioned among *core's* menu items.
//   `addMenuItem` / `addMenuItemOnExtraMenuOptions` patch `getExtraMenuOptions` and
//   splice an entry in by string-matching an anchor ("Shape", "Properties Panel").
//   `b.addMenuItem` covers the submenu and the callback-computed label, and `order`
//   sequences a pack's own entries; every pack entry is appended after core's, so each
//   entry is present and only its neighbourhood differs. `addHelpMenuItem`
//   ("🛟 Node Help") is `helpMenuItem` in base_node.js.
// DROPPED: `getLinkById`, `getOriginNodeByLink` and `findFromNodeForSubgraph`. The node
//   half of this family is published and is used: `getNodeById` is
//   `[comfy.graph, ...comfy.graph.subgraphs()]` searched in turn,
//   `findSomethingInAllSubgraphs` is that same iteration (services/bookmarks_services.js
//   does exactly it), and `reduceNodesDepthFirst` resolves a subgraph node through its
//   `type`, which is its definition's id. The three above are the half that is not: a
//   SubgraphHandle exposes `nodes()`/`node()` only, so there is no `links()` to look a
//   link id up in, and no way back from a definition to the node that places it.
//   Neither has a caller left — `findFromNodeForSubgraph`'s only one was Bookmark's jump
//   into a subgraph, which is stated as a LIMITATION in bookmark.js, and nothing calls
//   `getLinkById` at all once the link table stops being addressed by id.
// NO LONGER A GAP: `comfy.defs.isTypeCompatible` publishes the host's wildcard
//   and union rules. The old wrapper has no converted caller, so dead code is
//   not restored merely because its destination now exists.
// REFUSED, not a gap: the file also *replaces* `LiteGraph.isValidConnection`
//   globally so that a COMBO may connect to a comma-joined type list. Replacing
//   core connection validation for every pack is deliberately not expressible, so
//   this is not waiting on anything.
// REFUSED, not a gap: (26) `getNodeByIdFromApiPrompt` / `getFullNodeIdFromApiPrompt`
//   read a built prompt handed to them by the queue interception in rgthree.js.
//   Reading the built prompt is not published and will not be.
// NO LONGER A GAP, and deliberately not restored: `getFullColor` resolved
//   ComfyUI's named colours through `LGraphCanvas.node_colors[name]`, and
//   `comfy.defs.nodeColor(name)` publishes that now. It is not brought back
//   because nothing calls it — no caller in `web/` or in the pack's own
//   `src_web/` sources, only the export. Fast Groups Muter had its own copy of
//   the same six lines and that one, which is reachable, is converted.
// NO LONGER A GAP: `replaceNode` is `comfy.graph.replace(id, type)`. It carries
//   position, a title the user chose, colour, mode, declared properties and
//   widget values, sizes the replacement to whichever of the two is larger, and
//   re-makes every link by slot name in one undo step. Link ids are reallocated,
//   exactly as this routine's were — it also rebuilt every link on a freshly
//   created node. Used by the Context ⇄ Context Big menu items (converted) and by
//   "Convert selected Reroutes".
//
// `waitForCanvas` / `waitForGraph` are no longer a gap: they polled `app.canvas`
// and `app.graph` because nothing said when the app was up, and `comfy.onReady()`
// is that signal. Every caller here is punted for other reasons, so the poll is
// simply gone rather than converted.
//
// `getGroupNodes(group)` is no longer a gap: it is `group.nodes()`, which the group
// API recomputes on every call. Its callers are converted in place (see
// fast_groups_muter.js, menu_queue_node.js) rather than through this file.
//
// `IoDirection`, `PassThroughFollowing`, `shouldPassThrough` and the
// `getConnected*Nodes*` family walk the link table through reroute/collector
// chains. Those are converted, but in base_any_input_connected_node.js: every
// caller is a node that file already assembles, so the walk followed its callers
// rather than staying here.

// The walk resolves peers through `comfy.graph`, which addresses the graph on
// screen — the same scope the original had, where `getTypeFromSlot` read
// `app.canvas.getCurrentGraph()`. A link crossing a subgraph boundary was not
// followed before and is not followed now, so this is not a loss.
function typeOfSlot(slot) {
    return { type: slot.type, label: slot.label, name: slot.name };
}
/** The node and slot at the other end of each of this slot's links. */
function peersOf(node, slot, isOutput) {
    const graph = graphOf(node);
    if (isOutput) {
        const peers = [];
        for (const link of slot.links()) {
            const peerNode = graph.node(link.targetNodeId);
            const peerSlot = peerNode && peerNode.inputs.at(link.targetIndex);
            if (peerNode && peerSlot)
                peers.push({ node: peerNode, slot: peerSlot });
        }
        return peers;
    }
    const link = slot.link();
    if (!link)
        return [];
    const peerNode = graph.node(link.sourceNodeId);
    const peerSlot = peerNode && peerNode.outputs.at(link.sourceIndex);
    return peerNode && peerSlot ? [{ node: peerNode, slot: peerSlot }] : [];
}
function getTypeFromSlot(node, slot, isOutput, skipSelf = false) {
    if (!skipSelf && slot.type && slot.type !== "*") {
        return typeOfSlot(slot);
    }
    for (const peer of peersOf(node, slot, isOutput)) {
        if (peer.slot.type && peer.slot.type !== "*") {
            return typeOfSlot(peer.slot);
        }
        if (peer.slot.type === "*") {
            return followConnectionUntilType(peer.node, isOutput);
        }
    }
    return null;
}
// The original's `if (slotNum)` treated slot 0 as "none given". The explicit
// undefined check keeps Dynamic Context's selected-slot walk without that bug.
export function followConnectionUntilType(node, isOutput, skipSelf = false, slotIndex) {
    const collection = isOutput ? node.outputs : node.inputs;
    const selected = slotIndex == null ? undefined : collection.at(slotIndex);
    const slots = selected ? [selected] : slotIndex == null ? collection.all() : [];
    if (!slots.length) {
        return null;
    }
    for (const slot of slots) {
        const type = getTypeFromSlot(node, slot, isOutput, skipSelf);
        if (type) {
            return type;
        }
    }
    return null;
}

/**
 * Brings a saved node's slot order back in line with the server definition it was saved
 * against — the pack's most consequential migration, and the reason the `CLIP_HEIGTH`
 * typo rename "must live in perpetuity".
 *
 * The original did it by splicing the live `inputs`/`outputs` arrays and then rewriting
 * every affected `link.origin_slot` / `link.target_slot` by hand, because a link stores
 * its endpoint as an index and a bare permutation silently re-points every connection.
 * `reorder(names)` is that whole second half: it re-points every link into and out of
 * the node in one batch, so link ids survive and the saved workflow's `links` array is
 * unchanged.
 *
 * Add-then-reorder rather than insert-at-index reaches the same final order, since
 * `reorder` is given the server's list outright.
 *
 * The original ended by calling `stabilize()` on any Reroute downstream of a moved
 * output. That was needed because rewriting `origin_slot` by hand told nothing; here
 * each link still lands on the same *named* output it was on, so nothing downstream sees
 * a different source and there is nothing to restabilize.
 */
export function matchLocalSlotsToServer(slots, serverSlots) {
    const serverNames = serverSlots.map((slot) => slot.name);
    const names = slots.names();
    // The original's guard: act only when some slot is not where the server puts it,
    // which is also false when the node simply has fewer slots than the server declares.
    // Preserved rather than widened — adding a slot to a node that never had one is a
    // different migration, and would change the saved workflow for every such node.
    if (!names.some((name, i) => i !== serverNames.indexOf(name))) {
        return;
    }
    const wanted = new Set(serverNames);
    for (const name of names) {
        if (!wanted.has(name)) {
            slots.remove(name);
        }
    }
    const present = new Set(slots.names());
    for (const slot of serverSlots) {
        if (!present.has(slot.name)) {
            slots.add(slot.name, slot.type);
        }
    }
    slots.reorder(serverNames);
}
