import { version_at_least, create, is_UEnode, find_duplicate_broadcasted_types } from "./use_everywhere_utilities.js"
import { i18n, i18n_functional, GROUP_RESTRICTION_OPTIONS, COLOR_RESTRICTION_OPTIONS } from "./i18n.js";
import { fix_inputs } from "./connections.js";
import { VERSION } from "./shared.js";

const ALL_REGEXES = ['title', 'input', 'prompt', 'negative', 'group']

function properties_for(node) {
    return node.getProperty("ue_properties") || {}
}

function any_regex_restrictions(node) {
    const properties = properties_for(node)
    return ALL_REGEXES.some((r)=>{
        const reg = properties[`${r}_regex`]
        return !!(reg && reg.length>0)
    })
}

export function any_restrictions(node) {
    const properties = properties_for(node)
    return !!(
        properties.group_restricted ||
        properties.color_restricted ||
        properties.priority ||
        any_regex_restrictions(node)
    )
}

export function describe_restrictions(node) {
    const properties = properties_for(node)
    const statements = []
    ALL_REGEXES.forEach((r)=>{
        const reg = properties[`${r}_regex`]
        if (reg && reg.length>0) {
            const condition = i18n(properties[`${r}_regex_invert`] ? "not match" : "match")
            statements.push([`${i18n(r)} regex`, `${condition} ${reg}`])
        }
    })
    if (properties.group_restricted) statements.push([i18n('group'),i18n(GROUP_RESTRICTION_OPTIONS[properties.group_restricted])])
    if (properties.color_restricted) statements.push([i18n('color'),i18n(COLOR_RESTRICTION_OPTIONS[properties.color_restricted])])
    if (properties.priority !== undefined) statements.push([i18n('priority'), properties.priority])
    const table = create('table')
    statements.forEach((s)=>{
        const row = create('tr', null, table)
        create('th', null, row, {innerText:`${i18n(s[0], {titlecase:true})}:`})
        create('td', null, row, {innerText:s[1]})
    })
    return table
}

export function default_priority(node) {
    const properties = properties_for(node)
    var p = 10
    if (node.comfyClass === "Seed Everywhere" || node.comfyClass === "Prompts Everywhere") p += 10
    if (any_regex_restrictions(node) || find_duplicate_broadcasted_types(node).size) p += 20
    if (properties.group_restricted > 0) p += 3
    if (properties.color_restricted > 0) p += 6
    return p
}

const DEFAULT_PROPERTIES = {
    version               : VERSION,
    group_restricted      : 0,
    color_restricted      : 0,
    widget_ue_connectable : {},
    input_ue_unconnectable : {},
    title_regex           : null,
    input_regex           : null,
    group_regex           : null,
    title_regex_invert    : false,
    input_regex_invert    : false,
    group_regex_invert    : false,
    priority              : undefined,
    repeated_type_rule    : 0,
    apply_to_unrepeated   : 0,
    string_to_combo       : 0,
    send_to_any           : 0
}

function fresh_properties() {
    return {
        ...DEFAULT_PROPERTIES,
        widget_ue_connectable: {},
        input_ue_unconnectable: {}
    }
}

/*
Workflows saved before ComfyUI 1.16 did not persist the widget/socket policy
that Use Everywhere now stores in `widget_ue_connectable`. The old extension
wrapped whole-document loading only to build a node-id -> input-name map. The
published onConfigured data already carries this node's own serialized inputs,
so the same inference remains local to the pack and to the node it owns.
*/
function infer_legacy_widget_inputs(node, data, saved) {
    const nested = saved?.ue_properties
    if (nested && Object.hasOwn(nested, "widget_ue_connectable")) return null
    if (saved && Object.hasOwn(saved, "widget_ue_connectable")) return null
    if (!Array.isArray(data?.inputs)) return null

    const serialized = new Set(
        data.inputs.map((input) => input?.name).filter((name) => typeof name === "string")
    )
    const inferred = {}
    node.widgets.all().forEach((widget) => {
        if (serialized.has(widget.name)) inferred[widget.name] = true
    })
    return inferred
}

export function setup_ue_properties_oncreate(node) {
    node.setProperty("ue_properties", fresh_properties())
    convert_node_types(node)
    fix_inputs(node, "convert_node_types")
}

export function setup_ue_properties_onload(node, data) {
    const saved = data?.properties || node.getProperties()
    const inferred_widget_inputs = infer_legacy_widget_inputs(node, data, saved)
    let properties = saved?.ue_properties || {}
    if (!version_at_least(properties.version, "7.0")) {
        if (is_UEnode(node)) {
            properties = {
                ...fresh_properties(),
                group_restricted      : saved?.group_restricted,
                color_restricted      : saved?.color_restricted,
                widget_ue_connectable : saved?.widget_ue_connectable || {},
                title_regex           : data?.widgets_values?.[0],
                input_regex           : data?.widgets_values?.[1],
                group_regex           : data?.widgets_values?.[2]
            }
        } else {
            properties = {
                ...properties,
                version: VERSION,
                widget_ue_connectable: properties.widget_ue_connectable || saved?.widget_ue_connectable || {},
                input_ue_unconnectable: {}
            }
        }
        node.setProperty("group_restricted", undefined)
        node.setProperty("color_restricted", undefined)
        node.setProperty("widget_ue_connectable", undefined)
    }
    if (inferred_widget_inputs) {
        properties.widget_ue_connectable = {
            ...(properties.widget_ue_connectable || {}),
            ...inferred_widget_inputs
        }
    }
    node.setProperty("ue_properties", properties)
    convert_node_types(node)
}

function convert_node_types(node) {
    if (!is_UEnode(node)) return

    const properties = { ...properties_for(node) }
    if (node.comfyClass=="Anything Everywhere?") {
        node.widgets.all().forEach((widget)=>widget.setHidden(true))
        if (node.getTitle()=="Anything Everywhere?") node.setTitle("Anything Everywhere")
    } else if (node.comfyClass=="Anything Everywhere3") {
        if (node.getTitle()=="Anything Everywhere3") node.setTitle("Anything Everywhere")
    } else if (node.comfyClass=="Seed Everywhere") {
        node.setProperty("ue_convert", true)
        properties.fixed_inputs = true
        properties.seed_inputs  = true
        properties.input_regex  = properties.input_regex || i18n_functional('seed_input_regex')
    } else if (node.comfyClass=="Prompts Everywhere") {
        if (node.getTitle()=="Prompts Everywhere") node.setTitle("Anything Everywhere")
        properties.fixed_inputs = false
        node.inputs.at(0)?.modify({ label:i18n_functional('positive') })
        node.inputs.at(1)?.modify({ label:i18n_functional('negative') })
        properties.keep_inputs = [0,1]
    }

    ALL_REGEXES.forEach((r)=>{
        const rname = `${r}_regex`
        if (properties[rname]==".*") properties[rname] = undefined
    })
    node.setProperty("ue_properties", properties)
}

/*
COMPATIBILITY: the retired Anything Everywhere variants and Seed Everywhere keep
their registered type. The original reassigned node.type after construction;
that entity identity mutation is not published. Their supplier behavior is
selected from comfyClass instead.
*/
