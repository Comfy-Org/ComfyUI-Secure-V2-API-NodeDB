import { comfy } from '/comfy/api/v2.js';

// originally based on diffus3's SetGet: https://github.com/diffus3/ComfyUI-extensions

// Nodes that allow you to hide connections for cleaner graphs

const _typeColorMap = {
	"MODEL": { color: "#223", bgcolor: "#335"},
	"LATENT": { color: "#323", bgcolor: "#535"},
	"VAE": { color: "#322", bgcolor: "#533"},
	"WANVAE": { color: "#322", bgcolor: "#533"},
	"CONDITIONING": { color: "#332922", bgcolor: "#593930"},
	"IMAGE": { color: "#2a363b", bgcolor: "#3f5159"},
	"CLIP": { color: "#432", bgcolor: "#653"},
	"FLOAT": { color: "#232", bgcolor: "#353"},
	"MASK": { color: "#1c5715", bgcolor: "#1f401b"},
	"INT": { color: "#1b4669", bgcolor: "#29699c"},
	"CONTROL_NET": { color: "#156653", bgcolor: "#1c453b"},
	"NOISE": { color: "#2e2e2e", bgcolor: "#242121"},
	"GUIDER": { color: "#3c7878", bgcolor: "#1c453b"},
	"SAMPLER": { color: "#614a4a", bgcolor: "#3b2c2c"},
	"SIGMAS": { color: "#485248", bgcolor: "#272e27"},
};
function setColorAndBgColor(node, type) {
	const colors = _typeColorMap[type];
	if (colors) {
		node.setColor(colors.color);
		node.setBgColor(colors.bgcolor);
	}
}
function getDisablePrefix() {
	return comfy.settings.get("KJNodes.disablePrefix") ?? false;
}
function prefixedTitle(prefix, name) {
	return (getDisablePrefix() ? "" : prefix + "_") + name;
}
function autoColor(node, type) {
	if (!comfy.settings.get("KJNodes.nodeAutoColor")) return;
	if (type === '*') { node.setColor(undefined); node.setBgColor(undefined); }
	else setColorAndBgColor(node, type);
}
function addNodeToSelectedOrCursor(nodeType, side) {
	const selected = comfy.graph.selection();
	if (selected.length > 0) {
		for (const n of selected) window.kjNodes.addNode(nodeType, n, { side, offset: 30 });
	} else {
		const node = comfy.graph.add(nodeType, { position: comfy.graph.pointerPosition() });
		if (node) comfy.graph.select([node]);
	}
}
// Temporary map for paste rename coordination between Set and Get nodes.
// Key: old name, Value: new name. Cleared via setTimeout(0) after each paste cycle.
// This works because both onConfigured calls (Set + Get) fire synchronously within
// the same paste operation, before the timeout clears the entry.
const _pasteRenameMap = new Map();

// Per-node state. Handles carry no arbitrary properties, so the pack keeps its
// own, keyed by node id, and drops the entry when the node goes.
const _nodeState = new Map();
function stateFor(nodeId) {
	let state = _nodeState.get(nodeId);
	if (!state) _nodeState.set(nodeId, (state = {}));
	return state;
}

// DROPPED: lexical scoping between graphs — "a Set in a parent graph is visible to
// every descendant subgraph, and a Get looks up the chain". A Get resolves against
// its own graph only.
//
// Not a missing accessor. comfy.graph.subgraphs() enumerates every graph in the
// document and NodeHandle.graphId says which one a node sits in, so both halves of
// "where is this node" are published. What is not, and what the old scoping walked,
// is containment: a subgraph handle names no parent and no children. That is a
// deliberate boundary rather than an omission — these are subgraph DEFINITIONS, and
// a definition placed in three parents has no single parent to walk to, so "the
// ancestor chain" is only well defined for an instance. The old code walked
// graph._subgraph_node.graph, which is the instance chain.
//
// convertCrossGraphSetGet went with it: pairing across a boundary meant building
// SubgraphInput/SubgraphOutput slots, which are unpublished.

