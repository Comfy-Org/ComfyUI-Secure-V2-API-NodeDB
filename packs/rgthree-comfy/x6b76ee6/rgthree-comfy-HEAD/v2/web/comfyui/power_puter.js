import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { helpMenuItem } from "./base_node.js";
import { removeUnusedInputsFromEnd } from "./utils_inputs_outputs.js";
import { debounce } from "../../rgthree/common/shared_utils.js";
import { RgthreeBaseWidget } from "./utils_widgets.js";
import { drawPlusIcon, drawRoundedRectangle, drawWidgetButton, measureText } from "./utils_canvas.js";

// CONVERTED — both blockers are gone.
//
// The chips are drawn with the theme `draw` is handed, and clicking one opens
// `comfy.ui.showMenu({items, title, event})` where the pointer is, which is the
// whole of what `new LiteGraph.ContextMenu(OUTPUT_TYPES, {event, title, callback})`
// was doing. The pointer routing is `widgets.canvas`'s down/move/up through the
// converted `RgthreeBaseWidget` router in utils_widgets.js.
//
// The chip row is one widget again and sits above the code box, where it was. The
// marker that stood here — "`CanvasDef` has no `defaultValue`" — named a destination
// that already existed: a `widgets.canvas` surface takes `defaultValue`, `serialize` and
// `sendToPrompt` and forwards all three to the mount behind it, so a drawn control that
// holds a value is a single widget occupying a single `widgets_values` slot.
//
// COSMETIC: the type menu's separator before "🗑️ Delete" is gone; `MenuItemDef`
//   has no separator, and `null` in the items array is not a published entry.
//
// WIRE FORMAT: unchanged. `widgets_values` is still `[{outputs: [...]}, "<code>"]` and
// the prompt still carries `outputs` and `code` by name — the chips are the `outputs`
// widget at index 0 and the code box index 1, the order `addInitialWidgets` created them
// in. The setter's back-compat reads are carried over verbatim — a bare string becomes a
// one-entry list and the legacy "BOOL" becomes "BOOLEAN" — because old workflows
// hold both shapes.
const ALPHABET = "abcdefghijklmnopqrstuv".split("");
const OUTPUT_TYPES = ["STRING", "INT", "FLOAT", "BOOLEAN", "*"];
const OUTPUTS_WIDGET = "outputs";
const CODE_WIDGET = "code";
// Was `LiteGraph.NODE_WIDGET_HEIGHT - 4` and `NODE_WIDGET_HEIGHT * 0.5`. The
// renderer constant is not published, and a widget that owns its own surface picks
// its own size rather than borrowing core's.
const OUTPUTS_WIDGET_CHIP_HEIGHT = 16;
const OUTPUTS_WIDGET_CHIP_RADIUS = 10;
const OUTPUTS_WIDGET_CHIP_SPACE = 4;
const OUTPUTS_WIDGET_CHIP_ARROW_WIDTH = 5.5;
const OUTPUTS_WIDGET_CHIP_ARROW_HEIGHT = 4;
// Handles hold no arbitrary properties, so what the old class kept on the instance
// lives here, keyed by node id and dropped in onRemoved. `debounce` keys by
// function identity, so each node needs its own stabilizer.
const stabilizersByNode = new Map();
const chipsByNode = new Map();
function neededHeight(rows) {
    return OUTPUTS_WIDGET_CHIP_SPACE + (OUTPUTS_WIDGET_CHIP_HEIGHT + OUTPUTS_WIDGET_CHIP_SPACE) * rows;
}
function addAnyInput(node, num = 1) {
    for (let i = 0; i < num; i++)
        node.inputs.add(ALPHABET[node.inputs.length], "*");
}
function setOutputs(node, desiredOutputs) {
    // The secure schema declares ten stable wildcard slots so every persisted
    // link index validates. Trim those placeholders from the end before
    // applying the widget's selected output list. Removing while iterating
    // forward skips every other shifted slot.
    while (node.outputs.length > desiredOutputs.length) {
        const index = node.outputs.length - 1;
        const output = node.outputs.at(index);
        output?.disconnect();
        node.outputs.remove({ index });
    }
    for (let i = 0; i < desiredOutputs.length; i++) {
        const desired = desiredOutputs[i];
        let output = node.outputs.at(i);
        if (!output)
            output = node.outputs.add("", "");
        const outputLabel = output.label === "*" || output.label === output.type ? null : output.label;
        output.modify({ type: String(desired), label: outputLabel || String(desired) });
    }
}
function stabilize(node) {
    if (node.isDeleted)
        return;
    removeUnusedInputsFromEnd(node, 1);
    addAnyInput(node);
    const chips = chipsByNode.get(node.id);
    if (chips)
        setOutputs(node, chips.value.outputs);
}
function scheduleStabilize(node, ms = 64) {
    let stabilizer = stabilizersByNode.get(node.id);
    if (!stabilizer)
        stabilizersByNode.set(node.id, (stabilizer = () => stabilize(node)));
    return debounce(stabilizer, ms);
}
// The code box was `ComfyWidgets["STRING"](…, {multiline: true})`, which is a DOM
// widget holding a textarea. `mount` is that, owned by the pack.
function mountCodeWidget(node) {
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
            inputEl.addEventListener("input", () => value.set(inputEl.value));
            container.appendChild(inputEl);
            stopWatching = value.onChange((v) => (inputEl.value = String(v)));
        },
        destroy() {
            if (stopWatching)
                stopWatching();
        },
    });
}
// Not mountRgthreeWidget: the chip row wraps to a new line as outputs are added,
// and a surface that declares `height` has it read once. Left undeclared, the
// canvas takes whatever box the node gives it, and `setHeight` re-states that box
// as `rows` changes.
//
// One widget, not two: `CanvasDef.defaultValue` makes a drawing surface hold a value,
// so the chips *are* the `outputs` widget rather than a drawing sitting beside a hidden
// one — which is what puts the row back above the code box, where it was.
function mountChips(node, chips) {
    const surface = node.widgets.canvas({
        name: OUTPUTS_WIDGET,
        defaultValue: { outputs: ["STRING"] },
        serialize: true,
        draw(ctx, size, theme) {
            chips.size = size;
            chips.draw(ctx, node, size[0], 0, size[1], theme);
        },
        onPointerDown: (e) => chips.onPointerDown(e.event, [e.x, e.y], node),
        onPointerMove: (e) => chips.onPointerMove(e.event, [e.x, e.y], node),
        onPointerUp: (e) => chips.onPointerUp(e.event, [e.x, e.y], node),
    });
    chips.surface = surface;
    chips.valueWidget = surface.widget;
    chips.redraw = surface.redraw;
    surface.widget.setHeight(neededHeight(chips.rows));
}
function getHelp() {
    return `
      <p>
        The ${NodeTypesString.POWER_PUTER.replace("(rgthree)", "")} is a powerful and versatile node that opens the
        door for a wide range of utility by offering mult-line code parsing for output. This node
        can be used for simple string concatenation, or math operations; to an image dimension or a
        node's widgets with advanced list comprehension.
        If you want to output something in your workflow, this is the node to do it.
      </p>

      <ul>
        <li><p>
          Evaluate almost any kind of input and more, and choose your output from INT, FLOAT,
          STRING, or BOOLEAN.
        </p></li>
        <li><p>
          Connect some nodes and do simply math operations like <code>a + b</code> or
          <code>ceil(1 / 2)</code>.
        </p></li>
        <li><p>
          Or do more advanced things, like input an image, and get the width like
          <code>a.shape[2]</code>.
        </p></li>
        <li><p>
          Even more powerful, you can target nodes in the prompt that's sent to the backend. For
          instance; if you have a Power Lora Loader node at id #5, and want to get a comma-delimited
          list of the enabled loras, you could enter
          <code>', '.join([v.lora for v in node(5).inputs.values() if 'lora' in v and v.on])</code>.
        </p></li>
        <li><p>
          See more at the <a target="_blank"
          href="https://github.com/rgthree/rgthree-comfy/wiki/Node:-Power-Puter">rgthree-comfy
          wiki</a>.
        </p></li>
      </ul>`;
}
class OutputsWidget extends RgthreeBaseWidget {
    constructor(name) {
        super(name);
        this.type = "custom";
        this._value = { outputs: ["STRING"] };
        this.rows = 1;
        this.hitAreas = { add: { bounds: [0, 0], onClick: this.onAddChipDown } };
        for (let i = 0; i < 10; i++)
            this.hitAreas[`output${i}`] = { bounds: [0, 0], onClick: this.onOutputChipDown, data: { index: i } };
        // Assigned by mountChips: the surface it draws on is also the widget that holds
        // its value.
        this.valueWidget = null;
        this.surface = null;
    }
    set value(v) {
        let outputs = typeof v === "string" ? [v] : [...v.outputs];
        outputs = outputs.map((o) => (o === "BOOL" ? "BOOLEAN" : o));
        this._value.outputs = outputs;
        // The widget holds the same object, so a later splice or push is already
        // visible to it; this is what points it at the object the first time and after
        // a load replaces the list.
        this.valueWidget.setValue(this._value);
    }
    get value() {
        return this._value;
    }
    onAddChipDown(event, pos, node, bounds) {
        comfy.ui.showMenu({
            title: "Add an output",
            event,
            items: OUTPUT_TYPES.map((type) => ({
                label: type,
                run: () => {
                    this._value.outputs.push(type);
                    scheduleStabilize(node);
                    this.redraw();
                },
            })),
        });
        this.cancelMouseDown();
        return true;
    }
    onOutputChipDown(event, pos, node, bounds) {
        const index = bounds.data.index;
        const items = OUTPUT_TYPES.map((type) => ({
            label: type,
            run: () => this.setOutputType(node, index, type),
        }));
        if (this.value.outputs.length > 1) {
            items.push({ label: "🗑️ Delete", run: () => this.deleteOutput(node, index) });
        }
        comfy.ui.showMenu({ title: `Edit output #${index + 1}`, event, items });
        this.cancelMouseDown();
        return true;
    }
    setOutputType(node, index, type) {
        if (type === this._value.outputs[index])
            return;
        const output = node.outputs.at(index);
        if (output && output.links().length && type !== "*") {
            comfy.commands.notify({ severity: "warn", life: 3000, summary: "[Power Puter] Changing output type of linked output! You should check for compatibility." });
        }
        this._value.outputs[index] = type;
        scheduleStabilize(node);
        this.redraw();
    }
    deleteOutput(node, index) {
        const output = node.outputs.at(index);
        if (output && output.links().length) {
            comfy.commands.notify({ severity: "warn", life: 3000, summary: "[Power Puter] Removed and disconnected output from that was connected!" });
            output.disconnect();
        }
        node.outputs.remove({ index });
        this._value.outputs.splice(index, 1);
        scheduleStabilize(node);
        this.redraw();
    }
    draw(ctx, node, w, posY, height, theme) {
        ctx.save();
        // The surface is the widget's own box, so the inset the drawing used to
        // need to clear the node's edge is zero.
        const innerMargin = 3.3;
        let midY = posY + height * 0.5;
        let posX = 0;
        let rposX = w;
        drawRoundedRectangle(ctx, {
            theme,
            pos: [posX, posY],
            size: [w, height],
            borderRadius: OUTPUTS_WIDGET_CHIP_RADIUS,
        });
        posX += innerMargin * 2;
        rposX -= innerMargin * 2;
        ctx.fillStyle = theme.textSecondary;
        ctx.strokeStyle = theme.textSecondary;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText("outputs", posX, midY);
        posX += measureText(ctx, "outputs") + innerMargin * 2;
        ctx.stroke(new Path2D(`M ${posX} ${posY} v ${height}`));
        posX += 1 + innerMargin * 2;
        const inititalPosX = posX;
        posY += OUTPUTS_WIDGET_CHIP_SPACE;
        height = OUTPUTS_WIDGET_CHIP_HEIGHT;
        const borderRadius = height * 0.5;
        midY = posY + height / 2;
        ctx.textAlign = "center";
        ctx.lineJoin = ctx.lineCap = "round";
        ctx.fillStyle = ctx.strokeStyle = theme.text;
        let rows = 1;
        const values = this.value.outputs;
        const fontSize = ctx.font.match(/(\d+)px/);
        if (fontSize && fontSize[1]) {
            ctx.font = ctx.font.replace(fontSize[1], `${Number(fontSize[1]) - 2}`);
        }
        let i = 0;
        for (i; i < values.length; i++) {
            const hitArea = this.hitAreas[`output${i}`];
            const isClicking = !!hitArea.wasMouseClickedAndIsOver;
            hitArea.data.index = i;
            const text = values[i];
            const textWidth = measureText(ctx, text) + innerMargin * 2;
            const width = textWidth + OUTPUTS_WIDGET_CHIP_ARROW_WIDTH + innerMargin * 5;
            if (posX + width >= rposX) {
                posX = inititalPosX;
                posY = posY + height + 4;
                midY = posY + height / 2;
                rows++;
            }
            drawWidgetButton(ctx, { theme, pos: [posX, posY], size: [width, height], borderRadius }, null, isClicking);
            const startX = posX;
            posX += innerMargin * 2;
            const newMidY = midY + (isClicking ? 1 : 0);
            ctx.fillText(text, posX + textWidth / 2, newMidY);
            posX += textWidth + innerMargin;
            const arrow = new Path2D(`M${posX} ${newMidY - OUTPUTS_WIDGET_CHIP_ARROW_HEIGHT / 2}
         h${OUTPUTS_WIDGET_CHIP_ARROW_WIDTH}
         l-${OUTPUTS_WIDGET_CHIP_ARROW_WIDTH / 2} ${OUTPUTS_WIDGET_CHIP_ARROW_HEIGHT} z`);
            ctx.fill(arrow);
            ctx.stroke(arrow);
            posX += OUTPUTS_WIDGET_CHIP_ARROW_WIDTH + innerMargin * 2;
            hitArea.bounds = [startX, posY, width, height];
            posX += OUTPUTS_WIDGET_CHIP_SPACE;
        }
        for (i; i < 9; i++) {
            const hitArea = this.hitAreas[`output${i}`];
            if (hitArea.bounds[0] > 0)
                hitArea.bounds = [0, 0, 0, 0];
        }
        const addHitArea = this.hitAreas["add"];
        if (this.value.outputs.length < 10) {
            const isClicking = !!addHitArea.wasMouseClickedAndIsOver;
            const plusSize = 10;
            let plusWidth = innerMargin * 2 + plusSize + innerMargin * 2;
            if (posX + plusWidth >= rposX) {
                posX = inititalPosX;
                posY = posY + height + 4;
                midY = posY + height / 2;
                rows++;
            }
            drawWidgetButton(ctx, { theme, size: [plusWidth, height], pos: [posX, posY], borderRadius }, null, isClicking);
            drawPlusIcon(ctx, posX + innerMargin * 2, midY + (isClicking ? 1 : 0), plusSize);
            addHitArea.bounds = [posX, posY, plusWidth, height];
        }
        else {
            addHitArea.bounds = [0, 0, 0, 0];
        }
        ctx.restore();
        // Re-stated rather than declared once: the row count is only known after the
        // chips have been laid out, and restating it re-lays the node out, which
        // draws again. The very first draw runs inside the mount that creates the
        // surface, which sets the same height on the way out.
        if (rows !== this.rows) {
            this.rows = rows;
            if (this.surface)
                this.surface.widget.setHeight(neededHeight(rows));
        }
    }
}
comfy.defs.extend(NodeTypesString.POWER_PUTER, (b) => {
    b.onCreated((node) => {
        // onCreated fires whenever the node joins a graph, which can happen more
        // than once; the old constructor ran once, and mount() throws on a
        // duplicate name. The widget is checked as well as the map because a node
        // moved between graphs is removed and re-added, which drops the map entry
        // while its widgets survive.
        if (chipsByNode.has(node.id) || node.widgets.get(OUTPUTS_WIDGET))
            return;
        node.setSerializeWidgets(true);
        // Chips first, code box second — the order `addInitialWidgets` created them in,
        // and the order `widgets_values` records.
        const chips = new OutputsWidget(OUTPUTS_WIDGET);
        mountChips(node, chips);
        chips.value = chips.valueWidget.getValue();
        chipsByNode.set(node.id, chips);
        // The host builds a def's own widgets now, where the old base class
        // reimplemented that walk itself, so the code box is only mounted if the def
        // did not already supply one.
        if (!node.widgets.get(CODE_WIDGET))
            mountCodeWidget(node);
        if (!node.inputs.length)
            addAnyInput(node, 2);
        setOutputs(node, chips.value.outputs);
    });
    b.onConfigured((node) => {
        const chips = chipsByNode.get(node.id);
        const valueWidget = node.widgets.get(OUTPUTS_WIDGET);
        if (!chips || !valueWidget)
            return;
        const saved = valueWidget.getValue();
        if (saved) {
            chips.value = saved;
        }
        stabilize(node);
        chips.redraw();
    });
    b.onConnectionsChanged((node) => {
        scheduleStabilize(node);
    });
    b.onRemoved((node) => {
        chipsByNode.delete(node.id);
        stabilizersByNode.delete(node.id);
    });
    b.addMenuItem(helpMenuItem(NodeTypesString.POWER_PUTER, getHelp()));
});
