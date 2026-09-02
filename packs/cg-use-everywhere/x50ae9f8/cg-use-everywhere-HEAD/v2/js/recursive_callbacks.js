import { comfy } from '/comfy/api/v2.js';

export function all_graphs() {
    const root = comfy.graph.root()
    return root ? [root, ...comfy.graph.subgraphs()] : comfy.graph.subgraphs()
}

export function for_all_graphs(callback) {
    all_graphs().forEach(callback)
}

export function for_all_nodes(callback) {
    all_graphs().forEach((graph) => graph.nodes().forEach(callback))
}
