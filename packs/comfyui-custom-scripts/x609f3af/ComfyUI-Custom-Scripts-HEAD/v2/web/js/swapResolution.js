import { comfy } from '/comfy/api/v2.js';

comfy.defs.extend(
	(def) => {
		const inputs = new Set(def.inputs.map((input) => input.name));
		return inputs.has("width") && inputs.has("height");
	},
	(b) => {
		// The trailing null was a separator between this entry and core's. Pack
		// entries are now grouped by the host, which owns that presentation.
		b.addMenuItem({
			label: "Swap width/height",
			run(node) {
				const w = node.widgets.get("width");
				const h = node.widgets.get("height");
				if (!w || !h) {
					return;
				}
				const a = w.getValue();
				w.setValue(h.getValue());
				h.setValue(a);
			},
		});
	}
);
