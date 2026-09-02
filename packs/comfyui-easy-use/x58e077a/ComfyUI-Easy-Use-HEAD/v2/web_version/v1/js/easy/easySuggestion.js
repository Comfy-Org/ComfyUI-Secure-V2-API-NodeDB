// Previously changed what happens when a link is dropped on empty canvas, by
// replacing LGraphCanvas.prototype.createDefaultNodeForSlot and
// LGraphCanvas.prototype.showConnectionMenu with ~250-line reimplementations
// that ranked node types from LiteGraph.slot_types_default_in/out plus the
// pack's own weighting table, and presented the result through a hand-built
// LiteGraph.ContextMenu.
//
// REFUSED, not a pending gap: patching the renderer's prototypes.
// createDefaultNodeForSlot and showConnectionMenu are the canvas's own
// link-release routing — the code that decides what a released wire does. The
// renderer is ours to replace, and a pack that overwrites two of its methods
// pins the whole application to this one; worse, both replacements are global,
// so easy-use's ranking became the ranking for every link in the document,
// including links between nodes no easy-use user has ever installed. There is
// no version of this that is scoped to the pack, which is what makes it a
// mechanism rather than a missing hook.
//
// REFUSED, not a pending gap: building the host's menus out of
// LiteGraph.ContextMenu. That class is the legacy renderer's, and constructing
// it directly is how a pack ends up drawing chrome we intend to restyle.
// `comfy.ui.showMenu` is the published surface for a menu a pack raises itself
// — it does not help here, because the thing being replaced is a menu the HOST
// raises, but it is where a pack's own menu now goes.
//
// The capability is not refused and is not lost: core ships link-release
// suggestion itself, and ships it better. `Comfy.LinkRelease.Action` and
// `Comfy.LinkRelease.ActionShift` (src/platform/settings/constants/coreSettings.ts)
// let the user pick the context menu or the search box per modifier, and
// NodeSearchBoxPopover.vue:177 pre-filters the search by the released slot's
// data type — the same question this file answered with a static table. So a
// user releasing a wire still gets a type-appropriate list of nodes; what goes
// is easy-use's hand-tuned ORDERING of its own nodes within that list, which is
// a ranking preference, not a capability.
//
// DROPPED: the suggestion weighting in this file — that a STRING output offers
// the six prompt nodes first, a PIPE_LINE output the preSampling family, and so
// on. Core's list is alphabetical within the type filter.
//
// INOPERABLE: nothing. No node type is registered or extended by this file; it
// only re-ordered a menu.

export {}