// Every graph in the document. Subgraph handles scope node ids to their own graph,
// which is why the graph is threaded through rather than looked up again.
function documentGraphs() {
	return [comfy.graph, ...comfy.graph.subgraphs()];
}

function nodesOfTypeIn(graph, type) {
	return graph.nodes().filter(node => node.type === type);
}

function constantValue(node) {
	return node.widgets.get("Constant")?.getValue();
}

// Setter lookup by name, in the current graph.
function findSetterByName(name) {
	if (!name) return null;
	return comfy.graph.nodesOfType('SetNode').find(node => constantValue(node) === name) ?? null;
}

// Getter lookup by name, in one graph.
function findGettersByName(name, graph = comfy.graph) {
	if (!name) return [];
	return nodesOfTypeIn(graph, 'GetNode').filter(node => constantValue(node) === name);
}

// Get all SetNode names for a GetNode's combo dropdown.
function getVisibleSetNames(filterType) {
	const names = new Set();
	for (const node of comfy.graph.nodesOfType('SetNode')) {
		const name = constantValue(node);
		if (!name) continue;
		if (filterType && filterType !== '*') {
			const setType = node.inputs.at(0)?.type;
			if (setType && setType !== '*') {
				const filterTypes = String(filterType).split(",");
				if (!filterTypes.some(ft => ft === setType || setType.split(",").includes(ft))) continue;
			}
		}
		names.add(name);
	}
	return [...names].sort();
}

// Exposed globally for use in contextmenu.js
window.kjNodes = window.kjNodes || {};
window.kjNodes.convertOutputsToSetGet = convertOutputsToSetGet;
window.kjNodes.snapshotSelectedNodes = snapshotSelectedNodes;
function convertOutputsToSetGet(node) {
	if (!node) return;
	for (let slotIdx = 0; slotIdx < node.outputs.length; slotIdx++) {
		const output = node.outputs.at(slotIdx);
		const links = output.links();
		if (links.length === 0) continue;

		const linkType = output.type || "*";
		const linkName = output.name || linkType;

		// Collect targets to re-home, skipping existing Set/Get nodes
		const targets = [];
		for (const link of links) {
			const targetNode = comfy.graph.node(link.targetNodeId);
			if (targetNode && targetNode.type !== 'SetNode' && targetNode.type !== 'GetNode') {
				targets.push({ targetId: link.targetNodeId, targetSlot: link.targetIndex });
			}
		}
		if (targets.length === 0) continue;

		// Create Set node
		const nodePos = node.getPosition();
		const setNode = comfy.graph.add("SetNode", {
			position: {
				x: nodePos.x + node.getSize().width + 30,
				y: nodePos.y + slotIdx * 60
			}
		});
		setNode.setCollapsed(true);

		for (const target of targets) {
			comfy.graph.node(target.targetId)?.inputs.at(target.targetSlot)?.disconnect();
		}

		// Connect source → Set node input
		output.connectTo(setNode.id, { index: 0 });

		// Set the name widget
		setNode.widgets.get("Constant").setValue(linkName);
		setNode.setTitle(prefixedTitle("Set", linkName));
		validateName(setNode);
		const finalName = constantValue(setNode);
		setNode.setProperty("previousName", finalName);

		// Create a Get node for each target
		for (const target of targets) {
			const targetNode = comfy.graph.node(target.targetId);
			if (!targetNode) continue;

			const getNode = comfy.graph.add("GetNode");
			const targetPos = targetNode.getPosition();
			getNode.setPosition({
				x: targetPos.x - getNode.getSize().width - 30,
				y: targetPos.y
			});
			getNode.setCollapsed(true);

			getNode.widgets.get("Constant").setValue(finalName);
			onRename(getNode);

			getNode.outputs.at(0).connectTo(target.targetId, { index: target.targetSlot });
		}
	}
}

// Snapshot selection immediately (before right-click changes it)
function snapshotSelectedNodes(node, typeFilter) {
	const selected = comfy.graph.selection();
	// Always include the right-clicked node, even if selection state is inconsistent
	const byId = new Map(selected.map(n => [n.id, n]));
	byId.set(node.id, node);
	let nodes = [...byId.values()];
	if (typeFilter) nodes = nodes.filter(n => n.type === typeFilter);
	return nodes;
}

