// Previously added server-side workflow management, back when the frontend had
// none: dropdown arrows grafted onto the core Save and Load buttons listing
// workflows stored under /pysssss/workflows, a "🐍 Default Workflow" setting that
// replaced what Load Default loads, and a "Send to workflow" node menu entry that
// uploaded the hovered output image and opened another workflow with its LoadImage
// node pointed at it.
//
// REFUSED, not a pending gap: grafting onto core's own buttons. Every entry point
// was document.getElementById("comfy-save-button") or "comfy-load-button", plus an
// outright reassignment of "comfy-load-default-button".onclick — one pack taking
// over a control the host owns, by id, so a rename or a restyle breaks it silently
// and a second pack doing the same wins by load order. Chrome contributions are
// declarative for exactly this reason: a pack says what to show and the host
// renders it, which is what keeps the chrome ours to replace.
//
// REFUSED, not a pending gap: reading or editing the workflow snapshot. Saving was
// app.graph.serialize() and "Send to workflow" then rewrote
// targetNode.widgets_values[0] inside that snapshot before handing it back to be
// loaded. Writing into the serialized form edits what the document means without
// anything in the document saying so, and `widgets_values` is positional — a pack
// indexing into it is one added widget away from setting the wrong field.
//
// The capability is not refused and is not lost: core ships it. Server-side
// workflow storage, the browsable list, save, save-as and open are all native now
// — src/components/sidebar/tabs/WorkflowsSidebarTab.vue and the Comfy.OpenWorkflow
// / Comfy.SaveWorkflow / Comfy.SaveWorkflowAs / Comfy.LoadDefaultWorkflow commands,
// which any pack may invoke through comfy.commands.run(id). A user who kept
// workflows in this pack's folder gets the same three operations from the layer
// that owns the document, against the user storage core already syncs.
//
// DROPPED: "Send to workflow". Its first half converts — node.getOutputImages()
// with node.getDisplayedImageIndex() names the image the user picked, and
// comfy.backend.fetch uploads it — but the second half has to OPEN A NAMED
// workflow and point its LoadImage at the upload. Comfy.OpenWorkflow raises a
// picker rather than taking a name, so there is nothing to hand the name to.
// Repointing the node afterwards would not need the snapshot at all:
// comfy.onWorkflowLoaded plus graph.nodesOfType("LoadImage") does it on the live
// graph. Opening a workflow by name is the one missing piece.
//
// INOPERABLE: the /pysssss/workflows Save and Load dropdowns, the
// "pysssss.Workflows.Default" setting, and "Send to workflow".

export {}
