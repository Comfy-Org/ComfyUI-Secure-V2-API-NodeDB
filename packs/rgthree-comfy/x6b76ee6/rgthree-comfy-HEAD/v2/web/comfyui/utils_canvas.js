// CONVERTED — the palette was the whole refusal, and it is published.
//
// `draw(ctx, size, theme)` hands a pack-drawn widget the design system's own
// tokens — surface, surfaceHovered, border, text, textSecondary — resolved from the
// widget's computed style and re-read on every draw. That is what
// `LiteGraph.WIDGET_BGCOLOR`, `WIDGET_OUTLINE_COLOR`, `WIDGET_TEXT_COLOR` and
// `WIDGET_SECONDARY_TEXT_COLOR` were reached for here, so each helper is now told
// the palette it is painting into instead of reading a renderer constant. The
// theme travels in the options object the callers already build.
//
// COSMETIC: `app.canvas.editor_alpha` is gone. `drawTogglePart` multiplied it in
//   and then restored it; the ratios are kept verbatim, so the toggle still reads
//   as a faint track under a solid knob, but it no longer dims with the node it
//   sits on. A mounted surface's opacity is the host's to manage and the canvas's
//   alpha has no published reader.
// DROPPED: `isLowQuality()` — `app.canvas.ds.scale <= 0.5`, the level-of-detail
//   gate on rounded corners, strokes, text and the toggle's intermediate position.
//   A `widgets.canvas` surface is a DOM element the renderer scales with its own
//   transform, so the drawing is rasterized once at CSS size and does not get
//   cheaper by being simplified at low zoom. The gate has nothing left to decide,
//   which is also why the absence of a published zoom reader costs nothing.
// DROPPED: `drawNodeWidget` — `drawRoundedRectangle` inset by a fixed margin, plus
//   the `lowQuality` flag its one caller branched on. That caller,
//   `RgthreeBetterTextWidget`, is unconverted, and an export nothing imports is
//   worse than an absent one.
function binarySearch(max, getValue, match) {
    let min = 0;
    while (min <= max) {
        let guess = Math.floor((min + max) / 2);
        const compareVal = getValue(guess);
        if (compareVal === match)
            return guess;
        if (compareVal < match)
            min = guess + 1;
        else
            max = guess - 1;
    }
    return max;
}
export function fitString(ctx, str, maxWidth) {
    let width = ctx.measureText(str).width;
    const ellipsis = "…";
    const ellipsisWidth = measureText(ctx, ellipsis);
    if (width <= maxWidth || width <= ellipsisWidth) {
        return str;
    }
    const index = binarySearch(str.length, (guess) => measureText(ctx, str.substring(0, guess)), maxWidth - ellipsisWidth);
    return str.substring(0, index) + ellipsis;
}
export function measureText(ctx, str) {
    return ctx.measureText(str).width;
}
export function drawRoundedRectangle(ctx, options) {
    ctx.save();
    ctx.strokeStyle = options.colorStroke || options.theme.border;
    ctx.fillStyle = options.colorBackground || options.theme.surface;
    ctx.beginPath();
    ctx.roundRect(...options.pos, ...options.size, options.borderRadius ? [options.borderRadius] : [options.size[1] * 0.5]);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
}
export function drawNumberWidgetPart(ctx, options) {
    const arrowWidth = 9;
    const arrowHeight = 10;
    const innerMargin = 3;
    const numberWidth = 32;
    const xBoundsArrowLess = [0, 0];
    const xBoundsNumber = [0, 0];
    const xBoundsArrowMore = [0, 0];
    ctx.save();
    let posX = options.posX;
    const { posY, height, value, textColor } = options;
    const midY = posY + height / 2;
    if (options.direction === -1) {
        posX = posX - arrowWidth - innerMargin - numberWidth - innerMargin - arrowWidth;
    }
    ctx.fill(new Path2D(`M ${posX} ${midY} l ${arrowWidth} ${arrowHeight / 2} l 0 -${arrowHeight} L ${posX} ${midY} z`));
    xBoundsArrowLess[0] = posX;
    xBoundsArrowLess[1] = arrowWidth;
    posX += arrowWidth + innerMargin;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const oldTextcolor = ctx.fillStyle;
    if (textColor) {
        ctx.fillStyle = textColor;
    }
    ctx.fillText(fitString(ctx, value.toFixed(2), numberWidth), posX + numberWidth / 2, midY);
    ctx.fillStyle = oldTextcolor;
    xBoundsNumber[0] = posX;
    xBoundsNumber[1] = numberWidth;
    posX += numberWidth + innerMargin;
    ctx.fill(new Path2D(`M ${posX} ${midY - arrowHeight / 2} l ${arrowWidth} ${arrowHeight / 2} l -${arrowWidth} ${arrowHeight / 2} v -${arrowHeight} z`));
    xBoundsArrowMore[0] = posX;
    xBoundsArrowMore[1] = arrowWidth;
    ctx.restore();
    return [xBoundsArrowLess, xBoundsNumber, xBoundsArrowMore];
}
drawNumberWidgetPart.WIDTH_TOTAL = 9 + 3 + 32 + 3 + 9;
export function drawTogglePart(ctx, options) {
    ctx.save();
    const { posX, posY, height, value } = options;
    const toggleRadius = height * 0.36;
    const toggleBgWidth = height * 1.5;
    ctx.beginPath();
    ctx.roundRect(posX + 4, posY + 4, toggleBgWidth - 8, height - 8, [height * 0.5]);
    ctx.globalAlpha = 0.25;
    ctx.fillStyle = "rgba(255,255,255,0.45)";
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.fillStyle = value === true ? "#89B" : "#888";
    const toggleX = value === false
        ? posX + height * 0.5
        : value === true
            ? posX + height
            : posX + height * 0.75;
    ctx.beginPath();
    ctx.arc(toggleX, posY + height * 0.5, toggleRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    return [posX, toggleBgWidth];
}
export function drawInfoIcon(ctx, x, y, size = 12, treatment = 'GRAYED') {
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(x, y, size, size, [size * 0.1]);
    if (treatment === 'GRAYED') {
        ctx.fillStyle = "#aaa";
        ctx.strokeStyle = "#aaa";
    }
    else {
        ctx.fillStyle = "#2f82ec";
        ctx.strokeStyle = "#2f82ec";
    }
    if (treatment === 'FILLED') {
        ctx.fill();
    }
    else {
        ctx.stroke();
    }
    ctx.strokeStyle = "#FFF";
    ctx.lineWidth = 2;
    const midX = x + size / 2;
    const serifSize = size * 0.175;
    ctx.stroke(new Path2D(`
    M ${midX} ${y + size * 0.15}
    v 2
    M ${midX - serifSize} ${y + size * 0.45}
    h ${serifSize}
    v ${size * 0.325}
    h ${serifSize}
    h -${serifSize * 2}
  `));
    ctx.restore();
}
export function drawPlusIcon(ctx, x, midY, size = 12) {
    ctx.save();
    const s = size / 3;
    const plus = new Path2D(`
    M ${x} ${midY + s / 2}
    v-${s} h${s} v-${s} h${s}
    v${s} h${s} v${s} h-${s}
    v${s} h-${s} v-${s} h-${s}
    z
  `);
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.fillStyle = "#3a3";
    ctx.strokeStyle = "#383";
    ctx.fill(plus);
    ctx.stroke(plus);
    ctx.restore();
}
export function drawWidgetButton(ctx, options, text = null, isMouseDownedAndOver = false) {
    var _a;
    const theme = options.theme;
    const borderRadius = (_a = options.borderRadius) !== null && _a !== void 0 ? _a : 4;
    ctx.save();
    if (!isMouseDownedAndOver) {
        drawRoundedRectangle(ctx, {
            theme,
            size: [options.size[0] - 2, options.size[1]],
            pos: [options.pos[0] + 1, options.pos[1] + 1],
            borderRadius,
            colorBackground: "#000000aa",
            colorStroke: "#000000aa",
        });
    }
    drawRoundedRectangle(ctx, {
        theme,
        size: options.size,
        pos: [options.pos[0], options.pos[1] + (isMouseDownedAndOver ? 1 : 0)],
        borderRadius,
        colorBackground: isMouseDownedAndOver ? theme.surfaceHovered : theme.surface,
        colorStroke: "transparent",
    });
    if (!isMouseDownedAndOver) {
        drawRoundedRectangle(ctx, {
            theme,
            size: [options.size[0] - 0.75, options.size[1] - 0.75],
            pos: options.pos,
            borderRadius: borderRadius - 0.5,
            colorBackground: "transparent",
            colorStroke: "#00000044",
        });
        drawRoundedRectangle(ctx, {
            theme,
            size: [options.size[0] - 0.75, options.size[1] - 0.75],
            pos: [options.pos[0] + 0.75, options.pos[1] + 0.75],
            borderRadius: borderRadius - 0.5,
            colorBackground: "transparent",
            colorStroke: "#ffffff11",
        });
    }
    drawRoundedRectangle(ctx, {
        theme,
        size: options.size,
        pos: [options.pos[0], options.pos[1] + (isMouseDownedAndOver ? 1 : 0)],
        borderRadius,
        colorBackground: "transparent",
    });
    if (text) {
        ctx.textBaseline = "middle";
        ctx.textAlign = "center";
        ctx.fillStyle = theme.text;
        ctx.fillText(text, options.pos[0] + options.size[0] / 2, options.pos[1] + options.size[1] / 2 + (isMouseDownedAndOver ? 1 : 0));
    }
    ctx.restore();
}
