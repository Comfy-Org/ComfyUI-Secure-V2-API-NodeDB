// ComfyUI.mxToolkit.Slider v.0.9.92 - Max Smirnov 2025
import { comfy } from '/comfy/api/v2.js';
import {
    applyProperties, promptNumber, requireWidgets, setDefaults,
    settleProperty, updateOutputType,
} from './mxtoolkit.js';

const HEIGHT = 30;
const FONT_SIZE = 12;
const SHIFT_LEFT = 10;
const SHIFT_RIGHT = 60;
const sliders = new Map();
const PROPERTY_KEYS = ["value", "min", "max", "step", "decimals"];

function normalise(values, changed)
{
    const next = { ...values };
    if (Number(next.step) <= 0) next.step = 1;
    if (Number.isNaN(Number(next.value))) next.value = Number(next.min);
    if (Number(next.min) >= Number(next.max)) next.max = Number(next.min) + Number(next.step);
    if (changed === "min" && Number(next.value) < Number(next.min)) next.value = next.min;
    if (changed === "max" && Number(next.value) > Number(next.max)) next.value = next.max;
    next.decimals = Math.max(0, Math.min(4, Math.floor(Number(next.decimals))));
    const scale = 10 ** next.decimals;
    next.value = Math.round(scale * Number(next.value)) / scale;
    return next;
}

function syncWidgets(node, state, values)
{
    state.syncing = true;
    try
    {
        state.widgets[2].setValue(values.decimals > 0 ? 1 : 0);
        state.widgets[1].setValue(values.value);
        state.widgets[0].setValue(Math.floor(values.value));
    }
    finally
    {
        state.syncing = false;
    }
}

function updateDerived(node, state, values)
{
    state.position = Math.max(
        0,
        Math.min(1, (values.value - values.min) / (values.max - values.min)),
    );
    const type = values.decimals > 0 ? "FLOAT" : "INT";
    updateOutputType(node, 0, type);
    if (!state.capture) syncWidgets(node, state, values);
    state.surface?.redraw();
}

function drawSlider(node, state, context, size, theme)
{
    const [width] = size;
    const centerY = HEIGHT / 2;
    context.fillStyle = theme.surface;
    context.beginPath();
    context.roundRect(SHIFT_LEFT, centerY - 2, width - SHIFT_RIGHT - SHIFT_LEFT, 4, 2);
    context.fill();

    const x = SHIFT_LEFT + (width - SHIFT_RIGHT - SHIFT_LEFT) * state.position;
    context.fillStyle = theme.text;
    context.beginPath();
    context.arc(x, centerY, 7, 0, Math.PI * 2);
    context.fill();
    context.lineWidth = 1.5;
    context.strokeStyle = node.getBgColor() || theme.surface;
    context.beginPath();
    context.arc(x, centerY, 5, 0, Math.PI * 2);
    context.stroke();

    context.fillStyle = theme.text;
    context.font = `${FONT_SIZE}px Arial`;
    context.textAlign = "center";
    context.fillText(
        Number(node.getProperty("value")).toFixed(Number(node.getProperty("decimals"))),
        width - SHIFT_RIGHT + 24,
        FONT_SIZE * 1.5,
    );
}

function updateFromPointer(node, state, event)
{
    const width = state.width;
    const min = Number(node.getProperty("min"));
    const max = Number(node.getProperty("max"));
    const decimals = Number(node.getProperty("decimals"));
    let ratio = (event.x - SHIFT_LEFT) / (width - SHIFT_RIGHT - SHIFT_LEFT);
    if (event.event.ctrlKey) state.unlock = true;
    if (event.event.shiftKey !== Boolean(node.getProperty("snap")))
    {
        const step = Number(node.getProperty("step")) / (max - min);
        ratio = Math.round(ratio / step) * step;
    }
    state.position = Math.max(0, Math.min(1, ratio));
    const scale = 10 ** decimals;
    const value = Math.round(scale * (min + (max - min) * (state.unlock ? ratio : state.position))) / scale;
    node.setProperty("value", value);
}

comfy.defs.extend("mxSlider", (builder) =>
{
    builder.onCreated((node, event) =>
    {
        const state = {
            capture: false,
            configured: !event.loading,
            initializing: true,
            position: 0.2,
            syncing: false,
            unlock: false,
            updating: false,
            width: 210,
        };
        sliders.set(node.id, state);
        setDefaults(node, { value: 20, min: 0, max: 100, step: 1, decimals: 0, snap: true });
        state.initializing = false;
        state.widgets = requireWidgets(node, 3);
        for (const widget of state.widgets) widget.setHidden(true);
        node.outputs.at(0)?.modify({ name: "", localizedName: "" });
        state.surface = node.widgets.canvas({
            name: "mxSliderSurface",
            height: HEIGHT,
            draw: (context, size, theme) =>
            {
                state.width = size[0];
                drawSlider(node, state, context, size, theme);
            },
            onPointerDown: (pointer) =>
            {
                if (pointer.event.detail >= 2 && pointer.x > state.width - SHIFT_RIGHT + 10)
                {
                    promptNumber("value", node.getProperty("value"), (value) =>
                        node.setProperty("value", value));
                    return;
                }
                if (pointer.x < SHIFT_LEFT - 5 || pointer.x > state.width - SHIFT_RIGHT + 5) return;
                state.capture = true;
                state.unlock = false;
                updateFromPointer(node, state, pointer);
            },
            onPointerMove: (pointer) =>
            {
                if (state.capture) updateFromPointer(node, state, pointer);
            },
            onPointerUp: () =>
            {
                if (!state.capture) return;
                state.capture = false;
                syncWidgets(node, state, normalise(node.getProperties()));
            },
        });
        node.setSizeConstraints({ minWidth: 210, maxWidth: 210, minHeight: HEIGHT, maxHeight: HEIGHT });
        updateDerived(node, state, normalise(node.getProperties()));
    });

    builder.onConfigured((node) =>
    {
        const decimals = Number(node.getProperty("decimals"));
        node.outputs.at(0)?.modify({ type: decimals > 0 ? "FLOAT" : "INT" });
    });

    builder.onPropertyChanged((node, event) =>
    {
        const state = sliders.get(node.id);
        if (state) settleProperty(node, state, event, PROPERTY_KEYS, normalise, updateDerived);
    });

    builder.onRemoved((node) => sliders.delete(node.id));
});

comfy.onWorkflowLoaded(() =>
{
    for (const node of comfy.graph.nodesOfType("mxSlider"))
    {
        const state = sliders.get(node.id);
        if (!state) continue;
        state.configured = true;
        applyProperties(node, state, normalise(node.getProperties()), PROPERTY_KEYS, updateDerived);
    }
});
