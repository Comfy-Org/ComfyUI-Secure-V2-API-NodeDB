// REFUSED: writing the host renderer's own tuning knobs — `app.canvas.render_shadows`,
// `app.canvas.render_connections_border`, `LiteGraph.ROUND_RADIUS`, single-canvas pan
// mode and `setDirty(true, true)` — plus an FPS/info overlay painted from the canvas
// render loop.
//
// The mechanism, not the wish: how the editor draws itself, and how often, is the
// editor's. A node pack that mutates global renderer state changes every other pack's
// nodes and every core node too, and the flags it writes belong to a renderer Nodes 2.0
// replaces. There is no per-pack scoping that would make this safe, so there is nothing
// to convert it onto — a published "turn off shadows for everyone" would be the same
// mistake with our name on it.
//
// Software-rendering performance is a real need and stays an editor-level setting; the
// nodes in this pack are unaffected. No node in ComfyUI-KJNodes is made inoperable by
// this refusal — this file registered settings only.

export {}
