import { comfy } from '/comfy/api/v2.js';

import { any_restrictions, describe_restrictions } from "./ue_properties.js";
import { create } from "./use_everywhere_utilities.js";

const HOVERTIME = 500
const timers = new Map()
const ue_tooltip_element = create('span', 'ue_tooltip', document.body, {id:'ue_tooltip'})

function show_tooltip(node) {
    if (!comfy.settings.get('Use Everywhere.Graphics.tooltips')) return
    if (!any_restrictions(node)) return
    const rect = node.getScreenRect()
    if (!rect) return
    ue_tooltip_element.style.display = "block"
    ue_tooltip_element.style.left = `${rect.x+rect.width+10}px`
    ue_tooltip_element.style.top = `${rect.y+5}px`
    ue_tooltip_element.innerHTML = ""
    ue_tooltip_element.appendChild(describe_restrictions(node))
}

function hide_tooltip(node) {
    const timer = timers.get(node.id)
    if (timer) clearTimeout(timer)
    timers.delete(node.id)
    ue_tooltip_element.style.display = "none"
}

comfy.defs.extend(/.*/, (b) => {
    b.onHover((node, hovering) => {
        hide_tooltip(node)
        if (hovering) {
            timers.set(node.id, setTimeout(()=>show_tooltip(node), HOVERTIME))
        }
    })
})
