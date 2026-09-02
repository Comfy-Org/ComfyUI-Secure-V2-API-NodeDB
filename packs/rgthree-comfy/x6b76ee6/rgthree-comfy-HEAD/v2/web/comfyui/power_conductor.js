var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { comfy } from '/comfy/api/v2.js';
import { Exposed, execute, PyTuple } from "../../rgthree/common/py_parser.js";
import { NodeTypesString } from "./constants.js";
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
import { setModeDeep } from "./base_any_input_connected_node.js";

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
// SCRIPT-VISIBLE: `ComfyWidgetWrapper.label` hands the script the widget's `name`, where
//   it used to see `label`. `WidgetHandle` has `setLabel` and no reader, so there is
//   nothing else to give it — but the original handed the script `undefined` for every
//   widget that never set a label, which after this migration is all of them, so a name
//   is strictly more than it had rather than a loss.
// DROPPED: `ComfyWidgetWrapper.toggle(value)` duck-typed a `toggle` method that only
//   rgthree's own widget classes declared. A handle exposes the published widget surface
//   and nothing another pack hung on a widget, so the call is gone rather than
//   converted — and with those classes replaced by mounted DOM there is no `toggle` left
//   for it to have found.
//
// SCRIPT-VISIBLE: `node(5).mode` returned litegraph's number (0/2/4) and now returns the
//   published name ('always'/'never'/'bypass'). `mute()`, `bypass()` and `enable()` are
//   unchanged, and now descend into a subgraph node's children in one undo step.
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
        return this.getNode().id;
    }
    get title() {
        return this.getNode().getTitle();
    }
    set title(value) {
        this.getNode().setTitle(value);
    }
    get widgets() {
        return new PyTuple(this.getNode().widgets.all().map((w) => new ComfyWidgetWrapper(w)));
    }
    get mode() {
        return this.getNode().getMode();
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
    constructor(widget) {
        this.widget = widget;
    }
    get value() {
        return this.widget.getValue();
    }
    get label() {
        return this.widget.name;
    }
    toggle(value) {
        void value;
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
if (CONFIG_SERVICE.getConfigValue("unreleased.power_conductor.enabled")) {
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
