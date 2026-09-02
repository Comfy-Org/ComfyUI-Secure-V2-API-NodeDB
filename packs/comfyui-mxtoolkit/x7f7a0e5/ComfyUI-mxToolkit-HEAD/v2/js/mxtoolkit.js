import { comfy } from '/comfy/api/v2.js';

export function setDefaults(node, defaults)
{
    for (const [key, value] of Object.entries(defaults))
        if (node.getProperty(key) === undefined) node.setProperty(key, value);
}

export function requireWidgets(node, count)
{
    const widgets = Array.from({ length: count }, (_, index) => node.widgets.at(index));
    if (widgets.some((widget) => !widget))
        throw new Error(`${node.type} needs ${count} backend widgets`);
    return widgets;
}

export function promptNumber(title, current, onAccept)
{
    const raw = globalThis.prompt(title, String(current));
    if (raw === null) return;
    const value = Number(raw);
    if (!Number.isNaN(value)) onAccept(value);
}

export function updateOutputType(node, index, type)
{
    const output = node.outputs.at(index);
    if (!output) return;
    if (output.type !== type)
        for (const link of output.links())
            comfy.graph.node(link.targetNodeId)?.inputs.at(link.targetIndex)?.disconnect();
    output.modify({ type });
}

export function applyProperties(node, state, values, keys, update)
{
    state.updating = true;
    try
    {
        for (const key of keys)
            if (node.getProperty(key) !== values[key]) node.setProperty(key, values[key]);
    }
    finally
    {
        state.updating = false;
    }
    update(node, state, values);
}

export function settleProperty(node, state, event, keys, normalise, update)
{
    if (!state.configured || state.initializing || state.syncing || state.updating) return;
    const values = normalise({ ...node.getProperties(), [event.name]: event.value }, event.name);
    event.setValue(values[event.name]);
    state.updating = true;
    try
    {
        for (const key of keys)
            if (key !== event.name && node.getProperty(key) !== values[key])
                node.setProperty(key, values[key]);
    }
    finally
    {
        state.updating = false;
    }
    update(node, state, values);
}
