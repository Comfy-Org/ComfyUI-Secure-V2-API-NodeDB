// Previously added a "🐍 Link Render Mode" setting that wrote
// app.canvas.links_render_mode, letting you pick straight/linear/spline links.
//
// REFUSED, not a pending gap: retuning the host's renderer. Every arm of this
// file writes into the live canvas — links_render_mode to change how links are
// drawn for the whole document, then setDirtyCanvas to force the repaint — and
// reads LiteGraph.LINK_RENDER_MODES to enumerate what it may write. How links are
// drawn is the renderer's, and the renderer is ours to replace; a pack that can
// reach in and restyle it makes its choice every other pack's behaviour.
//
// REFUSED, not a pending gap: a pack-rendered element in the settings panel. The
// setting's `type` was a function returning a <tr><td><select> the pack built and
// bound itself, so it could apply on every keystroke. comfy.settings.declare
// renders declared control types only, deliberately — a pack-supplied renderer
// puts packs in charge of the settings panel's markup.
//
// The capability is not refused and is not lost: core ships this preference as
// Comfy.LinkRenderMode. The original knew that — its first act was to scan
// app.extensions for Comfy.LinkRenderMode and stand down when it found it — so on
// any current frontend this file was already doing nothing.
//
// INOPERABLE: pysssss.LinkRenderMode.

export {}
