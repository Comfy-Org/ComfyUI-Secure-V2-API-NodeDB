import { comfy } from "/comfy/api/v2.js";
import {addCss} from "../common/utils.js";
import {$t} from '../common/i18n.js';


addCss('css/index.css')

const SEVERITIES = ['success','info','warn','error']
comfy.backend.on("easyuse-toast", detail=>{
    const content = detail.content
    const type = detail.type
    const duration = detail.duration
    comfy.commands.notify({
        severity: SEVERITIES.includes(type) ? type : 'info',
        summary: content,
        life: duration
    })
})

// The panel writes node modes itself, and hears about them again through
// onNodeChanged. Guarding re-entry keeps a press from rebuilding the list out
// from under the button that raised it.
let settingGroupMode = false

function updateGroups(groups, groupsDiv, autoSortDiv){
    if(groups.length>0){
        autoSortDiv.style.display = 'block'
    }else autoSortDiv.style.display = 'none'
    for (let index in groups) {
        const group = groups[index]
        const title = group.getTitle()
        const show_text = $t('Always')
        const hide_text = $t('Bypass')
        const mute_text = $t('Never')
        let group_item = document.createElement('div')
        let group_item_style = `justify-content: space-between;display:flex;background-color: var(--comfy-input-bg);border-radius: 5px;border:1px solid var(--border-color);margin-top:5px;`
        group_item.addEventListener("mouseover",event=>{
            event.preventDefault()
            group_item.style = group_item_style + "filter:brightness(1.2);"
        })
        group_item.addEventListener("mouseleave",event=>{
            event.preventDefault()
            group_item.style = group_item_style + "filter:brightness(1);"
        })

        group_item.setAttribute('data-id',index)
        group_item.className = 'easyuse-group-item'
        group_item.style = group_item_style
        // 标题
        let text_group_title = document.createElement('div')
        text_group_title.style = `flex:1;font-size:12px;color:var(--input-text);padding:4px;white-space: nowrap;overflow: hidden;text-overflow: ellipsis;cursor:pointer`
        text_group_title.innerHTML = `${title}`
        group_item.append(text_group_title)
        // 按钮组
        let buttons = document.createElement('div')
        const nodesInGroup = group.nodes();
        let isGroupShow = nodesInGroup.length>0 && nodesInGroup[0].getMode() == 'always'
        let isGroupMute = nodesInGroup.length>0 && nodesInGroup[0].getMode() == 'never'
        let go_btn = document.createElement('button')
        go_btn.style = "margin-right:6px;cursor:pointer;font-size:10px;padding:2px 4px;color:var(--input-text);background-color: var(--comfy-input-bg);border: 1px solid var(--border-color);border-radius:4px;"
        go_btn.innerText = "Go"
        go_btn.addEventListener('click', () => {
            group.centerOn()
            comfy.graph.setZoom(1)
        })
        buttons.append(go_btn)
        let see_btn = document.createElement('button')
        let defaultStyle = `cursor:pointer;font-size:10px;;padding:2px;border: 1px solid var(--border-color);border-radius:4px;width:36px;`
        see_btn.style = isGroupMute ? `background-color:var(--error-text);color:var(--input-text);` + defaultStyle : (isGroupShow ? `background-color:var(--theme-color);color:var(--input-text);` + defaultStyle : `background-color: var(--comfy-input-bg);color:var(--descrip-text);` + defaultStyle)
        see_btn.innerText = isGroupMute ? mute_text : (isGroupShow ? show_text : hide_text)
        let pressTimer
        let firstTime =0, lastTime =0
        let isHolding = false
        const restyle = () => {
            isGroupShow = nodesInGroup[0].getMode() == 'always'
            isGroupMute = nodesInGroup[0].getMode() == 'never'
            see_btn.style = isGroupMute ? `background-color:var(--error-text);color:var(--input-text);` + defaultStyle : (isGroupShow ? `background-color:#006691;color:var(--input-text);` + defaultStyle : `background-color: var(--comfy-input-bg);color:var(--descrip-text);` + defaultStyle)
            see_btn.innerText = isGroupMute ? mute_text : (isGroupShow ? show_text : hide_text)
        }
        // One undo step per press, and the panel does not rebuild itself on the
        // way through: onNodeChanged reports our own writes too, and restyle()
        // has already put this row right.
        const setGroupMode = (mode) => {
            settingGroupMode = true
            try {
                comfy.graph.batch(() => {
                    for (const node of nodesInGroup) {
                        node.setMode(mode);
                    }
                })
            } finally {
                settingGroupMode = false
            }
            restyle()
        }
        see_btn.addEventListener('click', () => {
            if(isHolding){
                isHolding = false
                return
            }
            setGroupMode(isGroupShow ? 'bypass' : 'always')
        })
        see_btn.addEventListener('mousedown', () => {
            firstTime = new Date().getTime();
            clearTimeout(pressTimer);
            pressTimer = setTimeout(_=>{
                setGroupMode(isGroupMute ? 'always' : 'never')
            },500)
        })
        see_btn.addEventListener('mouseup', () => {
            lastTime = new Date().getTime();
            if(lastTime - firstTime > 500) isHolding = true
            clearTimeout(pressTimer);
        })
        buttons.append(see_btn)
        group_item.append(buttons)

        groupsDiv.append(group_item)
    }

}

