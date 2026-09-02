import { comfy } from '/comfy/api/v2.js';

import { is_UEnode, Logger, node_can_broadcast } from "./use_everywhere_utilities.js";

function result() {
    return { linked:0, failed:0 }
}

function combine(into, addition) {
    into.linked += addition.linked
    into.failed += addition.failed
    return into
}

function materialize(scope, controller_id) {
    const controllers = scope.nodes()
        .filter((node)=>node_can_broadcast(node) && (controller_id===undefined || node.id===controller_id))
    const states = new Map(controllers.map((node)=>[node.id, { node, failed:false, is_source:false }]))
    const converted = result()

    scope.resolvedSupplies()
        .filter((supply)=>states.has(supply.supplierNodeId))
        .forEach((supply)=>{
            const state = states.get(supply.supplierNodeId)
            if (supply.from.kind !== 'output') {
                state.failed = true
                converted.failed++
                Logger.log_problem(`Cannot materialize ${supply.from.kind} supplied by node ${supply.supplierNodeId}`)
                return
            }

            const output = scope.node(supply.from.nodeId)?.outputs.at(supply.from.output)
            if (!output) {
                state.failed = true
                converted.failed++
                Logger.log_problem(`Cannot find output ${supply.from.nodeId}[${supply.from.output}]`)
                return
            }

            const link = output.connectTo(supply.to.nodeId, { index:supply.to.input })
            if (!link) {
                state.failed = true
                converted.failed++
                Logger.log_problem(`Failed to connect ${supply.from.nodeId}[${supply.from.output}] -> ${supply.to.nodeId}[${supply.to.input}]`)
                return
            }

            state.is_source ||= supply.from.nodeId === supply.supplierNodeId
            converted.linked++
        })

    states.forEach(({ node, failed, is_source })=>{
        if (failed) return
        if (!is_UEnode(node)) {
            node.setProperty("ue_convert", false)
        } else if (is_source) {
            node.setProperty("ue_materialized", true)
        } else {
            node.remove()
        }
    })

    return converted
}

function report(converted) {
    if (!converted.failed) return
    comfy.commands.notify({
        severity : "error",
        summary  : "Use Everywhere conversion was incomplete",
        detail   : `${converted.linked} links created; ${converted.failed} could not be created.`
    })
}

export function convert_node_to_links(node) {
    const converted = comfy.graph.batch(()=>materialize(comfy.graph, node.id))
    report(converted)
    return converted
}

export function convert_visible_graph_to_links() {
    const converted = comfy.graph.batch(()=>materialize(comfy.graph))
    report(converted)
    return converted
}

export function convert_all_graphs_to_links() {
    const root = comfy.graph.root()
    const scopes = root ? [root, ...comfy.graph.subgraphs()] : [comfy.graph]
    const converted = comfy.graph.batch(()=>(
        scopes.reduce((total, scope)=>combine(total, materialize(scope)), result())
    ))
    report(converted)
    return converted
}
