import { comfy } from '/comfy/api/v2.js';

// Displays input text on a node

// TODO: This should need to be so complicated. Refactor at some point.

comfy.defs.extend("ShowText|pysssss", (b) => {
	function populate(text) {
		if (this.widgets) {
			// On older frontend versions there is a hidden converted-widget
			const isConvertedWidget = +!!this.inputs.at(0)?.isWidgetInput;
			for (const name of this.widgets.names().slice(isConvertedWidget)) {
				this.widgets.remove(name);
			}
		}

		const v = [...text];
		if (!v[0]) {
			v.shift();
		}
		for (let list of v) {
			// Force list to be an array, not sure why sometimes it is/isn't
			if (!(list instanceof Array)) list = [list];
			for (const l of list) {
				this.widgets.add({ type: "textarea", name: "text_" + this.widgets.length, value: l, disabled: true });
			}
		}
	}

	// When the node is executed we will be sent the input text, display this in the widget
	// `result.raw`, not `result.text`, which would flatten the nested lists handled below
	b.onExecuted((node, result) => {
		populate.call(node, result.raw.text);
	});

	b.onConfigured((node, data) => {
		// The saved values arrive here unmodified, even though configure has already
		// dropped them from widgets the node no longer has
		const widgets_values = data.widgets_values;
		if (widgets_values?.length) {
			// In newer frontend there seems to be a delay in creating the initial widget
			requestAnimationFrame(() => {
				populate.call(node, widgets_values.slice(+(widgets_values.length > 1 && node.inputs.at(0)?.isWidgetInput)));
			});
		}
	});
});
