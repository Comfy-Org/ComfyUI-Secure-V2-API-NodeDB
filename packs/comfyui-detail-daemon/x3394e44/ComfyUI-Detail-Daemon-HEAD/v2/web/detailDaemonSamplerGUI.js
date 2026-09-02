import { comfy } from "/comfy/api/v2.js";

// Converted to the V2 iframe API. The drawing and the hit testing are
// upstream's, essentially unchanged -- `widgets.canvas()` hands back the same
// `CanvasRenderingContext2D` and reports pointer coordinates in the same units
// `draw` receives, which is what that surface is for. What went away is the
// scaffolding upstream needed because `addDOMWidget` gave it a bare element:
// the `<canvas>` construction, the devicePixelRatio transform, the
// ResizeObserver, the requestAnimationFrame coalescing, the pointer capture,
// and the `getBoundingClientRect` coordinate mapping. The host owns all of it.
//
// `DetailDaemonSamplerGUINode` is backed by the prompt-scoped V2 node-closure
// surface: only this pack's sigma curve crosses into the sandbox, while the
// sampler and model evaluation remain host-owned.

const NODE_NAME = "DetailDaemonSamplerGUINode";
const GRAPH_HEIGHT = 250;
const MIN_WIDTH = 420;
const PARAMETER_NAMES = [
    "detail_amount",
    "start",
    "end",
    "bias",
    "exponent",
    "start_offset",
    "end_offset",
    "fade",
    "smooth",
];
const DEFAULTS = {
    detail_amount: 0.1,
    start: 0.2,
    end: 0.8,
    bias: 0.5,
    exponent: 1,
    start_offset: 0,
    end_offset: 0,
    fade: 0,
    smooth: true,
};

// Handles carry no arbitrary properties, so per-node drawing state lives here
// keyed by node id and is dropped in onRemoved.
const graphs = new Map();

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function round(value, places = 2) {
    const factor = 10 ** places;
    return Math.round(value * factor) / factor;
}

function formatTooltipValue(value) {
    return Number(value.toFixed(2)).toString();
}

function getHandleTooltip(drag, parameters) {
    const values = {
        start: [
            ["start", parameters.start],
            ["start_offset", parameters.startOffset],
        ],
        exponent_start: [["exponent", parameters.exponent]],
        peak: [
            ["detail_amount", parameters.detailAmount],
            ["bias", parameters.bias],
        ],
        exponent_end: [["exponent", parameters.exponent]],
        end: [
            ["end", parameters.end],
            ["end_offset", parameters.endOffset],
        ],
    }[drag];

    return values?.map(([name, value]) => `${name}:${formatTooltipValue(value)}`).join(" / ") ?? "";
}

function readParameters(node) {
    const value = (name, fallback) => {
        const current = Number(node.widgets.get(name)?.getValue());
        return Number.isFinite(current) ? current : fallback;
    };

    const end = clamp(value("end", 0.8), 0, 1);
    const start = Math.min(clamp(value("start", 0.2), 0, 1), end);
    return {
        detailAmount: clamp(value("detail_amount", 0.1), -5, 5),
        start,
        end,
        bias: clamp(value("bias", 0.5), 0, 1),
        exponent: clamp(value("exponent", 1), 0, 10),
        startOffset: clamp(value("start_offset", 0), -1, 1),
        endOffset: clamp(value("end_offset", 0), -1, 1),
        fade: clamp(value("fade", 0), 0, 1),
        smooth: Boolean(node.widgets.get("smooth")?.getValue() ?? true),
    };
}

