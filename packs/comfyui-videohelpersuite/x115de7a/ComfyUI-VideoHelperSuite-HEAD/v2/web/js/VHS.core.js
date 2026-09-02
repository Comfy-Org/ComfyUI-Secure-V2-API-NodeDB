import { comfy } from '/comfy/api/v2.js';

// NOT A GAP: builder hooks always have a target, so the old "Tried to add callback to non-existant object" guard from chainCallback cannot fire.

//Per-node state. Handles hold no arbitrary properties, so everything the pack
//used to hang off `this` lives here, keyed by node id and dropped on removal.
const nodeStates = new Map()
function nodeState(id) {
    let s = nodeStates.get(id)
    if (!s) {
        s = {}
        nodeStates.set(id, s)
    }
    return s
}

function allGraphs() {
    return [comfy.graph, ...comfy.graph.subgraphs()]
}
function getNodeById(id) {
    return comfy.executionNode(String(id))
}

const convDict = {
    VHS_LoadImages : ["directory", null, "image_load_cap", "skip_first_images", "select_every_nth"],
    VHS_LoadImagesPath : ["directory", "image_load_cap", "skip_first_images", "select_every_nth"],
    VHS_VideoCombine : ["frame_rate", "loop_count", "filename_prefix", "format", "pingpong", "save_image"],
    VHS_LoadVideo : ["video", "force_rate", "force_size", "frame_load_cap", "skip_first_frames", "select_every_nth"],
    VHS_LoadVideoPath : ["video", "force_rate", "force_size", "frame_load_cap", "skip_first_frames", "select_every_nth"],
};
const renameDict  = {VHS_VideoCombine : {save_output : "save_image"}}
function useKVState(b) {
    //The onSerialize half of this is deleted, not translated. Widget values are
    //name-keyed at runtime (widgetValueStore is graphId:nodeId:name), so the dict
    //the pack used to write into widgets_values only ever described the legacy
    //serialized form. Core writes the positional array; what has to be kept is
    //reading every shape a saved workflow may already be in.
    b.onConfigured(function(node, info) {
        if (!node.widgets.length) {
            //Node has no widgets, there is nothing to restore
            return
        }
        if (typeof(info.widgets_values) != "object") {
            //widgets_values is in some unknown inactionable format
            return
        }
        let widgetDict = info.widgets_values
        if (info.widgets_values.length) {
            //widgets_values is in the old list format
            if (node.type in convDict) {
                //widget does not have a conversion format provided
                let convList = convDict[node.type];
                if(info.widgets_values.length >= convList.length) {
                    //has all required fields
                    widgetDict = {}
                    for (let i = 0; i < convList.length; i++) {
                        if(!convList[i]) {
                            //Element should not be processed (upload button on load image sequence)
                            continue
                        }
                        widgetDict[convList[i]] = info.widgets_values[i];
                    }
                } else {
                    //widgets_values is missing elements marked as required
                    //let it fall through to failure state
                }
            }
        }
        if ('force_size' in widgetDict) {
            //force size has been phased out, Migrate state
            if (widgetDict.force_size.includes?.('x')) {
                let sizes = widgetDict.force_size.split('x')
                if (sizes[0] != '?') {
                    widgetDict.custom_width = parseInt(sizes[0])
                } else {
                    widgetDict.custom_width = 0
                }
                if (sizes[1] != '?') {
                    widgetDict.custom_height = parseInt(sizes[1])
                } else {
                    widgetDict.custom_height = 0
                }
            } else {
                if (['Disabled', 'Custom Height'].includes(widgetDict.force_size)) {
                    widgetDict.custom_width = 0
                }
                if (['Disabled', 'Custom Width'].includes(widgetDict.force_size)) {
                    widgetDict.custom_height = 0
                }
            }
        }
        if (widgetDict.videopreview?.params?.force_size) {
            delete widgetDict.videopreview.params.force_size
        }
        if (widgetDict.length == undefined) {
            for (let w of node.widgets) {
                if (w.widgetType == "button") {
                    continue
                }
                if (w.name in widgetDict) {
                    w.setValue(widgetDict[w.name]);
                } else {
                    //Check for a legacy name that needs migrating
                    if (node.type in renameDict && w.name in renameDict[node.type]) {
                        if (renameDict[node.type][w.name] in widgetDict) {
                            w.setValue(widgetDict[renameDict[node.type][w.name]])
                            continue
                        }
                    }
                    //attempt to restore default value
                    //The def's raw input spec is not published, but core builds the
                    //widget's options from it, so the default is still reachable.
                    let opts = w.getOptions();
                    let initialValue = null;
                    if (opts?.default != undefined) {
                        initialValue = opts.default;
                    } else if (opts?.values?.length) {
                        initialValue = opts.values[0];
                    }
                    if (initialValue) {
                        w.setValue(initialValue);
                    }
                }
            }
        } else {
            //Saved data was not a map made by this method
            //and a conversion dict for it does not exist
            //It's likely an array and that has been blindly applied
            if (info?.widgets_values?.length != node.widgets.length) {
                //Widget could not have restored properly
                comfy.commands.notify({severity: 'error',
                    summary: "Failed to restore node: " + node.getTitle(),
                    detail: "Please remove and re-add it."})
                node.setBgColor("#C00")
            }
        }
    });
}
//The duplicate check needs a stash shared by two copies of this file, which is
//what the app object was being used for. The pack's own global does the same job
//without holding the app open.
var helpDOM = window.VHSHelp;
if (!window.VHSHelp) {
    helpDOM = document.createElement("div");
    window.VHSHelp = helpDOM
} else {
    comfy.commands.notify({severity: 'error', summary: 'Duplicate VHS install detected',
        detail: 'Please check your custom_nodes directory and manually remove the duplicate.'})
    throw new Error('Duplicate VHS install detected. Check your custom_nodes directory')
}
function initHelpDOM() {
    let parentDOM = document.createElement("div");
    parentDOM.className = "VHS_floatinghelp"
    document.body.appendChild(parentDOM)
    parentDOM.appendChild(helpDOM)
    helpDOM.className = "litegraph";
    let scrollbarStyle = document.createElement('style');
    scrollbarStyle.innerHTML = `
            .VHS_floatinghelp {
                scrollbar-width: 6px;
                scrollbar-color: #0003  #0000;
                &::-webkit-scrollbar {
                    background: transparent;
                    width: 6px;
                }
                &::-webkit-scrollbar-thumb {
                    background: #0005;
                    border-radius: 20px
                }
                &::-webkit-scrollbar-button {
                    display: none;
                }
            }
            .VHS_loopedvideo::-webkit-media-controls-mute-button {
                display:none;
            }
            .VHS_loopedvideo::-webkit-media-controls-fullscreen-button {
                display:none;
            }
    `
    scrollbarStyle.id = 'scroll-properties'
    parentDOM.appendChild(scrollbarStyle)
    Object.assign(parentDOM.style, {
        left: '-5000px',
        top: '10px',
        width: "400px",
        minHeight: "100px",
        maxHeight: "600px",
        overflowY: 'scroll',
        transformOrigin: '0 0',
        fontSize: '18px',
        backgroundColor: '#353535',
        boxShadow: '0 0 10px black',
        borderRadius: '4px',
        padding: '3px',
        zIndex: 3,
        position: "fixed",
        display: 'inline',
    });
    const positionHelp = () => {
        const rect = helpDOM.node?.getScreenRect()
        if (!rect) {
            parentDOM.style.left = '-5000px'
            return
        }
        parentDOM.style.left = Math.min(window.innerWidth - parentDOM.offsetWidth,
            rect.x + rect.width + 8) + 'px'
        parentDOM.style.top = Math.max(8, Math.min(window.innerHeight - 100, rect.y)) + 'px'
    }
    comfy.onViewportChanged(positionHelp)
    comfy.onNodeMoved(({node}) => {
        if (helpDOM.node && comfy.sameEntity(helpDOM.node, node)) {
            positionHelp()
        }
    })
    function setCollapse(el, doCollapse) {
        if (doCollapse) {
            el.children[0].children[0].innerHTML = '+'
            Object.assign(el.children[1].style, {
                color: '#CCC',
                overflowX: 'hidden',
                width: '0px',
                minWidth: 'calc(100% - 20px)',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
            })
            for (let child of el.children[1].children) {
                if (child.style.display != 'none'){
                    child.origDisplay = child.style.display
                }
                child.style.display = 'none'
            }
        } else {
            el.children[0].children[0].innerHTML = '-'
            Object.assign(el.children[1].style, {
                color: '',
                overflowX: '',
                width: '100%',
                minWidth: '',
                textOverflow: '',
                whiteSpace: '',
            })
            for (let child of el.children[1].children) {
                child.style.display = child.origDisplay
            }
        }
    }
    helpDOM.collapseOnClick = function() {
        let doCollapse = this.children[0].innerHTML == '-'
        setCollapse(this.parentElement, doCollapse)
    }
    helpDOM.selectHelp = function(name, value) {
        //attempt to navigate to name in help
        function collapseUnlessMatch(items,t) {
            var match = items.querySelector('[vhs_title="' + t + '"]')
            if (!match) {
                for (let i of items.children) {
                    if (i.innerHTML.slice(0,t.length+5).includes(t)) {
                        match = i
                        break
                    }
                }
            }
            if (!match) {
                return null
            }
            //For longer documentation items with fewer collapsable elements,
            //scroll to make sure the entirety of the selected item is visible
            //This has the unfortunate side effect of trying to scroll the main
            //window if the documentation windows is forcibly offscreen,
            //but it's easy to simply scroll the main window back and seems to
            //have no visual side effects
            match.scrollIntoView(false)
            window.scrollTo(0,0)
            for (let i of items.querySelectorAll('.VHS_collapse')) {
                if (i.contains(match)) {
                    setCollapse(i, false)
                } else {
                    setCollapse(i, true)
                }
            }
            return match
        }
        let target = collapseUnlessMatch(helpDOM, name)
        if (target && value) {
            collapseUnlessMatch(target, value)
        }
    }
    helpDOM.addHelp = function(node, description) {
        if (!description) {
            return
        }
        if (helpDOM.node && comfy.sameEntity(helpDOM.node, node)) {
            helpDOM.node = undefined
            helpDOM.parentElement.style['left'] = '-5000px'
            return
        }
        helpDOM.node = node;
        helpDOM.innerHTML = description || "no help provided "
        for (let e of helpDOM.querySelectorAll('.VHS_collapse')) {
            e.children[0].onclick = helpDOM.collapseOnClick
            e.children[0].style.cursor = 'pointer'
        }
        for (let e of helpDOM.querySelectorAll('.VHS_precollapse')) {
            setCollapse(e, true)
        }
        for (let e of helpDOM.querySelectorAll('.VHS_loopedvideo')) {
            e?.play()
        }
        positionHelp()
        helpDOM.parentElement.scrollTo(0,0)
    }
    document.addEventListener('pointermove', (event) => {
        const node = helpDOM.node
        const screen = node?.getScreenRect()
        const bounds = node?.getBounds()
        if (!node || !screen || !bounds || !screen.width || !screen.height ||
            !bounds.width || !bounds.height) return
        let nearest
        for (const side of ['input', 'output']) {
            const slots = side == 'input' ? node.inputs : node.outputs
            for (let i = 0; i < slots.length; i++) {
                const point = node.getSlotPosition(side, i)
                if (!point) continue
                const x = screen.x + (point.x - bounds.x) * screen.width / bounds.width
                const y = screen.y + (point.y - bounds.y) * screen.height / bounds.height
                const distance = Math.hypot(event.clientX - x, event.clientY - y)
                if (distance < 14 && (!nearest || distance < nearest.distance)) {
                    nearest = {distance, name: slots.at(i).name}
                }
            }
        }
        if (nearest) helpDOM.selectHelp(nearest.name)
    })
    // COSMETIC: slot hover still focuses its help entry; widget-row geometry is not
    // published, so widget help is reached by scrolling the already-open panel.
}

