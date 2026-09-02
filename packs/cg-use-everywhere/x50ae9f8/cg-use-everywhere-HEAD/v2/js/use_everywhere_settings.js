import { comfy } from '/comfy/api/v2.js';

import { edit_restrictions } from "./ue_properties_editor.js";
import { Logger, is_UEnode, node_can_broadcast, is_able_to_broadcast } from "./use_everywhere_utilities.js";
import { convert_all_graphs_to_links, convert_node_to_links, convert_visible_graph_to_links } from "./use_everywhere_apply.js";

comfy.settings.declare({
    id           : "Use Everywhere.Graphics.tooltips",
    name         : "Show restrictions as tooltip",
    type         : "boolean",
    defaultValue : true
})

comfy.settings.declare({
    id           : "Use Everywhere.Options.connect_to_bypassed",
    name         : "Connect to bypassed nodes",
    type         : "boolean",
    defaultValue : true,
    tooltip      : "By default UE links are made to the node downstream of bypassed nodes."
})

comfy.settings.declare({
    id           : "Use Everywhere.Options.logging",
    name         : "Logging",
    type         : "combo",
    options      : [ {value:0, label:"Errors Only"}, {value:1, label:"Problems"}, {value:2, label:"Information"}, {value:3, label:"Detail"} ],
    defaultValue : 1,
    onChange     : Logger.level_changed
})
Logger.level_changed(comfy.settings.get("Use Everywhere.Options.logging"))

comfy.settings.declare({
    id           : "Use Everywhere.Options.use_output_name",
    name         : "When connecting, use the output slot's name as the input name",
    type         : "boolean",
    defaultValue : false,
    tooltip      : "By default the link type is used as the name"
})

function properties_for(node) {
    return node.getProperty("ue_properties") || {}
}

function set_ue_property(node, name, value) {
    node.setProperty("ue_properties", { ...properties_for(node), [name]:value })
}

export function is_connectable(node, input_name){
    if (node.getProperty("rejects_ue_links")) return false
    const input = node.inputs.byName(input_name)
    if (!input) {
        Logger.log_error(`Can't find input ${input_name} on node ${node.getTitle()}`)
        return false
    }
    const properties = properties_for(node)
    if (input.isWidgetInput) {
        return !!properties.widget_ue_connectable?.[input_name]
    }
    return !properties.input_ue_unconnectable?.[input_name]
}

function toggle_connectable(node, input_name){
    const input = node.inputs.byName(input_name)
    if (!input) return
    const properties = properties_for(node)
    if (input.isWidgetInput) {
        set_ue_property(node, "widget_ue_connectable", {
            ...(properties.widget_ue_connectable || {}),
            [input_name]:!properties.widget_ue_connectable?.[input_name]
        })
    } else {
        set_ue_property(node, "input_ue_unconnectable", {
            ...(properties.input_ue_unconnectable || {}),
            [input_name]:!properties.input_ue_unconnectable?.[input_name]
        })
    }
}

function toggle_broadcasting(node, output_name){
    const properties = properties_for(node)
    set_ue_property(node, "output_not_broadcasting", {
        ...(properties.output_not_broadcasting || {}),
        [output_name]:!properties.output_not_broadcasting?.[output_name]
    })
}

comfy.defs.extend(/.*/, (b) => {
    b.addMenuItem({
        label: "Edit restrictions",
        when: (node)=>node_can_broadcast(node),
        run: (node)=>edit_restrictions(node)
    })

    b.addMenuItem({
        label: "Convert to real links",
        when: (node)=>node_can_broadcast(node),
        run: (node)=>convert_node_to_links(node)
    })

    b.addMenuItem({
        label: (node)=>node.getProperty("rejects_ue_links") ? "Allow UE Links" : "Reject UE Links",
        when: (node)=>!is_UEnode(node) && node.inputs.length>0,
        run: (node)=>node.setProperty("rejects_ue_links", !node.getProperty("rejects_ue_links"))
    })

    b.addMenuItem({
        label: "UE Connectable Inputs",
        when: (node)=>!is_UEnode(node) && node.inputs.length>0 && !node.getProperty("rejects_ue_links"),
        items: (node)=>node.inputs.all()
            .filter((input)=>!input.name?.includes('$$'))
            .map((input)=>({
                label:`${is_connectable(node, input.name) ? "☑" : "☐"} ${input.label || input.name}`,
                run: ()=>toggle_connectable(node, input.name)
            }))
    })

    b.addMenuItem({
        label: (node)=>node.getProperty("ue_convert") ? "Remove UE broadcasting" : "Add UE broadcasting",
        when: (node)=>!is_UEnode(node) && node.outputs.length>0,
        run: (node)=>node.setProperty("ue_convert", !node.getProperty("ue_convert"))
    })

    b.addMenuItem({
        label: "Broadcasting Outputs",
        when: (node)=>!is_UEnode(node) && node.outputs.length>0 && !!node.getProperty("ue_convert"),
        items: (node)=>node.outputs.all().map((output)=>({
            label:`${is_able_to_broadcast(node, output.name) ? "☑" : "☐"} ${output.label || output.name}`,
            run: ()=>toggle_broadcasting(node, output.name)
        }))
    })
})

comfy.commands.register({
    id    : "UseEverywhere.convertVisibleToLinks",
    label : "Convert all UEs in this graph to real links",
    run   : ()=>{
        if (window.confirm("This will convert every Use Everywhere broadcast in the current graph to real links. Continue?")) {
            convert_visible_graph_to_links()
        }
    }
})

comfy.commands.register({
    id    : "UseEverywhere.convertAllToLinks",
    label : "Convert all UEs in this document to real links",
    run   : ()=>{
        if (window.confirm("This will convert every Use Everywhere broadcast in this document to real links. Continue?")) {
            convert_all_graphs_to_links()
        }
    }
})

/*
COSMETIC: the version-only setting row and controls for the legacy virtual-link
overlay are omitted. The overlay has no renderer-neutral surface to control.

PLACEMENT DELTA: canvas-menu placement. The node-specific restrictions and broadcast
controls above retain their behavior in the node menu. The two document-wide
conversion actions are commands, and per-node conversion is a node-menu item.
*/
