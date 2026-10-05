import { comfy } from "/comfy/api/v2.js";

const NODE_NAME = "FlowMatchSchedulerKleinEdit";
const PAD = 10;
const BUTTON_HEIGHT = 22;
const CURVE_HEIGHT = 140;
const PAD_HEIGHT = 120;
const SURFACE_HEIGHT = 326;
const CURVE_MIN = 0.01;
const CURVE_MAX = 10;
const SHIFT_MIN = 0.01;
const SHIFT_MAX = 20;

const editors = new Map();
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const finite = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const rounded = (value, places) => Number(value.toFixed(places));

export function computeSigmas(steps, denoise, sigmaMin, shift, curve) {
    const count = Math.max(1, Math.trunc(finite(steps, 4)));
    return Array.from({ length: count + 1 }, (_, index) => {
        let time = index / count;
        if (Math.abs(curve - 1) > 0.001) time **= curve;
        if (Math.abs(shift - 1) > 0.001) time /= time + shift * (1 - time);
        return denoise * (1 - time) + sigmaMin * time;
    });
}

export function xyValues(x, y, bounds) {
    const nx = clamp((x - bounds.x) / bounds.width, 0, 1);
    const ny = clamp((y - bounds.y) / bounds.height, 0, 1);
    return {
        curve: rounded(CURVE_MIN + nx * (CURVE_MAX - CURVE_MIN), 2),
        shift: rounded(SHIFT_MIN + (1 - ny) * (SHIFT_MAX - SHIFT_MIN), 2),
    };
}

function roundRect(context, x, y, width, height, radius = 5) {
    context.beginPath();
    context.moveTo(x + radius, y);
    context.lineTo(x + width - radius, y);
    context.quadraticCurveTo(x + width, y, x + width, y + radius);
    context.lineTo(x + width, y + height - radius);
    context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    context.lineTo(x + radius, y + height);
    context.quadraticCurveTo(x, y + height, x, y + height - radius);
    context.lineTo(x, y + radius);
    context.quadraticCurveTo(x, y, x + radius, y);
    context.closePath();
}

function inside(point, bounds) {
    return Boolean(bounds) && point.x >= bounds.x && point.x <= bounds.x + bounds.width
        && point.y >= bounds.y && point.y <= bounds.y + bounds.height;
}

function parseDots(text) {
    try {
        const values = JSON.parse(typeof text === "string" ? text : "[]");
        if (!Array.isArray(values) || values.length < 2 || values.length > 101) return null;
        if (!values.every((value) => Number.isFinite(value))) return null;
        const last = values.length - 1;
        return values.map((sigma, index) => ({ t: index / last, sigma: Number(sigma) }));
    } catch {
        return null;
    }
}