function fitHeight(node) {
    //Declared rather than re-asserted: the mounted preview is of unknown height and
    //the node should grow to fit it.
    node.setSizeConstraints({autoHeight: true})
}
// COSMETIC: the preview remains an interactive media surface, so the node is dragged
// from its title or body rather than by grabbing the preview itself.

async function uploadFile(file, progressCallback) {
    try {
        // Wrap file in formdata so it includes filename
        const body = new FormData();
        const i = file.webkitRelativePath.lastIndexOf('/');
        const subfolder = file.webkitRelativePath.slice(0,i+1)
        const new_file = new File([file], file.name, {
            type: file.type,
            lastModified: file.lastModified,
        });
        body.append("image", new_file);
        if (i > 0) {
            body.append("subfolder", subfolder);
        }
        const url = comfy.backend.url("/upload/image")
        const resp = await new Promise((resolve) => {
            let req = new XMLHttpRequest()
            req.upload.onprogress = (e) => progressCallback?.(e.loaded/e.total)
            req.onload = () => resolve(req)
            req.open('post', url, true)
            req.send(body)
        })

        if (resp.status !== 200) {
            alert(resp.status + " - " + resp.statusText);
        }
        return resp
    } catch (error) {
        alert(error);
    }
}

function rejectVaeFromUseEverywhere(node) {
    const current = node.getProperty('ue_properties')
    const properties = current && typeof current == 'object' ? current : {}
    const inputRules = properties.input_ue_unconnectable &&
        typeof properties.input_ue_unconnectable == 'object'
        ? properties.input_ue_unconnectable : {}
    node.setProperty('ue_properties', {
        ...properties,
        input_ue_unconnectable: {...inputRules, vae: true},
    })
}

