import { comfy } from '/comfy/api/v2.js';
import { commonPrefix, displayContext } from './common.js';
comfy.defs.extend('Show any [Crystools]', (b) => {
    displayContext(b, 3);
});
// Handles hold no arbitrary properties, so the per-node listener lives here and
// the entry is dropped in onRemoved.
const metadataListeners = new Map();
const documentNodes = () => comfy.graph.queryNodes({ scope: 'root-and-subgraphs' });
const nodeKey = (node) => node.graphId ? `${node.graphId}:${node.id}` : node.id;
const promptView = () => Object.fromEntries(documentNodes()
    .filter((item) => item.type !== 'Show Metadata [Crystools]')
    .map((item) => {
    const inputs = Object.fromEntries(item.widgets.all().map((widget) => [
        widget.name,
        widget.getValue(),
    ]));
    for (const input of item.inputs.all()) {
        const source = input.resolvedSource();
        if (source?.kind === 'output') {
            inputs[input.name] = [source.nodeId, source.outputIndex];
        }
        else if (source?.kind === 'literal') {
            inputs[input.name] = source.value;
        }
    }
    return [nodeKey(item), {
            class_type: item.comfyClass,
            inputs,
        }];
}));
const workflowView = () => {
    const nodes = documentNodes();
    const links = new Map();
    for (const item of nodes) {
        for (const input of item.inputs.all()) {
            const link = input.link();
            if (link)
                links.set(link.id, link);
        }
    }
    return {
        nodes: nodes.map((item) => ({
            ...item.snapshot(),
            graphId: item.graphId,
            comfyClass: item.comfyClass,
            properties: item.getProperties(),
            widgets_values: item.isSerializingWidgets()
                ? item.widgets.all().map((widget) => widget.getValue())
                : undefined,
        })),
        links: [...links.values()],
    };
};
comfy.defs.define({
    type: 'Show Metadata [Crystools]',
    title: `${commonPrefix} Show Metadata`,
    category: `crystools ${commonPrefix}/Debugger`,
    execution: 'frontend',
    widgets: [
        { type: 'textarea', name: '', value: '', disabled: true },
        { type: 'toggle', name: 'Active', value: true },
        { type: 'toggle', name: 'Parsed', value: true },
        { type: 'combo', name: 'What', value: 'Prompt', options: { values: ['Prompt', 'Workflow'] } },
    ],
    onCreated: (node) => {
        node.setShape('box');
        node.setSerializeWidgets(false);
        const fillMetadataWidget = () => {
            let result = 'inactive';
            if (node.widgets.length !== 4) {
                console.error('Something is wrong with the widgets, should be 4!');
                return 'error';
            }
            const active = Boolean(node.widgets.at(1)?.getValue());
            const parsed = Boolean(node.widgets.at(2)?.getValue());
            const what = String(node.widgets.at(3)?.getValue() || 'Prompt');
            if (active) {
                const value = what === 'Workflow' ? workflowView() : promptView();
                result = JSON.stringify(value, null, parsed ? 2 : undefined);
            }
            const output = node.widgets.at(0);
            if (output) {
                output.setValue(result);
            }
            else {
                console.error('Something is wrong with the widgets, output is undefined!');
                return 'error';
            }
            return result;
        };
        metadataListeners.set(node.id, comfy.backend.on('executed', fillMetadataWidget));
    },
    onRemoved: (node) => {
        metadataListeners.get(node.id)?.();
        metadataListeners.delete(node.id);
    },
});
