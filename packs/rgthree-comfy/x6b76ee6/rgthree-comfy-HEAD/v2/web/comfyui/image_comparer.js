import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { helpMenuItem } from "./base_node.js";
import { RgthreeBaseWidget, mountRgthreeWidget } from "./utils_widgets.js";

// CONVERTED — the two blockers that decided the earlier refusal are both gone.
//
// The pointer half is now expressible: `widgets.canvas` reports down / move / up in
// the same coordinates `draw` receives, which is all this node ever wanted. The
// apparatus around that goes rather than moves — `app.canvas.pointer_is_down`
// polled on a requestAnimationFrame loop is `onPointerDown`/`onPointerUp`, and the
// node-local `pointerOverPos` is the move event's own x. Entering and leaving the
// node is `b.onHover`. The serialization half was closed earlier by
// `on('beforeSerialize')`, which is what lets one widget write a bare array to the
// saved workflow and `{images: […]}` to the prompt.
//
// `measureText` was never a gap: utils_canvas.js's version is
// `ctx.measureText(str).width` and nothing more, so it is inlined rather than
// imported from a punted module. `isLowQuality` was never imported by this file.
//
// REFUSED, not a gap: (16) it wrote `this.imgs` — the array core's own right-click
//   menu reads for "Open Image" / "Save Image" — and swung `this.imageIndex`
//   between 0 and 1 so those entries followed whichever half you clicked. Reading
//   is published (`node.getOutputImages()`, `node.getDisplayedImageIndex()`);
//   writing is not, so a node cannot install its own pair into core's menu. Those
//   menu entries no longer appear, and the paragraph of `getHelp()` that promised
//   them is deleted rather than left to lie to users.
// Two markers here named destinations that already existed, and both are converted.
// A `widgets.canvas` surface does take `defaultValue`/`serialize` — it forwards them to
// the mount behind it — so the comparer is one widget holding one `widgets_values` slot
// rather than a drawing beside a hidden value. And a surface that states no height is
// the one the node hands its spare space to, which is what "grows when you drag the node
// taller" means; `setHeight` is what pinned it, and the comparer no longer calls it.
//
// LIMITATION: `'&rand=' + Math.random()` is suppressed by `app.getRandParam()` when the
//   host is cloud-served, so a cloud install can serve the image from cache. The one-line
//   value is trivial to reproduce; "am I on cloud?" is not readable, so the cache buster
//   is unconditional and a cloud install re-fetches each image once per execution. The
//   images shown are correct either way — this costs bandwidth, not behaviour.
// REFUSED, not a gap: `addConnectionLayoutSupport` — the pack's Left/Right slot layout,
//   which patches `getConnectionPos` on the node class and recomputes socket positions
//   from renderer constants. Deciding where the renderer draws a socket is refused, not
//   pending; see utils.js. `getSlotPosition()` reads where the renderer put one, which
//   is what anchoring to a socket needs.
// COSMETIC: no property metadata. `RgthreeImageComparer["@comparer_mode"] =
//   {type: "combo", values: ["Slide", "Click"]}` told the properties panel to edit
//   that property with a two-item picker rather than a free text field. The property
//   still works and still saves.
//
// WIRE FORMAT: unchanged. The saved workflow still holds one entry, the bare array
// `[{name, selected, url}, …]`, and the queued prompt still holds
// `{images: [{name, selected, url}, …]}` under the input `rgthree_comparer` — two
// shapes from one widget, which is why `e.context` is honoured rather than
// ignored. The drawing surface declares `serialize: false`, so it occupies no slot
// and adds no hole.
const COMPARER_HEIGHT = 300;
// `app.getPreviewFormatParam()` and `app.getRandParam()` are ComfyApp helpers with
// no published equivalent; both are one line of their own.
function getPreviewFormatParam() {
    const preview_format = comfy.settings.get("Comfy.PreviewFormat");
    return preview_format ? `&preview=${preview_format}` : "";
}
function getRandParam() {
    return "&rand=" + Math.random();
}
function imageDataToUrl(data) {
    return comfy.backend.url(`/view?filename=${encodeURIComponent(data.filename)}&type=${data.type}&subfolder=${data.subfolder}${getPreviewFormatParam()}${getRandParam()}`);
}
// Handles hold no arbitrary properties, so the widget — which carries the images,
// which pair is showing, and where the pointer is — lives here, keyed by node id,
// and is dropped in onRemoved.
const comparers = new Map();
function getHelp() {
    return `
      <p>
        The ${NodeTypesString.IMAGE_COMPARER.replace("(rgthree)", "")} node compares two images on top of each other.
      </p>
      <ul>
        <li>
          <p>
            <strong>Inputs</strong>
          </p>
          <ul>
            <li><p>
              <code>image_a</code> <i>Optional.</i> The first image to use to compare.
              image_a.
            </p></li>
            <li><p>
              <code>image_b</code> <i>Optional.</i> The second image to use to compare.
            </p></li>
            <li><p>
              <b>Note</b> <code>image_a</code> and <code>image_b</code> work best when a single
              image is provided. However, if each/either are a batch, you can choose which item
              from each batch are chosen to be compared. If either <code>image_a</code> or
              <code>image_b</code> are not provided, the node will choose the first two from the
              provided input if it's a batch, otherwise only show the single image (just as
              Preview Image would).
            </p></li>
          </ul>
        </li>
        <li>
          <p>
            <strong>Properties.</strong> You can change the following properties (by right-clicking
            on the node, and select "Properties" or "Properties Panel" from the menu):
          </p>
          <ul>
            <li><p>
              <code>comparer_mode</code> - Choose between "Slide" and "Click". Defaults to "Slide".
            </p></li>
          </ul>
        </li>
      </ul>`;
}
class RgthreeImageComparerWidget extends RgthreeBaseWidget {
    constructor(name) {
        super(name);
        this.type = "custom";
        this.hitAreas = {};
        this.selected = [];
        this._value = { images: [] };
        this.isPointerDown = false;
        this.isPointerOver = false;
        this.pointerOverPos = [0, 0];
        // Assigned by the caller: the surface it draws on is also the widget holding
        // its value.
        this.valueWidget = null;
    }
    set value(v) {
        let cleanedVal;
        if (Array.isArray(v)) {
            cleanedVal = v.map((d, i) => {
                if (!d || typeof d === "string") {
                    d = { url: d, name: i == 0 ? "A" : "B", selected: true };
                }
                return d;
            });
        }
        else {
            cleanedVal = v.images || [];
        }
        if (cleanedVal.length > 2) {
            const hasAAndB = cleanedVal.some((i) => i.name.startsWith("A")) &&
                cleanedVal.some((i) => i.name.startsWith("B"));
            if (!hasAAndB) {
                cleanedVal = [cleanedVal[0], cleanedVal[1]];
            }
        }
        let selected = cleanedVal.filter((d) => d.selected);
        if (!selected.length && cleanedVal.length) {
            cleanedVal[0].selected = true;
        }
        selected = cleanedVal.filter((d) => d.selected);
        if (selected.length === 1 && cleanedVal.length > 1) {
            cleanedVal.find((d) => !d.selected).selected = true;
        }
        this._value.images = cleanedVal;
        selected = cleanedVal.filter((d) => d.selected);
        this.setSelected(selected);
        // Handing the normalized object to the value widget is what puts the
        // truncated, `selected`-filled list into the saved workflow — `_value` used
        // to be what `serializeValue` read straight off this object. Identity is
        // also the re-entry guard: the change this provokes carries the very object
        // it was given.
        this.valueWidget.setValue(this._value);
        this.redraw();
    }
    get value() {
        return this._value;
    }
    setSelected(selected) {
        this._value.images.forEach((d) => (d.selected = false));
        for (const sel of selected) {
            if (!sel.img) {
                sel.img = new Image();
                // The surface repaints on mount, on resize and on request — never per
                // frame — so a decode finishing has to say so itself.
                sel.img.addEventListener("load", () => this.redraw());
                sel.img.src = sel.url;
            }
            sel.selected = true;
        }
        this.selected = selected;
    }
    draw(ctx, node, width, y) {
        this.hitAreas = {};
        if (this.value.images.length > 2) {
            ctx.textAlign = "left";
            ctx.textBaseline = "top";
            ctx.font = `14px Arial`;
            const drawData = [];
            const spacing = 5;
            let x = 0;
            for (const img of this.value.images) {
                const width = ctx.measureText(img.name).width;
                drawData.push({
                    img,
                    text: img.name,
                    x,
                    width,
                });
                x += width + spacing;
            }
            x = (width - (x - spacing)) / 2;
            for (const d of drawData) {
                ctx.fillStyle = d.img.selected ? "rgba(180, 180, 180, 1)" : "rgba(180, 180, 180, 0.5)";
                ctx.fillText(d.text, x, y);
                this.hitAreas[d.text] = {
                    bounds: [x, y, d.width, 14],
                    data: d.img,
                    onDown: this.onSelectionDown,
                };
                x += d.width + spacing;
            }
            y += 20;
        }
        if (node.getProperty("comparer_mode") === "Click") {
            this.drawImage(ctx, this.selected[this.isPointerDown ? 1 : 0], y);
        }
        else {
            this.drawImage(ctx, this.selected[0], y);
            if (this.isPointerOver) {
                this.drawImage(ctx, this.selected[1], y, this.pointerOverPos[0]);
            }
        }
    }
    onSelectionDown(event, pos, node, bounds) {
        const selected = [...this.selected];
        if (bounds === null || bounds === void 0 ? void 0 : bounds.data.name.startsWith("A")) {
            selected[0] = bounds.data;
        }
        else if (bounds === null || bounds === void 0 ? void 0 : bounds.data.name.startsWith("B")) {
            selected[1] = bounds.data;
        }
        this.setSelected(selected);
        this.redraw();
    }
    onMouseDown(event, pos, node) {
        this.isPointerDown = true;
        this.redraw();
    }
    onMouseUp(event, pos, node) {
        this.isPointerDown = false;
        this.redraw();
    }
    onMouseMove(event, pos, node) {
        this.pointerOverPos = [...pos];
        this.isPointerOver = true;
        this.redraw();
    }
    drawImage(ctx, image, y, cropX) {
        var _a, _b;
        if (!((_a = image === null || image === void 0 ? void 0 : image.img) === null || _a === void 0 ? void 0 : _a.naturalWidth) || !((_b = image === null || image === void 0 ? void 0 : image.img) === null || _b === void 0 ? void 0 : _b.naturalHeight)) {
            return;
        }
        let [nodeWidth, nodeHeight] = this.size;
        const imageAspect = (image === null || image === void 0 ? void 0 : image.img.naturalWidth) / (image === null || image === void 0 ? void 0 : image.img.naturalHeight);
        let height = nodeHeight - y;
        const widgetAspect = nodeWidth / height;
        let targetWidth, targetHeight;
        let offsetX = 0;
        if (imageAspect > widgetAspect) {
            targetWidth = nodeWidth;
            targetHeight = nodeWidth / imageAspect;
        }
        else {
            targetHeight = height;
            targetWidth = height * imageAspect;
            offsetX = (nodeWidth - targetWidth) / 2;
        }
        const widthMultiplier = (image === null || image === void 0 ? void 0 : image.img.naturalWidth) / targetWidth;
        const sourceX = 0;
        const sourceY = 0;
        const sourceWidth = cropX != null ? (cropX - offsetX) * widthMultiplier : image === null || image === void 0 ? void 0 : image.img.naturalWidth;
        const sourceHeight = image === null || image === void 0 ? void 0 : image.img.naturalHeight;
        const destX = (nodeWidth - targetWidth) / 2;
        const destY = y + (height - targetHeight) / 2;
        const destWidth = cropX != null ? cropX - offsetX : targetWidth;
        const destHeight = targetHeight;
        ctx.save();
        ctx.beginPath();
        let globalCompositeOperation = ctx.globalCompositeOperation;
        if (cropX) {
            ctx.rect(destX, destY, destWidth, destHeight);
            ctx.clip();
        }
        ctx.drawImage(image === null || image === void 0 ? void 0 : image.img, sourceX, sourceY, sourceWidth, sourceHeight, destX, destY, destWidth, destHeight);
        if (cropX != null && cropX >= (nodeWidth - targetWidth) / 2 && cropX <= targetWidth + offsetX) {
            ctx.beginPath();
            ctx.moveTo(cropX, destY);
            ctx.lineTo(cropX, destY + destHeight);
            ctx.globalCompositeOperation = "difference";
            ctx.strokeStyle = "rgba(255,255,255, 1)";
            ctx.stroke();
        }
        ctx.globalCompositeOperation = globalCompositeOperation;
        ctx.restore();
    }
}
comfy.defs.extend(NodeTypesString.IMAGE_COMPARER, (b) => {
    b.onCreated((node) => {
        // onCreated fires whenever the node joins a graph, which can happen more than
        // once; the constructor and onNodeCreated each ran once, and mount() throws on
        // a duplicate name — a throw here would take down the add itself. The widget
        // is checked as well as the map because a node moved between graphs is
        // removed and re-added, which drops the map entry while its widgets survive.
        if (comparers.has(node.id) || node.widgets.get("rgthree_comparer")) {
            return;
        }
        node.setSerializeWidgets(true);
        if (node.getProperty("comparer_mode") === undefined) {
            node.setProperty("comparer_mode", "Slide");
        }
        // One widget, not two: the drawing surface holds the value, so the node keeps
        // the single `widgets_values` slot it always had. No stated height, so this is
        // the widget that absorbs the node's spare space and the comparer grows again
        // when the user drags the node taller.
        const comparer = new RgthreeImageComparerWidget("rgthree_comparer");
        comparers.set(node.id, comparer);
        const valueWidget = mountRgthreeWidget(node, comparer, {
            defaultValue: { images: [] },
            serialize: true,
        }).widget;
        comparer.valueWidget = valueWidget;
        valueWidget.on("change", (v) => {
            if (v !== comparer.value) {
                comparer.value = v;
            }
        });
        valueWidget.on("beforeSerialize", (e) => {
            const images = e.value.images.map((data) => {
                const d = { ...data };
                delete d.img;
                return d;
            });
            // Two destinations, two shapes: `serializeValue` returned the object to the
            // prompt while `onSerialize` rewrote the same slot to a bare array.
            e.setSerializedValue(e.context === "prompt" ? { images } : images);
        });
        // `setSize(computeSize())` — the node is built before its widgets exist, so it
        // has to be re-fitted once the surface exists. A floor rather than `autoHeight`:
        // the surface declares no height of its own so that it can grow, and a node
        // asked to fit its content would have nothing to fit. A node being loaded is
        // configured after this and takes back its saved size, exactly as it did when
        // this ran from the constructor.
        node.setSizeConstraints({ minHeight: COMPARER_HEIGHT });
        const { width, height } = node.getSize();
        if (height < COMPARER_HEIGHT) {
            node.setSize({ width, height: COMPARER_HEIGHT });
        }
    });
    b.onExecuted((node, result) => {
        const comparer = comparers.get(node.id);
        if (!comparer) {
            return;
        }
        const output = result.raw;
        if ("images" in output) {
            comparer.value = {
                images: (output.images || []).map((d, i) => {
                    return {
                        name: i === 0 ? "A" : "B",
                        selected: true,
                        url: imageDataToUrl(d),
                    };
                }),
            };
        }
        else {
            // Read into locals rather than defaulted onto `output`: the result is frozen.
            const a_images = output.a_images || [];
            const b_images = output.b_images || [];
            const imagesToChoose = [];
            const multiple = a_images.length + b_images.length > 2;
            for (const [i, d] of a_images.entries()) {
                imagesToChoose.push({
                    name: a_images.length > 1 || multiple ? `A${i + 1}` : "A",
                    selected: i === 0,
                    url: imageDataToUrl(d),
                });
            }
            for (const [i, d] of b_images.entries()) {
                imagesToChoose.push({
                    name: b_images.length > 1 || multiple ? `B${i + 1}` : "B",
                    selected: i === 0,
                    url: imageDataToUrl(d),
                });
            }
            comparer.value = { images: imagesToChoose };
        }
    });
    // The surface reports moves over itself but nothing when the pointer leaves it,
    // so the node's own hover is what puts the slide away again.
    b.onHover((node, hovering) => {
        const comparer = comparers.get(node.id);
        if (!comparer) {
            return;
        }
        comparer.isPointerOver = hovering;
        if (!hovering) {
            comparer.isPointerDown = false;
        }
        comparer.redraw();
    });
    b.onRemoved((node) => {
        comparers.delete(node.id);
    });
    b.addMenuItem(helpMenuItem(NodeTypesString.IMAGE_COMPARER, getHelp()));
});
