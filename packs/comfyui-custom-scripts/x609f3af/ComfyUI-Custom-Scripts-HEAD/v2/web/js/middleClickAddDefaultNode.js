// Previously let you pick which node type a middle-click on a slot creates, by
// setting LiteGraph.middle_click_slot_add_default_node and hoisting the chosen
// type to the front of every entry in LiteGraph.slot_types_default_in/out.
//
// REFUSED, not a pending gap: rewriting a core global in place. The onChange
// handler flipped an editor-wide behaviour flag and then spliced the user's
// choice to the head of every array in two shared tables that decide what a
// dragged slot offers — for every node type in the document, core's and every
// other pack's. It is destructive as well as global: the splice runs on the live
// arrays with no record of what was there, so nothing can put them back, and a
// second pack doing the same thing leaves the answer decided by load order.
// Editor gestures are the host's, and this is the shape of reach-in we refuse.
//
// The enumeration went the same way: the options list came from
// LiteGraph.registered_node_types, the renderer's own registry. comfy.defs.all()
// publishes definitions, but the slot-default tables are not derived from it, so
// there is nothing here for a converted list to feed.
//
// Which node a middle-click creates is an editor preference rather than a node
// capability — it belongs to whoever owns the gesture, and that is the host.
//
// INOPERABLE: pysssss.MiddleClickAddDefaultNode.

export {}
