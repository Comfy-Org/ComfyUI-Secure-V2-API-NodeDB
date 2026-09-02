// Previously did three things: bound ALT+1..9 to paste node templates 1..9 by
// writing `litegrapheditor_clipboard` in localStorage and calling
// `app.canvas.pasteFromClipboard()`; replaced
// LGraphCanvas.prototype.pasteFromClipboard with a ~110-line reimplementation so
// pasted nodes reconnected to the previously selected node's outputs and pasted
// groups were rebuilt; and drew a progress bar inside ComfyUI's own queue button
// from the `progress` and `status` backend events.
//
// REFUSED, not a pending gap: patching the renderer's prototypes.
// pasteFromClipboard is the canvas's, and overwriting it made easy-use the
// owner of paste for every node in the document, including packs and core
// workflows that never asked. The replacement also constructs
// `new LiteGraph.LGraphGroup()` and calls `this.graph.add()` and
// `this.selectNodes()` on the canvas directly — the same renderer, reached three
// more ways.
//
// REFUSED, not a pending gap: rendering into the host's own chrome. The
// progress bar is `document.getElementById("queue-button")` followed by writes
// to that button's `innerText` and `data-attr`, plus
// `document.documentElement.style.setProperty('--process-bar-width', …)` — a
// pack laying out an element it does not own and setting a custom property on
// the document root, where it applies to everything. `comfy.ui.addTopBarBadge`
// is the published shape for a live readout and is declarative for exactly this
// reason: the host places it, in house style, and no pack can break the top bar
// for another. It is not used here because the capability already survives (see
// below), so a second percentage readout would be duplication, not restoration.
//
// REFUSED, not a pending gap: importing a core extension's internals.
// `import { GroupNodeConfig } from "../../../../extensions/core/groupNode.js"`
// reaches into a module core ships for its own use, whose shape is not a
// contract. A path into core's `extensions/` directory is the same coupling as
// a prototype patch, spelled as an import.
//
// The capability is not refused and is not lost: core ships all three.
//  - Node templates, and the load-and-paste path this file copied, are core's
//    own `src/extensions/core/nodeTemplates.ts` — lines 400-401 are the same
//    `localStorage.setItem('litegrapheditor_clipboard', template.data)` +
//    `pasteFromClipboard()` pair, reachable from the templates menu.
//  - Connect-on-paste is core's, under `LiteGraph.ctrl_shift_v_paste_connect_
//    unselected_outputs` (LiteGraphGlobal.ts:267, default true), consulted at
//    LGraphCanvas.ts:4158 and 4316; core's paste rebuilds groups too
//    (LGraphCanvas.ts:4348).
//  - The queue progress bar is core's, under `Comfy.Queue.ShowRunProgressBar`
//    (useQueueFeatureFlags.ts:11, on unless the user turns it off), rendered by
//    the action bar rather than injected into a button by string surgery.
//
// DROPPED: the ALT+1..9 shortcut itself, and the two settings
// `Comfy.EasyUse.NodeTemplateShortcut` and `Comfy.EasyUse.queueProcessBar`.
// `comfy.commands.register({ id, label, run, keybinding })` would bind the keys,
// and `comfy.settings.declare` would declare the settings, but `run` has nothing
// to call: inserting a template is the clipboard path above, which is refused.
// Templates 1..9 are still reachable, by name, from core's templates menu.
//
// INOPERABLE: nothing. No node type is registered or extended by this file.

export {}