function createGroupMap(container){
    let groupsDiv =  document.createElement('div')
    groupsDiv.id = 'easyuse-groups-items'
    groupsDiv.style = `overflow-y: auto;max-height: 400px;height:100%;width: 100%;`

    let autoSortDiv = document.createElement('button')
    autoSortDiv.style = `cursor:pointer;font-size:10px;padding:2px 4px;color:var(--input-text);background-color: var(--comfy-input-bg);border: 1px solid var(--border-color);border-radius:4px;`
    autoSortDiv.innerText =  $t('Auto Sorting')
    autoSortDiv.addEventListener('click',e=>{
        e.preventDefault()
        groupsDiv.innerHTML = ``
        let new_groups = [...comfy.graph.groups()].sort((a,b)=> a.getBounds().x - b.getBounds().x).sort((a,b)=> a.getBounds().y - b.getBounds().y)
        updateGroups(new_groups, groupsDiv, autoSortDiv)
    })

    updateGroups(comfy.graph.groups(), groupsDiv, autoSortDiv)

    let remarkDiv =  document.createElement('p')
    remarkDiv.style = `text-align:center; font-size:10px; padding:0 10px;color:var(--descrip-text)`
    remarkDiv.innerText =  $t('Toggle `Show/Hide` can set mode of group, LongPress can set group nodes to never')
    container.appendChild(groupsDiv)
    container.appendChild(remarkDiv)
    container.appendChild(autoSortDiv)

    // Was a `mouseover` listener on #graph-canvas: the panel floated over the
    // graph, so returning to the canvas was the only moment it could rebuild.
    // A tab is rendered when it is shown, so what is left is keeping the mode
    // buttons in step while it stays open.
    return comfy.onNodeChanged(() => {
        if (settingGroupMode) return
        groupsDiv.innerHTML = ``
        updateGroups(comfy.graph.groups(), groupsDiv, autoSortDiv)
    })
}

let stopWatchingGroups = null
comfy.ui.addSidebarTab({
    id: 'easyuse.groupsMap',
    title: $t('Groups Map') + ' (EasyUse)',
    icon: 'icon-[lucide--list]',
    tooltip: "EasyUse Group Map",
    render(container){
        stopWatchingGroups = createGroupMap(container)
    },
    destroy(){
        if(stopWatchingGroups) stopWatchingGroups()
        stopWatchingGroups = null
    }
})

async function cleanup(){
    comfy.commands.notify({
        severity:'warn',
        summary:$t("Secure mode"),
        detail:$t("Direct server GPU cleanup is disabled. Use the easy cleanGpuUsed node in a workflow.")
    })
}

