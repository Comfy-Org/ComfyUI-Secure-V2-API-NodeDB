// Previously implemented two nodes: ReroutePrimitive|pysssss, a titleless dot that
// takes on the type of whatever it is wired between and grows a matching widget
// when its input is unconnected, and MultiPrimitive|pysssss, which grows inputs as
// they fill and expands to every permutation of its values at prompt time. The
// file's own comment already called the first one "no longer supported" and hid it
// from the node search.
//
// REFUSED, not a pending gap: reading or editing the built prompt. MultiPrimitive
// was an app.graphToPrompt override that found its own entries in the finished
// prompt and replaced their inputs with the cross-product of every connected value,
// so one queue ran every combination. Amending the prompt after it is built makes
// the work the backend does something the saved workflow does not describe, and two
// packs doing it produce a result that depends on load order.
//
// REFUSED, not a pending gap: replacing a core global.
// LiteGraph.getNodeTypesCategories was reassigned so this pack decided what every
// node search in the application shows, purely to hide one of its own types.
// Whether a deprecated type appears in search is a real question with no published
// answer, but the answer cannot be one pack filtering everybody's list.
//
// REFUSED, not a pending gap: patching the renderer to change how a node is drawn.
// The dot appearance was nodeType.title_mode redefined as a getter reading
// app.canvas.current_node, plus overrides of computeSize (returning [1, 25] when
// collapsed and a width derived from LiteGraph.NODE_TEXT_SIZE otherwise), collapse,
// and onBounding to correct litegraph's collapsed bounding box. Those are the
// renderer's, and the renderer is ours to replace.
//
// REFUSED, not a pending gap: per-link colour. changeRerouteType walked the reroute
// chain writing link.color from LGraphCanvas.link_type_colors. Reading a type's
// colour is published — comfy.defs.typeColor(type) — and a slot's own colours are
// SlotPatch fields, but an individual link's colour is not and will not be: a link
// takes its colour from its type, so a wire means the same thing everywhere.
//
// The capability is not refused and is not lost: core ships both nodes. Rerouting
// is native — src/lib/litegraph/src/Reroute.ts with rerouteStore gives link reroute
// points that carry the type along the chain by construction, and
// src/utils/migration/migrateReroute.ts moves an existing workflow's Reroute nodes
// onto them. Growing a widget that matches whatever input it feeds is PrimitiveNode
// in src/extensions/core/widgetInputs.ts, the same feature checkPrimitiveWidget
// re-implemented — including the COMBO case this pack could no longer build for
// itself, because a COMBO's value list is the FIRST element of the input spec and
// NodeDef.inputs[].options carries only the second.
//
// DROPPED: MultiPrimitive's permutation expansion. Running one queue for every
// combination of a set of values is not something core replaces, and the only route
// this file had to it is the refused one. Producing more work than the graph
// literally contains is prompt construction, which belongs to whoever executes the
// prompt.
//
// INOPERABLE: ReroutePrimitive|pysssss and MultiPrimitive|pysssss. Both are
// backend-registered, so an existing workflow still loads and still queues; they
// lose the retyping, the grown widget and the permutation expansion, and both now
// appear in the node search.

export {}