function addVAEOutputToggle(b) {
    b.onCreated(rejectVaeFromUseEverywhere)
    b.onConnectionsChanged(function(node, event) {
        if (event.side != 'input') {
            return
        }
        let slotType = node.inputs.at(event.index)?.type
        if (slotType != "VAE") {
            return
        }
        const out = node.outputs.at(0)
        if (!out) {
            return
        }
        const s = nodeState(node.id)
        if (event.connected) {
            if (s.linkTimeout) {
                clearTimeout(s.linkTimeout)
                s.linkTimeout = false
            } else if (out.type == "IMAGE") {
                s.linkTimeout = setTimeout(() => {
                    const later = node.outputs.at(0)
                    if (!later || later.type != "IMAGE") {
                        return
                    }
                    s.linkTimeout = false
                    later.disconnect();
                }, 50)
            }
            out.modify({name: 'LATENT', type: 'LATENT'});
        } else{
            if (out.type == "LATENT") {
                s.linkTimeout = setTimeout(() => {
                    s.linkTimeout = false
                    const later = node.outputs.at(0)
                    if (later) {
                        later.disconnect();
                    }
                }, 50)
            }
            out.modify({name: "IMAGE", type: "IMAGE"});
        }
    });
}
function addVAEInputToggle(b) {
    b.onCreated(rejectVaeFromUseEverywhere)
    b.onConnectionsChanged(function(node, event) {
        const vae = node.inputs.at(3)
        const first = node.inputs.at(0)
        if (event.side == 'input' && event.index == 3 && vae?.type == "VAE" && first) {
            const s = nodeState(node.id)
            if (event.connected) {
                if (s.linkTimeout) {
                    clearTimeout(s.linkTimeout)
                    s.linkTimeout = false
                } else if (first.type == "IMAGE") {
                    s.linkTimeout = setTimeout(() => {
                        //workaround for out of order loading
                        const later = node.inputs.at(0)
                        if (!later || later.type != "IMAGE") {
                            return
                        }
                        s.linkTimeout = false
                        later.disconnect();
                    }, 50)
                }
                first.modify({type: 'LATENT'});
            } else {
                if (first.type == "LATENT") {
                    s.linkTimeout = setTimeout(() => {
                        s.linkTimeout = false
                        const later = node.inputs.at(0)
                        if (later) {
                            later.disconnect();
                        }
                    }, 50)
                }
                first.modify({type: "IMAGE"});
            }
        }
    });
}
function initializeLoadFormat(b) {
    const formats = b.def.inputs.find((input) => input.name == 'format')?.options?.formats
    b.onCreated(function(node) {
        let formatWidget = node.widgets.get("format")
        if (!formatWidget) {
            return
        }
        let base = {}
        for (let w of node.widgets) {
           if (['force_rate', 'custom_width', 'custom_height',
               'frame_load_cap'].includes(w.name)) {
               //TODO: filter these options?
               base[w.name] = w.getOptions()
           }
        }
        formatWidget.on('change', function(value) {
            let format = formats?.[value]
            if (!format) {
                return
            }
            if ('target_rate' in format) {
                format.force_rate = {'reset': format.target_rate}
            }
            if ('dim' in format) {
                format.custom_width = {'step': format.dim[0], 'mod': format.dim[1]}
                format.custom_height = {'step': format.dim[0], 'mod': format.dim[1]}
                if (format.dim[2]) {
                    format.custom_width.reset = format.dim[2]
                }
                if (format.dim[3]) {
                    format.custom_height.reset = format.dim[3]
                }
            }
            if ('frames' in format) {
                format.frame_load_cap = {'step': format.frames[0], 'mod': format.frames[1]}
            }
            for (let w of node.widgets) {
                if (w.name in base) {
                    let wasDefault = w.getOptions()?.reset == w.getValue()
                    let merged = Object.assign({}, base[w.name], format[w.name])
                    for (let key in merged) {
                        w.setOption(key, merged[key])
                    }
                    if (wasDefault && merged.reset != undefined) {
                        w.setValue(merged.reset)
                    }
                    refreshVhsWidget(node, w.name)
                }
            }

        });
        setVhsWidgetAnnotation(node, 'frame_load_cap', (value) => {
            let maxFrames = nodeState(node.id).video_query?.loaded?.frames
            if (!maxFrames || value && value < maxFrames) return ''
            let format = formats?.[formatWidget.getValue()]
            const div = format?.frames?.[0] ?? 1
            const mod = format?.frames?.[1] ?? 0
            if ((maxFrames % div) != mod) {
                maxFrames = ((maxFrames - mod) / div | 0) * div + mod
            }
            return maxFrames + '\u21FD'
        })
        setVhsWidgetAnnotation(node, 'force_rate', (value) => {
            const fps = nodeState(node.id).video_query?.source?.fps
            return value == 0 && fps != undefined ? roundToPrecision(fps, 2) + '\u21FD' : ''
        })
    });
}

function setUploadProgress(node, progress) {
    const s = nodeState(node.id)
    s.uploadProgress = Math.max(0, Math.min(1, progress))
    s.removeUploadBadge ??= node.addBadge(() => ({
        text: Math.round(s.uploadProgress * 100) + '%',
    }))
}

function clearUploadProgress(node) {
    const s = nodeState(node.id)
    s.removeUploadBadge?.()
    delete s.removeUploadBadge
    delete s.uploadProgress
}

function installUploadDropTarget(element, state) {
    const dragover = (event) => {
        if (!state.uploadDroppedFile || !event.dataTransfer?.types?.includes('Files')) return
        event.preventDefault()
        event.dataTransfer.dropEffect = 'copy'
    }
    const drop = async (event) => {
        const file = event.dataTransfer?.files?.[0]
        if (!file || !state.uploadDroppedFile ||
            state.uploadAccept && !state.uploadAccept.includes(file.type)) return
        event.preventDefault()
        event.stopPropagation()
        await state.uploadDroppedFile(file)
    }
    element.addEventListener('dragover', dragover)
    element.addEventListener('drop', drop)
    return () => {
        element.removeEventListener('dragover', dragover)
        element.removeEventListener('drop', drop)
    }
}

function addUploadWidget(b, widgetName, type="video") {
    b.onCreated(function(node) {
        const s = nodeState(node.id)
        const pathWidget = node.widgets.get(widgetName);
        if (!pathWidget) {
            return
        }
        const fileInput = document.createElement("input");
        s.fileInput = fileInput
        if (type == "folder") {
            Object.assign(fileInput, {
                type: "file",
                style: "display: none",
                webkitdirectory: true,
                onchange: async () => {
                    const directory = fileInput.files[0].webkitRelativePath;
                    const i = directory.lastIndexOf('/');
                    if (i <= 0) {
                        throw "No directory found";
                    }
                    const path = directory.slice(0,directory.lastIndexOf('/'))
                    if (pathWidget.getOptions()?.values?.includes(path)) {
                        alert("A folder of the same name already exists");
                        return;
                    }
                    let successes = 0;
                    setUploadProgress(node, 0)
                    try {
                        const total = fileInput.files.length
                        for(const file of fileInput.files) {
                            const onProg = (progress) =>
                                setUploadProgress(node, (successes + progress) / total)
                            if ((await uploadFile(file, onProg)).status == 200) {
                                successes++;
                            } else {
                                if (successes > 0) {
                                    break
                                } else {
                                    return;
                                }
                            }
                        }
                    } finally {
                        clearUploadProgress(node)
                    }
                    const values = [...(pathWidget.getOptions()?.values ?? []), path]
                    pathWidget.setOption('values', values);
                    pathWidget.setValue(path);
                },
            });
        } else {
            let accept = {'video': ["video/webm","video/mp4","video/x-matroska","image/gif"],
                          'audio': ["audio/mpeg","audio/wav","audio/x-wav","audio/ogg"]}[type]
            async function doUpload(file) {
                setUploadProgress(node, 0)
                try {
                    let resp = await uploadFile(file, (progress) =>
                        setUploadProgress(node, progress))
                    if (resp.status != 200) {
                        return false
                    }
                    const filename = JSON.parse(resp.responseText).name;
                    const values = [...(pathWidget.getOptions()?.values ?? []), filename]
                    pathWidget.setOption('values', values);
                    pathWidget.setValue(filename);
                    return true
                } finally {
                    clearUploadProgress(node)
                }
            }
            s.uploadDroppedFile = doUpload
            s.uploadAccept = accept
            Object.assign(fileInput, {
                type: "file",
                accept: accept.join(','),
                style: "display: none",
                onchange: async () => {
                    if (fileInput.files.length) {
                        return await doUpload(fileInput.files[0])
                    }
                },
            });
        }
        document.body.append(fileInput);
        let uploadWidget = node.widgets.add({type: "button",
            name: "choose " + type + " to upload", value: "image",
            options: {serialize: false}});
        uploadWidget.on('activate', () => {
            fileInput.click();
        });
    });
    b.onRemoved(function(node) {
        nodeStates.get(node.id)?.fileInput?.remove();
    });
}
function addAudioPreview(b, isInput=true) {
    b.onCreated(function(node) {
        var element = document.createElement("audio");
        element.controls = true
        element.style['width'] = "100%"
        element.style['minHeight'] = "50px"
        const s = nodeState(node.id)
        s.preview = {params: {}}
        const removeDropTarget = installUploadDropTarget(element, s)
        node.widgets.mount({
            name: "audiopreview",
            height: 50,
            render: (container) => {
                container.appendChild(element)
            },
            destroy: () => {
                if (s.timeout) {
                    clearTimeout(s.timeout)
                }
                removeDropTarget()
                element.remove()
            },
        });
        s.updateParameters = (params, force_update) => {
            Object.assign(s.preview.params, params)
            if (!force_update &&
                comfy.settings.get("VHS.AdvancedPreviews") == 'Never') {
                return;
            }
            if (s.timeout) {
                clearTimeout(s.timeout);
            }
            if (force_update) {
                s.updateSource();
            } else {
                s.timeout = setTimeout(() => s.updateSource(),100);
            }
        };
        s.updateSource = function () {
            if (s.preview.params == undefined) {
                return;
            }
            let params =  {}
            let advp = comfy.settings.get("VHS.AdvancedPreviews")
            if (advp == 'Never') {
                advp = false
            } else if (advp == 'Input Only') {
                advp = isInput
            } else {
                advp = true
            }
            Object.assign(params, s.preview.params);//shallow copy
            params.timestamp = Date.now()
            // The legacy advanced endpoint parsed arbitrary host paths. Saved
            // broker output is already viewable through ComfyUI's core route.
            element.src = comfy.backend.url('/view?' + new URLSearchParams(params));
        }


        //setup widget tracking
        function update(key) {
            return function(value) {
                let params = {}
                params[key] = value
                s.updateParameters(params)
            }
        }
        let widgetMap = { 'seek_seconds': 'start_time', 'duration': 'duration',
            'start_time': 'start_time' }
        for (let w of node.widgets) {
            if (w.name in widgetMap) {
                const onValue = update(widgetMap[w.name])
                w.on('change', onValue)
                onValue(w.getValue())
            }
        }
    });
}