function showAlert(message, nodes) {
	const nodeList = nodes ? (Array.isArray(nodes) ? nodes : [nodes]) : [];
	const nodeInfo = nodeList.map(n => {
		const pos = n.getPosition();
		return `${n.getTitle() || n.type} [${Math.round(pos.x)}, ${Math.round(pos.y)}]`;
	}).join(', ');
	// COSMETIC: node.has_errors drew a red outline on the offending node. There is
	// no published error flag — errors on a node are the host's to render — so the
	// nodes are named in the toast and put under the user's cursor by selecting
	// them, which is what the outline existed to achieve.
	if (nodeList.length) comfy.graph.select(nodeList);
	comfy.commands.notify({
		severity: 'warn',
		summary: "KJ Set/Get",
		detail: nodeInfo ? `${message} — ${nodeInfo}` : message,
		life: 5000,
	});
}
function convertAllSetGetToLinks() {
	// "ALL" means the document, not the graph on screen, so every subgraph is
	// walked too. Same-graph pairs only — see the cross-graph gap above.
	for (const graph of documentGraphs()) {
		for (const setNode of nodesOfTypeIn(graph, 'SetNode')) {
			convertSetGetToLinks(setNode, graph);
		}
	}
}

function convertSetGetToLinks(setNode, graph = comfy.graph) {
	if (!setNode || setNode.isDeleted) return;

	const name = constantValue(setNode);
	const getters = name ? findGettersByName(name, graph) : [];

	// Find the source connected to the Set node's input
	const source = setNode.inputs.at(0)?.source();
	if (!source) return;
	const sourceOutput = graph.node(source.nodeId)?.outputs.at(source.outputIndex);
	if (!sourceOutput) return;

	// Collect all consumer connections from Get nodes and SetNode's own output passthrough
	const connections = [];
	for (const getter of getters) {
		connections.push(...(getter.outputs.at(0)?.targets() ?? []));
	}
	connections.push(...(setNode.outputs.at(0)?.targets() ?? []));

	// Remove all Get nodes (this also removes their links)
	for (const getter of getters) {
		getter.remove();
	}
	// Remove the Set node
	setNode.remove();

	// Create direct links from source to each consumer
	for (const conn of connections) {
		sourceOutput.connectTo(conn.nodeId, { index: conn.inputIndex });
	}
}

// region SetNode

// Returns true if the name was changed
function validateName(node) {
	let widgetValue = constantValue(node);

	if (widgetValue !== '') {
		let tries = 0;
		const existingValues = new Set();

		for (const other of comfy.graph.nodesOfType('SetNode')) {
			if (other.id !== node.id) existingValues.add(constantValue(other));
		}

		const originalValue = widgetValue;
		// Only strip _N suffix during paste to avoid FOO_0_1_2 accumulation.
		// For manual renames, keep the full name as base (user may intend FOO_3).
		const baseName = stateFor(node.id)._pasted ? widgetValue.replace(/_\d+$/, '') : widgetValue;
		while (existingValues.has(widgetValue)) {
			widgetValue = baseName + "_" + tries;
			tries++;
		}

		node.widgets.get("Constant").setValue(widgetValue);
		node.setTitle(prefixedTitle("Set", widgetValue));
		return widgetValue !== originalValue;
	}
	return false;
}

// A pasted or duplicated Set node must not inherit the original's name or its
// resolved type: the copy is unconnected, and two setters answering to one name is
// what validateName exists to prevent. previousName is cleared first so the rename
// validateName performs cannot be read as "this setter was renamed" and drag the
// ORIGINAL's getters onto the copy.
function onSetNodePasted(node) {
	const state = stateFor(node.id);
	const oldName = constantValue(node);
	node.setProperty("previousName", "");
	state._pasted = true;
	validateName(node);
	state._pasted = false;
	const newName = constantValue(node);
	if (newName !== oldName) {
		_pasteRenameMap.set(oldName, newName);
		// Clear the map after this paste cycle
		setTimeout(() => _pasteRenameMap.delete(oldName), 0);
	}
	// Reset type and color on paste — nothing is connected yet
	if (!node.inputs.at(0)?.isConnected) {
		node.inputs.at(0).modify({ type: '*', name: '*' });
		node.outputs.at(0).modify({ type: '*', name: '*' });
		node.setColor(undefined);
		node.setBgColor(undefined);
	}
}

