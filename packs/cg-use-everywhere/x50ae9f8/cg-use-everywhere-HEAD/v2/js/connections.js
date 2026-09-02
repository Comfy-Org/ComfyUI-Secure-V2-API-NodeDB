import { comfy } from '/comfy/api/v2.js';

import { Logger } from "./use_everywhere_utilities.js";
import { graph_for_node } from "./use_everywhere_subgraph_utils.js";

/*
A UE node's input slots: retype and relabel a slot as a link arrives or leaves,
and grow or shrink the trailing pool of spare '*' inputs so there is always
exactly one free. The broadcast reads the resulting types, so this is what
makes a second connection to an "Anything Everywhere" node possible at all.

RESTORED: input.connectedType resolves the declared type through a subgraph
input panel without exposing the panel or its sentinel node id.

RESTORED: the combo_clone dispatch. b.onConnectionsChanged carries peerNodeId
and peerIndex, which is what the dispatch needed from link_info.
*/
const ANYTHING = 'anything'

/*
in_slot.transient_label was an ad-hoc property on a live slot - a 100ms window
so that re-plugging a link keeps the label the user gave it. Handles hold no
arbitrary properties, so it lives in a module map keyed nodeId:slot.
*/
const transient_labels = new Map()

function ue_props(node) { return node.getProperty('ue_properties') || {} }

/*
convert_node_types() in ue_properties.js normally writes fixed_inputs and
keep_inputs into a node's ue_properties. Take the two facts the pool logic
depends on from the node class when
the property is absent, rather than reading an empty bag: otherwise Seed
Everywhere grows an input it must not have, and Prompts Everywhere loses one of
its two fixed ones. Nothing is written, so no property appears in the workflow
that the unconverted pack would not have written itself.
*/
function has_fixed_inputs(node) {
    if (node.comfyClass=="Seed Everywhere") return true
    return !!ue_props(node).fixed_inputs
}

function to_keep(node, i) {
    const keep = (node.comfyClass=="Prompts Everywhere") ? [0,1] : ue_props(node).keep_inputs
    return !!(keep && keep.includes(i))
}

function is_removable(node, in_slot) {
    return (in_slot.type=='*' && !to_keep(node, in_slot.index))
}

function upstream_name(node, in_slot) {
    const source = in_slot.source()
    if (!source) return undefined
    const out_slot = graph_for_node(node)?.node(source.nodeId)?.outputs.at(source.outputIndex)
    return out_slot?.label || out_slot?.snapshot().localizedName || out_slot?.name
}

/*
Called by onConnectionsChanged for a UE node when the side is input.
*/
export function input_changed(node, event) {
    const in_slot = node.inputs.at(event.index)
    if (!in_slot) return Logger.log_problem(`input_changed called for node #${node.id} slot ${event.index} but that wasn't found`)
    const key = `${node.id}:${event.index}`

    if (event.connected) {
        const type = in_slot.connectedType
        if (!type || type=='*') return // no real idea what to do
        const transient = transient_labels.get(key)
        var label
        if (transient) {
            label = transient
            Logger.log("Restoring transient label")
        } else if (in_slot.label && in_slot.label != ANYTHING) {
            label = in_slot.label
            Logger.log("Leaving custom label")
        } else if (comfy.settings.get("Use Everywhere.Options.use_output_name")) {
            label = upstream_name(node, in_slot) || type
        } else {
            label = type
        }
        in_slot.modify({ label:label, type:type, color:comfy.defs.typeColor(type) })
    } else {
        transient_labels.set(key, in_slot.label)
        setTimeout(()=>{transient_labels.delete(key)}, 100)
        if (is_removable(node, in_slot)) in_slot.modify({ label:ANYTHING, type:'*', color:null })
    }
}

function fix_unconnected_inputs(node) {
    node.inputs.all().filter((input)=>(!input.isConnected && !to_keep(node, input.index))).forEach((input)=>{
        input.modify({ type:'*', label:ANYTHING })
    })
}

function fix_star_inputs(node) {
    node.inputs.all().filter((input)=>(input.type=='*' && input.isConnected)).forEach((input)=>{
        const type = input.link()?.type
        if (type) input.modify({ type:type })
    })
}

function add_new_input(node) {
    try {
        const props = { ...ue_props(node) }
        props.next_input_index = (props.next_input_index || 10) + 1
        node.setProperty('ue_properties', props)
        Logger.log_info(`Adding new anything input to node ${node.id}`)
        node.inputs.add(`anything${props.next_input_index}`, '*').modify({ label:ANYTHING })
        return true
    } catch (e) { Logger.log_error(e) }
    return false
}

function remove_excess_input(node) {
    const excess = node.inputs.all().find((input)=>is_removable(node, input))
    if (excess) {
        try {
            Logger.log_info(`Removing excess anything input from node ${node.id}`)
            node.inputs.remove(excess.id)
            return true
        } catch (e) { Logger.log_error(e) }
    } else { Logger.log_problem(`Something very odd happened in fix_inputs for ${node.id}`) }
    return false
}

/*
Removing an input that still carries a link fires onConnectionsChanged, which
calls back into here; the original leant on shared.in_midst_of_change and a
deferred queue to stop that recursing.
*/
const fixing = new Set()

export function fix_inputs(node) {
    if (node.isDeleted) return
    if (has_fixed_inputs(node)) return
    if (fixing.has(node.id)) return
    fixing.add(node.id)
    try {
        comfy.graph.batch(()=>{ adjust_input_pool(node) })
    } finally {
        fixing.delete(node.id)
    }
}

function adjust_input_pool(node) {
    fix_unconnected_inputs(node)
    fix_star_inputs(node)

    const empty_removable_inputs = node.inputs.all().filter((input)=>is_removable(node, input))
    const excess_inputs = empty_removable_inputs.length - 1

    if (excess_inputs<0) {
        if (add_new_input(node)) adjust_input_pool(node)
    } else if (excess_inputs>0) {
        if (remove_excess_input(node)) adjust_input_pool(node)
    }
}
