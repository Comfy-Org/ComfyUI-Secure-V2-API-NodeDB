// Reroute (rgthree) — the pack's largest single node, 981 lines. A resizable reroute
// whose input and output can sit on any of the four sides, which propagates type, label
// and link colour down chains of reroutes, plus a "fast reroute" service that spawns a
// reroute and splices it into a link **while the user is mid-drag**.
//
// Its resolution is the easy part: a reroute is `{forwardTo: {nodeId: self.id, input: 0}}`
// and the published resolution system already chains reroute → reroute to a fixpoint.
// Everything around it is refused, and it is refused as a body of technique rather than
// one call at a time.
//
// REFUSED, not a pending gap: trapping the canvas's own state to observe a gesture. The
// fast-reroute service replaces `connecting_links` with an accessor pair —
//   Object.defineProperty(canvas, "connecting_links", {get, set})
// — so that the pack is told when a drag begins, then reads `connecting_node`,
// `connecting_input`, `connecting_output`, `connecting_slot` and `connecting_pos`, writes
// new endpoints back into `connecting_links[0]`, and claims the pointer with
// `canvas.node_capturing_input = this`. Installing a property trap on the editor and then
// rewriting a gesture in flight is the most invasive thing in this pack.
// `comfy.isInteracting()` answers *whether* a gesture is running, deliberately and only:
// which gestures exist, and what their intermediate state looks like, is the editor's
// business and changes with the renderer.
//
// REFUSED, not a pending gap: drawing a node's whole body. `onDrawForeground(ctx, canvas)`
// paints the entire reroute — there is no title bar (`LiteGraph.NO_TITLE`) and no widget
// band, so there is nowhere for a `widgets.canvas` to go. Same substance as label.js: a
// chromeless node is not something a pack can assemble out of renderer flags and a draw
// callback. `getConnectionPos` overridden through `addConnectionLayoutSupport`, with
// `LiteGraph.LEFT/RIGHT/UP/DOWN`, `layout_slot_offset` and `hideSlotLabels`, is the same
// thing for the sockets — see utils.js.
//
// REFUSED, not a pending gap: overriding a node's own plumbing. `findInputSlot`,
// `findOutputSlot`, `disconnectInput`, `disconnectOutput`, `setSize`, `clone`,
// `configure`, `onMouseMove`, `onKeyDown`/`onKeyUp` and `onDeselected` are all replaced
// on the class. Those are the host's methods with the host's invariants; a pack that
// redefines what "disconnect this input" means for a node is not extending the editor, it
// is forking it inside the same process.
//
// REFUSED, not a pending gap: editing the link table. It reads and writes
// `app.graph.links[id]`, calls `removeLink`, and assigns `origin_id` / `origin_slot` /
// `target_id` / `target_slot` by hand to splice itself into an existing link. That is the
// wire format written directly, with no command behind it and nothing to undo.
// `output.moveLinksTo` exists precisely so link ids survive a re-home, but splicing a new
// node into the middle of a link is a different operation and the published pair
// (`connectTo` + `disconnect`) allocates new ids.
//
// REFUSED, not a pending gap: impersonating another node's widget. It sets and then
// *deletes* `node.inputs[0].widget = {name: "value"}` and carries core's private widget
// config through utils_deprecated_comfyui.js — which is refused there, for the same
// reason — so that a reroute can sit between a primitive and its target and pretend to be
// the widget the primitive is driving.
//
// REFUSED, not a pending gap: link colour. Reading `LGraphCanvas.link_type_colors[type]`
// is `comfy.defs.typeColor(type)`, but assigning `link.color` so a chain keeps the
// upstream type's colour is a per-link write into the renderer's own record. Slot colour
// is published (`slot.modify({color})`); link colour is not.
//
// Two of the markers that stood here are closed and are recorded so they are not
// re-raised. The fast-reroute chord reads rgthree's own key service, which is converted
// (services/key_events_services.js) and needs nothing published. `canvas.selectNode()` is
// `comfy.graph.select([node])`, and `convertEventToCanvasOffset(event)` /
// `last_mouse_position` — where to drop the new node — is `comfy.graph.pointerPosition()`.
// COSMETIC: (8) the rotate / resize / label / connection-layout submenus are all
//   expressible through `b.addMenuItem`; only their splice position among core's own
//   entries is not.
//
// The capability is not lost. ComfyUI ships reroutes twice over: the `Reroute` node in
// `src/extensions/core/rerouteNode.ts`, which core's own `slotDefaults` offers first for
// every type, and native link reroute points (`src/lib/litegraph/src/Reroute.ts` and
// `rerouteStore`), which are part of the link rather than a node and so need none of the
// machinery above. What a user loses by this refusal is the four-sided slot layout, the
// resize handles and the mid-drag splice; what they keep is rerouting.
//
// INOPERABLE: Reroute (rgthree), and the fast-reroute shortcut with it. State lived in
// node `properties` — `resizable`, `size`, `connections_layout`, `connections_dir`,
// `showLabel` — and there are no widgets, so a saved workflow holding one keeps
// everything it held.

export {}
