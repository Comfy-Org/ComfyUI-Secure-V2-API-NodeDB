// ComfyUI.mxToolkit.Reroute v.0.9.6 - Max Smirnov 2024
import { comfy } from '/comfy/api/v2.js';

const SIZE = 62;
const DIRECTIONS = new Set(["LEFT", "RIGHT", "UP", "DOWN"]);
const SHORT_DIRECTIONS = { L: "LEFT", R: "RIGHT", U: "UP", D: "DOWN", T: "UP" };
const PUBLIC_DIRECTIONS = { LEFT: "left", RIGHT: "right", UP: "up", DOWN: "down" };
const reroutes = new Map();

function normaliseDirection(value, fallback)
{
    const upper = String(value ?? fallback).toUpperCase();
    const expanded = SHORT_DIRECTIONS[upper] ?? upper;
    return DIRECTIONS.has(expanded) ? expanded : fallback;
}

function slotPosition(direction, width, height)
{
    if (direction === "LEFT") return { x: 0, y: height / 2 };
    if (direction === "RIGHT") return { x: width, y: height / 2 };
    if (direction === "UP") return { x: width / 2, y: 0 };
    return { x: width / 2, y: height };
}

function applyOrientation(node, inputDir, outputDir)
{
    const { width, height } = node.getSize();
    node.inputs.at(0)?.modify({
        position: slotPosition(inputDir, width, height),
        direction: PUBLIC_DIRECTIONS[inputDir],
    });
    node.outputs.at(0)?.modify({
        position: slotPosition(outputDir, width, height),
        direction: PUBLIC_DIRECTIONS[outputDir],
    });
    reroutes.get(node.id)?.surface?.redraw();
}

function settleOrientation(node, event)
{
    let inputDir = normaliseDirection(
        event.name === "inputDir" ? event.value : node.getProperty("inputDir"),
        "LEFT",
    );
    let outputDir = normaliseDirection(
        event.name === "outputDir" ? event.value : node.getProperty("outputDir"),
        "RIGHT",
    );
    if (inputDir === outputDir) outputDir = outputDir === "RIGHT" ? "LEFT" : "RIGHT";

    if (event.name === "inputDir") event.setValue(inputDir);
    if (event.name === "outputDir") event.setValue(outputDir);
    if (event.name !== "inputDir" && node.getProperty("inputDir") !== inputDir)
        node.setProperty("inputDir", inputDir);
    if (event.name !== "outputDir" && node.getProperty("outputDir") !== outputDir)
        node.setProperty("outputDir", outputDir);
    if (event.name === "inputDir" && node.getProperty("outputDir") !== outputDir)
        node.setProperty("outputDir", outputDir);
    if (event.name === "outputDir" && node.getProperty("inputDir") !== inputDir)
        node.setProperty("inputDir", inputDir);

    applyOrientation(node, inputDir, outputDir);
}

function drawReroute(node, context, size, theme)
{
    const state = reroutes.get(node.id);
    if (!state) return;
    const [width, height] = size;
    const inputDir = normaliseDirection(node.getProperty("inputDir"), "LEFT");
    const outputDir = normaliseDirection(node.getProperty("outputDir"), "RIGHT");
    const input = slotPosition(inputDir, width, height);
    const output = slotPosition(outputDir, width, height);
    const color = comfy.defs.typeColor(state.linkType) || theme.textSecondary;

    const path = () =>
    {
        context.beginPath();
        context.moveTo(input.x, input.y);
        context.quadraticCurveTo(width / 2, height / 2, output.x, output.y);
        context.stroke();
    };

    context.lineWidth = 7;
    context.strokeStyle = "rgba(0, 0, 0, 0.45)";
    path();
    context.lineWidth = 3;
    context.strokeStyle = color;
    path();

    if (state.hovering)
    {
        context.lineWidth = 1;
        context.strokeStyle = color;
        context.strokeRect(0.5, 0.5, width - 1, height - 1);
    }
}

function isReroute(node)
{
    return node.type.includes("Reroute");
}

function updateWidgetConfigs(nodes, outputType, linkType, configured)
{
    let widgetType;
    let widgetOptions;

    if (configured)
    {
        for (const node of nodes)
        {
            for (const link of node.outputs.at(0)?.links() ?? [])
            {
                const input = comfy.graph.node(link.targetNodeId)?.inputs.at(link.targetIndex);
                const config = input?.widgetConfig();
                if (!input || !config) continue;
                if (widgetType === undefined)
                {
                    widgetType = config.type;
                    widgetOptions = config.options ?? {};
                }
                const merged = input.mergeWidgetConfig({
                    type: config.type,
                    options: widgetOptions,
                });
                if (merged) widgetOptions = merged.options ?? {};
            }
        }
    }

    for (const node of nodes)
    {
        const input = node.inputs.at(0);
        if (!input) continue;
        if (widgetType !== undefined && outputType)
        {
            input.modify({
                widget: "value",
                widgetConfig: {
                    type: widgetType ?? linkType,
                    options: widgetOptions,
                },
            });
        }
        else if (input.isWidgetInput)
        {
            input.modify({ widget: null });
        }
    }
}

