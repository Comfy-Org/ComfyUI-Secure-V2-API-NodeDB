// Group header fast toggles — draws mute / bypass / queue buttons into the header of
// every group (or just the hovered one) and handles clicks on them.
//
// REFUSED, not a pending gap: painting over the canvas. The buttons are drawn by
// replacing `LGraphCanvas.prototype.drawGroups`, because a group header is not a thing
// that exists to draw on — it is a rectangle the renderer paints, and the only way to put
// something in it is to take over the routine that paints it. The renderer is ours to
// replace, and a pack holding a reference to today's draw routine is a pack that breaks
// on the day it changes, silently and for its users rather than for its author.
// `widgets.canvas` is the published drawing surface and is per node and clipped to it; a
// canvas-wide overlay is deliberately absent.
//
// REFUSED, not a pending gap: intercepting and cancelling a canvas gesture. The hit test
// runs from rgthree's own `on-process-mouse-down` event, which exists only because
// rgthree.js patches `LGraphCanvas.prototype.processMouseDown`, and having decided the
// click was its own it cancels the drag the canvas had already begun by writing
// `canvas.selected_group = null` and `canvas.dragging_canvas = false`. Reaching into a
// gesture in flight and rewriting the renderer's idea of what the user is doing is not
// something to give a published equivalent; `comfy.isInteracting()` exists so a pack can
// stand *down* while the editor is mid-gesture, which is the opposite move.
// `canvas.selected_group` is unpublished for the same reason and is not a separate gap:
// it is only read on that cancellation path.
//
// What the file needed *besides* those two is published, and is recorded here so the next
// reader does not re-derive it. The enumeration, geometry, colour and membership it read
// off `graph._groups` / `group._pos` / `group._size` / `group._children` are
// `comfy.graph.groups()`, `getBounds()`, `getColor()` and `nodes()`; `getGroupOnPos` is a
// bounds test over `groups()` from `comfy.graph.pointerPosition()`, with
// `comfy.onViewportChanged` saying when to re-ask — so the `adjustMouseEvent` patch and
// the `setInterval` that forced a repaint four times a second, because nothing signalled
// hover, are both deleted rather than converted. The mute and bypass toggles are
// `setMode` over `group.nodes()`, and "queue" is `comfy.queue.run` over the same list.
// Only the surface to draw them on, and the click to catch, are refused.
//
// The capability survives in the pack's own Fast Groups Muter and Fast Groups Bypasser,
// which are converted: they list every group as a row with the same mute/bypass toggle
// and a jump arrow, on a node the pack owns and draws in. That is one node instead of a
// button on every header, and it is the same set of actions on the same set of groups.
//
// INOPERABLE: the `group_header_fast_toggle` feature. It registers no node type; what it
// changed was how every group in the document is drawn.

export {}
