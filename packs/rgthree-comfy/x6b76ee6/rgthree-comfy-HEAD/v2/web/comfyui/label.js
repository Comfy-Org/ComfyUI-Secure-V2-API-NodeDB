// Label — a chrome-less floating text annotation. Its title *is* its content:
// multi-line, rotatable, with a font, colour, alignment, padding, background and border
// radius kept in node properties.
//
// REFUSED, not a pending gap: drawing a node by taking over the routine that draws every
// node. `LGraphCanvas.prototype.drawNode` is replaced at module load; for a Label it
// makes the node transparent, calls through, and paints the text itself on top. Every
// other node in the document — core's and every other pack's — goes through rgthree's
// wrapper to get there. Two packs doing this cannot both be right, the winner is whoever
// imported last, and the routine is the renderer's, which is what Nodes 2.0 replaces.
// `LiteGraph.NO_TITLE` as `title_mode` and `collapsable = false` are the same substance:
// renderer flags describing chrome the renderer owns.
//
// REFUSED, not a pending gap: `LGraph.prototype.getNodeOnPos` is replaced too, so a
// *pinned* Label is filtered out of the hit list and clicks pass through it — unless the
// click was a double click, decided by reading `LGraphCanvas.active_canvas.last_mouseclick`
// and rgthree's own record of the last canvas mouse event. That is a pack rewriting what
// the editor thinks the user clicked on, for every node, from a global. `graph.nodeAt()`
// and `comfy.graph.pointerPosition()` publish the reading; replacing the answer is not
// on offer, and `b.onDoubleClick` is the double click itself without the timing
// machinery.
//
// REFUSED, not a pending gap: editing core's properties panel. `onDblClick` opens it
// with `LGraphCanvas.active_canvas.showShowNodePanel(this)` and `onShowCustomPanelInfo`
// then `querySelector`s the Mode and Color rows out of the panel's DOM. A pack deleting
// rows from the host's own form by CSS selector is coupled to markup we rename freely.
// `inResizeCorner()` overridden to make the node unresizable, and `flags.allow_interaction`
// rewritten from `flags.pinned` on every frame, are the same move on the same surface.
//
// The capability is refused only in this form, and it is worth being exact about what
// would return it. Everything the node *stores* is ordinary — eight properties and a
// title — and `comfy.defs.define({execution: 'frontend'})` registers the type,
// `widgets.canvas` paints text under both renderers, `measureText` still works inside
// that draw, and `setColor`/`setBgColor` make the frame transparent. What has no
// published destination is a node with no title bar and no body: the text *is* the
// title, so drawing it in the body as well shows it twice inside a frame the pack cannot
// remove. Half-converting it would ship exactly that, which is worse than not shipping
// it. A declared chromeless node — no title bar, no background, sized to its own
// drawing — is what this needs, and that is a request to make of the host rather than
// something a pack can install over `drawNode`.
//
// COSMETIC: the `@fontSize` / `@fontFamily` / `@fontColor` / … property descriptors that
// gave the properties panel typed editors have no destination either. The properties are
// plain values and would still save.
//
// INOPERABLE: Label (rgthree). Nothing else in the pack depends on it, and a saved
// workflow holding one keeps its properties and title, so the text is not lost and
// returns if the type is registered again.

export {}