function update(node) {
	if (node.isDeleted) return;

	const getters = findGetters(node);
	getters.forEach(getter => {
		setType(getter, node.inputs.at(0)?.type);
	});

	const previousName = node.getProperty("previousName");
	if (constantValue(node) && previousName) {
		const gettersWithPreviousName = findGetters(node, true);
		gettersWithPreviousName.forEach(getter => {
			setName(getter, constantValue(node));
		});
	}
}

function findGetters(node, checkForPreviousName) {
	const name = checkForPreviousName ? node.getProperty("previousName") : constantValue(node);
	if (!name || name === '') return [];
	return findGettersByName(name);
}

comfy.defs.extend("SetNode", (b) => {
	b.addMenuItem({
		label: "Convert to links",
		run: (node) => {
			for (const n of snapshotSelectedNodes(node, 'SetNode')) convertSetGetToLinks(n);
		},
	});
	b.addMenuItem({
		label: "Add paired GetNode",
		run: (node) => {
			const pos = node.getPosition();
			const getNode = comfy.graph.add("GetNode", {
				position: { x: pos.x + node.getSize().width + 30, y: pos.y }
			});
			// Set the widget value to match — this drives type, color, and connection
			const constant = getNode.widgets.get("Constant");
			if (!constant) {
				throw new Error("GetNode has no 'Constant' widget; cannot pair it.");
			}
			constant.setValue(constantValue(node));
			onRename(getNode);
			comfy.graph.select([getNode]);
		},
	});
	// `order` puts this first among the pack's own entries, which is what the
	// old options.unshift did relative to them.
	// DROPPED: getters in other graphs are not listed. subgraphs() finds them, but the
	// entry's whole job is to jump to one, and there is no published navigation into a
	// subgraph — centerOn and select address the graph on screen. An entry that cannot
	// go where it says is worse than no entry, so the submenu lists same-graph getters.
	// The "Show connections" / "Hide all connections" entries went with the link
	// drawing below.
	b.addMenuItem({
		label: "Getters",
		order: -1,
		items: (node) => findGetters(node).map(getter => ({
			label: `${getter.getTitle()} id: ${getter.id}`,
			run: () => {
				comfy.graph.centerOn(getter);
				comfy.graph.select([getter]);
			},
		})),
	});
});

