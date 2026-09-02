import { comfy } from '/comfy/api/v2.js';

// Node that allows you to tunnel connections for cleaner graphs

const SET_TYPE = 'easy setNode';
const GET_TYPE = 'easy getNode';

// LGraphCanvas.node_colors.blue.color
const BLUE = '#223';

// Guards the Constant widget against re-entry: writing a widget value through a
// handle notifies listeners, where the old plain assignment did not.
const renaming = new Set();

function nameOf(node) {
	return node.widgets.at(0).getValue();
}

function setNameQuietly(node, value) {
	renaming.add(node.id);
	try {
		node.widgets.at(0).setValue(value);
	} finally {
		renaming.delete(node.id);
	}
}

function findGetters(name) {
	if (!name) return [];
	return comfy.graph.nodesOfType(GET_TYPE).filter((otherNode) => nameOf(otherNode) === name);
}

function findSetter(name) {
	if (!name) return undefined;
	return comfy.graph.nodesOfType(SET_TYPE).find((otherNode) => nameOf(otherNode) === name);
}

function validateName(node) {
	let widgetValue = nameOf(node);
	if (widgetValue != '') {
		let tries = 0;
		let collisions = [];

		do {
			collisions = comfy.graph.nodesOfType(SET_TYPE).filter((otherNode) => {
				if (otherNode.id === node.id) {
					return false;
				}
				return nameOf(otherNode) === widgetValue;
			})
			if (collisions.length > 0) {
				widgetValue = nameOf(node) + "_" + tries;
			}
			tries++;
		} while (collisions.length > 0)
		setNameQuietly(node, widgetValue);
		update(node);
	}
}

function update(node) {
	const type = node.inputs.at(0)?.type ?? '*';
	findGetters(nameOf(node)).forEach((getter) => {
		setGetterType(getter, type);
	});
	if (nameOf(node)) {
		findGetters(node.getProperty('previousName')).forEach((getter) => {
			// Writing the value raises the getter's own change listener, which is
			// what called onRename explicitly before.
			getter.widgets.at(0).setValue(nameOf(node));
		});
	}
}

function setGetterType(node, type) {
	node.outputs.at(0).modify({ name: type, type });
	validateLinks(node);
}

function validateLinks(node) {
	const output = node.outputs.at(0);
	if (!output || output.type == '*') return;
	for (const link of output.links()) {
		if (link.type != output.type && link.type != '*') {
			// Was graph.removeLink(linkId). An input carries at most one link, so
			// disconnecting the link's own target slot drops exactly this link and
			// leaves a sibling into the same node alone.
			const target = comfy.graph.node(link.targetNodeId);
			const input = target && target.inputs.byId(link.targetSlotId);
			if (input) input.disconnect();
		}
	}
}

function onRename(node) {
	const setter = findSetter(nameOf(node));
	if (setter) {
		setGetterType(node, setter.inputs.at(0)?.type ?? '*');
		node.setTitle("Get_" + nameOf(setter));
	} else {
		setGetterType(node, '*');
	}
}

comfy.defs.define({
	type: SET_TYPE,
	title: "Set",
	category: "EasyUse/Util",
	// This node is purely frontend and does not impact the resulting prompt so
	// should not be serialized. Its value reaches the prompt through the Get
	// node's resolver below, not by mutating the graph.
	execution: 'frontend',
	inputs: [{ name: '*', type: '*' }],
	widgets: [{ type: 'text', name: 'Constant', value: '' }],

	onCreated(node, event) {
		node.setColor(BLUE);
		node.setProperty("showOutputText", true);

		// Was `clone()`, which ran before the copy had an id and so had nothing
		// to hand a pack. A pasted or duplicated Set must not keep the typed slot
		// it was given, because the wire that typed it did not come with it; one
		// arriving from the saved file must keep it, or the workflow opens wrong.
		// `restored && !loading` is exactly that distinction.
		if (event.restored && !event.loading) {
			node.inputs.at(0).modify({ name: '*', type: '*' });
			node.setProperty("previousName", '');
		}

		node.widgets.at(0).on('change', () => {
			if (renaming.has(node.id)) return;
			validateName(node);
			if (nameOf(node) !== '') {
				node.setTitle("Set_" + nameOf(node));
			}
			update(node);
			node.setProperty("previousName", nameOf(node));
		});

		validateName(node);
	},

	onConnectionsChanged(node, event) {
		//On Disconnect
		if (event.side == 'input' && !event.connected) {
			const slot = node.inputs.at(event.index);
			if (slot) slot.modify({ type: '*', name: '*' });
		}

		//On Connect
		if (event.side == 'input' && event.connected) {
			const source = node.inputs.at(event.index)?.source();
			const fromNode = source ? comfy.graph.node(source.nodeId) : undefined;
			const type = fromNode?.outputs.at(source.outputIndex)?.type;

			if (type) {
				if (node.getTitle() === "Set"){
						node.setTitle("Set_" + type);
				}
				if (nameOf(node) === '*'){
					setNameQuietly(node, type);
				}

				validateName(node);
				node.inputs.at(0).modify({ type, name: type });

				setTimeout(_=>{
					if(type != nameOf(node)){
						node.setTitle("Set_" + nameOf(node));
					}
				},1)
			}
		}

		//Update either way
		update(node);
	}
});

comfy.defs.define({
	type: GET_TYPE,
	title: "Get",
	category: "EasyUse/Util",
	execution: 'frontend',
	outputs: [{ name: '*', type: '*' }],
	widgets: [{
		type: 'combo',
		name: 'Constant',
		value: '',
		options: {
			values: () => comfy.graph.nodesOfType(SET_TYPE).map((otherNode) => otherNode.widgets.at(0).getValue()).sort()
		}
	}],

	// Replaces getInputLink(): the output stands for whatever feeds the matching
	// Set node's input. Keyed by index because the output is retyped and renamed
	// as the wire changes. Pure — the graph is not touched.
	resolve: (view) => {
		const name = view.self.widgetValue('Constant');
		const setter = view.nodesOfType(SET_TYPE).find((other) => other.widgetValue('Constant') === name && name);
		const source = setter?.input(0);
		return { '0': source ? { forwardTo: source } : { omit: true } };
	},

	onCreated(node) {
		node.setColor(BLUE);
		node.setProperty("showOutputText", true);
		node.widgets.at(0).on('change', () => onRename(node));
	},

	onConnectionsChanged(node) {
		validateLinks(node);
		setTimeout(_=>{
			node.setTitle('Get_' + nameOf(node))
		},1)
	}
});