function addVideoPreview(b, isInput=true) {
    b.onCreated(function(node) {
        var element = document.createElement("div");
        const s = nodeState(node.id)
        s.preview = {hidden: false, paused: false, params: {},
            muted: comfy.settings.get("VHS.DefaultMute")}
        node.widgets.mount({
            name: "videopreview",
            render: (container) => {
                container.appendChild(element)
            },
            destroy: () => {
                if (s.timeout) {
                    clearTimeout(s.timeout)
                }
                removeDropTarget()
                element.remove()
            },
        });
        const removeDropTarget = installUploadDropTarget(element, s)
        //Other packs read the <video> element off this node. It is the first
        //<video> inside the mounted `.vhs_preview` container, reachable from the DOM.
        s.parentEl = document.createElement("div");
        s.parentEl.className = "vhs_preview";
        s.parentEl.style['width'] = "100%"
        element.appendChild(s.parentEl);
        s.videoEl = document.createElement("video");
        s.videoEl.controls = false;
        s.videoEl.loop = true;
        s.videoEl.muted = true;
        s.videoEl.style['width'] = "100%"
        s.videoEl.addEventListener("loadedmetadata", () => {
            fitHeight(node);
        });
        s.videoEl.addEventListener("error", () => {
            //TODO: consider a way to properly notify the user why a preview isn't shown.
            s.parentEl.hidden = true;
            fitHeight(node);
        });
        s.videoEl.onmouseenter =  () => {
            s.videoEl.muted = s.preview.muted
        };
        s.videoEl.onmouseleave = () => {
            s.videoEl.muted = true;
        };

        s.imgEl = document.createElement("img");
        s.imgEl.style['width'] = "100%"
        s.imgEl.hidden = true;
        s.imgEl.onload = () => {
            fitHeight(node);
        };
        s.parentEl.appendChild(s.videoEl)
        s.parentEl.appendChild(s.imgEl)
        s.updateParameters = (params, force_update) => {
            if (!Object.entries(params).some(([k,v]) => s.preview.params[k] !== v)) {
                return
            }
            Object.assign(s.preview.params, params)
            if (!force_update &&
                comfy.settings.get("VHS.AdvancedPreviews") == 'Never') {
                return;
            }
            if (s.timeout) {
                clearTimeout(s.timeout);
            }
            if (force_update) {
                s.updateSource();
            } else {
                s.timeout = setTimeout(() => s.updateSource(),100);
            }
        };
        s.updateSource = function () {
            if (s.preview.params == undefined) {
                return;
            }
            let params =  {}
            let advp = comfy.settings.get("VHS.AdvancedPreviews")
            if (advp == 'Never') {
                advp = false
            } else if (advp == 'Input Only') {
                advp = isInput
            } else {
                advp = true
            }
            Object.assign(params, s.preview.params);//shallow copy
            params.timestamp = Date.now()
            s.parentEl.hidden = s.preview.hidden;
            if (params.format?.split('/')[0] == 'video'
                || advp && (params.format?.split('/')[1] == 'gif')
                || params.format == 'folder') {

                s.videoEl.autoplay = !s.preview.paused && !s.preview.hidden;
                s.videoEl.src = comfy.backend.url('/view?' + new URLSearchParams(params));
                s.videoEl.hidden = false;
                s.imgEl.hidden = true;
            } else if (params.format?.split('/')[0] == 'image'){
                //Is animated image
                s.imgEl.src = comfy.backend.url('/view?' + new URLSearchParams(params));
                s.videoEl.hidden = true;
                s.imgEl.hidden = false;
            }
            delete s.video_query
            // Source probing now happens inside the brokered loader. VideoInfo
            // nodes expose the resulting metadata without a custom HTTP route.
        }
    });
}
let copiedPath = undefined
function previewURL(node) {
    const s = nodeState(node.id)
    let url = null
    if (!s.preview) {
        return url
    }
    if (s.videoEl?.hidden == false && s.videoEl.src) {
        if (['input', 'output', 'temp'].includes(s.preview.params.type)) {
            //Use full quality video
            url = comfy.backend.url('/view?' + new URLSearchParams(s.preview.params));
            //Workaround for 16bit png: Just do first frame
            url = url.replace('%2503d', '001')
        }
    } else if (s.imgEl?.hidden == false && s.imgEl.src) {
        url = s.imgEl.src;
        url = new URL(url);
    }
    return url
}
function addPreviewOptions(b) {
    b.addMenuItem({label: "Open preview", when: (node) => !!previewURL(node), run: (node) => {
        const url = previewURL(node)
        if (url) {
            window.open(url, "_blank")
        }
    }});
    b.addMenuItem({label: "Save preview", when: (node) => !!previewURL(node), run: (node) => {
        const url = previewURL(node)
        if (!url) {
            return
        }
        const a = document.createElement("a");
        a.href = url;
        a.setAttribute("download", nodeState(node.id).preview.params.filename);
        document.body.append(a);
        a.click();
        requestAnimationFrame(() => a.remove());
    }});
    b.addMenuItem({label: "Copy output filepath",
        when: (node) => !!previewURL(node) && !!nodeState(node.id).preview?.params?.fullpath,
        run: async (node) => {
        const params = nodeState(node.id).preview?.params
        if (!previewURL(node) || !params?.fullpath) {
            return
        }
        copiedPath = params.fullpath
        const blob = new Blob([params.fullpath], { type: 'text/plain'})
        await navigator.clipboard.write([
            new ClipboardItem({
                'text/plain': blob
            })])
    }});
    b.addMenuItem({label: "Save workflow image",
        when: (node) => !!previewURL(node) && !!nodeState(node.id).preview?.params?.workflow,
        run: (node) => {
        const params = nodeState(node.id).preview?.params
        if (!previewURL(node) || !params?.workflow) {
            return
        }
        let wParams = {...params, filename: params.workflow}
        let wUrl = comfy.backend.url('/view?' + new URLSearchParams(wParams));
        const a = document.createElement("a");
        a.href = wUrl;
        a.setAttribute("download", params.workflow);
        document.body.append(a);
        a.click();
        requestAnimationFrame(() => a.remove());
    }});
    b.addMenuItem({
        label: (node) => (nodeState(node.id).preview?.paused ? "Resume" : "Pause") + " preview",
        when: (node) => nodeState(node.id).videoEl?.hidden == false,
        run: (node) => {
        //animated images can't be paused and are more likely to cause performance issues.
        //changing src to a single keyframe is possible,
        //For now, the option is disabled if an animated image is being displayed
        const s = nodeState(node.id)
        if (s.videoEl?.hidden != false) {
            return
        }
        if(s.preview.paused) {
            s.videoEl?.play();
        } else {
            s.videoEl?.pause();
        }
        s.preview.paused = !s.preview.paused;
    }});
    //TODO: Consider hiding elements if no video preview is available yet.
    //It would reduce confusion at the cost of functionality
    //(if a video preview lags the computer, the user should be able to hide in advance)
    b.addMenuItem({
        label: (node) => (nodeState(node.id).preview?.hidden ? "Show" : "Hide") + " preview",
        run: (node) => {
        const s = nodeState(node.id)
        if (!s.videoEl) {
            return
        }
        if (!s.videoEl.hidden && !s.preview.hidden) {
            s.videoEl.pause();
        } else if (s.preview.hidden && !s.videoEl.hidden && !s.preview.paused) {
            s.videoEl.play();
        }
        s.preview.hidden = !s.preview.hidden;
        s.parentEl.hidden = s.preview.hidden;
        fitHeight(node);
    }});
    b.addMenuItem({label: "Sync preview", run: () => {
        //TODO: address case where videos have varying length
        //Consider a system of sync groups which are opt-in?
        for (let p of document.getElementsByClassName("vhs_preview")) {
            for (let child of p.children) {
                if (child.tagName == "VIDEO") {
                    child.currentTime=0;
                } else if (child.tagName == "IMG") {
                    child.src = child.src;
                }
            }
        }
    }});
    b.addMenuItem({
        label: (node) => (nodeState(node.id).preview?.muted ? "Unmute" : "Mute") + " Preview",
        run: (node) => {
        const s = nodeState(node.id)
        if (s.preview) {
            s.preview.muted = !s.preview.muted
        }
    }});
}
function addFormatWidgets(b) {
    const formats = b.def.inputs.find((input) => input.name == 'format')?.options?.formats
    b.onCreated(function(node) {
        var formatWidget = node.widgets.get("format");
        if (!formatWidget) {
            return
        }
        var formatWidgetIndex = node.widgets.names().indexOf("format") + 1;
        let formatWidgetNames = [];
        const updateFormat = (value) => {
            const definitions = formats?.[value] ?? []
            const nextNames = new Set(definitions.map((definition) => definition[0]))
            for (const name of formatWidgetNames) {
                if (nextNames.has(name)) continue
                node.widgets.remove(name)
                const slot = node.inputs.byName(name)
                if (slot) node.inputs.remove(slot.id)
            }
            const newWidgets = []
            if (formats?.[value]) {
                for (const wDef of definitions) {
                    const declaredType = wDef[1]
                    const configOptions = {...(wDef[2] ?? {})}
                    const options = {...configOptions}
                    let type = options.widgetType
                    if (!type && Array.isArray(declaredType)) {
                        type = 'combo'
                        options.values = [...declaredType]
                    } else if (!type && ['INT', 'FLOAT'].includes(declaredType)) {
                        type = 'number'
                    } else if (!type && declaredType == 'BOOLEAN') {
                        type = 'toggle'
                    } else if (!type) {
                        type = 'text'
                    }
                    const def = {type, name: wDef[0], options}
                    if ('default' in options) def.value = options.default
                    else if (Array.isArray(declaredType)) def.value = declaredType[0]
                    else if (declaredType == 'BOOLEAN') def.value = false
                    else if (['INT', 'FLOAT'].includes(declaredType)) def.value = 0
                    else def.value = ''
                    node.widgets.remove(wDef[0])
                    node.widgets.add(def)
                    const widgetConfig = {type: declaredType, options: configOptions}
                    const slot = node.inputs.byName(wDef[0])
                    if (slot) {
                        slot.modify({type: declaredType, widget: wDef[0], widgetConfig})
                    } else {
                        node.inputs.add(wDef[0], declaredType, {
                            widget: wDef[0],
                            widgetConfig,
                        })
                    }
                    newWidgets.push({name: wDef[0]})
                }
            }
            newWidgets.forEach((w, i) => node.widgets.move(w.name, formatWidgetIndex + i))
            fitHeight(node);
            formatWidgetNames = newWidgets.map((w) => w.name);
        }
        formatWidget.on('change', updateFormat);
        updateFormat(formatWidget.getValue())
    });
}
function addLoadCommon(b) {
    addVideoPreview(b);
    initializeLoadFormat(b)
    addPreviewOptions(b);
    b.onCreated(function(node) {
        const s = nodeState(node.id)
        function update(key) {
            return function(value) {
                let params = {}
                params[key] = value
                s.updateParameters?.(params)
            }
        }
        let prior_ar = -2
        const widthWidget = node.widgets.get("custom_width");
        const heightWidget = node.widgets.get("custom_height");
        function updateAR() {
            let new_ar = -1
            if (widthWidget.getValue() & heightWidget.getValue()) {
                new_ar = widthWidget.getValue() / heightWidget.getValue()
            }
            if (new_ar != prior_ar) {
                s.updateParameters?.({'custom_width': widthWidget.getValue(),
                    'custom_height': heightWidget.getValue()})
                prior_ar = new_ar
            }
        }
        let widgetMap = {'frame_load_cap': 'frame_load_cap',
            'skip_first_frames': 'skip_first_frames', 'select_every_nth': 'select_every_nth',
            'start_time': 'start_time', 'force_rate': 'force_rate',
            'custom_width': updateAR, 'custom_height': updateAR,
            'image_load_cap': 'image_load_cap', 'skip_first_images': 'skip_first_images'
        }
        for (let w of node.widgets) {
            if (w.name in widgetMap) {
                const onValue = typeof(widgetMap[w.name]) == 'function'
                    ? widgetMap[w.name] : update(widgetMap[w.name])
                w.on('change', onValue)
                onValue(w.getValue())
            }
        }
    });
}