// Unchanged from upstream: the same curve the Python `make_detail_daemon_schedule`
// produces, sampled at 121 points for display.
function makeSchedule(parameters, steps = 121) {
    const schedule = new Float64Array(steps);
    const mid = parameters.start + parameters.bias * (parameters.end - parameters.start);
    const startIndex = Math.round(parameters.start * (steps - 1));
    const midIndex = Math.round(mid * (steps - 1));
    const endIndex = Math.round(parameters.end * (steps - 1));

    schedule.fill(parameters.startOffset, 0, startIndex);
    for (let index = startIndex; index <= midIndex; index++) {
        const length = midIndex - startIndex;
        let value = length ? (index - startIndex) / length : 0;
        if (parameters.smooth) value = 0.5 * (1 - Math.cos(value * Math.PI));
        value **= parameters.exponent;
        schedule[index] = value * (parameters.detailAmount - parameters.startOffset) + parameters.startOffset;
    }
    for (let index = midIndex; index <= endIndex; index++) {
        const length = endIndex - midIndex;
        let value = length ? 1 - (index - midIndex) / length : 1;
        if (parameters.smooth) value = 0.5 * (1 - Math.cos(value * Math.PI));
        value **= parameters.exponent;
        schedule[index] = value * (parameters.detailAmount - parameters.endOffset) + parameters.endOffset;
    }
    schedule.fill(parameters.endOffset, endIndex + 1);

    const fadeScale = 1 - parameters.fade;
    for (let index = 0; index < schedule.length; index++) schedule[index] *= fadeScale;
    return schedule;
}

function setWidgetValue(node, name, value) {
    const widget = node.widgets.get(name);
    if (!widget || Object.is(widget.getValue(), value)) return;
    widget.setValue(value);
}

