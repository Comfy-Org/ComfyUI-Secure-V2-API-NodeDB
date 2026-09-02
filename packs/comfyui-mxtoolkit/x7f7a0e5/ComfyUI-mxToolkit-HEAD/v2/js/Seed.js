// ComfyUI.mxToolkit.Seed v.0.9.9 - Max Smirnov 2024
import { comfy } from '/comfy/api/v2.js';
import { promptNumber, requireWidgets, setDefaults } from './mxtoolkit.js';

const SLOT_HEIGHT = 30;
const FONT_SIZE = 12;
const HEIGHT = SLOT_HEIGHT * 3.4;
const seeds = new Map();

function incrementSeed(node) {
    const current = Number(node.getProperty("seed"));
    const min = Number(node.getProperty("min"));
    const max = Number(node.getProperty("max"));
    return current < max ? current + 1 : min;
}

function processSeed(node, state, requested) {
    if (state.processing) return;
    let next;
    if (requested === undefined) {
        const min = Number(node.getProperty("min"));
        const max = Number(node.getProperty("max"));
        do next = Math.round(Math.random() * (max - min) + min);
        while (next === state.lastProcessed && max > min);
    }
    else next = requested;

    if (state.lastProcessed === null && state.configured) next = state.history[0];
    if (next !== state.history[0]) {
        state.history.unshift(next);
        if (state.history.length === 2 && state.lastProcessed === null && !state.configured) {
            state.history.splice(1);
            state.configured = true;
        }
        if (state.history.length > 3) state.history.splice(3);
    }

    state.lastProcessed = next;
    state.processing = true;
    try {
        node.setProperty("seed", next);
        state.seedWidget.setValue(next);
    }
    finally {
        state.processing = false;
    }

    if (node.getProperty("interruptQueue"))
        void comfy.backend.fetch("/interrupt", { method: "POST" });
    if (node.getProperty("autorunQueue")) void comfy.queue.run();
    state.surface?.redraw();
}

function settleProperties(node, state, event) {
    if (state.initializing || state.processing) return;
    const values = { ...node.getProperties(), [event.name]: event.value };
    values.min = Math.max(0, Number(values.min));
    values.max = Math.min(4294967296, Number(values.max));
    if (values.max < values.min) values.max = values.min + 1;

    if (event.name in values) event.setValue(values[event.name]);
    for (const key of ["min", "max"])
        if (key !== event.name && node.getProperty(key) !== values[key])
            node.setProperty(key, values[key]);

    if (state.configured && values.seed !== state.lastProcessed)
        processSeed(node, state, values.seed);
}

function drawSeed(state, context, size, theme) {
    const [width] = size;
    context.fillStyle = theme.surface;
    context.strokeStyle = theme.border;
    context.beginPath(); context.roundRect(20, 5, width - 40, FONT_SIZE + 6, 6);
    context.fill(); context.stroke();

    context.fillStyle = state.hovering ? theme.text : theme.textSecondary;
    context.beginPath(); context.moveTo(width - 18, 6); context.lineTo(width - 7, 14);
    context.lineTo(width - 18, 22); context.fill();

    context.font = `${FONT_SIZE}px Arial`;
    context.textAlign = "center";
    context.fillStyle = theme.text;
    for (let index = 0; index < state.history.length; index++)
        context.fillText(state.history[index], width / 2, SLOT_HEIGHT * (index + 1));
}

function handlePointer(node, state, event) {
    if (event.y < SLOT_HEIGHT && event.x > state.width - 24) {
        processSeed(node, state, event.event.shiftKey ? incrementSeed(node) : undefined);
        return;
    }

    const index = Math.floor((event.y - (SLOT_HEIGHT - FONT_SIZE) / 2) / SLOT_HEIGHT);
    if (index > 0 && index < state.history.length) {
        state.history.unshift(state.history[index]);
        state.history.splice(index + 1, 1);
        state.lastProcessed = null;
        processSeed(node, state);
    }
    else if (index === 0) {
        if (state.configured) state.lastProcessed = state.history[0];
        promptNumber("Seed", node.getProperty("seed"), (value) =>
            processSeed(node, state, value));
    }
}

comfy.defs.extend("mxSeed", (builder) => {
    builder.onCreated((node) => {
        const [seedWidget] = requireWidgets(node, 1);
        const state = { configured: false, history: [], hovering: false,
            initializing: true, lastProcessed: null, processing: false, seedWidget, width: 210 };
        seeds.set(node.id, state);
        setDefaults(node, {
            seed: 0, min: 0, max: 4294967296,
            autorunQueue: true, interruptQueue: true,
        });
        state.initializing = false;
        seedWidget.setHidden(true);
        node.outputs.at(0)?.modify({ name: "", localizedName: "" });
        state.history = [node.getProperty("seed")];
        state.surface = node.widgets.canvas({
            name: "mxSeedSurface",
            height: HEIGHT,
            draw: (context, size, theme) => { state.width = size[0]; drawSeed(state, context, size, theme); },
            onPointerDown: (event) => handlePointer(node, state, event),
        });
        node.setSizeConstraints({ minWidth: 210, maxWidth: 210, minHeight: HEIGHT, maxHeight: HEIGHT });
    });

    builder.onConfigured((node) => {
        const state = seeds.get(node.id);
        if (!state) return;
        state.history = [node.getProperty("seed")];
        state.configured = true;
        state.surface?.redraw();
    });

    builder.onPropertyChanged((node, event) => {
        const state = seeds.get(node.id);
        if (state) settleProperties(node, state, event);
    });

    builder.onHover((node, hovering) => {
        const state = seeds.get(node.id);
        if (!state) return;
        state.hovering = hovering;
        state.surface?.redraw();
    });

    builder.addMenuItem({ label: "Randomize seed", run(node) {
        const state = seeds.get(node.id); if (state) processSeed(node, state);
    } });
    builder.addMenuItem({ label: "Increment seed", run(node) {
        const state = seeds.get(node.id); if (state) processSeed(node, state, incrementSeed(node));
    } });

    builder.onRemoved((node) => seeds.delete(node.id));
});