function path_stem(path) {
    let i = path.lastIndexOf("/");
    if (i >= 0) {
        return [path.slice(0,i+1),path.slice(i+1)];
    }
    return ["",path];
}

function roundToPrecision(value, precision) {
    return String(Math.round(value * 10 ** precision) / 10 ** precision)
}

function parseTimestamp(value) {
    let result = 0
    for (const chunk of String(value).split(':')) {
        result = result * 60 + Number(chunk)
    }
    return result
}

function displayTimestamp(value) {
    let seconds = Number(value) || 0
    const hours = Math.floor(seconds / 3600)
    seconds -= hours * 3600
    let minutes = Math.floor(seconds / 60)
    seconds -= minutes * 60
    const parts = []
    if (hours) parts.push(String(hours))
    if (hours) parts.push(String(minutes).padStart(2, '0'))
    else if (minutes) parts.push(String(minutes))
    let tail = roundToPrecision(seconds, 4)
    if ((hours || minutes) && Number(tail) < 10) tail = '0' + tail
    parts.push(tail)
    return parts.join(':')
}

function setVhsWidgetAnnotation(node, name, annotation) {
    const s = nodeState(node.id)
    s.widgetAnnotations ??= new Map()
    s.widgetAnnotations.set(name, annotation)
    refreshVhsWidget(node, name)
}

