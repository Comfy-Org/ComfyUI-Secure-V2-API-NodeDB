import { shared } from "./shared.js"
import { Logger } from "./use_everywhere_utilities.js"
import { graph_for_node } from "./use_everywhere_subgraph_utils.js"

/*
The "Combo Clone" node copies a downstream combo widget's option list onto
itself, so the user picks from the real choices. It stores what it copied in
`properties.comboclone`, which is how the list survives a reload.

The V2 connection event supplies the peer node and slot directly, so this
module can preserve the original option-cloning behavior without reading a
live host link object.
*/

function update_me(node) {
    const cloned = node.getProperty("comboclone")
    if (!cloned) return
    Logger.log_problem(`Resetting combo clone node ${node.id}`)
    // Checked rather than optional-chained: a Combo Clone with no widget or no
    // output is not a state this can repair, and a write that evaporates is a
    // bug the pack cannot see.
    const widget = node.widgets.at(0)
    const output = node.outputs.at(0)
    if (!widget || !output) {
        return Logger.log_problem(`Combo clone node ${node.id} has no widget or output to reset`)
    }
    widget.setOption("values", [...cloned.options])
    output.modify({ type: "COMBO", label: cloned.name })
}

export function is_combo_clone(node) {
    return (node.comfyClass == "Combo Clone")
}

export function reset_comboclone_on_load(node) {
    if (is_combo_clone(node)) update_me(node)
}

export function comboclone_on_connection(node, peerNodeId, peerIndex, connect) {
    if (!is_combo_clone(node)) return Logger.log_problem(`comboclone_on_connection called for node ${node.id} of type ${node.type}`)
    if (shared.graph_being_configured) return
    if (!connect || peerNodeId === undefined) return

    const target_node = graph_for_node(node)?.node(String(peerNodeId))
    const input_name = target_node?.inputs.at(peerIndex)?.name
    if (!input_name) return
    const widget = target_node?.widgets.get(input_name)

    const values = widget?.getOptions()?.values
    if (widget?.widgetType == "combo" && values) {
        node.setProperty("comboclone", {
            options : [...values],
            name    : input_name
        })
        update_me(node)
        const own = node.widgets.at(0)
        if (own) own.setValue(widget.getValue())
    }
}
