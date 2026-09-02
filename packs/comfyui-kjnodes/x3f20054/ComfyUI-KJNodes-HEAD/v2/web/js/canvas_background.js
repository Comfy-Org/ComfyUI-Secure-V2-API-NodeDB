// REFUSED: overriding `app.canvas.onRenderBackground` to repaint the host graph
// canvas behind every node — tiled patterns (dots, grid, blueprint, isometric,
// hexagons, waves, carbon fiber) with colour, scale and thickness settings, and
// `app.canvas.setDirty(true, true)` to force the repaint.
//
// The mechanism, not the wish: this paints the editor's own surface, not a node's.
// `widgets.canvas` is the published drawing surface and it is deliberately per node —
// a pack draws on what it owns. The single `onRenderBackground` hook is winner-takes-all
// across every pack that claims it, returns `true` to suppress the host's own grid, and
// is a method on the renderer Nodes 2.0 replaces.
//
// Canvas background appearance is a real need and stays an editor-level setting, where
// one owner can arbitrate. No node in ComfyUI-KJNodes is made inoperable by this
// refusal — this file registered settings and a canvas hook only, and defined no node.

export {}
