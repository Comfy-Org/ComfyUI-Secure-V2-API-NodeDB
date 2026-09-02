// ComfyUI.mxToolkit.Stop v.0.9.7 - Max Smirnov 2024
import { comfy } from '/comfy/api/v2.js';

const stops = new Map();

function resize(node)
{
    const output = node.outputs.at(0);
    const width = node.getProperty("showOutputText") && output?.name
        ? 140 + (output.name.length + 5) * 7.2
        : 140;
    node.setSizeConstraints({
        minWidth: width,
        maxWidth: width,
        minHeight: 39,
        maxHeight: 39,
    });
}

function reset(node)
{
    node.inputs.at(0)?.modify({ type: "*" });
    node.outputs.at(0)?.modify({ name: "", type: "*" });
    resize(node);
}

function refreshType(node)
{
    const state = stops.get(node.id);
    const input = node.inputs.at(0);
    const output = node.outputs.at(0);
    if (!state || !input || !output) return;

    const source = input.source();
    if (source)
    {
        const type = comfy.graph.node(source.nodeId)?.outputs.at(source.outputIndex)?.type;
        if (!type) return;
        input.modify({ type });
        output.modify({ type, name: type });
        if (state.configured)
            for (const link of output.links())
                if (link.type !== type)
                    comfy.graph.node(link.targetNodeId)?.inputs.at(link.targetIndex)?.disconnect();
        resize(node);
        return;
    }

    const firstLink = output.links()[0];
    const targetType = firstLink &&
        comfy.graph.node(firstLink.targetNodeId)?.inputs.at(firstLink.targetIndex)?.type;
    if (targetType)
    {
        input.modify({ type: targetType });
        output.modify({ type: targetType, name: targetType });
        resize(node);
        return;
    }

    reset(node);
}

comfy.defs.extend("mxStop", (builder) =>
{
    builder.onCreated((node, event) =>
    {
        const state = { configured: !event.loading, hovering: false };
        stops.set(node.id, state);
        reset(node);
        node.addBadge(() => ({
            text: state.hovering ? "⏩" : "⏸",
            onClick: () => { void comfy.queue.run(); },
        }));
    });

    builder.onConnectionsChanged((node) => refreshType(node));
    builder.onPropertyChanged((node, event) =>
    {
        if (event.name === "showOutputText") resize(node);
    });
    builder.onHover((node, hovering) =>
    {
        const state = stops.get(node.id);
        if (state) state.hovering = hovering;
    });
    builder.onRemoved((node) => stops.delete(node.id));
});

comfy.onWorkflowLoaded(() =>
{
    for (const node of comfy.graph.nodesOfType("mxStop"))
    {
        const state = stops.get(node.id);
        if (!state) continue;
        state.configured = true;
        refreshType(node);
    }
});
