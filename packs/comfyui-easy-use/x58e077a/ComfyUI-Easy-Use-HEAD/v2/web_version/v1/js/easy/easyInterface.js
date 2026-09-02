import { comfy } from "/comfy/api/v2.js";

// 增加Slot颜色
const customPipeLineLink = "#7737AA"
const customPipeLineSDXLLink = "#7737AA"
const customXYPlotLink = "#74DA5D"
const customLoraStackLink = "#94dccd"
const customXYLink = "#38291f"

var customLinkColors = {
    "PIPE_LINE": customPipeLineLink,
    "PIPE_LINE_SDXL": customPipeLineSDXLLink,
    "XYPLOT": customXYPlotLink,
    "X_Y": customXYLink,
    "LORA_STACK": customLoraStackLink,
    "CONTROL_NET_STACK": customLoraStackLink,
}
for(const [type, color] of Object.entries(customLinkColors)){
    // Throws for a type somebody else already coloured, which is the same
    // "leave it if it is taken" the localStorage guard was reaching for.
    try{ comfy.defs.setTypeColor(type, color) } catch(e){}
}

// 节点颜色
// Was LGraphCanvas.node_colors, read after this file had overwritten it. Only
// the four keys NODE_COLORS names are kept, at core's own values.
const COLOR_THEMES = {
    red: { color: "#322", bgcolor: "#533" },
    green: { color: "#232", bgcolor: "#353" },
    cyan: { color: "#233", bgcolor: "#355" },
    pale_blue: { color: "#2a363b", bgcolor: "#3f5159" }
}
const NODE_COLORS = {
    "easy positive":"green",
    "easy negative":"red",
    "easy promptList":"cyan",
    "easy promptLine":"cyan",
    "easy promptConcat":"cyan",
    "easy promptReplace":"cyan",
    "easy XYInputs: Seeds++ Batch": customXYLink,
    "easy XYInputs: ModelMergeBlocks": customXYLink,
    'easy textSwitch': "pale_blue"
}

function setNodeColors(node, theme) {
    if (!theme) {return;}
    if(theme.color) node.setColor(theme.color);
    if(theme.bgcolor) node.setBgColor(theme.bgcolor);
}

comfy.defs.extend(Object.keys(NODE_COLORS), (b) => {
    b.onCreated((node, event) => {
        // onCreated runs AFTER configure, where nodeCreated ran before it, so a
        // restored node that already carries a colour keeps the one the user
        // saved. One that carries none still takes the pack's default, which is
        // what running first used to achieve.
        if (event.restored && (node.getColor() || node.getBgColor())) return;
        const colorKey = NODE_COLORS[node.comfyClass]
        const theme = COLOR_THEMES[colorKey];
        setNodeColors(node, theme);
    })
})

// Previously also replaced the renderer. The file overwrote
// LGraphCanvas.prototype.drawNodeShape and LGraphCanvas.prototype.drawNodeWidgets
// with ~570 lines of its own painting, reassigned LGraphCanvas.node_colors,
// LiteGraph.NODE_TEXT_SIZE and LiteGraph.DEFAULT_BACKGROUND_IMAGE, and shipped
// two colour palettes ("Obsidian", "Obsidian Dark") by writing them into
// localStorage under core's own `Comfy.Settings.Comfy.CustomColorPalettes` key
// and then pushing them to the server with api.storeSettings.
//
// REFUSED, not a pending gap: patching the renderer's prototypes. drawNodeShape
// and drawNodeWidgets ARE the renderer — every node in the document, from every
// pack, was drawn by this file once it loaded. The renderer is ours to replace,
// and a per-node drawing surface (`widgets.canvas`) is deliberately not a way
// back in: it is clipped to the widget, so a pack can draw its own control and
// cannot repaint somebody else's frame or title bar. Reassigning
// LGraphCanvas.node_colors and the two LiteGraph constants is the same act at
// module scope — global renderer state a pack does not own.
//
// REFUSED, not a pending gap: writing another owner's settings behind its back.
// `localStorage.setItem('Comfy.Settings.Comfy.CustomColorPalettes', …)` plus
// `api.storeSettings({ 'Comfy.ColorPalette': … })` reaches past the settings
// system into the storage key a setting happens to live under, and rewrites
// core's palette registry and, conditionally, the user's selected theme.
// `comfy.settings` is namespaced (`<Pack>.<name>`) precisely so that installing
// a pack cannot silently change what another owner stores; a palette is also
// not a `SettingValue`, and that is the same boundary rather than a second gap.
//
// The capability is not refused and is not lost, for the parts that are a
// pack's to have. The custom LINK colours are converted above through
// `comfy.defs.setTypeColor`, which exists for exactly this — its own
// documentation names PIPE_LINE and LORA_STACK. The pack's default NODE colours
// are converted above through `b.onCreated` + `setColor`/`setBgColor`. And the
// control-widget relabel this file carried as a "修复官方bug" is not carried
// over because core now does it: `src/scripts/widgets.ts:78` sets the label from
// `Comfy.WidgetControlMode`, and `src/components/graph/GraphCanvas.vue:379`
// re-applies it to every control widget and its linked widgets when the setting
// changes — including the `w.linkedWidgets` walk this file had to write itself.
//
// DROPPED: the `INT` link colour. `setTypeColor` refuses a type the host
// already colours, deliberately — recolouring a core type restyles every graph
// for every pack and the user cannot see who did it. The five pack-owned types
// keep their colours.
//
// DROPPED: the Obsidian / Obsidian Dark palettes, the redrawn node shape and
// widget row, the 13px node text size and the custom canvas background. Nodes
// render with core's own appearance.
//
// WIRE FORMAT: a NEWLY CREATED node of the nine types above is saved with
// core's palette values (`easy positive` → color "#232", bgcolor "#353") rather
// than the Obsidian palette this file used to install first (color "#346434").
// Safe in both directions: `color`/`bgcolor` are presentation only, both are
// valid CSS colours in the same field, every previously saved workflow loads
// byte-identically because a restored node's own colour still wins, and a node
// created before the change and one created after differ only in the shade a
// user may override from the node menu either way.
//
// INOPERABLE: nothing. Every easy-use node still registers and runs.
