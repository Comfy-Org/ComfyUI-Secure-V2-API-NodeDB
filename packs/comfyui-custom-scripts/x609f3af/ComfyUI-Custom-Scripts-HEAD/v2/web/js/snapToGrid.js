// Previously forced snap-to-grid on permanently, by pretending shift was held
// (app.shiftDown = true) around every editor operation that consults it —
// LGraphCanvas.prototype.drawNode, node.onResize, LGraphGroup.prototype.move,
// LGraphCanvas.prototype.drawGroups and LGraphCanvas.onGroupAdd — installing all
// of them from inside a patched LGraph.prototype.configure so they landed after
// core's own snap extension.
//
// REFUSED, not a pending gap: lying about the host's input state. Nothing here
// snaps anything. The file sets app.shiftDown true, calls through, and sets it
// back, so that code it does not own reads a modifier the user is not holding.
// Any other reader of that flag during the call — core's own handlers, another
// pack — is told the same untruth, and a pack cannot know who is listening. A
// preference is a preference; it is not a synthetic keypress.
//
// REFUSED, not a pending gap: patching the renderer's prototypes. drawNode,
// drawGroups, onGroupAdd and LGraphGroup.move are the renderer's internals and
// the renderer is ours to replace, and LGraph.prototype.configure was patched
// solely to control when the other five patches landed relative to core's
// extension. Load-order-sensitive prototype patching is the coupling this
// migration exists to delete, not something to give a published equivalent.
//
// The capability is not refused and is not lost: core ships it, under this pack's
// own setting id. src/renderer/extensions/vueNodes/composables/useNodeSnap.ts
// reads `pysssss.SnapToGrid` directly, so a user who had the box ticked keeps
// exactly the behaviour they had, and gets it from the layer that owns node
// placement rather than from a hook wrapped around a repaint.
//
// INOPERABLE: pysssss.SnapToGrid.

export {}