comfy.defs.define({
	type: "SetNode",
	title: "Set",
	category: "KJNodes",
	// This node is purely frontend and does not impact the resulting prompt so
	// should not be serialized into it.
	execution: 'frontend',
	inputs: [{ name: "*", type: "*" }],
	outputs: [{ name: "*", type: "*" }],
	widgets: [{ type: "text", name: "Constant", value: "" }],

	// Be a wire: this output stands for whatever feeds the input.
	resolve: ({ self }) => {
		const source = self.input(0);
		return { "0": source ? { forwardTo: source } : { omit: true } };
	},

	onCreated(node, created) {
		node.setSerializeWidgets(true);
		node.setProperty("previousName", "");
		node.setProperty("Node name for S&R", "SetNode");
		node.setProperty("aux_id", "kijai/ComfyUI-KJNodes");

		node.widgets.get("Constant").on('change', () => {
			validateName(node);
			if (constantValue(node) !== '') {
				node.setTitle(prefixedTitle("Set", constantValue(node)));
			}
			update(node);
			node.setProperty("previousName", constantValue(node));
		});

		// Paste and workflow load both add the node before configuring it, so this
		// runs first for both and records which one is happening — replacing the
		// app.configuringGraph flag the old onConfigure read. A DUPLICATE is
		// different: clone() configures the copy before it joins the graph and while
		// it still carries the source's id, so onConfigured cannot address it at all
		// and would act on the source. `restored` names exactly that case, which is
		// what clone() used to handle by resetting the copy's slot and previousName.
		const state = stateFor(node.id);
		state._awaitingConfigure = !created.restored;
		state._fromLoad = created.loading;
		// configure follows add synchronously for both paste and load, so a flag still
		// set after this turn will never be answered — and leaving it set would let a
		// LATER clone's payload, which arrives under this node's id, be applied here.
		if (state._awaitingConfigure) queueMicrotask(() => { state._awaitingConfigure = false; });
		if (created.restored) onSetNodePasted(node);
	},

	onConfigured(node) {
		const state = stateFor(node.id);
		// Not this node's configure: a clone being built under an id we already own.
		if (!state._awaitingConfigure) return;
		state._awaitingConfigure = false;
		if (!state._fromLoad) onSetNodePasted(node);
	},

	onConnectionsChanged(node, event) {
		//On Disconnect
		if (event.side === 'input' && !event.connected) {
			const output = node.outputs.at(0);
			if (output?.isConnected) {
				node.inputs.at(event.index)?.modify({ type: output.type, name: output.name });
			} else {
				node.inputs.at(event.index)?.modify({ type: '*', name: '*' });
				output?.modify({ type: '*', name: '*' });
				node.setTitle("Set");
				node.setColor(undefined);
				node.setBgColor(undefined);
			}
			update(node);
		}
		if (event.side === 'output' && !event.connected) {
			const output = node.outputs.at(event.index);
			if (output) {
				// Keep type if input has a real connection
				const input = node.inputs.at(0);
				if (input?.isConnected) {
					output.modify({ type: input.type, name: input.name });
				} else {
					input?.modify({ type: '*', name: '*' });
					output.modify({ type: '*', name: '*' });
					node.setColor(undefined);
					node.setBgColor(undefined);
				}
			}
		}
		//On Connect
		if (event.side === 'input' && event.connected) {
			const source = node.inputs.at(event.index)?.source();
			const sourceSlot = source && comfy.graph.node(source.nodeId)?.outputs.at(source.outputIndex);
			const type = sourceSlot?.type;
			if (source && !type) {
				showAlert(`node ${node.getTitle()} input undefined.`, node);
			// During graph load, slots are restored by configure — the input already
			// carries the resolved type, so there is nothing left to derive.
			} else if (type && node.inputs.at(0)?.type !== type) {
				if (node.getTitle() === "Set"){
					node.setTitle(prefixedTitle("Set", type));
				}
				const constant = node.widgets.get("Constant");
				if (constant.getValue() === '' || constant.getValue() === '*'){
					// Determine the initial widget value based on naming setting
					const namingMode = comfy.settings.get("KJNodes.setGetNaming") ?? "empty";
					if (namingMode !== "empty") {
						const slotName = sourceSlot.name || type;
						switch (namingMode) {
							case "slot name": constant.setValue(slotName); break;
							case "slot name (lowercase)": constant.setValue(slotName.toLowerCase()); break;
							case "slot name (UPPERCASE)": constant.setValue(slotName.toUpperCase()); break;
						}
					}
				}

				validateName(node);
				node.setProperty("previousName", constantValue(node));
				node.inputs.at(0).modify({ type, name: type });
				node.outputs.at(0).modify({ type, name: type });

				autoColor(node, type);
			}
		}
		if (event.side === 'output' && event.connected) {
			const inputType = node.inputs.at(0)?.type;
			if (inputType && inputType !== '*') {
				node.outputs.at(0).modify({ type: inputType, name: inputType });
			} else {
				const peer = event.peerNodeId !== undefined && comfy.graph.node(event.peerNodeId);
				const type = peer && peer.inputs.at(event.peerIndex)?.type;
				if (type && type !== '*') {
					node.inputs.at(0).modify({ type, name: type });
					node.outputs.at(0).modify({ type, name: type });
					autoColor(node, type);
				}
			}
		}

		//Update either way
		update(node);
	},

	onRemoved(node) {
		_nodeState.delete(node.id);
	},
});

// region GetNode

function setName(node, name) {
	node.widgets.get("Constant").setValue(name);
	onRename(node);
}

