import { Logger, broadcast_matches, broadcasts_from, bypassed_counts_as_live, candidate_is_connectable, display_name, is_ue_type, mode_is_live } from "./use_everywhere_utilities.js";

/*
The broadcast, as a supplier.

GraphAnalyser used to build a UseEverywhereList, materialise it as real links,
serialize, and unwind - the modify/restore bracket the whole pack was built
on. Supply-side resolution answers the same question without writing anything:
this file is asked, for one broadcasting node, which unconnected inputs it
feeds, and the host substitutes the sources while it builds the prompt.

The matching below is UseEverywhere.matches() against an UnconnectedInput
instead of a live (node, input) pair. The view already computes what the pack's
input_name() did - `label` is `label || localized_name || name` - and carries
nodeTitle, nodeType, nodeMode, nodeColor, nodeGroups and the frozen
nodeProperties the opt-in flags live in.

What the node itself broadcasts comes from view.self. A UE node forwards the
source connected to one of its inputs; an ordinary node with `ue_convert`
broadcasts its own live outputs, including dynamic and retyped slots.

Priority is handed to the host rather than arbitrated here. The host takes the
highest and, on an exact tie, feeds nothing and logs - which is what
find_best_match() did with its Ambiguity, and it is now correct across packs
rather than only within this one.

RETIRED (26): graph.extra['ue_links'] and ['links_added_by_ue']. Those were
temporary bookkeeping for real links injected during prompt serialization.
The supplier never injects links, so neither the repair record nor prompt
mutation exists anymore.

RESTORED: broadcasting inside a subgraph. The original ran this over every
graph in the document. The host now resolves suppliers once per graph the
prompt draws from, so a UE node placed inside a subgraph feeds the unfed
inputs beside it exactly as it does in the root. Nothing here changed - the
supplier is asked in each scope now.

SCOPE DELTA: broadcasting across a boundary. The original also fed the subgraph
output panel's empty slots (graph.outputNode.slots), reaching out of the graph
it was invoked for. That makes a subgraph's interior depend on state that is
not in it: the same subgraph placed twice would resolve differently, and
reading the workflow would not show why. The capability survives within each
scope, which is where a broadcast can still be seen and reasoned about.

INTEROP DELTA: node.reject_ue_connection(input), an opt-out another pack could define
as a method on its own node class to refuse one specific input. Nothing on
UnconnectedInput can carry a function, and a property flag would be a different
contract. The blanket properties.rejects_ue_links opt-out still works.

BYPASS DELTA: is_connected()'s bypass-awareness. The original treated an input whose
only upstream chain dead-ends in bypassed nodes as unconnected, and so still
broadcastable. The view's definition is simply "no link", so such an input is
left alone.
*/

export function ue_supply(view) {
    /*
    setup_ue_properties_oncreate() writes DEFAULT_PROPERTIES onto a new UE
    node. Every matching-related default in it is falsy - no
    regexes, no restrictions, no priority override - so an empty bag is the same
    broadcast, and a node the user dropped a moment ago still works.
    */
    const props = view.self.properties.ue_properties || {}
    if (view.self.properties.ue_materialized) return []
    if (!is_ue_type(view.self.type) && !view.self.properties.ue_convert) return []

    if (!mode_is_live(view.self.mode, false)) return []

    const broadcasts = broadcasts_from(view.self, props)
    if (!broadcasts.length) return []

    const bypassed_is_live = bypassed_counts_as_live()
    const candidates = view.unconnectedInputs().filter((candidate) => (
        !is_ue_type(candidate.nodeType) &&
        mode_is_live(candidate.nodeMode, bypassed_is_live) &&
        candidate_is_connectable(candidate)
    ))

    const edges = []
    broadcasts.forEach((broadcast) => {
        candidates.filter((candidate)=>broadcast_matches(broadcast, candidate)).forEach((candidate) => {
            Logger.log_detail(`${broadcast.description} -> '${display_name(candidate)}' input '${candidate.label}'`)
            edges.push({
                to       : { nodeId:candidate.nodeId, input:candidate.input },
                from     : broadcast.from,
                priority : broadcast.priority,
            })
        })
    })
    return edges
}