function updateConnections(node, side, connected)
{
    const state = reroutes.get(node.id);
    if (!state || state.updating) return;
    state.updating = true;

    try
    {
        if (state.configured && connected && side === "output")
        {
            const links = node.outputs.at(0)?.links() ?? [];
            const types = new Set(links.map((link) => link.type).filter((type) => type !== "*"));
            if (types.size > 1)
                for (const link of links.slice(0, -1))
                    comfy.graph.node(link.targetNodeId)?.inputs.at(link.targetIndex)?.disconnect();
        }

        let current = node;
        const updateNodes = [];
        let inputType = null;
        while (current)
        {
            updateNodes.unshift(current);
            const source = current.inputs.at(0)?.source();
            if (!source) break;
            const origin = comfy.graph.node(source.nodeId);
            if (!origin) return;
            if (isReroute(origin))
            {
                if (comfy.sameEntity(origin, node))
                {
                    current.inputs.at(0)?.disconnect();
                    break;
                }
                current = origin;
            }
            else
            {
                inputType = origin.outputs.at(source.outputIndex)?.type ?? null;
                break;
            }
        }

        const pending = [node];
        let outputType = null;
        while (pending.length)
        {
            current = pending.pop();
            for (const link of current.outputs.at(0)?.links() ?? [])
            {
                const target = comfy.graph.node(link.targetNodeId);
                if (!target) continue;
                if (isReroute(target))
                {
                    pending.push(target);
                    if (!updateNodes.some((entry) => comfy.sameEntity(entry, target)))
                        updateNodes.push(target);
                    continue;
                }

                const input = target.inputs.at(link.targetIndex);
                const targetType = input?.type ?? null;
                if (state.configured && inputType && inputType !== "*" && targetType !== inputType)
                    input?.disconnect();
                else
                    outputType = targetType;
            }
        }

        const linkType = inputType || outputType || "*";
        const touchedStates = updateNodes.map((entry) => reroutes.get(entry.id)).filter(Boolean);
        for (const touched of touchedStates) touched.updating = true;
        try
        {
            for (const entry of updateNodes)
            {
                const output = entry.outputs.at(0);
                if (!output) continue;
                output.modify({
                    type: inputType || "*",
                    name: entry.getProperty("showOutputText") ? linkType : "",
                    color: "#0000",
                    shape: output.links().length ? "list" : "default",
                });
                const entryState = reroutes.get(entry.id);
                if (entryState)
                {
                    entryState.linkType = linkType;
                    entryState.surface?.redraw();
                }
            }
            updateWidgetConfigs(updateNodes, outputType, linkType, state.configured);
        }
        finally
        {
            for (const touched of touchedStates) touched.updating = false;
        }
    }
    finally
    {
        state.updating = false;
    }
}

const menuDirections = [
    ["🠖", "LEFT", "RIGHT"], ["🠔", "RIGHT", "LEFT"],
    ["🠕", "DOWN", "UP"], ["🠗", "UP", "DOWN"],
    ["⮥", "LEFT", "UP"], ["⮧", "LEFT", "DOWN"],
    ["⮤", "RIGHT", "UP"], ["⮦", "RIGHT", "DOWN"],
    ["⮡", "UP", "RIGHT"], ["⮣", "DOWN", "RIGHT"],
    ["⮢", "DOWN", "LEFT"], ["⮠", "UP", "LEFT"],
];

comfy.defs.define({
    type: "mxReroute",
    title: "mxReroute",
    category: "utils",
    execution: "frontend",
    inputs: [{ name: "", type: "*" }],
    outputs: [{ name: "", type: "*" }],
    resolve: ({ self }) =>
    {
        const source = self.input(0);
        return { "0": source ? { forwardTo: source } : { omit: true } };
    },
    onCreated(node, event)
    {
        const state = { configured: false, hovering: false, linkType: "*", updating: false };
        reroutes.set(node.id, state);
        if (node.getProperty("inputDir") === undefined) node.setProperty("inputDir", "LEFT");
        if (node.getProperty("outputDir") === undefined) node.setProperty("outputDir", "RIGHT");
        node.setBgColor("#0000");
        if (event.restored && !event.loading) node.outputs.at(0)?.modify({ type: "*" });
        state.surface = node.widgets.canvas({
            name: "mxRerouteSurface",
            height: SIZE,
            draw: (context, size, theme) => drawReroute(node, context, size, theme),
        });
        node.setSizeConstraints({ minWidth: SIZE, maxWidth: SIZE, minHeight: SIZE, maxHeight: SIZE });
        applyOrientation(
            node,
            normaliseDirection(node.getProperty("inputDir"), "LEFT"),
            normaliseDirection(node.getProperty("outputDir"), "RIGHT"),
        );
    },
    onConfigured(node)
    {
        node.setBgColor("#0000");
        applyOrientation(
            node,
            normaliseDirection(node.getProperty("inputDir"), "LEFT"),
            normaliseDirection(node.getProperty("outputDir"), "RIGHT"),
        );
    },
    onConnectionsChanged(node, event)
    {
        updateConnections(node, event.side, event.connected);
    },
    onPropertyChanged(node, event)
    {
        if (event.name === "inputDir" || event.name === "outputDir") settleOrientation(node, event);
    },
    onHover(node, hovering)
    {
        const state = reroutes.get(node.id);
        if (!state) return;
        state.hovering = hovering;
        state.surface?.redraw();
    },
    onRemoved(node)
    {
        reroutes.delete(node.id);
    },
});

for (const [label, inputDir, outputDir] of menuDirections)
    comfy.defs.extend("mxReroute", (builder) =>
    {
        builder.addMenuItem({
            label,
            run: (node) => comfy.graph.batch(() =>
            {
                node.setProperty("inputDir", inputDir);
                node.setProperty("outputDir", outputDir);
            }),
        });
    });

comfy.onWorkflowLoaded(() =>
{
    for (const node of comfy.graph.nodesOfType("mxReroute"))
    {
        const state = reroutes.get(node.id);
        if (!state) continue;
        state.configured = true;
        updateConnections(node);
    }
});

// COSMETIC: the legacy class hid and disabled its title bar. The published node
// definition keeps the host-owned title and collapse affordance.
// COSMETIC: the internal wire follows the pack's curve and data-type colour, but
// not the renderer's private global width/border/style settings.