function createGraph(node) {
    if (graphs.has(node.id)) return;

    const state = {
        drag: null,
        dragStartY: 0,
        dragStartExponent: 1,
        dragYMax: 1,
        layout: null,
        surface: null,
    };
    graphs.set(node.id, state);

    const redraw = () => state.surface?.redraw();

    const draw = (context, [width, height]) => {
        if (width < 1 || height < 1) return;

        context.clearRect(0, 0, width, height);

        const parameters = readParameters(node);
        const schedule = makeSchedule(parameters);
        const fadeScale = 1 - parameters.fade;
        const peakX = parameters.start + parameters.bias * (parameters.end - parameters.start);
        const exponentStrength = 0.5 ** parameters.exponent;
        const exponentStartY = (parameters.startOffset + (parameters.detailAmount - parameters.startOffset) * exponentStrength) * fadeScale;
        const exponentEndY = (parameters.endOffset + (parameters.detailAmount - parameters.endOffset) * exponentStrength) * fadeScale;
        const handles = [
            { name: "start", x: parameters.start, y: parameters.startOffset * fadeScale, color: "#5ac8fa" },
            { name: "exponent_start", x: (parameters.start + peakX) / 2, y: exponentStartY, color: "#bf5af2", label: "E" },
            { name: "peak", x: peakX, y: parameters.detailAmount * fadeScale, color: "#ffcc00" },
            { name: "exponent_end", x: (peakX + parameters.end) / 2, y: exponentEndY, color: "#bf5af2", label: "E" },
            { name: "end", x: parameters.end, y: parameters.endOffset * fadeScale, color: "#ff6b6b" },
        ];
        const largest = Math.max(1, ...schedule.map(Math.abs), ...handles.map((handle) => Math.abs(handle.y)));
        const yMax = state.drag ? state.dragYMax : Math.min(5.5, Math.max(1, largest * 1.2));
        const padding = { left: 42, right: 12, top: 25, bottom: 27 };
        const plotWidth = Math.max(1, width - padding.left - padding.right);
        const plotHeight = Math.max(1, height - padding.top - padding.bottom);
        const pointX = (value) => padding.left + value * plotWidth;
        const pointY = (value) => padding.top + (1 - (value + yMax) / (2 * yMax)) * plotHeight;
        state.layout = { padding, plotWidth, plotHeight, yMax, handles };

        context.fillStyle = "#17191c";
        context.fillRect(0, 0, width, height);
        context.font = "11px sans-serif";
        context.lineWidth = 1;

        for (let tick = 0; tick <= 4; tick++) {
            const ratio = tick / 4;
            const x = pointX(ratio);
            context.strokeStyle = "rgba(255,255,255,.09)";
            context.beginPath();
            context.moveTo(x, padding.top);
            context.lineTo(x, padding.top + plotHeight);
            context.stroke();
            context.fillStyle = "rgba(255,255,255,.55)";
            context.textAlign = "center";
            context.fillText(`${Math.round(ratio * 100)}%`, x, height - 8);
        }

        for (let tick = -2; tick <= 2; tick++) {
            const value = tick * yMax / 2;
            const y = pointY(value);
            context.strokeStyle = tick === 0 ? "rgba(255,255,255,.28)" : "rgba(255,255,255,.09)";
            context.beginPath();
            context.moveTo(padding.left, y);
            context.lineTo(padding.left + plotWidth, y);
            context.stroke();
            context.fillStyle = "rgba(255,255,255,.55)";
            context.textAlign = "right";
            context.fillText(value.toFixed(yMax < 1 ? 2 : 1), padding.left - 6, y + 4);
        }

        const gradient = context.createLinearGradient(padding.left, 0, padding.left + plotWidth, 0);
        gradient.addColorStop(0, "#5ac8fa");
        gradient.addColorStop(0.5, "#ffcc00");
        gradient.addColorStop(1, "#ff6b6b");
        context.strokeStyle = gradient;
        context.lineWidth = 2.5;
        context.beginPath();
        schedule.forEach((value, index) => {
            const x = pointX(index / (schedule.length - 1));
            const y = pointY(value);
            if (index === 0) context.moveTo(x, y);
            else context.lineTo(x, y);
        });
        context.stroke();

        for (const handle of handles) {
            const x = pointX(handle.x);
            const y = pointY(handle.y);
            handle.canvasX = x;
            handle.canvasY = y;
            context.fillStyle = handle.color;
            context.strokeStyle = "#101214";
            context.lineWidth = 2;
            context.beginPath();
            context.arc(x, y, state.drag === handle.name ? 7 : 6, 0, Math.PI * 2);
            context.fill();
            context.stroke();
            if (handle.label) {
                context.fillStyle = "#fff";
                context.font = "bold 9px sans-serif";
                context.textAlign = "center";
                context.fillText(handle.label, x, y + 3);
            }
        }

        if (state.drag) {
            const activeHandle = handles.find((handle) => handle.name === state.drag);
            const tooltip = getHandleTooltip(state.drag, parameters);
            if (activeHandle && tooltip) {
                context.font = "bold 11px sans-serif";
                const tooltipPadding = 8;
                const tooltipHeight = 24;
                const tooltipWidth = context.measureText(tooltip).width + tooltipPadding * 2;
                const tooltipGap = 12;
                const tooltipX = clamp(activeHandle.canvasX - tooltipWidth / 2, 4, width - tooltipWidth - 4);
                let tooltipY = activeHandle.canvasY - tooltipHeight - tooltipGap;
                if (tooltipY < 4) tooltipY = activeHandle.canvasY + tooltipGap;
                tooltipY = clamp(tooltipY, 4, height - tooltipHeight - 4);

                context.fillStyle = "rgba(8,10,12,.94)";
                context.strokeStyle = activeHandle.color;
                context.lineWidth = 1;
                context.beginPath();
                if (typeof context.roundRect === "function") context.roundRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight, 5);
                else context.rect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
                context.fill();
                context.stroke();

                context.fillStyle = "rgba(255,255,255,.92)";
                context.textAlign = "center";
                context.textBaseline = "middle";
                context.fillText(tooltip, tooltipX + tooltipWidth / 2, tooltipY + tooltipHeight / 2);
                context.textBaseline = "alphabetic";
            }
        }

        context.fillStyle = "rgba(255,255,255,.78)";
        context.textAlign = "left";
        context.font = "12px sans-serif";
        context.fillText("Detail adjustment schedule", padding.left, 16);
        context.textAlign = "right";
        context.fillStyle = "rgba(255,255,255,.48)";
        context.font = "10px sans-serif";
        context.fillText("drag handles", width - padding.right, 16);
    };

    const resetToDefaults = () => {
        for (const [name, value] of Object.entries(DEFAULTS)) setWidgetValue(node, name, value);
        redraw();
    };

    const updateFromPointer = (event) => {
        if (!state.drag || !state.layout) return;
        const { padding, plotWidth, plotHeight, yMax } = state.layout;
        const x = clamp((event.x - padding.left) / plotWidth, 0, 1);
        const displayedY = clamp((1 - (event.y - padding.top) / plotHeight) * 2 * yMax - yMax, -yMax, yMax);
        const parameters = readParameters(node);
        const fadeScale = Math.max(0.01, 1 - parameters.fade);

        if (state.drag.startsWith("exponent_")) {
            const delta = (event.y - state.dragStartY) / plotHeight * 10;
            const exponent = Math.round(clamp(state.dragStartExponent + delta, 0, 10) / 0.05) * 0.05;
            setWidgetValue(node, "exponent", round(exponent));
        } else if (state.drag === "start") {
            setWidgetValue(node, "start", round(clamp(x, 0, parameters.end)));
            setWidgetValue(node, "start_offset", round(clamp(displayedY / fadeScale, -1, 1)));
        } else if (state.drag === "peak") {
            const span = parameters.end - parameters.start;
            const bias = span > 0 ? (x - parameters.start) / span : 0;
            setWidgetValue(node, "bias", round(clamp(bias, 0, 1)));
            setWidgetValue(node, "detail_amount", round(clamp(displayedY / fadeScale, -5, 5)));
        } else if (state.drag === "end") {
            setWidgetValue(node, "end", round(clamp(x, parameters.start, 1)));
            setWidgetValue(node, "end_offset", round(clamp(displayedY / fadeScale, -1, 1)));
        }
        redraw();
    };

    state.surface = node.widgets.canvas({
        name: "detail_daemon_schedule",
        height: GRAPH_HEIGHT,
        serialize: false,
        draw,
        onPointerDown(event) {
            if (!state.layout) return;
            // Upstream bound a separate dblclick listener on its own element.
            // The primary button arrives here, so the second click of a
            // double click is the same gesture with `detail === 2`.
            if (event.event.detail === 2) {
                resetToDefaults();
                event.event.preventDefault();
                return;
            }
            let closest = null;
            let distance = 14;
            for (const handle of state.layout.handles) {
                const current = Math.hypot(event.x - handle.canvasX, event.y - handle.canvasY);
                if (current < distance) {
                    closest = handle;
                    distance = current;
                }
            }
            if (!closest) return;
            state.drag = closest.name;
            state.dragStartY = event.y;
            state.dragStartExponent = readParameters(node).exponent;
            state.dragYMax = state.layout.yMax;
            redraw();
            event.event.preventDefault();
        },
        onPointerMove(event) {
            if (state.drag) {
                updateFromPointer(event);
                event.event.preventDefault();
            }
        },
        onPointerUp() {
            if (!state.drag) return;
            state.drag = null;
            redraw();
        },
    });

    for (const name of PARAMETER_NAMES) {
        node.widgets.get(name)?.on("change", redraw);
    }

    node.setSizeConstraints({ minWidth: MIN_WIDTH, minHeight: GRAPH_HEIGHT });
    redraw();
}

comfy.defs.extend(NODE_NAME, (b) => {
    b.onCreated((node) => {
        createGraph(node);
    });

    b.onConfigured((node) => {
        graphs.get(node.id)?.surface?.redraw();
    });

    b.onRemoved((node) => {
        graphs.delete(node.id);
    });
});
