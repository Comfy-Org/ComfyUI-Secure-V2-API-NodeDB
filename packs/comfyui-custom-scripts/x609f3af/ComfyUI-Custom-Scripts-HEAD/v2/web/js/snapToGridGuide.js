// Previously drew drag guides while snap-to-grid was active: a translucent block
// showing where the dragged node would land, plus four long orthogonal lines
// through its edges. It hooked LGraphCanvas.prototype.drawNode and painted into
// the graph's shared 2D context before core drew the node.
//
// REFUSED, not a pending gap: painting over the canvas. widgets.canvas is per node
// and clipped to it, so guide lines that span the whole workflow cannot be drawn at
// all — and the block preview is painted for a node that has not moved yet, which a
// per-node surface also cannot express. Drawing into the graph's shared context is
// what ties a pack to one renderer, and it is not coming back.
//
// REFUSED, not a pending gap: renderer constants. The maths needs the grid pitch,
// the title height, the collapsed width and the title mode. node.getBounds() gives
// the node rectangle, but the rest is geometry the renderer owns, and re-deriving it
// in a pack is exactly what the removal of the renderer constants was meant to stop.
//
// The drag state it gated on — canvas.isDragging plus canvas.selected_nodes — is
// not a separate gap. comfy.graph.selection() gives the selection and
// comfy.onNodeMoved reports movement under both renderers; the only thing missing
// is "is a drag in progress" *at draw time*, and it is wanted at draw time solely
// because the answer was consumed inside the refused drawNode hook. Nothing asks
// it once the hook is gone.
//
// INOPERABLE: pysssss.SnapToGrid.Guide.
//
// REFUSED, not a pending gap: a pack-rendered element in the settings panel. The
// colour/enabled pairs were one `type: (name, setter, value) => <tr>` building four
// controls and writing straight to localStorage. The type union now covers `color`
// among others, but a pack-supplied RENDERER function stays refused, and this needed
// four values in one row rather than one control of a declarable type.

export {}
