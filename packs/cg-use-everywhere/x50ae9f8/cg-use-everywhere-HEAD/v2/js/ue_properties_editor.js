import { comfy } from '/comfy/api/v2.js';

import { i18n, GROUP_RESTRICTION_OPTIONS, COLOR_RESTRICTION_OPTIONS, REPEATED_TYPE_OPTIONS } from "./i18n.js";
import { default_priority } from "./ue_properties.js";

const REGEXES = ['title', 'input', 'group']

function create_element(tag, parent, options={}) {
    const elem = document.createElement(tag)
    if (parent) parent.appendChild(elem)
    Object.assign(elem, options)
    return elem
}

function properties_for(node) {
    return node.getProperty("ue_properties") || {}
}

export function edit_restrictions(node) {
    comfy.ui.showDialog({
        key: 'use-everywhere-restrictions',
        title: `Restrictions for node #${node.id}`,
        render(container) {
            container.appendChild(create_editor_html(node))
        }
    })
}

function add_row(table, header) {
    const row = document.createElement('div')
    row.className = 'ue_properties_row'
    table.appendChild(row)
    const header_elem = document.createElement('span')
    header_elem.className = 'ue_properties_title'
    header_elem.innerText = header
    row.appendChild(header_elem)
    return row
}

function add_cell(row, cell) {
    const td = document.createElement('span')
    td.className = 'ue_properties_cell'
    row.appendChild(td)
    td.appendChild(cell)
}

function changed(node, root, property, value) {
    node.setProperty("ue_properties", { ...properties_for(node), [property]:value })

    const priority = root.querySelector('#priority_value')
    if (priority && !properties_for(node).priority) {
        priority.value = `${default_priority(node)}`
    }

    const elem = root.querySelector(`#${property}_value`)
    if (elem) elem.style.opacity = value ? "1" : "0.5"
}

function create_editor_html(node) {
    const table = document.createElement('div')
    table.className = 'ue_properties_table'

    for (var i=0; i<=2; i++) {
        const name = REGEXES[i]
        const row = add_row(table, `${i18n(name)} regex`)
        const contents = create_element('span', null, {'className':'regex_input_container'})
        const checkbox_props = {
            type:'checkbox',
            id:`${name}_regex_invert`,
            checked: properties_for(node)[`${name}_regex_invert`] ? true : undefined,
            className: 'checkbox'
        }
        create_element('input', contents, checkbox_props).
            addEventListener('input', (e)=>{ changed(node, table, `${name}_regex_invert`, e.target.checked); } )

        create_element('span', contents, {innerText:i18n('Invert'), className:'regex_checkbox_label'})
        create_element('input', contents, {type:'text', value:properties_for(node)[`${name}_regex`] || ''}).
            addEventListener('input', (e)=>{ changed(node, table, `${name}_regex`, e.target.value)})

        if (i==2) row.classList.add('break_below')
        add_cell(row,contents)
    }

    const gr_row    = add_row(table, i18n("Group"))
    const gr_select = document.createElement('select')
    add_cell(gr_row,gr_select)
    add_select_options(node, table, gr_select, GROUP_RESTRICTION_OPTIONS, `group_restricted`)

    const col_row    = add_row(table, i18n("Color"))
    const col_select = document.createElement('select')
    add_cell(col_row,col_select)
    add_select_options(node, table, col_select, COLOR_RESTRICTION_OPTIONS, `color_restricted` )
    col_row.classList.add('break_below')

    const repeated_type_row = add_row(table, i18n("Repeated Types"))
    const repeated_type_select = document.createElement('select')
    add_cell(repeated_type_row,repeated_type_select)
    add_select_options(node, table, repeated_type_select, REPEATED_TYPE_OPTIONS, `repeated_type_rule`)

    const apply_to_unrepeated_row = add_row(table, i18n("Apply to Unrepeated"))
    const apply_to_unrepeated_select = document.createElement('select')
    add_cell(apply_to_unrepeated_row, apply_to_unrepeated_select)
    add_select_options(node, table, apply_to_unrepeated_select, ["no", "yes"], `apply_to_unrepeated`)
    apply_to_unrepeated_row.classList.add('break_below')

    if (node.inputs.all().some((input)=>input.type=="STRING")) {
        const send_to_combos_row = add_row(table, i18n("String to Combos"))
        const send_to_combos_select = document.createElement('select')
        add_cell(send_to_combos_row, send_to_combos_select)
        add_select_options(node, table, send_to_combos_select, ["no", "yes"], `string_to_combo`)
        send_to_combos_row.classList.add('break_below')
    }

    const send_to_any_row = add_row(table, i18n("Send to Any"))
    const send_to_any_select = document.createElement('select')
    add_cell(send_to_any_row, send_to_any_select)
    add_select_options(node, table, send_to_any_select, ["no", "yes"], `send_to_any`)
    send_to_any_row.classList.add('break_below')

    const priority_row = add_row(table, i18n("Priority"))
    const priority_edit = document.createElement("input")
    priority_edit.value = `${properties_for(node).priority || default_priority(node)}`
    priority_edit.addEventListener('input', ()=>{
        const p = parseInt(priority_edit.value)
        if (p) changed(node, table, `priority`, p)
        if (priority_edit.value=='') changed(node, table, `priority`, undefined)
    })
    priority_edit.id = 'priority_value'
    if (!properties_for(node).priority) priority_edit.style.opacity = 0.5
    add_cell(priority_row,priority_edit)
    priority_row.classList.add('break_below')

    return table
}

function add_select_options(node, root, select, OPTIONS, property) {
    OPTIONS.forEach((txt, i)=>{
        const option = document.createElement('option')
        option.value = `${i}`
        option.innerText = txt
        select.appendChild(option)
    })
    select.value = `${properties_for(node)[property] || 0}`
    select.addEventListener('input', ()=>{ changed(node, root, property, parseInt(select.value))})
}
