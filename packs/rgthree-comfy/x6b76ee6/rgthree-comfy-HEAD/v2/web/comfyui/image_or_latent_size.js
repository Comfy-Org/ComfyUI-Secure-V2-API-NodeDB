import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
// A union slot type is spellable: `SlotType` is `string | string[]`, so the array
// below is accepted. The API stores it as the comma string litegraph actually
// compares against (`String(type).split(',')`), so the saved workflow holds
// "IMAGE,LATENT,MASK" where the original held the array — a byte difference with
// no behavioural one, and the same call the API takes for slot `shape`.
comfy.defs.extend(NodeTypesString.IMAGE_OR_LATENT_SIZE, (b) => {
    b.onCreated((node) => {
        // onCreated fires when the node joins a graph, which can happen more than
        // once for one node; the old onNodeCreated ran only at construction. Adding
        // a second "input" slot would change the serialized inputs.
        if (!node.inputs.names().includes("input")) {
            node.inputs.add("input", ["IMAGE", "LATENT", "MASK"]);
        }
    });
    b.onConfigured((node) => {
        const input = node.inputs.at(0);
        if (input) {
            input.modify({ type: ["IMAGE", "LATENT", "MASK"] });
        }
    });
});
