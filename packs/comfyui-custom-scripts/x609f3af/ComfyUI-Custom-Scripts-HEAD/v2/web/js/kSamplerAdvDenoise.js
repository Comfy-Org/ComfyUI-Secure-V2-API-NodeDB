import { comfy } from '/comfy/api/v2.js';

// Add menu options to conver to/from widgets
// The trailing null was a separator between this entry and core's. Pack entries
// are now grouped by the host, which owns that presentation.
comfy.defs.extend(
	(def) => {
		const names = new Set(def.inputs.map((input) => input.name));
		return names.has("steps") && names.has("start_at_step") && names.has("end_at_step");
	},
	(b) => {
		b.addMenuItem({
			label: "Set Denoise",
			when: (node) =>
				Boolean(
					node.widgets.get("steps") && node.widgets.get("start_at_step") && node.widgets.get("end_at_step")
				),
			run(node) {
				const stepsWidget = node.widgets.get("steps");
				const startAtWidget = node.widgets.get("start_at_step");
				const endAtWidget = node.widgets.get("end_at_step");

				const steps = +prompt("How many steps do you want?", 15);
				if (isNaN(steps)) {
					return;
				}
				const denoise = +prompt("How much denoise? (0-1)", 0.5);
				if (isNaN(denoise)) {
					return;
				}

				stepsWidget.setValue(Math.floor(steps / Math.max(0, Math.min(1, denoise))));
				startAtWidget.setValue(stepsWidget.getValue() - steps);
				endAtWidget.setValue(stepsWidget.getValue());
			},
		});
	}
);