function onRename(node) {
	if (node.isDeleted) return;
	const setter = findSetterByName(constantValue(node));
	if (setter) {
		setType(node, setter.inputs.at(0)?.type);
		node.setTitle(prefixedTitle("Get", constantValue(setter)));
	} else {
		setType(node, '*');
		const name = constantValue(node);
		node.setTitle(name ? prefixedTitle("Get", name) : "Get");
		// The old code raised this from getInputLink, i.e. while the prompt was
		// being built. resolve() is pure and has no channel to report through, so
		// the warning moves to the moment the name changes.
		if (name) showAlert("No SetNode found for " + name + "(" + node.type + ")", node);
	}
}

function validateLinks(node) {
	const output = node.outputs.at(0);
	if (!output || output.type === '*') return;
	for (const link of output.links()) {
		if (!link.type || link.type === '*') continue;
		const targetNode = comfy.graph.node(link.targetNodeId);
		const targetInput = targetNode?.inputs.at(link.targetIndex);
		const targetType = targetInput?.type;
		if (targetType === '*') continue;
		if (targetType && String(targetType).split(",").includes(output.type)) continue;
		if (link.type.split(",").includes(output.type)) continue;
		targetInput?.disconnect();
	}
}

function setType(node, type) {
	node.outputs.at(0)?.modify({ name: type, type });
	validateLinks(node);
	autoColor(node, type);
}

comfy.defs.extend("GetNode", (b) => {
	b.addMenuItem({
		label: "Convert to links",
		run: (node) => {
			const setters = new Set(snapshotSelectedNodes(node, 'GetNode')
				.map(n => findSetterByName(constantValue(n))).filter(Boolean));
			for (const s of setters) convertSetGetToLinks(s);
		},
	});
	// DROPPED: "Go to setter (in parent graph)". Navigating into or out of a subgraph
	// has no published equivalent, so the entry is hidden when the setter is not in
	// this graph rather than offered and inert.
	b.addMenuItem({
		label: "Go to setter",
		when: (node) => !!findSetterByName(constantValue(node)),
		run: goToSetter,
	});
	// The double-click shortcut for the same action. Replaces a document-level
	// dblclick listener plus a 'litegraph:canvas' node-double-click event that
	// existed only to stop a collapsed Get node opening its title editor instead.
	b.onDoubleClick(goToSetter);
});

// A Get node that was pasted or duplicated alongside its Set node has to follow the
// rename that node's own paste performed a moment ago; see _pasteRenameMap.
function followRenamedSetter(node) {
	const name = constantValue(node);
	if (!name) return;
	const newName = _pasteRenameMap.get(name);
	if (newName) node.widgets.get("Constant").setValue(newName);
	// Restore type/color from setter after paste
	setTimeout(() => onRename(node), 0);
}

function goToSetter(node) {
	const setter = findSetterByName(constantValue(node));
	if (!setter) return;
	comfy.graph.centerOn(setter);
	comfy.graph.select([setter]);
}

comfy.defs.define({
	type: "GetNode",
	title: "Get",
	category: "KJNodes",
	// This node is purely frontend and does not impact the resulting prompt so
	// should not be serialized into it.
	execution: 'frontend',
	outputs: [{ name: "*", type: "*" }],

	// Be a wire: this output stands for whatever feeds the matching Set node.
	resolve: ({ self, nodesOfType }) => {
		const name = self.widgetValue("Constant");
		const setter = name
			? nodesOfType("SetNode").find(n => n.widgetValue("Constant") === name)
			: undefined;
		const source = setter?.input(0);
		return { "0": source ? { forwardTo: source } : { omit: true } };
	},

	onCreated(node, created) {
		node.setSerializeWidgets(true);
		node.setProperty("Node name for S&R", "GetNode");
		node.setProperty("aux_id", "kijai/ComfyUI-KJNodes");

		const comboOptions = {};
		Object.defineProperty(comboOptions, 'values', {
			get: () => {
				let filterType = null;
				if (comfy.settings.get("KJNodes.filterGetNodeOptions") !== false) {
					const target = node.outputs?.at(0)?.targets()[0];
					if (target) {
						filterType = comfy.graph.node(target.nodeId)?.inputs.at(target.inputIndex)?.type || null;
					}
				}
				return getVisibleSetNames(filterType);
			},
			enumerable: true,
			configurable: true
		});
		node.widgets
			.add({ type: "combo", name: "Constant", value: "", options: comboOptions })
			.on('change', () => onRename(node));

		const state = stateFor(node.id);
		state._awaitingConfigure = !created.restored;
		state._fromLoad = created.loading;
		// configure follows add synchronously for both paste and load, so a flag still
		// set after this turn will never be answered — and leaving it set would let a
		// LATER clone's payload, which arrives under this node's id, be applied here.
		if (state._awaitingConfigure) queueMicrotask(() => { state._awaitingConfigure = false; });
		if (created.restored) followRenamedSetter(node);
	},

	onConfigured(node) {
		const state = stateFor(node.id);
		if (!state._awaitingConfigure) return;
		state._awaitingConfigure = false;
		if (!state._fromLoad) followRenamedSetter(node);
	},

	onConnectionsChanged(node) {
		validateLinks(node);
	},

	onRemoved(node) {
		_nodeState.delete(node.id);
	},
});

