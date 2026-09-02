// ComfyUI.mxToolkit.Slider2D v.0.9.92 - Max Smirnov 2025
import { comfy } from '/comfy/api/v2.js';
import {
    applyProperties, promptNumber, requireWidgets, setDefaults,
    settleProperty, updateOutputType,
} from './mxtoolkit.js';

const FONT_SIZE = 12;
const SHIFT_LEFT = 10;
const SHIFT_RIGHT = 60;
const pads = new Map();
const PROPERTY_KEYS = [
    "valueX", "valueY", "minX", "minY", "maxX", "maxY",
    "stepX", "stepY", "decimalsX", "decimalsY",
];

function normalise(values, changed)
{
    const next = { ...values };
    for (const axis of ["X", "Y"])
    {
        if (Number(next[`step${axis}`]) <= 0) next[`step${axis}`] = 1;
        if (Number.isNaN(Number(next[`value${axis}`])))
            next[`value${axis}`] = Number(next[`min${axis}`]);
        if (Number(next[`min${axis}`]) >= Number(next[`max${axis}`]))
            next[`max${axis}`] = Number(next[`min${axis}`]) + 1;
        if (changed === `min${axis}` && Number(next[`value${axis}`]) < Number(next[`min${axis}`]))
            next[`value${axis}`] = next[`min${axis}`];
        if (changed === `max${axis}` && Number(next[`value${axis}`]) > Number(next[`max${axis}`]))
            next[`value${axis}`] = next[`max${axis}`];
        next[`decimals${axis}`] = Math.max(
            0,
            Math.min(4, Math.floor(Number(next[`decimals${axis}`]))),
        );
        const scale = 10 ** next[`decimals${axis}`];
        next[`value${axis}`] = Math.round(scale * Number(next[`value${axis}`])) / scale;
    }
    return next;
}

function syncWidgets(node, state, values)
{
    state.syncing = true;
    try
    {
        state.widgets[5].setValue(values.decimalsY > 0 ? 1 : 0);
        state.widgets[4].setValue(values.decimalsX > 0 ? 1 : 0);
        state.widgets[3].setValue(values.valueY);
        state.widgets[2].setValue(Math.floor(values.valueY));
        state.widgets[1].setValue(values.valueX);
        state.widgets[0].setValue(Math.floor(values.valueX));
    }
    finally
    {
        state.syncing = false;
    }
}

function updateDerived(node, state, values)
{
    state.position.x = Math.max(
        0,
        Math.min(1, (values.valueX - values.minX) / (values.maxX - values.minX)),
    );
    state.position.y = Math.max(
        0,
        Math.min(1, (values.valueY - values.minY) / (values.maxY - values.minY)),
    );
    updateOutputType(node, 0, values.decimalsX > 0 ? "FLOAT" : "INT");
    updateOutputType(node, 1, values.decimalsY > 0 ? "FLOAT" : "INT");
    if (!state.capture) syncWidgets(node, state, values);
    state.surface?.redraw();
}

function drawPad(node, state, context, size, theme)
{
    const [width, height] = size;
    const plotWidth = width - SHIFT_RIGHT - SHIFT_LEFT;
    const plotHeight = height - SHIFT_LEFT * 2;
    context.fillStyle = theme.surface;
    context.beginPath();
    context.roundRect(SHIFT_LEFT - 4, SHIFT_LEFT - 4, plotWidth + 8, plotHeight + 8, 4);
    context.fill();

    if (node.getProperty("dots"))
    {
        const stepX = plotWidth * Number(node.getProperty("stepX")) /
            (Number(node.getProperty("maxX")) - Number(node.getProperty("minX")));
        const stepY = plotHeight * Number(node.getProperty("stepY")) /
            (Number(node.getProperty("maxY")) - Number(node.getProperty("minY")));
        if (Number.isFinite(stepX) && Number.isFinite(stepY) && stepX > 0 && stepY > 0)
        {
            context.fillStyle = theme.textSecondary;
            for (let x = 0; x < plotWidth + stepX / 2; x += stepX)
                for (let y = 0; y < plotHeight + stepY / 2; y += stepY)
                    context.fillRect(SHIFT_LEFT + x - 0.5, SHIFT_LEFT + y - 0.5, 1, 1);
        }
    }

    if (node.getProperty("frame"))
    {
        const alert = Number(node.getProperty("frameAlert")) > 0 &&
            Number(node.getProperty("valueX")) * Number(node.getProperty("valueY")) >
                Number(node.getProperty("frameAlert"));
        context.fillStyle = alert ? "rgba(250, 0, 0, 0.2)" : theme.surfaceHovered;
        context.strokeStyle = alert ? "rgba(250, 0, 0, 0.7)" : theme.border;
        context.beginPath();
        context.rect(
            SHIFT_LEFT,
            SHIFT_LEFT + plotHeight * (1 - state.position.y),
            plotWidth * state.position.x,
            plotHeight * state.position.y,
        );
        context.fill();
        context.stroke();
    }

    const x = SHIFT_LEFT + plotWidth * state.position.x;
    const y = SHIFT_LEFT + plotHeight * (1 - state.position.y);
    context.fillStyle = theme.text;
    context.beginPath();
    context.arc(x, y, 7, 0, Math.PI * 2);
    context.fill();
    context.lineWidth = 1.5;
    context.strokeStyle = node.getBgColor() || theme.surface;
    context.beginPath();
    context.arc(x, y, 5, 0, Math.PI * 2);
    context.stroke();

    context.fillStyle = theme.text;
    context.font = `${FONT_SIZE}px Arial`;
    context.textAlign = "center";
    context.fillText(
        Number(node.getProperty("valueX")).toFixed(Number(node.getProperty("decimalsX"))),
        width - SHIFT_RIGHT + 24,
        FONT_SIZE * 1.5,
    );
    context.fillText(
        Number(node.getProperty("valueY")).toFixed(Number(node.getProperty("decimalsY"))),
        width - SHIFT_RIGHT + 24,
        FONT_SIZE * 1.5 + 20,
    );
}

