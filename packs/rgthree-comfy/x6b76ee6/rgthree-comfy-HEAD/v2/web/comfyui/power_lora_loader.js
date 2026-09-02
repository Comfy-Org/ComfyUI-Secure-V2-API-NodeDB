import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { helpMenuItem } from "./base_node.js";
import { RgthreeBaseWidget, mountRgthreeWidget } from "./utils_widgets.js";
import { drawInfoIcon, drawNumberWidgetPart, drawRoundedRectangle, drawTogglePart, drawWidgetButton, fitString, } from "./utils_canvas.js";
import { rgthreeApi } from "../../rgthree/common/rgthree_api.js";
import { SERVICE as CONFIG_SERVICE } from "./services/config_service.js";
import { LORA_INFO_SERVICE } from "../../rgthree/common/model_info_service.js";

// CONVERTED — all three of the blockers that decided the last refusal are closed.
//
// The palette is published, so a row is painted in the theme `draw` is handed
// rather than in `LiteGraph.WIDGET_*`. Right-click on a row is
// `CanvasDef.onContextMenu`, which retires the whole fabricated-slot trick: the
// node no longer answers `getSlotInPosition` with `{widget, output: {type: "LORA
// WIDGET"}}` so that `getSlotMenuOptions` fires for a click on a widget, because
// the widget is asked directly. The entries open with `comfy.ui.showMenu({items,
// title, event})` where the pointer is, which is also what the lora picker uses.
//
// COSMETIC: clicking a strength value opened `app.canvas.prompt("Value", …)`, a
//   field drawn at the cursor. `comfy.ui.prompt({label, value})` asks the same
//   question in a modal — the capability is served, the placement is not.
// COSMETIC: the two zero-thickness `RgthreeDividerWidget`s are gone. Both drew
//   nothing; they were 4px of padding above the header and above the button, and
//   the second doubled as the insertion point new rows were spliced in front of.
//   Ordering is now stated outright in `relayout`, so the spacer has no second job
//   left and 8px of padding is not worth two mounted elements.
// COSMETIC: `setSizeConstraints({autoHeight: true})` fits the node to its rows
//   whenever they change, where `_tempWidth`/`_tempHeight` grew the node to fit and
//   never shrank it. A node the user had dragged taller than its content comes back
//   at content height.
// COSMETIC: `app.canvas.editor_alpha` is gone (see utils_canvas.js). A row still
//   dims to 0.4 when it is switched off and the header still writes its labels at
//   0.55, but neither follows the node's own fade any more.
// DROPPED: the lora info dialog, and with it the "ℹ️ Show Info" menu entry and the
//   click on the info badge. `RgthreeLoraInfoDialog` lives in dialog_info.js, which
//   is punted, and importing a name a punted module no longer exports throws at
//   load. The badge is still drawn, because `LORA_INFO_SERVICE` still answers what
//   it reports — civitai data, a local info file, or neither — and it is still
//   what colours a strength that falls outside the lora's recommended range. It is
//   an indicator now rather than a button.
// REFUSED, not a gap: (26) the API-JSON load path. `rgthree.loadingApiJson` plus
//   `configureFromApiJson` synthesised `configure({widgets_values: …})` out of the
//   built prompt's inputs. Reading the built prompt is deliberately not published.
// COSMETIC: no property metadata. `RgthreePowerLoraLoader["@Show Strengths"] =
//   {type: "combo", values: [...]}` told the properties panel to edit that property
//   with a two-item picker rather than a free text field; `"@Match"` declared the
//   other as a string. Both properties still exist, still save and still work.
// REFUSED, not a gap: `addConnectionLayoutSupport` — the pack's Left/Right slot layout,
//   which patches `getConnectionPos` on the node class and recomputes socket positions
//   from renderer constants. Deciding where the renderer draws a socket is refused
//   rather than pending; see utils.js.
//
// WIRE FORMAT: changed, and deliberately. A row is two widgets now — a hidden one
// holding `{on, lora, strength, strengthTwo?}`, which is what the prompt reads
// under the input name `lora_N` and what the saved file stores, and the drawing the
// user sees, which carries no value at all. `relayout` puts every value widget
// before every surface, because `widgets_values` is written at each widget's own
// index and skipped for the ones that opt out — interleaved, the saved array would
// gain a null between every pair. What leaves the array are the four entries the
// old widget list contributed and nothing read: two dividers (`{}`), the header
// (`{type: "PowerLoraLoaderHeaderWidget"}`) and the button (`""`). Loading is
// unaffected in both directions, because the rows have always been recovered by
// scanning `widgets_values` for entries carrying a `.lora` key rather than by
// position — which is exactly why they can be dropped.
const PROP_LABEL_SHOW_STRENGTHS = "Show Strengths";
const PROP_LABEL_LORA_MATCH = "Match";
const PROP_VALUE_SHOW_STRENGTHS_SINGLE = "Single Strength";
const PROP_VALUE_SHOW_STRENGTHS_SEPARATE = "Separate Model & Clip";
const HEADER_SURFACE = "lora_header";
const ADD_LORA_SURFACE = "lora_add";
// Was `LiteGraph.NODE_WIDGET_HEIGHT`. The renderer constant is not published, and a
// widget that owns its own surface states the height it wants.
const ROW_HEIGHT = 20;
const DEFAULT_LORA_WIDGET_DATA = {
    on: true,
    lora: null,
    strength: 1,
    strengthTwo: null,
};
// Handles hold no arbitrary properties, so what the old class kept on the instance
// — the row list, the name counter, and the two chrome widgets — lives here, keyed
// by node id and dropped in onRemoved.
const nodeStates = new Map();
function stateOf(node) {
    let state = nodeStates.get(node.id);
    if (!state) {
        state = { counter: 0, rows: [], header: null };
        nodeStates.set(node.id, state);
    }
    return state;
}
function isShowingModelAndClip(node) {
    return node.getProperty(PROP_LABEL_SHOW_STRENGTHS) === PROP_VALUE_SHOW_STRENGTHS_SEPARATE;
}
function allLorasState(node) {
    const rows = stateOf(node).rows;
    let allOn = true;
    let allOff = true;
    for (const row of rows) {
        const on = row.value.on;
        allOn = allOn && on === true;
        allOff = allOff && on === false;
        if (!allOn && !allOff) {
            return null;
        }
    }
    return allOn && rows.length ? true : false;
}
function toggleAllLoras(node) {
    const toggledTo = !allLorasState(node) ? true : false;
    for (const row of stateOf(node).rows) {
        if (row.value.on != null) {
            row.value.on = toggledTo;
        }
    }
    redrawAll(node);
}
// A `widgets.canvas` surface repaints on mount, on resize and on request, not once
// a frame, so a value the user just changed has to ask to be shown.
function redrawAll(node) {
    const state = stateOf(node);
    for (const row of state.rows) {
        row.redraw();
    }
    if (state.header) {
        state.header.redraw();
    }
}
function relayout(node) {
    const state = stateOf(node);
    const ordered = [
        ...state.rows.map((row) => row.valueName),
        HEADER_SURFACE,
        ...state.rows.map((row) => row.name),
        ADD_LORA_SURFACE,
    ];
    const rest = node.widgets.names().filter((name) => !ordered.includes(name));
    node.widgets.reorder([...rest, ...ordered]);
    node.setSizeConstraints({ autoHeight: true });
}
function addLoraRow(node, lora) {
    const state = stateOf(node);
    state.counter++;
    const valueName = `lora_${state.counter}`;
    const valueWidget = node.widgets.mount({
        name: valueName,
        defaultValue: { ...DEFAULT_LORA_WIDGET_DATA },
        serialize: true,
        hidden: true,
        render() { },
    });
    const row = new PowerLoraLoaderWidget(`${valueName}_row`, valueName, valueWidget);
    row.value = valueWidget.getValue();
    valueWidget.on("beforeSerialize", (e) => {
        const v = { ...row.value };
        if (!row.showModelAndClip) {
            delete v.strengthTwo;
        }
        else {
            if (row.value.strengthTwo == null) {
                row.value.strengthTwo = 1;
            }
            v.strengthTwo = row.value.strengthTwo;
        }
        e.setSerializedValue(v);
    });
    mountRgthreeWidget(node, row, { height: ROW_HEIGHT });
    state.rows.push(row);
    if (lora) {
        row.setLora(lora);
    }
    return row;
}
export function configurePowerLoraValues(node, values) {
    const state = stateOf(node);
    for (const row of [...state.rows]) {
        removeLoraRow(node, row);
    }
    state.counter = 0;
    comfy.graph.batch(() => {
        for (const value of values) {
            if (!value || value.lora === undefined) continue;
            const row = addLoraRow(node);
            row.value = { ...value };
        }
        relayout(node);
    });
    redrawAll(node);
}
function removeLoraRow(node, row) {
    const state = stateOf(node);
    const index = state.rows.indexOf(row);
    if (index > -1) {
        state.rows.splice(index, 1);
    }
    node.widgets.remove(row.name);
    node.widgets.remove(row.valueName);
}
function moveLoraRow(node, from, to) {
    const rows = stateOf(node).rows;
    rows.splice(to, 0, ...rows.splice(from, 1));
    relayout(node);
}
// Was utils_menu.js's `showLoraChooser`, which is punted with the rest of that file
// for the menu it could not open. The menu is published now, and the filtering and
// common-prefix trimming below were always this node's own.
async function showLoraChooser(node, event, onChoose) {
    const lorasDetails = await rgthreeApi.getLoras();
    let loras = lorasDetails.map((l) => l.file);
    let prefix = "";
    const match = node.getProperty(PROP_LABEL_LORA_MATCH);
    if (match) {
        const rgx = new RegExp(match);
        loras = loras.filter((l) => l.match(rgx));
        if (loras[0]) {
            prefix = loras[0];
            for (const lora of loras) {
                let similar = "";
                let i = 0;
                while (prefix[i] && prefix[i] === lora[i]) {
                    similar += prefix[i++];
                }
                prefix = similar;
                if (!prefix)
                    break;
            }
            if (prefix) {
                loras = loras.map((l) => l.replace(prefix, ""));
            }
        }
    }
    if (!loras.length) {
        comfy.commands.notify({
            severity: "warn",
            summary: "[Power Lora Loader] No loras matched.",
        });
        return;
    }
    comfy.ui.showMenu({
        title: "Choose a lora",
        event,
        items: loras.map((lora) => ({
            label: lora,
            run: () => onChoose(prefix + lora),
        })),
    });
}
function showRowMenu(node, row, event) {
    const rows = stateOf(node).rows;
    const index = rows.indexOf(row);
    comfy.ui.showMenu({
        title: "LORA WIDGET",
        event,
        items: [
            {
                label: `${row.value.on ? "⚫" : "🟢"} Toggle ${row.value.on ? "Off" : "On"}`,
                run: () => {
                    row.value.on = !row.value.on;
                    redrawAll(node);
                },
            },
            {
                label: `⬆️ Move Up`,
                disabled: index <= 0,
                run: () => moveLoraRow(node, index, index - 1),
            },
            {
                label: `⬇️ Move Down`,
                disabled: index >= rows.length - 1,
                run: () => moveLoraRow(node, index, index + 1),
            },
            {
                label: `🗑️ Remove`,
                run: () => {
                    removeLoraRow(node, row);
                    relayout(node);
                    redrawAll(node);
                },
            },
        ],
    });
}
function getHelp() {
    return `
      <p>
        The ${NodeTypesString.POWER_LORA_LOADER.replace("(rgthree)", "")} is a powerful node that condenses 100s of pixels
        of functionality in a single, dynamic node that allows you to add loras, change strengths,
        and quickly toggle on/off all without taking up half your screen.
      </p>
      <ul>
        <li><p>
          Add as many Lora's as you would like by clicking the "+ Add Lora" button.
          There's no real limit!
        </p></li>
        <li><p>
          Right-click on a Lora widget for special options to move the lora up or down
          (no image affect, only presentational), toggle it on/off, or delete the row all together.
        </p></li>
        <li>
          <p>
            <strong>Properties.</strong> You can change the following properties (by right-clicking
            on the node, and select "Properties" or "Properties Panel" from the menu):
          </p>
          <ul>
            <li><p>
              <code>${PROP_LABEL_SHOW_STRENGTHS}</code> - Change between showing a single, simple
              strength (which will be used for both model and clip), or a more advanced view with
              both model and clip strengths being modifiable.
            </p></li>
          </ul>
        </li>
      </ul>`;
}
class PowerLoraLoaderHeaderWidget extends RgthreeBaseWidget {
    constructor(name) {
        super(name);
        this.type = "custom";
        this.hitAreas = {
            toggle: { bounds: [0, 0], onDown: this.onToggleDown },
        };
        this.showModelAndClip = null;
    }
    draw(ctx, node, w, posY, height, theme) {
        if (!stateOf(node).rows.length) {
            return;
        }
        this.showModelAndClip = isShowingModelAndClip(node);
        const innerMargin = 3.3;
        const allLoraState = allLorasState(node);
        posY += 2;
        const midY = posY + height * 0.5;
        let posX = 0;
        ctx.save();
        this.hitAreas.toggle.bounds = drawTogglePart(ctx, { posX, posY, height, value: allLoraState });
        posX += this.hitAreas.toggle.bounds[1] + innerMargin;
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = theme.text;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText("Toggle All", posX, midY);
        let rposX = w - innerMargin - innerMargin;
        ctx.textAlign = "center";
        ctx.fillText(this.showModelAndClip ? "Clip" : "Strength", rposX - drawNumberWidgetPart.WIDTH_TOTAL / 2, midY);
        if (this.showModelAndClip) {
            rposX = rposX - drawNumberWidgetPart.WIDTH_TOTAL - innerMargin * 2;
            ctx.fillText("Model", rposX - drawNumberWidgetPart.WIDTH_TOTAL / 2, midY);
        }
        ctx.restore();
    }
    onToggleDown(event, pos, node) {
        toggleAllLoras(node);
        this.cancelMouseDown();
        return true;
    }
}
// Replaces `RgthreeBetterButtonWidget`, which utils_widgets.js does not export
// because nothing else converted wanted it. It stays a drawn surface rather than
// becoming a plain `widgets.add({type: "button"})` because the picker it opens has
// to land under the pointer, and only a surface is handed the event that says where
// that is.
class AddLoraButtonWidget extends RgthreeBaseWidget {
    constructor(name, label) {
        super(name);
        this.type = "custom";
        this.label = label;
    }
    draw(ctx, node, w, posY, height, theme) {
        drawWidgetButton(ctx, { theme, size: [w, height], pos: [0, posY] }, this.label, this.isMouseDownedAndOver);
    }
    onMouseClick(event, pos, node) {
        showLoraChooser(node, event, (value) => {
            if (value.includes("Power Lora Chooser")) {
            }
            else if (value !== "NONE") {
                // One undo step for the whole addition, rather than one per widget.
                comfy.graph.batch(() => {
                    addLoraRow(node, value);
                    relayout(node);
                });
                redrawAll(node);
            }
        });
        return true;
    }
}
class PowerLoraLoaderWidget extends RgthreeBaseWidget {
    constructor(name, valueName, valueWidget) {
        super(name);
        this.type = "custom";
        this.valueName = valueName;
        this.valueWidget = valueWidget;
        this.haveMouseMovedStrength = false;
        this.lastStrengthX = null;
        this.loraInfoPromise = null;
        this.loraInfo = null;
        this.showModelAndClip = null;
        this.hitAreas = {
            toggle: { bounds: [0, 0], onDown: this.onToggleDown },
            lora: { bounds: [0, 0], onClick: this.onLoraClick },
            strengthDec: { bounds: [0, 0], onClick: this.onStrengthDecDown },
            strengthVal: { bounds: [0, 0], onClick: this.onStrengthValUp },
            strengthInc: { bounds: [0, 0], onClick: this.onStrengthIncDown },
            strengthAny: { bounds: [0, 0], onMove: this.onStrengthAnyMove },
            strengthTwoDec: { bounds: [0, 0], onClick: this.onStrengthTwoDecDown },
            strengthTwoVal: { bounds: [0, 0], onClick: this.onStrengthTwoValUp },
            strengthTwoInc: { bounds: [0, 0], onClick: this.onStrengthTwoIncDown },
            strengthTwoAny: { bounds: [0, 0], onMove: this.onStrengthTwoAnyMove },
        };
        this._value = { ...DEFAULT_LORA_WIDGET_DATA };
    }
    set value(v) {
        this._value = v;
        if (typeof this._value !== "object") {
            this._value = { ...DEFAULT_LORA_WIDGET_DATA };
            if (this.showModelAndClip) {
                this._value.strengthTwo = this._value.strength;
            }
        }
        // The hidden widget holds this very object, so every later mutation is
        // already visible to the prompt and the saved file; this points it at the
        // object the first time, and again when a load replaces it wholesale.
        this.valueWidget.setValue(this._value);
        this.getLoraInfo();
    }
    get value() {
        return this._value;
    }
    setLora(lora) {
        this._value.lora = lora;
        this.getLoraInfo();
    }
    draw(ctx, node, w, posY, height, theme) {
        let currentShowModelAndClip = isShowingModelAndClip(node);
        if (this.showModelAndClip !== currentShowModelAndClip) {
            let oldShowModelAndClip = this.showModelAndClip;
            this.showModelAndClip = currentShowModelAndClip;
            if (this.showModelAndClip) {
                if (oldShowModelAndClip != null) {
                    this.value.strengthTwo = this.value.strength != null ? this.value.strength : 1;
                }
            }
            else {
                this.value.strengthTwo = null;
                this.hitAreas.strengthTwoDec.bounds = [0, -1];
                this.hitAreas.strengthTwoVal.bounds = [0, -1];
                this.hitAreas.strengthTwoInc.bounds = [0, -1];
                this.hitAreas.strengthTwoAny.bounds = [0, -1];
            }
        }
        ctx.save();
        // The surface is the widget's own box, so the inset the drawing used to need
        // to clear the node's edge is zero.
        const innerMargin = 3.3;
        const midY = posY + height * 0.5;
        const loraInfo = this.loraInfo;
        let posX = 0;
        drawRoundedRectangle(ctx, { theme, pos: [posX, posY], size: [w, height] });
        this.hitAreas.toggle.bounds = drawTogglePart(ctx, { posX, posY, height, value: this.value.on });
        posX += this.hitAreas.toggle.bounds[1] + innerMargin;
        if (!this.value.on) {
            ctx.globalAlpha = 0.4;
        }
        ctx.fillStyle = theme.text;
        let rposX = w - innerMargin - innerMargin;
        const strengthValue = this.showModelAndClip
            ? (this.value.strengthTwo != null ? this.value.strengthTwo : 1)
            : (this.value.strength != null ? this.value.strength : 1);
        let textColor = undefined;
        if (loraInfo && loraInfo.strengthMax != null && strengthValue > loraInfo.strengthMax) {
            textColor = "#c66";
        }
        else if (loraInfo && loraInfo.strengthMin != null && strengthValue < loraInfo.strengthMin) {
            textColor = "#c66";
        }
        const [leftArrow, text, rightArrow] = drawNumberWidgetPart(ctx, {
            posX: rposX,
            posY,
            height,
            value: strengthValue,
            direction: -1,
            textColor,
        });
        this.hitAreas.strengthDec.bounds = leftArrow;
        this.hitAreas.strengthVal.bounds = text;
        this.hitAreas.strengthInc.bounds = rightArrow;
        this.hitAreas.strengthAny.bounds = [leftArrow[0], rightArrow[0] + rightArrow[1] - leftArrow[0]];
        rposX = leftArrow[0] - innerMargin;
        if (this.showModelAndClip) {
            rposX -= innerMargin;
            this.hitAreas.strengthTwoDec.bounds = this.hitAreas.strengthDec.bounds;
            this.hitAreas.strengthTwoVal.bounds = this.hitAreas.strengthVal.bounds;
            this.hitAreas.strengthTwoInc.bounds = this.hitAreas.strengthInc.bounds;
            this.hitAreas.strengthTwoAny.bounds = this.hitAreas.strengthAny.bounds;
            let textColor = undefined;
            if (loraInfo && loraInfo.strengthMax != null && this.value.strength > loraInfo.strengthMax) {
                textColor = "#c66";
            }
            else if (loraInfo && loraInfo.strengthMin != null && this.value.strength < loraInfo.strengthMin) {
                textColor = "#c66";
            }
            const [leftArrow, text, rightArrow] = drawNumberWidgetPart(ctx, {
                posX: rposX,
                posY,
                height,
                value: this.value.strength != null ? this.value.strength : 1,
                direction: -1,
                textColor,
            });
            this.hitAreas.strengthDec.bounds = leftArrow;
            this.hitAreas.strengthVal.bounds = text;
            this.hitAreas.strengthInc.bounds = rightArrow;
            this.hitAreas.strengthAny.bounds = [
                leftArrow[0],
                rightArrow[0] + rightArrow[1] - leftArrow[0],
            ];
            rposX = leftArrow[0] - innerMargin;
        }
        const infoIconSize = height * 0.66;
        if (CONFIG_SERVICE.getConfigValue("nodes.power_lora_loader.show_info_badge")) {
            rposX -= innerMargin;
            drawInfoIcon(ctx, rposX - infoIconSize, posY + (height - infoIconSize) / 2, infoIconSize, loraInfo && loraInfo.raw && loraInfo.raw.civitai
                ? "FILLED"
                : loraInfo && loraInfo.hasInfoFile
                    ? "OUTLINED"
                    : "GRAYED");
            rposX = rposX - infoIconSize - innerMargin;
        }
        const loraWidth = rposX - posX;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        const loraLabel = String(this.value.lora || "None");
        ctx.fillText(fitString(ctx, loraLabel, loraWidth), posX, midY);
        this.hitAreas.lora.bounds = [posX, loraWidth];
        posX += loraWidth + innerMargin;
        ctx.globalAlpha = 1;
        ctx.restore();
    }
    onContextMenu(event, pos, node) {
        showRowMenu(node, this, event);
    }
    onToggleDown(event, pos, node) {
        this.value.on = !this.value.on;
        this.cancelMouseDown();
        redrawAll(node);
        return true;
    }
    onLoraClick(event, pos, node) {
        showLoraChooser(node, event, (value) => {
            this.value.lora = value;
            this.loraInfo = null;
            this.getLoraInfo();
            this.redraw();
        });
        this.cancelMouseDown();
    }
    onStrengthDecDown(event, pos, node) {
        this.stepStrength(-1, false);
    }
    onStrengthIncDown(event, pos, node) {
        this.stepStrength(1, false);
    }
    onStrengthTwoDecDown(event, pos, node) {
        this.stepStrength(-1, true);
    }
    onStrengthTwoIncDown(event, pos, node) {
        this.stepStrength(1, true);
    }
    onStrengthAnyMove(event, pos, node) {
        this.doOnStrengthAnyMove(pos, false);
    }
    onStrengthTwoAnyMove(event, pos, node) {
        this.doOnStrengthAnyMove(pos, true);
    }
    // The scrub used `event.deltaX`, which litegraph put on the event it synthesized
    // for a widget. A surface reports the raw DOM pointer, which has no such field,
    // so the step is measured against the previous position — in the units the
    // drawing already uses, which is what `deltaX` was in.
    doOnStrengthAnyMove(pos, isTwo = false) {
        const deltaX = this.lastStrengthX == null ? 0 : pos[0] - this.lastStrengthX;
        this.lastStrengthX = pos[0];
        if (!deltaX)
            return;
        let prop = isTwo ? "strengthTwo" : "strength";
        this.haveMouseMovedStrength = true;
        this.value[prop] = (this.value[prop] != null ? this.value[prop] : 1) + deltaX * 0.05;
        this.redraw();
    }
    onStrengthValUp(event, pos, node) {
        this.doOnStrengthValUp(event, false);
    }
    onStrengthTwoValUp(event, pos, node) {
        this.doOnStrengthValUp(event, true);
    }
    doOnStrengthValUp(event, isTwo = false) {
        if (this.haveMouseMovedStrength)
            return;
        let prop = isTwo ? "strengthTwo" : "strength";
        const current = this.value[prop] != null ? this.value[prop] : 1;
        comfy.ui.prompt({ label: "Value", value: String(current) }).then((v) => {
            if (v === undefined)
                return;
            this.value[prop] = Number(v);
            this.redraw();
        });
    }
    onMouseDown(event, pos, node) {
        this.lastStrengthX = pos[0];
    }
    onMouseUp(event, pos, node) {
        super.onMouseUp(event, pos, node);
        this.haveMouseMovedStrength = false;
        this.lastStrengthX = null;
    }
    stepStrength(direction, isTwo = false) {
        let step = 0.05;
        let prop = isTwo ? "strengthTwo" : "strength";
        let strength = (this.value[prop] != null ? this.value[prop] : 1) + step * direction;
        this.value[prop] = Math.round(strength * 100) / 100;
        this.redraw();
    }
    getLoraInfo(force = false) {
        if (!this.loraInfoPromise || force == true) {
            let promise;
            if (this.value.lora && this.value.lora != "None") {
                promise = LORA_INFO_SERVICE.getInfo(this.value.lora, force, true);
            }
            else {
                promise = Promise.resolve(null);
            }
            this.loraInfoPromise = promise.then((v) => {
                this.loraInfo = v;
                this.redraw();
            });
        }
        return this.loraInfoPromise;
    }
}
// Fires whoever caused the reload, where `refreshComboInNode(defs)` only fired for
// the node hook ComfyUI called when object_info came back.
comfy.defs.onRefreshed(() => {
    rgthreeApi.getLoras(true);
});
comfy.defs.extend(NodeTypesString.POWER_LORA_LOADER, (b) => {
    b.onCreated((node) => {
        // onCreated fires whenever the node joins a graph, which can happen more
        // than once; the old constructor ran once, and mount() throws on a duplicate
        // name. The chrome widget is what answers that, where `nodeStates` cannot:
        // `stateOf` creates an entry on first read, so the map says nothing about
        // whether this ever ran.
        if (node.widgets.get(HEADER_SURFACE)) {
            return;
        }
        node.setSerializeWidgets(true);
        if (node.getProperty(PROP_LABEL_SHOW_STRENGTHS) === undefined) {
            node.setProperty(PROP_LABEL_SHOW_STRENGTHS, PROP_VALUE_SHOW_STRENGTHS_SINGLE);
        }
        if (node.getProperty(PROP_LABEL_LORA_MATCH) === undefined) {
            node.setProperty(PROP_LABEL_LORA_MATCH, "");
        }
        rgthreeApi.getLoras();
        const state = stateOf(node);
        state.header = new PowerLoraLoaderHeaderWidget(HEADER_SURFACE);
        mountRgthreeWidget(node, state.header, { height: ROW_HEIGHT });
        mountRgthreeWidget(node, new AddLoraButtonWidget(ADD_LORA_SURFACE, "➕ Add Lora"), { height: ROW_HEIGHT });
        node.setSizeConstraints({ autoHeight: true });
    });
    b.onConfigured((node, data) => {
        const values = Array.isArray(data.widgets_values) ? data.widgets_values : [];
        configurePowerLoraValues(node, values);
    });
    b.onPropertyChanged((node, event) => {
        if (event.name === PROP_LABEL_SHOW_STRENGTHS) {
            redrawAll(node);
        }
    });
    b.onRemoved((node) => {
        nodeStates.delete(node.id);
    });
    b.addMenuItem(helpMenuItem(NodeTypesString.POWER_LORA_LOADER, getHelp()));
});