function refreshVhsWidget(node, name) {
    nodeState(node.id).widgetControls?.get(name)?.()
}

let pathInputSequence = 0
function renderPathWidget(container, value, name, context) {
    const label = document.createElement('label')
    const input = document.createElement('input')
    const list = document.createElement('datalist')
    const listId = 'vhs-path-' + pathInputSequence++
    label.textContent = name
    input.type = 'text'
    input.placeholder = String(context.getOptions().placeholder ?? '')
    input.value = String(value.get() ?? '')
    input.setAttribute('list', listId)
    list.id = listId
    label.appendChild(input)
    container.append(label, list)

    let timeout
    const updateOptions = async () => {
        // Secure loaders accept names from the host input catalogue but never
        // enumerate arbitrary directories from a text prefix.
        list.replaceChildren()
    }
    const search = () => {
        clearTimeout(timeout)
        timeout = setTimeout(updateOptions, 50)
    }
    const commit = () => value.set(input.value)
    const sync = (next) => input.value = String(next ?? '')
    input.addEventListener('input', search)
    input.addEventListener('change', commit)
    const stopValue = value.onChange(sync)
    updateOptions()
    return () => {
        clearTimeout(timeout)
        stopValue()
    }
}

function numberFromInput(raw, options, integer, timestamp) {
    let result = timestamp ? parseTimestamp(raw) : Number(raw)
    if (!Number.isFinite(result)) return undefined
    if (options.round) {
        result = Math.round((result + Number.EPSILON) / options.round) * options.round
    }
    if (integer) {
        const step = Number(options.step) || 1
        const mod = Number(options.mod) || 0
        result = Math.round((result - mod) / step) * step + mod
    }
    if (options.min != null) result = Math.max(result, Number(options.min))
    if (options.max != null) result = Math.min(result, Number(options.max))
    return result
}

function numericRenderer({integer = false, timestamp = false} = {}) {
    // COSMETIC: an unavailable action is hidden instead of drawing the old inactive
    // "No Reset" or "No Disable" glyph; reset and disable themselves are retained.
    return function renderNumericWidget(container, value, name, context) {
        const label = document.createElement('span')
        const annotation = document.createElement('span')
        const input = document.createElement('input')
        const unit = document.createElement('span')
        const action = document.createElement('button')
        label.textContent = name
        label.style.cursor = 'ew-resize'
        input.type = timestamp ? 'text' : 'number'
        container.append(label, annotation, input, unit, action)

        let owner
        const refresh = () => {
            const options = context.getOptions()
            const current = Number(value.get()) || 0
            input.value = timestamp ? displayTimestamp(current) : roundToPrecision(
                current, Number(options.precision ?? (integer ? 0 : 3)))
            if (!timestamp) {
                input.step = String(options.step ?? (integer ? 1 : 'any'))
                input.min = options.min == null ? '' : String(options.min)
                input.max = options.max == null ? '' : String(options.max)
            }
            unit.textContent = options.unit == null ? '' : String(options.unit)
            const dynamic = owner && nodeState(owner.id).widgetAnnotations?.get(name)
            const declared = options.annotation && typeof options.annotation == 'object'
                ? options.annotation[current] : undefined
            annotation.textContent = String(dynamic?.(current) ?? declared ?? '')
            let target
            let title
            if (options.reset != null && current != options.reset) {
                target = options.reset
                title = 'Reset'
            } else if (options.disable != null && current != options.disable) {
                target = options.disable
                title = 'Disable'
            }
            action.hidden = target == null
            action.textContent = title == 'Reset' ? '↺' : '⊘'
            action.title = title ?? ''
            action.onclick = () => {
                value.set(target)
                refresh()
            }
        }
        const commit = (raw) => {
            const next = numberFromInput(raw, context.getOptions(), integer, timestamp)
            if (next != undefined) value.set(next)
            refresh()
        }
        input.addEventListener('change', () => commit(input.value))
        let dragStart
        const pointerDown = (event) => {
            if (event.button != 0) return
            dragStart = {x: event.clientX, value: Number(value.get()) || 0}
            label.setPointerCapture(event.pointerId)
        }
        const pointerMove = (event) => {
            if (!dragStart) return
            const step = Number(context.getOptions().step) || 1
            commit(dragStart.value + (event.clientX - dragStart.x) * step)
        }
        const pointerUp = () => dragStart = undefined
        label.addEventListener('pointerdown', pointerDown)
        label.addEventListener('pointermove', pointerMove)
        label.addEventListener('pointerup', pointerUp)
        const stopValue = value.onChange(refresh)
        const stopReady = context.onNodeReady((node) => {
            owner = node
            const s = nodeState(node.id)
            s.widgetControls ??= new Map()
            s.widgetControls.set(name, refresh)
            refresh()
            return () => {
                if (s.widgetControls?.get(name) == refresh) s.widgetControls.delete(name)
                owner = undefined
            }
        })
        refresh()
        return () => {
            stopValue()
            stopReady()
        }
    }
}

comfy.defs.defineWidgetType('VHSPATH', {
    defaultValue: '',
    minHeight: 28,
    render: renderPathWidget,
})
comfy.defs.defineWidgetType('VHSFLOAT', {
    defaultValue: 0,
    minHeight: 28,
    render: numericRenderer(),
})
comfy.defs.defineWidgetType('VHSINT', {
    defaultValue: 0,
    minHeight: 28,
    render: numericRenderer({integer: true}),
})
comfy.defs.defineWidgetType('VHSTIMESTAMP', {
    defaultValue: 0,
    minHeight: 28,
    render: numericRenderer({timestamp: true}),
})

function installVhsWidgetTypes(b) {
    const inputs = b.def.inputs.map((input) => {
        const requested = typeof input.options.widgetType == 'string'
            ? input.options.widgetType : undefined
        let type = requested?.startsWith('VHS') ? requested : undefined
        if (!requested && input.type == 'INT') type = 'VHSINT'
        if (!requested && input.type == 'FLOAT') type = 'VHSFLOAT'
        if (input.options.vhs_path_extensions) type = 'VHSPATH'
        return type ? {input, type} : undefined
    }).filter(Boolean)
    if (!inputs.length) return
    b.onCreated((node) => {
        for (const {input, type} of inputs) {
            const widget = node.widgets.get(input.name)
            if (!widget || widget.widgetType == type) continue
            const index = node.widgets.names().indexOf(input.name)
            const value = widget.getValue()
            const disabled = widget.isDisabled()
            const hidden = widget.isHidden()
            const serialize = widget.isSerialized()
            node.widgets.remove(input.name)
            node.widgets.add({
                type,
                name: input.name,
                value,
                options: input.options,
                disabled,
                hidden,
                serialize,
            })
            node.widgets.move(input.name, index)
            node.inputs.byName(input.name)?.modify({
                widget: input.name,
                widgetConfig: {type: input.type, options: input.options},
            })
        }
    })
}

