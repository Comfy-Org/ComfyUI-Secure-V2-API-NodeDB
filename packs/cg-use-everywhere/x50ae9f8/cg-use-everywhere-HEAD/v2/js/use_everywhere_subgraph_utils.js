import { comfy } from '/comfy/api/v2.js';

import { all_graphs } from "./recursive_callbacks.js";

export function visible_graph() {
    return comfy.graph
}

export function in_visible_graph(node) {
    return node.graphId === comfy.graph.id
}

export function graph_for_node(node) {
    return all_graphs().find((graph) => graph.id === node.graphId)
}

/*
RETIRED: constructing links by writing the subgraph input panel's link table
and wrapping app.graph.convertToSubgraph. The panel is renderer-owned and the
conversion mutates host topology while the editor is cutting a graph apart.

SCOPE DELTA: "Convert to subgraph" no longer copies a downstream node's
widget_ue_connectable flag onto the new subgraph instance. Supplier resolution
inside subgraphs remains tracked in use_everywhere_graph_analysis.js.
*/
