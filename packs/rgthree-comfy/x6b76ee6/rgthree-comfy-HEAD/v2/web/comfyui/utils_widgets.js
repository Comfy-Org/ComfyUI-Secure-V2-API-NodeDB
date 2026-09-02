// PARTIALLY CONVERTED — the hit-test router is live; the five drawn widgets built
// on it are not.
//
// `widgets.canvas` now reports pointer events in the same coordinates `draw`
// receives, so `RgthreeBaseWidget` — a `hitAreas` map of `{bounds, onDown, onUp,
// onMove, onClick}` that litegraph used to route through one `mouse(event, pos,
// node)` — converts almost unchanged: the three phases become three entry points.
// What goes with the node's shared canvas is the *frame* of reference, not the
// maths: a widget owns its whole surface now, so `pos` is relative to the drawing
// and no longer to the node. That is also what retires `last_y` and
// `LiteGraph.NODE_WIDGET_HEIGHT` from the pointer-left-the-widget test, which
// existed only to work out where in the node's canvas the widget had been drawn.
//
// A `widgets.canvas` surface repaints on mount, on resize and on `redraw()`, not
// once a frame, so anything that used to rely on the next frame picking a change
// up — an image finishing loading, a value the user just clicked — has to ask.
// `redraw` is handed to the widget below for exactly that.
//
// The palette is no longer a reason to hold anything back: `draw` receives the
// theme, and `mountRgthreeWidget` forwards it to the widget as a sixth argument.
// `drawLabelAndValue`, `RgthreeBetterButtonWidget`, `RgthreeBetterTextWidget`,
// `RgthreeDividerWidget` and `RgthreeLabelWidget` are still absent, but only
// because nothing converted imports them — power_lora_loader.js draws its own
// button, and the rest belong to files that are punted for their own reasons.
// COSMETIC: `app.canvas.prompt("Label", value, cb, event)`, the field
//   `RgthreeBetterTextWidget` drew at the cursor, is `comfy.ui.prompt({label})` —
//   the same question asked in a modal. The capability is served; the placement is
//   not.
//
// `RgthreeInvisibleWidget` is no longer blocked in any part. A zero-height widget
// that still occupies a `widgets_values` slot is `widgets.add({...})` plus
// `setHeight(0)` — the earlier note here claimed that had no equivalent and
// offered `setHidden(true)`, which is a different thing; `setHeight` shipped and
// closes it exactly. Its prompt-time `serializeValueFn(node, index)` is
// `on('beforeSerialize', e => { if (e.context === 'prompt') e.setSerializedValue(v) })`.
// It is not written here because its only caller, dynamic_context_base.js, is
// punted for slot gaps, and an export nothing imports is worse than an absent one.
export class RgthreeBaseWidget {
    constructor(name) {
        this.type = "custom";
        this.options = {};
        this.size = [0, 0];
        this.disabled = false;
        this.mouseDowned = null;
        this.isMouseDownedAndOver = false;
        this.hitAreas = {};
        this.downedHitAreasForMove = [];
        this.downedHitAreasForClick = [];
        this.name = name;
        this.redraw = () => { };
    }
    clickWasWithinBounds(pos, bounds) {
        let xStart = bounds[0];
        let xEnd = xStart + (bounds.length > 2 ? bounds[2] : bounds[1]);
        const clickedX = pos[0] >= xStart && pos[0] <= xEnd;
        if (bounds.length === 2) {
            return clickedX;
        }
        return clickedX && pos[1] >= bounds[1] && pos[1] <= bounds[1] + bounds[3];
    }
    // The three phases still answer "did I handle this", because the hit areas a
    // subclass declares do. Nothing reads the answer any more — the surface has
    // already taken the primary button by the time these run — but composing it is
    // what lets a subclass keep the handlers it wrote.
    onPointerDown(event, pos, node) {
        var _a;
        this.mouseDowned = [...pos];
        this.isMouseDownedAndOver = true;
        this.downedHitAreasForMove.length = 0;
        this.downedHitAreasForClick.length = 0;
        let anyHandled = false;
        for (const part of Object.values(this.hitAreas)) {
            if (this.clickWasWithinBounds(pos, part.bounds)) {
                if (part.onMove) {
                    this.downedHitAreasForMove.push(part);
                }
                if (part.onClick) {
                    this.downedHitAreasForClick.push(part);
                }
                if (part.onDown) {
                    const thisHandled = part.onDown.apply(this, [event, pos, node, part]);
                    anyHandled = anyHandled || thisHandled == true;
                }
                part.wasMouseClickedAndIsOver = true;
            }
        }
        return (_a = this.onMouseDown(event, pos, node)) !== null && _a !== void 0 ? _a : anyHandled;
    }
    onPointerUp(event, pos, node) {
        var _a;
        if (!this.mouseDowned)
            return true;
        this.downedHitAreasForMove.length = 0;
        const wasMouseDownedAndOver = this.isMouseDownedAndOver;
        this.cancelMouseDown();
        let anyHandled = false;
        for (const part of Object.values(this.hitAreas)) {
            if (part.onUp && this.clickWasWithinBounds(pos, part.bounds)) {
                const thisHandled = part.onUp.apply(this, [event, pos, node, part]);
                anyHandled = anyHandled || thisHandled == true;
            }
            part.wasMouseClickedAndIsOver = false;
        }
        for (const part of this.downedHitAreasForClick) {
            if (this.clickWasWithinBounds(pos, part.bounds)) {
                const thisHandled = part.onClick.apply(this, [event, pos, node, part]);
                anyHandled = anyHandled || thisHandled == true;
            }
        }
        this.downedHitAreasForClick.length = 0;
        if (wasMouseDownedAndOver) {
            const thisHandled = this.onMouseClick(event, pos, node);
            anyHandled = anyHandled || thisHandled == true;
        }
        return (_a = this.onMouseUp(event, pos, node)) !== null && _a !== void 0 ? _a : anyHandled;
    }
    onPointerMove(event, pos, node) {
        var _a;
        this.isMouseDownedAndOver = !!this.mouseDowned;
        if (this.mouseDowned &&
            (pos[0] < 0 ||
                pos[0] > this.size[0] ||
                pos[1] < 0 ||
                pos[1] > this.size[1])) {
            this.isMouseDownedAndOver = false;
        }
        for (const part of Object.values(this.hitAreas)) {
            if (this.downedHitAreasForMove.includes(part)) {
                part.onMove.apply(this, [event, pos, node, part]);
            }
            if (this.downedHitAreasForClick.includes(part)) {
                part.wasMouseClickedAndIsOver = this.clickWasWithinBounds(pos, part.bounds);
            }
        }
        return (_a = this.onMouseMove(event, pos, node)) !== null && _a !== void 0 ? _a : true;
    }
    cancelMouseDown() {
        this.mouseDowned = null;
        this.isMouseDownedAndOver = false;
        this.downedHitAreasForMove.length = 0;
    }
    onMouseDown(event, pos, node) {
        return;
    }
    onMouseUp(event, pos, node) {
        return;
    }
    onMouseClick(event, pos, node) {
        return;
    }
    onMouseMove(event, pos, node) {
        return;
    }
}
/**
 * Gives a widget a surface of its own and routes that surface's pointers into the
 * router above.
 *
 * `draw` keeps the `(ctx, node, width, y, height)` signature it always had, with
 * `y` fixed at 0: a subclass drew a band of the node's canvas and now owns the
 * whole thing, so the offset it used to be handed is always the origin. The theme
 * follows as a sixth argument, since a subclass that paints has to be told the
 * palette rather than reading a renderer constant.
 *
 * Right-click is claimed only for a widget that declares a handler for it —
 * declaring it at all suppresses the node's own menu, which is right for a lora
 * row and wrong for everything else.
 */
export function mountRgthreeWidget(node, w, { height, defaultValue, serialize } = {}) {
    const surface = node.widgets.canvas({
        name: w.name,
        ...(height == null ? {} : { height }),
        ...(defaultValue === undefined ? {} : { defaultValue, serialize }),
        draw(ctx, size, theme) {
            w.size = size;
            w.draw(ctx, node, size[0], 0, size[1], theme);
        },
        onPointerDown: (e) => w.onPointerDown(e.event, [e.x, e.y], node),
        onPointerMove: (e) => w.onPointerMove(e.event, [e.x, e.y], node),
        onPointerUp: (e) => w.onPointerUp(e.event, [e.x, e.y], node),
        ...(w.onContextMenu ? { onContextMenu: (e) => w.onContextMenu(e.event, [e.x, e.y], node) } : {}),
    });
    // A stated height is pinned, so the node reserves the height the drawing actually
    // uses instead of handing the surface whatever it has spare. Omitting it is the
    // other half of the same rule: a widget that declares no height is the one that
    // absorbs the node's spare space, which is what a panel meant to fill the node —
    // the image comparer — wants.
    if (height != null) {
        surface.widget.setHeight(height);
    }
    w.redraw = surface.redraw;
    return surface;
}
