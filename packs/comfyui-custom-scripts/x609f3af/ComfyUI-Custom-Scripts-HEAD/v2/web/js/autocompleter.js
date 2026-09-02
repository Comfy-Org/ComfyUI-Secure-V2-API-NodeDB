// Previously attached the tag autocompleter (common/autocomplete.js) to every
// multiline STRING widget in the graph, fed it embeddings, LoRAs and a user-editable
// custom word list, and offered an "ℹ️" link on each suggestion that opened the
// model info dialog.
//
// REFUSED, not a pending gap: replacing a core global. The file assigned over
// ComfyWidgets.STRING, so every multiline text widget in the document — core's and
// every other pack's — was constructed by this pack, only so it could keep the
// resulting widget.inputEl. Two packs doing that leaves the answer to load order and
// the loser's widgets are silently plain, and the constructor table is core's to
// change. defs.defineWidgetType is the published form of "this input type looks like
// this", and it deliberately refuses a type core already owns, for the same reason.
//
// REFUSED, not a pending gap: a pack rendering the settings panel's markup. The
// "🐍 Text Autocomplete" setting was a hand-built <tr> holding seven controls
// (enable, LoRAs, auto-comma, underscore replacement, insert-on-Tab/Enter, max
// suggestions, and a "Manage Custom Words" button) writing straight to localStorage.
// The capability survives: those are seven declared settings of type boolean, number
// and text, plus a command for the word-list dialog. It is not written here because
// there is nothing left to configure — see below.
//
// DROPPED: the autocompleter itself. Offering completions inside a prompt box is a
// reasonable thing for a pack to want and it is not refused; what is missing is any
// way to contribute behaviour to a widget the pack did not create. A WidgetHandle
// publishes value, options, hidden, disabled and events, never its element, and
// widgets.mount() hands back a container only for a widget the pack adds itself.
// Substituting one is not a way round it either: a mounted replacement lands at the
// end of node.widgets while the original sat at its declared index, and
// widgets_values is positional, so every saved workflow for that node would change.
// The missing capability is narrow and the pack already declares the opt-in for it —
// its own Python puts "pysssss.autocomplete" in the input's option dict — so what
// this needs is a hook keyed on an INPUT rather than on the widget TYPE.
//
// DROPPED: the LoRA suggestions' source. addLoras() read the list out of
// LiteGraph.registered_node_types["LoraLoader"].nodeData.input.required.lora_name[0].
// NodeDef.inputs[].options publishes the declaration dict, but a COMBO's values are
// the FIRST element of the spec and are not carried, so a converted read would have
// to come from the pack's own /pysssss/loras route instead.
//
// The rest of the file does have destinations — the per-input configuration is
// readable (NodeDef.inputs[].options["pysssss.autocomplete"]), the routes are
// comfy.backend.fetch, and the info dialogs are converted in modelInfo.js — but with
// nowhere to attach the completer there is nothing for any of it to serve.
//
// common/autocomplete.js is converted and still exports TextAreaAutoComplete for
// packs that construct it against their own mounted elements; nothing in this pack
// imports it now.
//
// INOPERABLE: pysssss.AutoCompleter and its "🐍 Text Autocomplete" settings.

export {}
