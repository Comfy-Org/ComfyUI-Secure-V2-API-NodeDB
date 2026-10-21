var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { comfy } from '/comfy/api/v2.js';
import { Exposed, execute, PyTuple } from "../common/py_parser.js";
import { NodeTypesString } from "./constants.js";
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
import { setModeDeep } from "./base_any_input_connected_node.js";
import { getWidgetControl } from './widget_controls.js';
// Imported for their registrations, which every node type must receive before this
// pack's `define` calls run (extendEveryNodeType in base_node.js).
import "./menu_queue_node.js";
import "./feature_import_individual_nodes.js";

// Power Conductor (unreleased; gated on `unreleased.power_conductor.enabled`) — a code
// box and a Run button that execute a small python-like script against the live graph,
// e.g. `node(5).mute()`. The parser is the pack's own and untouched; what changed is
// what the script's `node()` builtin is holding.
//
// The code box was `ComfyWidgets.STRING(this, "", ["STRING", {multiline: true}], app)`,
// a DOM widget wrapping a textarea, and the Run button was `RgthreeBetterButtonWidget`,
// a hand-drawn canvas widget with its own hit testing. Both are the pack drawing its own
// front end: `widgets.mount` hands over a container to fill, and a `button` widget with
// `on('activate')` is the published press.
//
// getLabel is the generic read-only primitive supplied by the Label/API lane.
// Missing and explicitly empty labels keep their original distinct values.
// rgthree's group-row toggle is registered pack-side in widget_controls.js.
// The script can call its original behavior without duck-typing a host handle.
//
// Script-visible mode preserves original numbers (0/2/4); the public facade's
// names are translated only at this boundary.
//
// WIRE FORMAT: `widgets_values` goes from three entries to two. The original called
//   `addCustomWidget(this.codeWidget)` on a widget `ComfyWidgets.STRING` had *already*
//   added, so the same widget appeared twice in the list and its value was written
//   twice. Index 0 — the code — is unchanged, so a saved node still loads its script.
const BUILT_INS = {
    node: {
        fn: (query) => {
            if (typeof query === "number" || /^\d+(\.\d+)?/.exec(query)) {
                return new ComfyNodeWrapper(String(query));
            }
            return null;
        },
    },
};
// `getNodeById` searched the root graph, the graph on screen, then every subgraph. A
// node id only resolves inside its own graph, so each is asked in turn.
function getNodeById(id) {
    return (comfy.graph.node(id) ??
        comfy.graph.subgraphs().reduce((found, subgraph) => found ?? subgraph.node(id), undefined));
}
class ComfyNodeWrapper {
    constructor(id) {
        this.nodeId = id;
    }
    getNode() {
        const node = getNodeById(this.nodeId);
        if (!node) {
            throw new Error(`[rgthree.PowerConductor] no node with id ${this.nodeId}.`);
        }
        return node;
    }
    get id() {
        const id = this.getNode().id;
        return /^\d+$/.test(id) && Number.isSafeInteger(Number(id)) ? Number(id) : id;
    }
    get title() {
        return this.getNode().getTitle();
    }
    set title(value) {
        this.getNode().setTitle(value);
    }
    get widgets() {
        const node = this.getNode();
        return new PyTuple(node.widgets.all().map((w) => new ComfyWidgetWrapper(w, node)));
    }
    get mode() {
        return { always: 0, never: 2, bypass: 4 }[this.getNode().getMode()];
    }
    mute() {
        this.setMode("never");
    }
    bypass() {
        this.setMode("bypass");
    }
    enable() {
        this.setMode("always");
    }
    setMode(mode) {
        const node = this.getNode();
        comfy.graph.batch(() => setModeDeep([node], mode));
    }
}
__decorate([
    Exposed
], ComfyNodeWrapper.prototype, "id", null);
__decorate([
    Exposed
], ComfyNodeWrapper.prototype, "title", null);
__decorate([
    Exposed
], ComfyNodeWrapper.prototype, "widgets", null);
__decorate([
    Exposed
], ComfyNodeWrapper.prototype, "mode", null);
__decorate([
    Exposed
], ComfyNodeWrapper.prototype, "mute", null);
__decorate([
    Exposed
], ComfyNodeWrapper.prototype, "bypass", null);
__decorate([
    Exposed
], ComfyNodeWrapper.prototype, "enable", null);
class ComfyWidgetWrapper {
    constructor(widget, node) {
        this.widget = widget;
        this.node = node;
    }
    get value() {
        const control = this.node && getWidgetControl(this.node, this.widget.name);
        return control ? control.getValue() : this.widget.getValue();
    }
    get label() {
        return this.widget.getLabel();
    }
    toggle(value) {
        if (this.node) getWidgetControl(this.node, this.widget.name)?.toggle(value);
    }
}
__decorate([
    Exposed
], ComfyWidgetWrapper.prototype, "value", null);
__decorate([
    Exposed
], ComfyWidgetWrapper.prototype, "label", null);
__decorate([
    Exposed
], ComfyWidgetWrapper.prototype, "toggle", null);
const CODE_WIDGET = "code";
const RUN_WIDGET = "Run";
// The opt-in is read when its value is known, not only when this module evaluates. In
// process the stored value is readable at once. Sandbox guest c6b97a15 answers a
// declared setting with its default until the host returns the stored value, so revision
// 5's single read at evaluation saw `false` and the type never registered. The stored
// value arrives as a 'config-change' (config_service.js), and `onReady` — when the
// published API says settings exist — reads it once more. The type registers once, the
// first time any of these sees the opt-in on. Turning it off still needs a reload, as the
// setting's name says.
const ENABLED_KEY = "unreleased.power_conductor.enabled";
let registered = false;
function registerWhenEnabled() {
    if (registered || !CONFIG_SERVICE.getConfigValue(ENABLED_KEY)) {
        return;
    }
    registered = true;
    comfy.defs.define({
        type: NodeTypesString.POWER_CONDUCTOR,
        title: NodeTypesString.POWER_CONDUCTOR,
        category: "rgthree",
        // Drives other nodes; it must never reach graphToPrompt.
        execution: 'frontend',
        onCreated(node) {
            if (node.widgets.get(CODE_WIDGET)) {
                return;
            }
            let stopWatching = null;
            node.widgets.mount({
                name: CODE_WIDGET,
                defaultValue: "",
                serialize: true,
                render(container, value) {
                    const inputEl = document.createElement("textarea");
                    inputEl.style.width = "100%";
                    inputEl.style.height = "100%";
                    inputEl.value = String(value.get());
                    inputEl.addEventListener("input", () => {
                        value.set(inputEl.value);
                    });
                    container.appendChild(inputEl);
                    stopWatching = value.onChange((v) => {
                        inputEl.value = String(v);
                    });
                },
                destroy() {
                    stopWatching?.();
                    stopWatching = null;
                },
            });
            const run = node.widgets.add({ type: "button", name: RUN_WIDGET, value: null });
            run.on("activate", () => {
                const code = node.widgets.get(CODE_WIDGET);
                if (!code) {
                    throw new Error(`[rgthree.PowerConductor] node ${node.id} has no code widget.`);
                }
                execute(String(code.getValue() ?? ""), {}, BUILT_INS);
            });
        },
    });
}
registerWhenEnabled();
CONFIG_SERVICE.addEventListener("config-change", (event) => {
    if (event.detail?.key === ENABLED_KEY) {
        registerWhenEnabled();
    }
});
comfy.onReady(registerWhenEnabled);
