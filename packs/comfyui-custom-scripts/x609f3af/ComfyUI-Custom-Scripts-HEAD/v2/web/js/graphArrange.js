import { comfy } from '/comfy/api/v2.js';

// Previously added two canvas menu entries — "Arrange (float left)", a bare
// graph.arrange(), and "Arrange (float right)", a copy of that algorithm that
// right-aligns each column — by replacing
// LGraphCanvas.prototype.getCanvasMenuOptions.
//
// REFUSED, not a pending gap: replacing the canvas menu builder. That method is
// the renderer's, the renderer is ours to replace, and whichever pack loads last
// wraps the others. Arranging is not one node's business either, so the entries
// are commands: they carry a keybinding, appear in the palette, and are reachable
// without a right-click having to land on empty canvas.
//
// LIMITATION: within a column the rows used to follow the graph's execution order,
// which came from the unpublished computeExecutionOrder. Columns are relaxed from
// the published links here instead, and rows follow column order then the graph's
// own node order — so a column's rows can come out in a different vertical order
// than before. Which column a node lands in is unchanged, and float-right's own
// sort (outputs first, then by slot count) still decides that column's order.

// Column per node: one to the right of its furthest-left feeder. This is the
// `_level` computeExecutionOrder(false, true) wrote onto each node, derived from
// the links rather than read back off somebody else's object.
function columnLevels(nodes) {
	const level = new Map(nodes.map((n) => [n.id, 1]));
	const edges = nodes.flatMap((n) =>
		n.inputs.all().flatMap((input) => {
			const source = input.source();
			return source && level.has(source.nodeId) ? [[source.nodeId, n.id]] : [];
		})
	);
	for (let pass = 0; pass < nodes.length; pass++) {
		let moved = false;
		for (const [from, to] of edges) {
			if (level.get(from) + 1 > level.get(to)) {
				level.set(to, level.get(from) + 1);
				moved = true;
			}
		}
		if (!moved) break;
	}
	return level;
}

function arrange(margin, floatRight) {
	const nodes = comfy.graph.nodes();
	const level = columnLevels(nodes);
	const ordered = [...nodes].sort((a, b) => level.get(a.id) - level.get(b.id));

	// Find node first use: pull each node as far right as its earliest consumer
	// allows. Consumers first, which descending column order guarantees.
	if (floatRight) {
		for (const node of [...ordered].reverse()) {
			let max = null;
			for (const out of node.outputs) {
				for (const link of out.links()) {
					const l = level.get(link.targetNodeId);
					if (l === undefined) continue;
					if (max === null) max = l - 1;
					else if (l - 1 < max) max = l - 1;
				}
			}
			if (max != null) level.set(node.id, max);
		}
	}

	const columns = [];
	for (const node of ordered) {
		const col = level.get(node.id) || 1;
		if (!columns[col]) {
			columns[col] = [];
		}
		columns[col].push(node);
	}

	let x = margin;

	for (let i = 0; i < columns.length; ++i) {
		const column = columns[i];
		if (!column) {
			continue;
		}
		if (floatRight) {
			column.sort((a, b) => {
				var as = !(a.type === "SaveImage" || a.type === "PreviewImage");
				var bs = !(b.type === "SaveImage" || b.type === "PreviewImage");
				var r = as - bs;
				if (r === 0) r = a.inputs.length - b.inputs.length;
				if (r === 0) r = a.outputs.length - b.outputs.length;
				return r;
			});
		}
		let max_size = 100;
		// y is the top of the title bar, which is what the old
		// `margin + NODE_TITLE_HEIGHT` start worked out to; setPosition addresses
		// the body, so each row adds back its own title height.
		let y = margin;
		for (let j = 0; j < column.length; ++j) {
			const node = column[j];
			const size = node.getSize();
			const bounds = node.getBounds();
			node.setPosition({ x, y: y + (node.getPosition().y - bounds.y) });
			if (size.width > max_size) {
				max_size = size.width;
			}
			y += bounds.height + margin + j;
		}

		if (floatRight) {
			// Right align in column
			for (let j = 0; j < column.length; ++j) {
				const node = column[j];
				const pos = node.getPosition();
				node.setPosition({ x: pos.x + max_size - node.getSize().width, y: pos.y });
			}
		}
		x += max_size + margin;
	}
}

comfy.commands.register({
	id: "pysssss.GraphArrange.FloatLeft",
	label: "Arrange (float left)",
	run: () => comfy.graph.batch(() => arrange(100, false)),
});

comfy.commands.register({
	id: "pysssss.GraphArrange.FloatRight",
	label: "Arrange (float right)",
	run: () => comfy.graph.batch(() => arrange(50, true)),
});