// region UI: commands, keybindings, settings
comfy.settings.declare({
	id: "KJNodes.setGetNaming",
	name: "Default SetNode widget value",
	category: ["KJNodes", "Set & Get", "Default SetNode widget value"],
	tooltip: "Initial Constant value when a Set node is first connected to a slot",
	type: "combo",
	options: ["empty", "slot name", "slot name (lowercase)", "slot name (UPPERCASE)"],
	defaultValue: "empty",
});
comfy.settings.declare({
	id: "KJNodes.nodeAutoColor",
	name: "Auto-color nodes",
	category: ["KJNodes", "Set & Get", "Auto-color nodes"],
	tooltip: "Automatically color Set/Get nodes based on their connection type",
	type: "boolean",
	defaultValue: true,
});
comfy.settings.declare({
	id: "KJNodes.disablePrefix",
	name: "Disable Set_/Get_ prefix",
	category: ["KJNodes", "Set & Get", "Disable Set_/Get_ prefix"],
	tooltip: "Prevents automatically adding Set_ and Get_ prefixes to node titles",
	defaultValue: false,
	type: "boolean",
});
comfy.settings.declare({
	id: "KJNodes.filterGetNodeOptions",
	name: "Filter Get node options by type",
	category: ["KJNodes", "Set & Get", "Filter Get node options by type"],
	tooltip: "When a Get node is connected, only show Set nodes with compatible types in the dropdown",
	type: "boolean",
	defaultValue: true,
});
// "KJNodes.showSetGetLinks", "KJNodes.shiftMiddleClickSetGet" and
// "KJNodes.middleClickSetGet" are no longer declared: each gated exactly one of the
// refused mechanisms below, and a setting that toggles nothing is worse than no
// setting.