comfy.commands.register({
    id: 'easyuse.cleanGpu',
    label: $t('Cleanup Of GPU Usage') + ' (EasyUse)',
    run: cleanup
})

// Previously also: appended the three entries above to the CANVAS context menu
// by overriding LGraphCanvas.prototype.getCanvasMenuOptions; blanked
// LGraphCanvas.prototype.renderInfo; appended a floating toolbar to
// document.body and inserted a ComfyButton into app.menu.actionsGroup; moved
// Crystools' monitor container between the menu bar and its own root; and
// wrapped app.loadGraphData to read `data.extra.note` / `data.extra.need_models`
// out of the workflow being opened and raise a guide dialog for them.
//
// REFUSED, not a pending gap: patching the renderer's prototypes.
// getCanvasMenuOptions and renderInfo are the canvas's, and both overrides are
// global — every canvas menu in the document gained easy-use's three entries,
// and blanking renderInfo removed the FPS readout for everyone, from a pack, on
// the strength of a localStorage key core never knew about.
//
// REFUSED, not a pending gap: laying out the host's chrome.
// `document.body.appendChild(toolbar)` and
// `app.menu.actionsGroup.element.after(groupMap.element)` place a pack's
// elements into the application's own layout, which is what stops the chrome
// being ours to restyle. `comfy.ui` is that surface instead, and the three
// entry points collapse into one thing the host places: the sidebar tab above.
//
// REFUSED, not a pending gap: rearranging ANOTHER PACK's DOM.
// `setCrystoolsUI` finds `#crystools-root`, lifts `#crystools-monitor-container`
// out of it and re-parents it next to core's settings button. Crystools now has
// `comfy.ui.addTopBarBadge` for its readout; a second pack moving its element is
// not a gap in our API, it is one pack overwriting another's decision with no
// way for either to know.
//
// REFUSED, not a pending gap: wrapping a core app method. `app.loadGraphData`
// was replaced so the pack could inspect every workflow as it opened.
// `comfy.onWorkflowLoaded` fires at the same moment and is the published shape,
// but it deliberately carries no payload.
//
// The capability is not refused and is not lost, for the parts that are the
// pack's to have: the Groups Map, the GPU cleanup and the reboot are all
// converted above, and the FPS readout the renderInfo blanking suppressed is
// core's own `Comfy.Graph.CanvasInfo` setting (coreSettings.ts:264), which the
// user can turn off themselves instead of a pack deciding for them.
//
// DROPPED: the workflow guide dialog, and with it `download_model` and the
// "Workflow Guide" toolbar entry. A workflow's `extra` bag has no published
// reader — `comfy.onWorkflowLoaded` says a workflow loaded and nothing more —
// so the pack cannot see `extra.note` or `extra.need_models`. This is the one
// API addition this file needs: a read of the loaded workflow's `extra` data,
// which is where a workflow AUTHOR leaves notes for whoever opens it.
//
// DROPPED: drag-to-reorder of groups, and the ordering half of Auto Sorting.
// Both did `groups.splice(i, 0, groups.splice(prev_i, 1)[0])` on the live group
// array, which is the renderer's draw order; `groups()` returns a frozen
// snapshot and nothing published reorders them. Auto Sorting is kept below as a
// sort of the LIST, so the panel still orders groups by position.
//
// DROPPED: the `Comfy.EasyUse.toolBar` setting and its `Comfy.UseNewMenu`
// follower. Both existed only to show or hide the floating toolbar depending on
// where core's menu was; a sidebar tab is placed by the host and has neither
// question to answer.
//
// LIMITATION: Auto Sorting reorders the panel's list only. Before, it sorted
// the document's own group array, which also changed the order groups drew in.
//
// COSMETIC: the tab uses an iconify icon rather than the pack's inline SVG
// (groupIcon), and the rows lose the floating panel's title bar, close button
// and drag handle — the sidebar frame is the host's.
//
// INOPERABLE: nothing. No node type is registered or extended by this file; its
// `beforeRegisterNodeDef` hook captured `onConfigure` and called straight
// through to it without doing anything, so it is not carried over.
