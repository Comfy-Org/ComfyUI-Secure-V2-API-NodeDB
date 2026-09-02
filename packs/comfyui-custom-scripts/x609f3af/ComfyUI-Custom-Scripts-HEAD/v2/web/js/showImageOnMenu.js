// Previously showed the most recent output (or live preview) as a thumbnail in the
// app menu, clicking which centred and zoomed the canvas onto the node that
// produced it.
//
// REFUSED, not a pending gap: a pack's own element in the app chrome. The thumbnail
// was appended to app.ui.menuContainer. comfy.ui.addTopBarBadge() and
// addActionBarButton() now let a pack contribute there, but declaratively — text, an
// icon class, a tooltip — and an <img> of the latest output is none of those. The
// host renders chrome; a pack does not hand it an element. A node-mounted widget is
// the wrong shape too, since the point was to see it while looking elsewhere.
//
// Nothing else here is blocked any more. The click handler is
// comfy.graph.centerOn(node) followed by comfy.graph.setZoom(1); the b_preview
// branch's app.runningNodeId is comfy.executingNode(); the "executed" half is
// comfy.backend.on("executed", …) plus comfy.backend.url("/view?…"). All of it
// still has nowhere to draw, so converting it would leave listeners building URLs
// for an element that cannot exist.

export {}