function createEditor(node) {
    if (editors.has(node.id)) return;
    const widget = (name) => node.widgets.get(name);
    const read = (name, fallback) => finite(widget(name)?.getValue(), fallback);
    const state = {
        button: null,
        curve: null,
        pad: null,
        screenDots: [],
        dots: null,
        dragIndex: -1,
        xyDragging: false,
        syncing: false,
        width: 0,
        unsubscribers: [],
    };

    const set = (name, value) => {
        const handle = widget(name);
        if (handle && !Object.is(handle.getValue(), value)) handle.setValue(value);
    };
    const inDrawMode = () => widget("draw_mode")?.getValue() === "draw";
    const redraw = () => state.surface?.redraw();
    const seedDots = () => {
        const values = computeSigmas(
            read("steps", 4), read("denoise", 1), read("sigma_min", 0),
            read("shift", 1), read("curve", 1),
        );
        const last = values.length - 1;
        state.dots = values.map((sigma, index) => ({ t: index / last, sigma }));
    };
    const syncDots = () => {
        if (!state.dots || state.syncing) return;
        state.syncing = true;
        set("custom_sigmas", JSON.stringify(state.dots.map(({ sigma }) => rounded(sigma, 4))));
        state.syncing = false;
    };
    const restoreDots = () => {
        state.dots = parseDots(widget("custom_sigmas")?.getValue());
        if (!state.dots) seedDots();
    };
    const ensureDotCount = () => {
        const count = Math.max(1, Math.trunc(read("steps", 4))) + 1;
        if (!state.dots || state.dots.length !== count) {
            seedDots();
            syncDots();
        }
    };

    function draw(context, size, theme) {
        const [width, height] = size;
        state.width = width;
        const innerWidth = Math.max(40, width - PAD * 2);
        const drawMode = inDrawMode();
        if (drawMode) ensureDotCount();
        const steps = Math.max(1, Math.trunc(read("steps", 4)));
        const denoise = read("denoise", 1);
        const sigmaMin = read("sigma_min", 0);
        const shift = read("shift", 1);
        const curve = read("curve", 1);
        const maxSigma = Math.max(denoise, 1);

        context.clearRect(0, 0, width, height);
        state.button = { x: PAD, y: PAD, width: innerWidth, height: BUTTON_HEIGHT };
        roundRect(context, state.button.x, state.button.y, state.button.width, state.button.height, 4);
        context.fillStyle = drawMode ? "#3a1a6a" : theme.surface;
        context.fill();
        context.strokeStyle = drawMode ? "#8b6fff" : theme.border;
        context.stroke();
        context.fillStyle = drawMode ? "#c8b8ff" : theme.textSecondary;
        context.font = "bold 10px monospace";
        context.textAlign = "center";
        context.fillText(drawMode ? "DRAW MODE — click for parametric" : "PARAMETRIC — click to draw", width / 2, 25);

        state.curve = { x: PAD, y: PAD + BUTTON_HEIGHT + 6, width: innerWidth, height: CURVE_HEIGHT };
        roundRect(context, state.curve.x, state.curve.y, state.curve.width, state.curve.height);
        context.fillStyle = "#0d0d1a";
        context.fill();
        context.strokeStyle = drawMode ? "#4a2a8a" : theme.border;
        context.stroke();
        for (let index = 1; index < 4; index++) {
            context.strokeStyle = "#1c1c30";
            context.beginPath();
            context.moveTo(state.curve.x + state.curve.width * index / 4, state.curve.y);
            context.lineTo(state.curve.x + state.curve.width * index / 4, state.curve.y + state.curve.height);
            context.stroke();
        }

        const active = drawMode
            ? state.dots
            : computeSigmas(steps, denoise, sigmaMin, shift, curve)
                .map((sigma, index, all) => ({ t: index / (all.length - 1), sigma }));
        const xOf = (dot) => state.curve.x + dot.t * state.curve.width;
        const yOf = (dot) => state.curve.y + state.curve.height
            - clamp(dot.sigma / maxSigma, 0, 1) * (state.curve.height - 8) - 4;
        context.beginPath();
        active.forEach((dot, index) => index ? context.lineTo(xOf(dot), yOf(dot)) : context.moveTo(xOf(dot), yOf(dot)));
        context.strokeStyle = drawMode ? "#b06fff" : "#8b6fff";
        context.lineWidth = 2;
        context.stroke();
        state.screenDots = active.map((dot, index) => {
            const point = { x: xOf(dot), y: yOf(dot) };
            const edge = index === 0 || index === active.length - 1;
            context.beginPath();
            context.arc(point.x, point.y, drawMode ? (edge ? 6 : 7) : 3, 0, Math.PI * 2);
            context.fillStyle = drawMode ? (edge ? "#50c8f0" : "#b06fff") : "#b39dff";
            context.fill();
            return point;
        });
        context.fillStyle = theme.textSecondary;
        context.font = "9px monospace";
        context.textAlign = "left";
        context.fillText(drawMode ? "teal=edge Y · purple=middle XY" : "sigma schedule", state.curve.x + 6, state.curve.y + 13);

        state.pad = {
            x: PAD,
            y: state.curve.y + state.curve.height + PAD,
            width: innerWidth,
            height: PAD_HEIGHT,
        };
        roundRect(context, state.pad.x, state.pad.y, state.pad.width, state.pad.height);
        context.fillStyle = "#0d0d1a";
        context.fill();
        context.strokeStyle = theme.border;
        context.stroke();
        if (!drawMode) {
            const x = state.pad.x + clamp((curve - CURVE_MIN) / (CURVE_MAX - CURVE_MIN), 0, 1) * state.pad.width;
            const y = state.pad.y + state.pad.height
                - clamp((shift - SHIFT_MIN) / (SHIFT_MAX - SHIFT_MIN), 0, 1) * state.pad.height;
            context.beginPath();
            context.arc(x, y, 7, 0, Math.PI * 2);
            context.fillStyle = "#8b6fff";
            context.fill();
            context.fillStyle = "#8b6fff";
            context.font = "bold 10px monospace";
            context.fillText(`curve: ${curve.toFixed(2)}   shift: ${shift.toFixed(2)}`, state.pad.x + 6, state.pad.y + 14);
        } else {
            context.fillStyle = "#8b6fff";
            context.font = "bold 9px monospace";
            context.fillText("DRAWN SIGMAS (saved to workflow)", state.pad.x + 6, state.pad.y + 14);
            const values = state.dots.slice(0, 9);
            values.forEach((dot, index) => {
                const x = state.pad.x + 10 + index * (state.pad.width - 20) / Math.max(values.length - 1, 1);
                context.textAlign = "center";
                context.fillText(dot.sigma.toFixed(3), x, state.pad.y + 62);
            });
            context.textAlign = "left";
        }
    }

    function updatePad(pointer) {
        const value = xyValues(pointer.x, pointer.y, state.pad);
        set("curve", value.curve);
        set("shift", value.shift);
        redraw();
    }

    state.surface = node.widgets.canvas({
        name: "klein_graph",
        height: SURFACE_HEIGHT,
        serialize: false,
        sendToPrompt: false,
        draw,
        onPointerDown(pointer) {
            if (inside(pointer, state.button)) {
                const drawing = !inDrawMode();
                set("draw_mode", drawing ? "draw" : "parametric");
                if (drawing) {
                    seedDots();
                    syncDots();
                } else {
                    state.dots = null;
                }
                redraw();
                pointer.event.preventDefault();
                return;
            }
            if (inDrawMode() && inside(pointer, state.curve)) {
                let nearest = -1;
                let distance = 16;
                state.screenDots.forEach((point, index) => {
                    const current = Math.hypot(pointer.x - point.x, pointer.y - point.y);
                    if (current < distance) {
                        distance = current;
                        nearest = index;
                    }
                });
                state.dragIndex = nearest;
                if (nearest >= 0) pointer.event.preventDefault();
                return;
            }
            if (!inDrawMode() && inside(pointer, state.pad)) {
                state.xyDragging = true;
                updatePad(pointer);
                pointer.event.preventDefault();
            }
        },
        onPointerMove(pointer) {
            if (state.xyDragging) {
                updatePad(pointer);
                pointer.event.preventDefault();
                return;
            }
            if (state.dragIndex < 0 || !state.dots) return;
            const index = state.dragIndex;
            const last = state.dots.length - 1;
            const maxSigma = Math.max(read("denoise", 1), 1);
            const normalized = clamp(
                (state.curve.y + state.curve.height - pointer.y - 4) / (state.curve.height - 8), 0, 1,
            );
            state.dots[index].sigma = rounded(normalized * maxSigma, 4);
            if (index === 0) set("denoise", rounded(state.dots[index].sigma, 3));
            if (index === last) set("sigma_min", rounded(state.dots[index].sigma, 3));
            if (index > 0 && index < last) {
                const raw = clamp((pointer.x - state.curve.x) / state.curve.width, 0, 1);
                const gap = Math.max(0.02, 1 / (state.dots.length * 4));
                state.dots[index].t = rounded(clamp(
                    raw, state.dots[index - 1].t + gap, state.dots[index + 1].t - gap,
                ), 4);
            }
            syncDots();
            redraw();
            pointer.event.preventDefault();
        },
        onPointerUp() {
            state.xyDragging = false;
            state.dragIndex = -1;
        },
    });

    widget("draw_mode")?.setHidden(true);
    if (inDrawMode()) restoreDots();
    for (const name of ["steps", "denoise", "sigma_min", "shift", "curve", "draw_mode"]) {
        const unsubscribe = widget(name)?.on("change", () => {
            if (name === "draw_mode" && inDrawMode() && !state.dots) restoreDots();
            redraw();
        });
        if (unsubscribe) state.unsubscribers.push(unsubscribe);
    }
    const customUnsubscribe = widget("custom_sigmas")?.on("change", (value) => {
        if (!state.syncing && inDrawMode()) {
            const parsed = parseDots(value);
            if (parsed) state.dots = parsed;
            redraw();
        }
    });
    if (customUnsubscribe) state.unsubscribers.push(customUnsubscribe);
    node.setSizeConstraints({ minWidth: 300, minHeight: SURFACE_HEIGHT });
    editors.set(node.id, state);
    redraw();
}

comfy.defs.extend(NODE_NAME, (builder) => {
    builder.onCreated((node) => createEditor(node));
    builder.onConfigured((node) => {
        const state = editors.get(node.id);
        if (!state) return;
        if (node.widgets.get("draw_mode")?.getValue() === "draw") {
            state.dots = parseDots(node.widgets.get("custom_sigmas")?.getValue());
        } else {
            state.dots = null;
        }
        state.surface?.redraw();
    });
    builder.onRemoved((node) => {
        const state = editors.get(node.id);
        state?.unsubscribers.forEach((unsubscribe) => unsubscribe());
        editors.delete(node.id);
    });
});

export const __testing = { editors, parseDots, SURFACE_HEIGHT };
