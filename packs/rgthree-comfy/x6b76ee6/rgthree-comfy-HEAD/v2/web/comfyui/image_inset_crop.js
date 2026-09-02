import { comfy } from '/comfy/api/v2.js';
import { NodeTypesString } from "./constants.js";
import { exposeActions } from "./base_node.js";
const maxResolution = 8192;
// The "Reset Crop" action, which the Fast Actions Button invokes on this node from a
// neighbour. Keyed by type rather than hung on the class, since a handle has no
// `constructor` — see base_node.js.
exposeActions(NodeTypesString.IMAGE_INSET_CROP, ["Reset Crop"], (node, action) => {
    if (action === "Reset Crop") {
        for (const name of ["left", "right", "top", "bottom"]) {
            const widget = node.widgets.get(name);
            if (!widget) {
                throw new Error(`[rgthree.ImageInsetCrop] node ${node.id} has no "${name}" widget.`);
            }
            widget.setValue(0);
        }
    }
});
comfy.defs.extend(NodeTypesString.IMAGE_INSET_CROP, (b) => {
    function setWidgetStep(node) {
        const measurementWidget = node.widgets.at(0);
        if (!measurementWidget) {
            throw new Error(`[rgthree.ImageInsetCrop] node ${node.id} has no measurement widget.`);
        }
        for (let i = 1; i <= 4; i++) {
            const widget = node.widgets.at(i);
            if (!widget) {
                throw new Error(`[rgthree.ImageInsetCrop] node ${node.id} is missing widget ${i}.`);
            }
            if (measurementWidget.getValue() === "Pixels") {
                widget.setOption("step", 80);
                widget.setOption("max", maxResolution);
            }
            else {
                widget.setOption("step", 10);
                widget.setOption("max", 99);
            }
        }
    }
    b.onCreated((node) => {
        const measurementWidget = node.widgets.at(0);
        if (!measurementWidget) {
            throw new Error(`[rgthree.ImageInsetCrop] node ${node.id} has no measurement widget.`);
        }
        measurementWidget.on("change", () => {
            setWidgetStep(node);
        });
        setWidgetStep(node);
    });
    b.onConfigured((node) => {
        setWidgetStep(node);
    });
});
// The original walked every widget and reset the four it recognised by name; addressing
// them by name directly is the same set, and is how a widget is identified now.