let latentPreviewNodes = new Set()
comfy.settings.declare({
    id: 'VHS.AdvancedPreviews',
    category: ['🎥🅥🅗🅢', 'Previews', 'Advanced Previews'],
    name: 'Advanced Previews',
    tooltip: 'Automatically transcode previews on request. Required for advanced functionality',
    type: 'combo',
    options: ['Never', 'Always', 'Input Only'],
    defaultValue: 'Input Only',
});
comfy.settings.declare({
    id: 'VHS.AdvancedPreviewsMinWidth',
    category: ['🎥🅥🅗🅢', 'Previews', 'Min Width'],
    name: 'Minimum preview width',
    tooltip: 'Advanced previews have their resolution downscaled to the node size for performance. While a node can be resized to increase preview quality, a minimum width can be set that previews won\'t be downscaled beneath. Preveiws will never be upscaled, so this can safely be set large.',
    type: 'number',
    attrs: {
      min: 0,
      step: 1,
      max: 3840,
    },
    defaultValue: 0,
});
comfy.settings.declare({
    id: 'VHS.AdvancedPreviewsDeadline',
    category: ['🎥🅥🅗🅢', 'Previews', 'Deadline'],
    name: 'Deadline',
    tooltip: 'Determines how much time can be spent when encoding advanced previews. Realtime results in reduced quality, but good will likely cause the preview to stutter as initial generation occurs',
    type: 'combo',
    options: ['realtime', 'good'],
    defaultValue: 'realtime',
});
comfy.settings.declare({
    id: 'VHS.AdvancedPreviewsDefaultMute',
    category: ['🎥🅥🅗🅢', 'Previews', 'Default Mute'],
    name: 'Mute videos by default',
    type: 'boolean',
    defaultValue: false,
});
comfy.settings.declare({
    id: 'VHS.LatentPreview',
    category: ['🎥🅥🅗🅢', 'Sampling', 'Latent Previews'],
    name: 'Display animated previews when sampling',
    type: 'boolean',
    defaultValue: false,
    onChange(value) {
        if (!value) {
            //Remove any previewWidgets
            for (let id of latentPreviewNodes) {
                let n = comfy.executionNode(id)
                if (n) {
                    n.widgets.remove('vhslatentpreview')
                    delete nodeState(id).latentPreview
                }
            }
            latentPreviewNodes = new Set()
        }
    },
});
comfy.settings.declare({
    id: "VHS.LatentPreviewRate",
    category: ['🎥🅥🅗🅢', 'Sampling', 'Latent Preview Rate'],
    name: "Playback rate override.",
    type: 'number',
    attrs: {
      min: 0,
      step: 1,
      max: 60
    },
    tooltip:
      'Force a specific frame rate for the playback of latent frames. This should not be confused with the output frame rate and will not match for video models.',
    defaultValue: 0,
});
comfy.settings.declare({
    id: 'VHS.MetadataImage',
    category: ['🎥🅥🅗🅢', 'Output', 'MetadataImage'],
    name: 'Save png of first frame for metadata',
    type: 'boolean',
    defaultValue: true,
});
comfy.settings.declare({
    id: 'VHS.KeepIntermediate',
    category: ['🎥🅥🅗🅢', 'Output', 'Keep Intermediate'],
    name: 'Keep required intermediate files after sucessful execution',
    type: 'boolean',
    defaultValue: true,
});

//The selector is the guard clause the hook opened with.
comfy.defs.extend(/^VHS_/, (b) => {
    installVhsWidgetTypes(b)
    useKVState(b);
    if (b.def.description) {
        let description = b.def.description
        let el = document.createElement("div")
        el.innerHTML = description
        if (!el.children.length) {
            //Is plaintext. Do minor convenience formatting
            let chunks = description.split('\n')
            description = chunks.join('<br>')
        }
        // COSMETIC: the standard tooltip keeps the full description while the badge
        // opens the same formatted help; only the old one-line tooltip is gone.
        b.onCreated((node) => {
            node.addBadge({text: '?', onClick: () => helpDOM.addHelp(node, description)})
        })
    }
    //Check and migrate inputs named batch_manager from old workflows
    b.onConfigured(function(node) {
        const batchInput = node.inputs.byName("batch_manager")
        if (batchInput) {
            batchInput.modify({name: "meta_batch"})
        }
    });
    if (b.def.type == "VHS_LoadImages") {
        addUploadWidget(b, "directory", "folder");
        b.onCreated(function(node) {
            const pathWidget = node.widgets.get("directory");
            pathWidget?.on('change', (value) => {
                if (!value) {
                    return;
                }
                let params = {filename : value, type : "input", format: "folder"};
                nodeState(node.id).updateParameters?.(params, true);
            });
        });
        addLoadCommon(b);
    } else if (b.def.type == "VHS_LoadImagesPath") {
        b.onCreated(function(node) {
            const pathWidget = node.widgets.get("directory");
            pathWidget?.on('change', (value) => {
                if (!value) {
                    return;
                }
                let params = {filename : value, type : "path", format: "folder"};
                nodeState(node.id).updateParameters?.(params, true);
            });
        });
        addLoadCommon(b);
    } else if (b.def.type == "VHS_LoadVideo" || b.def.type == "VHS_LoadVideoFFmpeg") {
        b.onCreated(function(node) {
            const pathWidget = node.widgets.get("video");
            pathWidget?.on('change', (value) => {
                if (!value) {
                    return;
                }
                let parts = ["input", value];
                let extension_index = parts[1].lastIndexOf(".");
                let extension = parts[1].slice(extension_index+1);
                let format = "video"
                if (["gif", "webp", "avif"].includes(extension)) {
                    format = "image"
                }
                format += "/" + extension;
                let params = {filename : parts[1], type : parts[0], format: format};
                nodeState(node.id).updateParameters?.(params, true);
            });
        });
        addUploadWidget(b, "video");
        addLoadCommon(b);
        addVAEOutputToggle(b);
    } else if (b.def.type == "VHS_LoadAudio") {
        addAudioPreview(b)
        b.onCreated(function(node) {
            const pathWidget = node.widgets.get("audio_file");
            pathWidget?.on('change', (filename) => {
                nodeState(node.id).updateParameters?.({filename, type: 'path'}, true);
            });
        });
    } else if (b.def.type == "VHS_LoadAudioUpload") {
        addUploadWidget(b, "audio", "audio");
        addAudioPreview(b)
        b.onCreated(function(node) {
            const pathWidget = node.widgets.get("audio");
            pathWidget?.on('change', (filename) => {
                if (!filename) return
                let params = {filename, type : "input"};
                nodeState(node.id).updateParameters?.(params, true);
            });
        });
    } else if (b.def.type == "VHS_LoadVideoPath" || b.def.type == "VHS_LoadVideoFFmpegPath") {
        b.onCreated(function(node) {
            const pathWidget = node.widgets.get("video");
            pathWidget?.on('change', (value) => {
                let extension_index = value.lastIndexOf(".");
                let extension = value.slice(extension_index+1);
                let format = "video"
                if (["gif", "webp", "avif"].includes(extension)) {
                    format = "image"
                }
                format += "/" + extension;
                let params = {filename : value, type: "path", format: format};
                nodeState(node.id).updateParameters?.(params, true);
            });
        });
        addLoadCommon(b);
        addVAEOutputToggle(b);
    } else if (b.def.type == "VHS_LoadImagePath") {
        addLoadCommon(b);
        addVAEOutputToggle(b);
        b.onCreated(function(node) {
            const pathWidget = node.widgets.get("image");
            pathWidget?.on('change', (value) => {
                let extension_index = value.lastIndexOf(".");
                let extension = value.slice(extension_index+1);
                let format = "video" +  "/" + extension;
                let params = {filename : value, type: "path", format: format};
                nodeState(node.id).updateParameters?.(params, true);
            });
        });
    } else if (b.def.type == "VHS_VideoCombine") {
        b.onCreated((node) => {
            node.widgets.get('filename_prefix')?.on('beforeSerialize', (event) => {
                if (event.context == 'prompt') {
                    event.setSerializedValue(comfy.workflow.applyTextReplacements(
                        String(event.value ?? '')))
                }
            })
        })
        b.onExecuted(function(node, result) {
            if (result.raw?.gifs) {
                nodeState(node.id).updateParameters?.(result.raw.gifs[0], true);
            }
        });
        addVideoPreview(b, false);
        addPreviewOptions(b);
        addFormatWidgets(b);
        addVAEInputToggle(b)
    } else if (b.def.type == "VHS_SaveImageSequence") {
        //Disabled for safety as VHS_SaveImageSequence is not currently merged
        //addDateFormating(nodeType, "directory_name", timestamp_widget=true);
        //addTimestampWidget(nodeType, nodeData, "directory_name")
        //These remain disabled upstream; the active VideoCombine path above keeps
        //the replacement behavior users can currently reach.
    }
    //Registered last: callbacks run in registration order, so the per-node state has
    //to outlive every other teardown above.
    b.onRemoved(function(node) {
        nodeStates.delete(node.id)
    });
});
//afterQueued was per widget; onAfterRun is global, so each BatchManager's
//subscription is held here. Kept out of nodeStates because the /^VHS_/ extension
//above clears that map first, and this teardown has to outlive it.
const batchCounters = new Map()
comfy.defs.extend("VHS_BatchManager", (b) => {
    b.onCreated(function(node) {
        const count = node.widgets.add({name: "count", type: "number", value: 0, hidden: true});
        batchCounters.set(node.id, comfy.queue.onAfterRun(() => {
            count.setValue(count.getValue() + 1);
        }));
    });
    b.onRemoved(function(node) {
        const stop = batchCounters.get(node.id);
        if (stop) stop();
        batchCounters.delete(node.id);
    });
});
// REFUSED, not a pending gap: editing the built workflow. The four settings VHS
// wrote into workflow.extra — VHS_latentpreview, VHS_latentpreviewrate,
// VHS_MetadataImage and VHS_KeepIntermediate — never reach the backend.
//This was beforeConfigureGraph; onWorkflowLoaded runs after the nodes are in,
//which is just as good for dropping a panel that describes the old ones.
comfy.onWorkflowLoaded(() => {
    if (helpDOM?.node) {
        helpDOM.node = undefined
        helpDOM.parentElement.style['left'] = '-5000px'
    }
})
// REFUSED: replacing another pack's definition hook. Definition extensions are now
// selector-scoped, so a migrated UVR5 previewer can target its own nodes without
// running against VHS types and the conflict this workaround patched cannot arise.

