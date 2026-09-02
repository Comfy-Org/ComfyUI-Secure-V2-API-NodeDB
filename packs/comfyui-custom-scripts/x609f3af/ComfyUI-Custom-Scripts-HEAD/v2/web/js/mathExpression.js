import { comfy } from '/comfy/api/v2.js';

// The init() wrapper around ComfyWidgets.STRING is deleted, not ported: it existed
// only to carry `dynamicPrompts` from the input spec onto the widget, and the
// host's own string widget reads it from the spec itself.

const VALUE_WIDGET = "pysssss.value";
const readouts = new Map();

comfy.defs.extend("MathExpression|pysssss", (b) => {
	b.onCreated((node) => {
		// These are typed as any to bypass backend validation
		// update frontend to restrict types
		for (const input of node.inputs) {
			input.modify({ type: "INT,FLOAT,IMAGE,LATENT" });
		}

		// Re-adding a node runs this again, and mounting the same widget twice throws.
		if (node.widgets.get(VALUE_WIDGET)) return;

		const state = {};
		// The value was painted over the node body at NODE_SLOT_HEIGHT * 3, which is
		// renderer geometry; it gets its own drawing surface instead. No defaultValue,
		// so the surface is decoration and stays out of widgets_values.
		state.surface = node.widgets.canvas({
			name: VALUE_WIDGET,
			height: 20,
			draw(ctx, [w, h]) {
				if (node.isCollapsed() || state.text === undefined) return;
				ctx.save();
				ctx.font = "bold 12px sans-serif";
				ctx.fillStyle = "dodgerblue";
				const sz = ctx.measureText(state.text);
				ctx.fillText(state.text, w - sz.width - 5, h - 5);
				ctx.restore();
			},
		});
		readouts.set(node.id, state);
	});

	// The value used to be read out of app.nodeOutputs on every repaint; it now
	// arrives once, when the node executes.
	b.onExecuted((node, result) => {
		const state = readouts.get(node.id);
		if (!state) return;
		const value = result.raw.value?.[0];
		state.text = value === undefined ? undefined : value + "";
		state.surface.redraw();
	});

	b.onRemoved((node) => {
		readouts.delete(node.id);
	});
});
