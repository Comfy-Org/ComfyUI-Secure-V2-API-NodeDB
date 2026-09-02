// Detect and update Efficiency Nodes from v1.92 to v2.00 changes (Final update?)
import { comfy } from '/comfy/api/v2.js';
import { addNode } from "./node_options/common/utils.js";

function reloadHiResFixNode(originalNode) {

    // Safeguard against missing 'pos' property
    const position = originalNode.getPosition();

    // Recreate the node
    const newNode = addNode("HighRes-Fix Script", originalNode, position);

    // Transfer input connections from old node to new node
    // WIRE FORMAT: this re-creates the links, so they get new ids — exactly as
    // the original did. There is no way to re-home a link onto a DIFFERENT node
    // while keeping its id (moveLinksTo only moves between outputs of one node).
    for (const input of originalNode.inputs) {
        const source = input.source();
        if (source) {
            const originNode = comfy.graph.node(source.nodeId);
            if (originNode) {
                const from = originNode.outputs.at(source.outputIndex);
                if (from) from.connectTo(newNode.id, { index: input.index });
            }
        }
    }

    // Transfer output connections from old node to new node
    for (const output of originalNode.outputs) {
        const index = output.index;
        for (const link of output.links()) {
            const from = newNode.outputs.at(index);
            if (from) from.connectTo(link.targetNodeId, { index: link.targetIndex });
        }
    }

    // Remove the original node after all connections are transferred
    originalNode.remove();

    return newNode;
}

comfy.defs.extend([
    "Efficient Loader",
    "Eff. Loader SDXL",
    "KSampler (Efficient)",
    "KSampler Adv. (Efficient)",
    "KSampler SDXL (Eff.)",
    "HighRes-Fix Script"
], (b) => {

// `loadedGraphNode` ran once per node after the workflow was loaded; onConfigured
// is the same moment — it fires at the end of LGraphNode.configure, with
// widgets_values already applied.
b.onConfigured((node) => {
    const originalNode = node; // This line ensures that originalNode refers to the provided node
    const kSamplerTypes = [
        "KSampler (Efficient)",
        "KSampler Adv. (Efficient)",
        "KSampler SDXL (Eff.)"
    ];

    // EFFICIENT LOADER & EFF. LOADER SDXL
    /*  Changes:
            Added "token_normalization" & "weight_interpretation" widget below prompt text boxes,
            below code fixes the widget values for empty_latent_width, empty_latent_height, and batch_size
            by shifting down by 2 widget values starting from the "token_normalization" widget.
            Logic triggers when "token_normalization" is a number instead of a string.
    */
    if (node.comfyClass === "Efficient Loader" || node.comfyClass === "Eff. Loader SDXL") {
        const tokenWidget = node.widgets.get("token_normalization");
        const weightWidget = node.widgets.get("weight_interpretation");

        if (typeof tokenWidget.getValue() === 'number') {
            console.log("[EfficiencyUpdate]", `Fixing '${node.comfyClass}' token and weight widgets:`, node);
            const index = node.widgets.names().indexOf("token_normalization");
            if (index !== -1) {
                for (let i = node.widgets.length - 1; i > index + 1; i--) {
                    node.widgets.at(i).setValue(node.widgets.at(i - 2).getValue());
                }
            }
            tokenWidget.setValue("none");
            weightWidget.setValue("comfy");
        }
    }

    // KSAMPLER (EFFICIENT), KSAMPLER ADV. (EFFICIENT), & KSAMPLER SDXL (EFF.)
    /*  Changes:
            Removed the "sampler_state" widget which cause all widget values to shift down by a factor of 1.
            Fix involves moving all widget values by -1. "vae_decode" value is lost in this process, so in
            below fix I manually set it to its default value of "true".
    */
    else if (kSamplerTypes.includes(node.comfyClass)) {

        const seedWidgetName = (node.comfyClass === "KSampler (Efficient)") ? "seed" : "noise_seed";
        const stepsWidgetName = (node.comfyClass === "KSampler (Efficient)") ? "steps" : "start_at_step";

        const seedWidget = node.widgets.get(seedWidgetName);
        const stepsWidget = node.widgets.get(stepsWidgetName);

        if (isNaN(seedWidget.getValue()) && isNaN(stepsWidget.getValue())) {
            console.log("[EfficiencyUpdate]", `Fixing '${node.comfyClass}' node widgets:`, node);
            for (let i = 0; i < node.widgets.length - 1; i++) {
                node.widgets.at(i).setValue(node.widgets.at(i + 1).getValue());
            }
            node.widgets.at(node.widgets.length - 1).setValue("true");
        }
    }

    // HIGHRES-FIX SCRIPT
    /*  Changes:
            Many new changes where added, so in order to properly update, aquired the values of the original
            widgets, reload a new node, transffer the known original values, and transffer connection.
            This fix is triggered when the upscale_type widget is neither "latent" or "pixel".
    */
    // Check if the current node is "HighRes-Fix Script" and if any of the above fixes were applied
    else if (node.comfyClass === "HighRes-Fix Script") {
        const upscaleTypeWidget = node.widgets.get("upscale_type");

        if (upscaleTypeWidget && upscaleTypeWidget.getValue() !== "latent" && upscaleTypeWidget.getValue() !== "pixel" && upscaleTypeWidget.getValue() !== "both") {
            console.log("[EfficiencyUpdate]", "Reloading 'HighRes-Fix Script' node:", node);

            // Extract the first five values of the original node.
            // Read BEFORE the node is removed: a handle to a deleted node reads
            // as empty, where the old live object stayed readable afterwards.
            const originalValues = originalNode.widgets.all().slice(0, 5).map(w => w.getValue());

            // Reload the node and get the new node instance
            const newNode = reloadHiResFixNode(node);

            // Update the widgets of the new node
            const targetWidgetNames = ["latent_upscaler", "upscale_by", "hires_steps", "denoise", "iterations"];

            targetWidgetNames.forEach((name, index) => {
                const widget = newNode.widgets.get(name);
                if (widget && originalValues[index] !== undefined) {
                    if (name === "latent_upscaler" && typeof originalValues[index] === 'string') {
                        widget.setValue(originalValues[index].replace("SD-Latent-Upscaler", "city96"));
                    } else {
                        widget.setValue(originalValues[index]);
                    }
                }
            });
        }
    }
});

});