//Add a handler for pasting video data
document.addEventListener('paste', async (e) => {
    if (!e.target.classList.contains('litegraph') &&
        !e.target.classList.contains('graph-canvas-container')) {
            return
        }
    let data = e.clipboardData || window.clipboardData
    let filepath = data.getData('text/plain')
    let video
    for (const item of data.items) {
        if (item.type.startsWith('video/')) {
            video = item
            break
        }
    }
    if (filepath && copiedPath == filepath) {
        //Add a Load Video (Path) and populate filepath
        const pastedNode = comfy.graph.add('VHS_LoadVideoPath')
        const at = comfy.graph.pointerPosition()
        if (at) {
            pastedNode.setPosition(at)
        }
        pastedNode.widgets.at(0).setValue(filepath)
    } else if (video && false) {
        //Disabled due to lack of testing
        //Add a Load Video (Upload), then upload the file, then select the file
        const pastedNode = comfy.graph.add('VHS_LoadVideo')
        const pathWidget = pastedNode.widgets.at(0)
        //TODO: upload to pasted dir?
        const blob = video.getAsFile()
        const resp = await uploadFile(blob)
        if (resp.status != 200) {
            //upload failed and file can not be added to options
            return;
        }
        const filename = (await resp.json()).name;
        pathWidget.setOption('values', [...(pathWidget.getOptions()?.values ?? []), filename]);
        pathWidget.setValue(filename);
    } else {
        return
    }
    e.preventDefault()
    e.stopImmediatePropagation()
    return false
}, true)

async function initVHS() {
    if (comfy.settings.get("VHS.AdvancedPreviews") == true) {
        await comfy.settings.set("VHS.AdvancedPreviews", 'Always')
    }
    if (comfy.settings.get("VHS.AdvancedPreviews") == false) {
        await comfy.settings.set("VHS.AdvancedPreviews", 'Never')
    }
    initHelpDOM()
}
initVHS()
comfy.backend.on('executing', (detail) => {
    if (detail === null) {
        for (let graph of allGraphs()) {
            for (let node of graph.nodes()) {
                if (node.type.startsWith("VHS_")) {
                    nodeStates.get(node.id)?.onPromptExecuted?.()
                }
            }
        }
        //Execution finished; stop every running latent animation.
        for (let id in animateIntervals) {
            clearTimeout(animateIntervals[id])
            delete animateIntervals[id]
        }
    }
})
function getLatentPreviewSurface(id) {
    const node = getNodeById(id)
    if (!node) {
        return undefined
    }
    const s = nodeState(node.id)
    if (!s.latentPreview) {
        //check for and remove any native preview
        // REFUSED, not pending: clearing node.imgs is a WRITE to what the node
        // displays, which belongs to the renderer, not to a pack. Reading is
        // published (node.getOutputImages()); writing is not, and will not be.
        // Core's own image preview may therefore return on the next execution.
        node.widgets.remove('$$canvas-image-preview')
        s.latentPreview = node.widgets.canvas({
            name: "vhslatentpreview",
            draw: (ctx, [width, height]) => {
                if (s.latentFrame) {
                    ctx.drawImage(s.latentFrame, 0, 0, width, height)
                }
            },
        });
        fitHeight(node)
    }
    return s.latentPreview
}
let animateIntervals = {}
function beginLatentPreview(id, previewImages, rate) {
    latentPreviewNodes.add(id)
    if (animateIntervals[id]) {
        clearTimeout(animateIntervals[id])
    }
    let displayIndex = 0
    animateIntervals[id] = setInterval(() => {
        if (!getNodeById(id)) {
            clearTimeout(animateIntervals[id])
            delete animateIntervals[id]
            return
        }
        if (!previewImages[displayIndex]) {
            return
        }
        const surface = getLatentPreviewSurface(id)
        if (surface) {
            nodeState(id).latentFrame = previewImages[displayIndex]
            surface.redraw()
        }
        displayIndex = (displayIndex + 1) % previewImages.length
    }, 1000/rate);

}
let previewImagesDict = {}
comfy.backend.on('VHS_latentpreview', (detail) => {
    if (detail.id == null) {
        return
    }
    let previewImages = previewImagesDict[detail.id] = []
    previewImages.length = detail.length

    let idParts = detail.id.split(':')
    for (let i=1; i <= idParts.length; i++) {
        let id = idParts.slice(0,i).join(':')
        beginLatentPreview(id, previewImages, detail.rate)
    }
});
let td = new TextDecoder()
comfy.backend.on('b_preview', async (detail) => {
    if (Object.keys(animateIntervals).length == 0) {
        return
    }
    const dv = new DataView(await detail.slice(0,24).arrayBuffer())
    const index = dv.getUint32(4)
    const idlen = dv.getUint8(8)
    const id = td.decode(dv.buffer.slice(9,9+idlen))
    previewImagesDict[id][index] = await window.createImageBitmap(detail.slice(24))
    return false
});
