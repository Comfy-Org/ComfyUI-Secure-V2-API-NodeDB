import { comfy } from '/comfy/api/v2.js';
import { tryToGetWorkflowDataFromEvent } from '../../rgthree/common/utils_workflow.js';
import { configurePowerLoraValues } from './power_lora_loader.js';
import { SERVICE as CONFIG_SERVICE } from './services/config_service.js';

const POWER_LORA_LOADER = 'Power Lora Loader (rgthree)';
const MODES = ['always', 'on-event', 'never', 'on-trigger', 'bypass'];

function enabled(node) {
    return node.widgets.length > 0 &&
        CONFIG_SERVICE.getFeatureValue('import_individual_nodes.enabled');
}

function applyValues(node, values) {
    if (node.type === POWER_LORA_LOADER) {
        configurePowerLoraValues(node, values);
        return;
    }
    for (const [index, value] of values.entries()) {
        const widget = node.widgets.at(index);
        if (!widget) {
            throw new Error(`Missing widget ${index} on ${node.type}`);
        }
        widget.setValue(value);
    }
}

async function importNode(node, event) {
    if (!enabled(node)) return false;
    const { workflow } = await tryToGetWorkflowDataFromEvent(event);
    const exact = (workflow?.nodes ?? []).find((candidate) =>
        String(candidate.id) === node.id &&
        candidate.type === node.type &&
        (node.type === POWER_LORA_LOADER ||
            candidate.widgets_values?.length === node.widgets.length));

    if (!exact) {
        return !window.confirm(
            '[rgthree-comfy] Could not find a matching node (same id & type) in the dropped workflow. ' +
            'Would you like to continue with the default drop behaviour instead?'
        );
    }
    const values = Array.isArray(exact.widgets_values) ? exact.widgets_values : [];
    if (!values.length) {
        return !window.confirm(
            '[rgthree-comfy] Matching node found (same id & type) but there are no widgets to set. ' +
            'Would you like to continue with the default drop behaviour instead?'
        );
    }
    const accepted = window.confirm(
        '[rgthree-comfy] Found a matching node (same id & type) in the dropped workflow. ' +
        'Would you like to set the widget values?'
    );
    if (!accepted) return false;

    applyValues(node, values);
    const mode = typeof exact.mode === 'number'
        ? MODES[exact.mode]
        : MODES.includes(exact.mode) ? exact.mode : undefined;
    if (mode) node.setMode(mode);
    return true;
}

comfy.defs.extend(/./, (builder) => {
    builder.onDragOver((node) => enabled(node));
    builder.onDrop(importNode);
});
