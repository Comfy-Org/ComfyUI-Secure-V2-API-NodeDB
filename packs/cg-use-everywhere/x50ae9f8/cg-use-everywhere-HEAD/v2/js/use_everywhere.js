import { comfy } from '/comfy/api/v2.js';

import { fix_inputs, input_changed } from "./connections.js";
import { ue_supply } from "./use_everywhere_graph_analysis.js";
import { UE_TYPES, is_ue_type, node_can_broadcast } from "./use_everywhere_utilities.js";
import { comboclone_on_connection, reset_comboclone_on_load } from "./combo_clone.js";
import { for_all_nodes } from "./recursive_callbacks.js";
import { any_restrictions, setup_ue_properties_oncreate, setup_ue_properties_onload } from "./ue_properties.js";
import { edit_restrictions } from "./ue_properties_editor.js";
import "./use_everywhere_settings.js";
import "./tooltip_window.js";

const ueStylesheet = document.createElement("link")
ueStylesheet.rel = "stylesheet"
ueStylesheet.href = new URL("./ue.css", import.meta.url).href
document.head.append(ueStylesheet)

/*
The pack's registration hub. The broadcast now runs as a supplier: the host
asks each UE node which unconnected inputs it feeds and substitutes the sources
while it builds the prompt. Nothing is written to the graph, so the whole
modify/serialize/unwind bracket the pack was built on is gone, along with
graph.extra['links_added_by_ue'] and the repair it needed.

Settings and node-menu contributions live in use_everywhere_settings.js. The
numeric combo values remain numeric through labelled setting options.

CONVERSION DELTAS AND REPLACEMENTS
----------------------------------
REPLACED (26): reading or rewriting the built prompt and the workflow.
  init() wrapped app.graphToPrompt to bracket serialization, recorded the
  injected link ids in graph.extra, published app.ue_modified_prompt for other
  packs, and replaced the 'Comfy.ExportWorkflowAPI' command so an API export
  carried the UE links. Supply-side resolution replaces the first; the rest are
  prompt rewriting and are not a pending gap.
COSMETIC DELTA (2): painting virtual links, slot rings and ambiguity crosses
  the canvas - use_everywhere_ui.js, ue_nodes2.js, and the drawNode /
  drawFrontCanvas / drawConnections / onDrawOverlay patches that drove them.
  The broadcast works without the overlay; the user simply cannot see it.
RESTORED (30): pre-1.16 widget/socket migration. `onConfigured` carries the
serialized node's own input list, which is the only portion of the old
whole-document map this node needs. ue_properties.js intersects those names
with its widgets and persists the inferred opt-ins. No document-wide read or
validation-setting override is required.
RESTORED: broadcasting inside every subgraph. The host resolves suppliers once
  per graph the prompt draws from, so a UE node placed inside a subgraph feeds
  the unfed inputs beside it. What does not survive is carrying a broadcast
  across the cut - see the refusal in use_everywhere_graph_analysis.js - so the
  app.graph.convertToSubgraph wrapper that re-homed UE links through it is gone
  with it.
REPLACED: publishing a pack-to-pack channel on the host object.
  app.ue_modified_prompt hung this pack's API off app for other packs to find,
  which makes every consumer depend on load order and on a shape no one owns.
  A pack that wants to offer one can export it from its own module, which is
  what an ES module already is.
The four canvas menu items, one at a time - they do not share a fate:
  "Show/Hide UE links" toggled the overlay refused above. With nothing drawn
    there is nothing to toggle, so it goes with it.
  "Show UE broadcast clashes" listed the ambiguities find_best_match() had
    collected. The host arbitrates ties now and logs them, so this file never
    sees the list it used to print. The host log owns that diagnostic with the
    arbitration it describes.
  "Convert all UEs to real links" is restored as graph/document commands, and
    the per-node form is restored in the node menu. Both transcribe the host's
    resolved supply snapshot rather than running a second matching engine.

NO LONGER NEEDED
----------------
(27) app.queuePrompt was wrapped only to set shared.in_queuePrompt, which told
  "the user pressed Queue" from "something else asked for a prompt" - the whole
  basis of Options.always_modify_graph. Resolution never modifies the graph, so
  the distinction has nothing left to guard.
(12) app.graph.beforeChange/afterChange were observed to gate a deferred
  fix-up queue. fix_inputs now runs inline under comfy.graph.batch() with its
  own re-entry guard.
(25) setup()/init() are module load, and b.onConnectionsChanged replaces the
  onConnectionsChange prototype patch.
The mirror of each UE node's own slots that nodeCreated / loadedGraphNode /
  onNodeChanged used to keep fresh. view.self carries the supplier's mode,
  color and inputs, resolved against the graph being supplied, so there is
  nothing left to record - and nothing left to be ambiguous about when the same
  node id appears in two graphs.
*/

comfy.defs.extend(/.*/, (b) => {
    b.setSupply(ue_supply)

    b.onCreated((node) => {
        if (is_ue_type(node.comfyClass)) {
            setup_ue_properties_oncreate(node)
        } else if (!node.getProperty("ue_properties")) {
            node.setProperty("ue_properties", {
                widget_ue_connectable:{},
                input_ue_unconnectable:{}
            })
        }
        node.addBadge(() => ({
            text: node_can_broadcast(node) ? "UE" : "",
            color: "#111111",
            bgColor: any_restrictions(node) ? "#ffff48" : "#48ff48",
        }))
    })
    b.onConfigured((node, data) => setup_ue_properties_onload(node, data))
    b.onDoubleClick((node) => {
        if (node_can_broadcast(node)) edit_restrictions(node)
    })
})

comfy.defs.extend(UE_TYPES, (b) => {
    b.onConnectionsChanged((node, event) => {
        if (event.side=='input') input_changed(node, event)
        fix_inputs(node)
    })
})

/*
Combo Clone is not a broadcast node, so it sits outside UE_TYPES and needs its
own registration. The dispatch reads peerNodeId and peerIndex off the
connection event, which is what the original took from link_info.
*/
comfy.defs.extend('Combo Clone', (b) => {
    b.onConnectionsChanged((node, event) => {
        if (event.side != 'input') return
        comboclone_on_connection(node, event.peerNodeId, event.peerIndex, event.connected)
    })
    b.onConfigured((node) => reset_comboclone_on_load(node))
})

/*
The pack's afterConfigureGraph pass. fix_inputs adds and removes slots, and
LGraph.configure re-keys links to slots after every node has configured
(realignInputLinkSlots), so a slot added or removed from inside b.onConfigured
would be re-keyed against serialized data that never had it. The original
guarded the same hazard with shared.graph_being_configured and ran the fix at
afterConfigureGraph; onWorkflowLoaded is that moment.
*/
comfy.onWorkflowLoaded(() => {
    for_all_nodes((node) => {
        if (is_ue_type(node.comfyClass)) fix_inputs(node)
    })
})
