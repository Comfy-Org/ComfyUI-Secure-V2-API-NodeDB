// Previously made the canvas value-entry prompt use <input type="number"> when the
// widget being edited held a number, copying the widget's min/max/step onto it.
//
// REFUSED: patches LGraphCanvas.prototype.prompt. The file replaced the editor's
// own value-entry dialog for every widget in the document, took the element it
// returned and rewrote its <input>, and read app.canvas.node_widget to discover
// which widget the editor was mid-edit on. Retuning the host's dialog from a pack
// is the mechanism we will not support: the dialog is chrome we replace, and one
// pack's patch silently becomes every other pack's behaviour.
//
// Not a capability refusal. "A numeric widget is edited with a numeric field
// carrying its own min/max/step" is correct and is the host's job — nothing about
// it is node-specific, so no pack should have to ask for it. comfy.ui.prompt
// raises a pack's OWN prompt and is deliberately not a hook on the host's.
//
// The "🐍 Use number input on value entry" setting goes with it: it existed only
// to gate that patch.
//
// INOPERABLE: pysssss.UseNumberInputPrompt.

export {}