function updateFromPointer(node, state, pointer)
{
    const minX = Number(node.getProperty("minX"));
    const minY = Number(node.getProperty("minY"));
    const maxX = Number(node.getProperty("maxX"));
    const maxY = Number(node.getProperty("maxY"));
    let x = (pointer.x - SHIFT_LEFT) / (state.width - SHIFT_RIGHT - SHIFT_LEFT);
    let y = 1 - (pointer.y - SHIFT_LEFT) / (state.height - SHIFT_LEFT * 2);
    if (pointer.event.shiftKey !== Boolean(node.getProperty("snap")))
    {
        const stepX = Number(node.getProperty("stepX")) / (maxX - minX);
        const stepY = Number(node.getProperty("stepY")) / (maxY - minY);
        x = Math.round(x / stepX) * stepX;
        y = Math.round(y / stepY) * stepY;
    }
    state.position.x = Math.max(0, Math.min(1, x));
    state.position.y = Math.max(0, Math.min(1, y));
    const scaleX = 10 ** Number(node.getProperty("decimalsX"));
    const scaleY = 10 ** Number(node.getProperty("decimalsY"));
    node.setProperty(
        "valueX",
        Math.round(scaleX * (minX + (maxX - minX) * state.position.x)) / scaleX,
    );
    node.setProperty(
        "valueY",
        Math.round(scaleY * (minY + (maxY - minY) * state.position.y)) / scaleY,
    );
}

function canSwap(node)
{
    return node.getProperty("decimalsX") === node.getProperty("decimalsY") &&
        Number(node.getProperty("valueX")) <= Number(node.getProperty("maxY")) &&
        Number(node.getProperty("valueX")) >= Number(node.getProperty("minY")) &&
        Number(node.getProperty("valueY")) <= Number(node.getProperty("maxX")) &&
        Number(node.getProperty("valueY")) >= Number(node.getProperty("minX"));
}

comfy.defs.extend("mxSlider2D", (builder) =>
{
    builder.onCreated((node, event) =>
    {
        const state = {
            capture: false,
            configured: !event.loading,
            height: 160,
            initializing: true,
            position: { x: 0.5, y: 0.5 },
            syncing: false,
            updating: false,
            width: 210,
        };
        pads.set(node.id, state);
        setDefaults(node, {
            valueX: 512, valueY: 512, minX: 0, minY: 0,
            maxX: 1024, maxY: 1024, stepX: 128, stepY: 128,
            decimalsX: 0, decimalsY: 0, snap: true, dots: true,
            frame: true, frameAlert: 0,
        });
        state.initializing = false;
        state.widgets = requireWidgets(node, 6);
        for (const widget of state.widgets) widget.setHidden(true);
        node.outputs.at(0)?.modify({ name: "", localizedName: "" });
        node.outputs.at(1)?.modify({ name: "", localizedName: "" });
        state.surface = node.widgets.canvas({
            name: "mxSlider2DSurface",
            draw: (context, size, theme) =>
            {
                state.width = size[0];
                state.height = size[1];
                drawPad(node, state, context, size, theme);
            },
            onPointerDown: (pointer) =>
            {
                const valueColumn = pointer.x > state.width - SHIFT_RIGHT + 10;
                if (pointer.event.detail >= 2 && valueColumn)
                {
                    const axis = pointer.y < FONT_SIZE * 1.5 + 5
                        ? "X"
                        : pointer.y < FONT_SIZE * 1.5 + 25 ? "Y" : null;
                    if (axis)
                        promptNumber(`value${axis}`, node.getProperty(`value${axis}`), (value) =>
                            node.setProperty(`value${axis}`, value));
                    return;
                }
                if (pointer.event.shiftKey && valueColumn && canSwap(node))
                {
                    const x = node.getProperty("valueX");
                    comfy.graph.batch(() =>
                    {
                        node.setProperty("valueX", node.getProperty("valueY"));
                        node.setProperty("valueY", x);
                    });
                    return;
                }
                if (pointer.x < SHIFT_LEFT - 5 || pointer.x > state.width - SHIFT_RIGHT + 5) return;
                if (pointer.y < SHIFT_LEFT - 5 || pointer.y > state.height - SHIFT_LEFT + 5) return;
                state.capture = true;
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
        node.setSizeConstraints({ minWidth: 110, autoHeight: true });
        updateDerived(node, state, normalise(node.getProperties()));
    });

    builder.onConfigured((node) =>
    {
        node.outputs.at(0)?.modify({ type: Number(node.getProperty("decimalsX")) > 0 ? "FLOAT" : "INT" });
        node.outputs.at(1)?.modify({ type: Number(node.getProperty("decimalsY")) > 0 ? "FLOAT" : "INT" });
    });

    builder.onPropertyChanged((node, event) =>
    {
        const state = pads.get(node.id);
        if (state) settleProperty(node, state, event, PROPERTY_KEYS, normalise, updateDerived);
    });

    builder.onRemoved((node) => pads.delete(node.id));
});

comfy.onWorkflowLoaded(() =>
{
    for (const node of comfy.graph.nodesOfType("mxSlider2D"))
    {
        const state = pads.get(node.id);
        if (!state) continue;
        state.configured = true;
        applyProperties(node, state, normalise(node.getProperties()), PROPERTY_KEYS, updateDerived);
    }
});