comfy.commands.register({
	id: "KJNodes.AddSetNodeToSelected",
	label: "Add Set node to selected / at cursor",
	run: () => addNodeToSelectedOrCursor("SetNode", "right"),
	keybinding: { key: "s", ctrl: true, shift: true },
	scope: 'canvas',
});
comfy.commands.register({
	id: "KJNodes.AddGetNodeAtCursor",
	label: "Add Get node to selected / at cursor",
	run: () => addNodeToSelectedOrCursor("GetNode", "left"),
	keybinding: { key: "g", ctrl: true, shift: true },
	scope: 'canvas',
});
// Was a button rendered into the settings panel via `type: () => HTMLButtonElement`.
// REFUSED, not a pending gap: settings declare a control type and the host renders
// it. A pack-supplied renderer function inside the settings panel is the thing that
// will not be published, so the action is a command.
comfy.commands.register({
	id: "KJNodes.ConvertAllSetGetToLinks",
	label: "Convert ALL Set/Get to links",
	run: () => {
		if (confirm("This will replace ALL Set/Get pairs with direct links. This is irreversible. Continue?")) {
			convertAllSetGetToLinks();
			comfy.commands.notify({
				severity: 'info',
				summary: "KJ Set/Get",
				detail: "All Set/Get nodes converted to direct links",
				life: 3000,
			});
		}
	},
});
// Previously a dashed link was drawn between each Set node and its Get nodes by
// replacing lgCanvas.onDrawBackground, and — because a link between two offscreen
// nodes is culled — by patching computeVisibleNodes to force Set/Get nodes back into
// the visible set on every frame.
//
// REFUSED, not a pending gap: painting into the host canvas's own background pass.
// onDrawBackground is the renderer's, it is winner-takes-all across every pack that
// claims it, and the renderer is ours to replace.
//
// REFUSED, not a pending gap: patching computeVisibleNodes. What is on screen is the
// renderer's own culling decision, taken every frame for every node in the document.
// A pack that overrides it pays that cost for everyone and changes what every other
// pack sees as visible, to make its own decoration reach the edges of the viewport.
//
// The capability is not refused, and it is the host's rather than the pack's: the
// Set/Get relationship is declared to the host through resolve(), so the host knows
// the edge exists and is the only layer that can draw it under both renderers. Until
// it does, the pairing is still visible and still navigable without it: titles carry
// the name on both ends ("Set_foo" / "Get_foo"), the Set node's "Getters" submenu
// lists its getters and centres on one, and a Get node's "Go to setter" — or a
// double-click on it — jumps to its setter.
//
// COSMETIC: no dashed line is drawn between the pair.

// Previously "Convert outputs on all selected nodes to Set/Get" and "Convert selected
// Set/Get to links" hung off getCanvasMenuItems. addMenuItem contributes to a node's
// own menu, so both move to commands — the sanctioned action layer, reachable from
// the command palette and bindable to a key, which the canvas menu entries were not.
comfy.commands.register({
	id: "KJNodes.ConvertSelectedOutputsToSetGet",
	label: "Convert outputs on all selected nodes to Set/Get",
	run: () => {
		for (const node of comfy.graph.selection()) convertOutputsToSetGet(node);
	},
});
comfy.commands.register({
	id: "KJNodes.ConvertSelectedSetGetToLinks",
	label: "Convert selected Set/Get to links",
	run: () => {
		const selected = comfy.graph.selection();
		const setters = new Set(selected.filter(n => n.type === 'SetNode'));
		for (const n of selected.filter(n => n.type === 'GetNode')) {
			const setter = findSetterByName(constantValue(n));
			if (setter) setters.add(setter);
		}
		for (const s of setters) convertSetGetToLinks(s);
	},
});

// Previously "Convert to Set/Get" was added to a LINK's context menu by calling the
// canvas class's showLinkMenu and then counting .litecontextmenu elements in the
// document to find the menu it had just opened, so a row could be appended to it.
//
// REFUSED, not a pending gap: reaching into the DOM to find and edit a menu another
// component built. There is no contract that the menu is an element, that it carries
// that class, or that it is the last one on the page — the original had to guess all
// three — and a pack editing a menu it did not build is the shape addMenuItem exists
// to replace.
//
// The capability is not lost: a node's own menu carries "Convert all outputs to
// Set/Get" (contextmenu.js), which converts the very links this entry acted on, and
// the two commands above act on a selection.

// Previously a middle-click on a slot was intercepted through the canvas class's
// _processMiddleButton and createDefaultNodeForSlot, so the reroute that gesture
// normally creates was replaced with a Set/Get pair.
//
// REFUSED, not a pending gap: taking over an editor gesture and changing what a
// built-in action does. Middle-click-on-slot creates a reroute; a pack that silently
// substitutes its own node type has redefined a host gesture for every graph the user
// opens, and the two settings that gated it existed because the author knew it.
//
// The capability is not lost: Ctrl+Shift+S and Ctrl+Shift+G above create a Set or Get
// node against the selection or at the cursor, they are rebindable because they are
// commands, and the node menu offers the same on any node.

// The ExecutableNodeDTO.resolveOutput patch that made cross-subgraph Set/Get work is
// gone: chain following (Get → Set → Reroute → …) with cycle detection is what
// resolve() does, and a pack no longer patches the prompt builder to get it.
