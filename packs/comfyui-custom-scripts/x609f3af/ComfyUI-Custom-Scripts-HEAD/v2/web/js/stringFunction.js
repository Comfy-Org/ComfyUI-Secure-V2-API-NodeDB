import { comfy } from '/comfy/api/v2.js';

// Displays input text on a node

comfy.defs.extend("StringFunction|pysssss", (b) => {
	b.onExecuted((node, result) => {
		if (node.widgets) {
			const names = node.widgets.names();
			const pos = names.indexOf("result");
			if (pos !== -1) {
				for (const name of names.slice(pos)) {
					node.widgets.remove(name);
				}
			}
		}

		const w = node.widgets.add({ type: "textarea", name: "result", value: "", disabled: true });
		w.setValue(result.raw.text);
	});
});
