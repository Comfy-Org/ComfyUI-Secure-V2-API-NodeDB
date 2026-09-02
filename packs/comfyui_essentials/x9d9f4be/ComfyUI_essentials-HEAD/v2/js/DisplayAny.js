import { comfy } from '/comfy/api/v2.js';

comfy.defs.extend("DisplayAny", (b) => {
    b.onExecuted((node, result) => {
        for (const name of node.widgets.names().slice(1)) {
            node.widgets.remove(name);
        }

        // Check if the "text" widget already exists.
        let textWidget = node.widgets.get("displaytext");
        if (!textWidget) {
            textWidget = node.widgets.add({ type: "textarea", name: "displaytext", value: "", disabled: true });
        }
        textWidget.setValue(result.text.join(""));
    });
});
