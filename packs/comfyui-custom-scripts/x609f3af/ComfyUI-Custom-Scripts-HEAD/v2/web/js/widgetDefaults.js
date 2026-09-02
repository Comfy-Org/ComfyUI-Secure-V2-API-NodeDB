import { comfy } from '/comfy/api/v2.js';

// Allows you to specify custom default values for any widget on any node

const id = "pysssss.WidgetDefaults";

let defaults;
let regexDefaults;

const getNodeDefaults = (node, defaults) => {
	const nodeDefaults = defaults[node.type] ?? {};
	const propSetBy = {};

	Object.keys(regexDefaults)
		.filter((r) => new RegExp(r).test(node.type))
		.reduce((p, n) => {
			const props = regexDefaults[n];
			for (const k in props) {
				// Use the longest matching key as its probably the most specific
				if (!(k in nodeDefaults) || (k in propSetBy && n.length > propSetBy[k].length)) {
					propSetBy[k] = n;
					nodeDefaults[k] = props[k];
				}
			}
			return p;
		}, nodeDefaults);

	return nodeDefaults;
};

const getDefaults = () => {
	let items;
	regexDefaults = {};
	try {
		items = JSON.parse(comfy.settings.get(id));
		items = items.reduce((p, n) => {
			if (n.node.startsWith("/") && n.node.endsWith("/")) {
				const name = n.node.substring(1, n.node.length - 1);
				try {
					// Validate regex
					new RegExp(name);

					if (!regexDefaults[name]) regexDefaults[name] = {};
					regexDefaults[name][n.widget] = n.value;
				} catch (error) {}
			}

			if (!p[n.node]) p[n.node] = {};
			p[n.node][n.widget] = n.value;
			return p;
		}, {});
	} catch (error) {}
	if (!items) {
		items = {};
	}
	return items;
};

const showDialog = () => {
	const dialog = document.createElement("dialog");
	dialog.classList.add("comfy-manage-templates");

	const rows = document.createElement("div");
	rows.style.display = "contents";

	const grid = document.createElement("div");
	grid.className = "pysssss-widget-defaults";
	Object.assign(grid.style, {
		display: "grid",
		gridTemplateColumns: "1fr auto auto auto",
		gap: "5px",
	});
	for (const text of ["Node Class", "Widget Name", "Default Value", ""]) {
		const label = document.createElement("label");
		label.textContent = text;
		grid.append(label);
	}
	grid.append(rows);

	const addRow = (node = "", widget = "", value = "") => {
		const row = document.createElement("div");
		row.className = "pysssss-widget-defaults-row";
		row.style.display = "contents";
		const inputs = [
			["e.g. CheckpointLoaderSimple", node],
			["e.g. ckpt_name", widget],
			["e.g. myBestModel.safetensors", value],
		].map(([placeholder, v]) => {
			const el = document.createElement("input");
			el.placeholder = placeholder;
			el.value = v;
			row.append(el);
			return el;
		});

		const del = document.createElement("button");
		del.textContent = "Delete";
		Object.assign(del.style, { fontSize: "12px", color: "red", fontWeight: "normal" });
		del.onclick = () => {
			inputs[1].value = "";
			row.style.display = "none";
		};
		row.append(del);
		rows.append(row);
	};

	const save = async () => {
		const items = [];

		for (const row of rows.children) {
			const inputs = row.querySelectorAll("input");
			const node = inputs[0].value.trim();
			const widget = inputs[1].value.trim();
			const value = inputs[2].value;
			if (node && widget) {
				items.push({ node, widget, value });
			}
		}

		await comfy.settings.set(id, JSON.stringify(items));
		defaults = getDefaults();

		dialog.close();
	};

	for (const nodeName in defaults) {
		const node = defaults[nodeName];
		for (const widgetName in node) {
			addRow(nodeName, widgetName, node[widgetName]);
		}
	}
	addRow();

	const buttons = document.createElement("div");
	for (const [text, onclick] of [
		["Add New", () => addRow()],
		["Save", save],
		["Cancel", () => dialog.close()],
	]) {
		const button = document.createElement("button");
		button.type = "button";
		button.textContent = text;
		button.onclick = onclick;
		buttons.append(button);
	}

	dialog.append(grid, buttons);
	dialog.addEventListener("close", () => dialog.remove());
	document.body.append(dialog);
	dialog.showModal();
};

comfy.settings.declare({
	id,
	name: "🐍 Widget & Property Defaults",
	type: "text",
	defaultValue: "[]",
	tooltip: 'A JSON array of { node, widget, value }. Wrap node in / / to match by regex, and prefix widget with "property." to set a node property instead.',
});

comfy.commands.register({
	id: "pysssss.WidgetDefaults.manage",
	label: "🐍 Manage Widget & Property Defaults",
	run: showDialog,
});

defaults = getDefaults();

comfy.defs.extend(/.*/, (b) => {
	b.onCreated((node, event) => {
		// See if we have any defaults for this type of node
		const nodeDefaults = getNodeDefaults(node, defaults);
		if (!nodeDefaults) return;

		// The default used to be written onto the node definition so the widget was
		// built with it. onCreated runs from onAdded, which LGraph.configure calls
		// before node.configure(), so a saved value still wins — same as before.
		for (const k in nodeDefaults) {
			if (k.startsWith("property.")) continue;
			const widget = node.widgets.get(k);
			if (!widget) continue;
			let v = nodeDefaults[k];
			const declared = b.def.inputs.find((i) => i.name === k);
			if (declared?.type === "INT" || declared?.type === "FLOAT") {
				v = +v;
			}
			widget.setValue(v);
		}

		// Dont run if they are pre-configured nodes from load/pastes
		//
		// The old test read `new Error().stack` for the names "pasteFromClipboard"
		// and "loadGraphData", which is the question `event.restored` answers
		// directly. It answers it more completely too: a DUPLICATED node is also
		// pre-configured, and the stack test missed it, so its colour and title were
		// overwritten by the defaults. They are now left as the user had them.
		if (event.restored) {
			return;
		}

		for (const k in nodeDefaults) {
			if (k.startsWith("property.")) {
				const name = k.substring(9);
				let v = nodeDefaults[k];
				// Special handling for some built in values
				if (name === "color") {
					node.setColor(v);
				} else if (name === "bgcolor") {
					node.setBgColor(v);
				} else if (name === "title") {
					node.setTitle(v);
				} else {
					// REFUSED, not a pending gap: assigning an arbitrary named field on
					// the live node. The old test was `name in node`, so a row naming
					// `graph`, `id`, `inputs` or `flags` wrote straight onto litegraph's
					// object — including fields the document's meaning depends on. What
					// this dialog is actually used to set routes to accessors above;
					// anything else is a node property, which is where a user-authored
					// key and value belong.
					//
					// LIMITATION: a row naming another live field — mode, size, order,
					// horizontal — used to write it and now stores a property of that
					// name instead. setMode, setSize, setShape, setCollapsed and
					// setPinned exist, but each takes a typed value while this dialog
					// collects free text, and the old raw string assignment did not
					// work for them either.
					// Try using the correct type
					const existing = node.getProperty(name);
					if (typeof existing === "number") v = +v;
					else if (typeof existing === "boolean") v = v === "true";
					else if (v === "true") v = true;

					node.setProperty(name, v);
				}
			}
		}
	});
});
