import { comfy } from '/comfy/api/v2.js';
import { applySecureWorkflowActions, customAlert, isBeforeFrontendVersion } from "./common.js";
import { showReceivedImage } from './impact-image-util.js';

const is_legacy_front = () => isBeforeFrontendVersion('1.16.9');

if(is_legacy_front()) {
	customAlert("An outdated version(<1.16.9) of the `comfyui-frontend-package` is installed. It is not compatible with the current version of the Impact Pack.");
}

let wildcards_list = [];
let wildcard_status = {
	on_demand_mode: false,
	total_available: 0,
	loaded_count: 0,
	last_update: null,
	secure_catalogue: true
};

async function load_wildcards() {
	// Execution resolves named files from the pack's declared asset catalogue.
	// The browser gets no path/listing authority; custom names are entered as
	// __folder/name__ tokens.
	wildcards_list = [];
	refresh_wildcard_widgets();
}

async function load_wildcard_status() {
	wildcard_status = {
		on_demand_mode: false,
		total_available: 0,
		loaded_count: 0,
		last_update: new Date(),
		secure_catalogue: true
	};
}

export function get_wildcard_label() {
	if (wildcard_status.secure_catalogue) {
		return `Select Wildcard 🔒 Declared catalogue`;
	}
	if (wildcard_status.on_demand_mode) {
		return `Select Wildcard 🔵 On-Demand: ${wildcard_status.loaded_count} loaded`;
	} else {
		return `Select Wildcard 🟢 Full Cache`;
	}
}

export function is_wildcard_label(value) {
	// Check if value is a label (not an actual wildcard selection)
	return value === "Select the Wildcard to add to the text" ||
	       value === "Select Wildcard 🔒 Declared catalogue" ||
	       value.startsWith("Select Wildcard 🔵 On-Demand:") ||
	       value === "Select Wildcard 🟢 Full Cache";
}

export function get_wildcards_list() {
	return wildcards_list;
}

export { load_wildcard_status };

// temporary implementation (copying from https://github.com/pythongosssss/ComfyUI-WD14-Tagger)
// I think this should be included into master!!
class ImpactProgressBadge {
	constructor() {
		// Handles hold no arbitrary properties, so the per-node badge state and
		// the handle that removes it live here; both are dropped in onRemoved.
		this.states = new Map();
		this.removers = new Map();
	}

	getState(node) {
		return this.states.get(node.id) || {};
	}

	setState(node, state) {
		this.states.set(node.id, state);
	}

	attach(node) {
		if (this.removers.has(node.id)) {
			return;
		}
		const self = this;
		this.removers.set(node.id, node.addBadge(() => {
			const status = self.getState(node).status;
			if (!status?.text) {
				return { text: "" };
			}
			const progress = Number.isFinite(status.progress)
				? ` ${Math.round(Math.max(0, Math.min(1, status.progress)) * 100)}%`
				: '';
			return {
				text: `${status.text}${progress}`,
				color: status.fgColor,
				bgColor: status.bgColor || "dodgerblue"
			};
		}));
	}

	addStatusHandler() {
		if (this.statusTagHandler) {
			return;
		}
		this.statusTagHandler = true;

		comfy.backend.on("impact/update_status", (detail) => {
			// app.runningNodeId was the fallback when the event carries no node.
			let { node, progress, text } = detail;
			const n = node ? comfy.graph.node(String(node)) : comfy.executingNode();
			if (!n) return;
			const state = this.getState(n);
			state.status = Object.assign(state.status || {}, { progress: text ? progress : null, text: text || null });
			this.setState(n, state);
		});
	}

	release(node) {
		const remove = this.removers.get(node.id);
		if (remove) remove();
		this.removers.delete(node.id);
		this.states.delete(node.id);
	}
}

// COSMETIC: progress is shown as a numeric percentage in the native badge;
// its old partial-width fill and separate progress colour are not reproduced.

const maskPainterStates = new Map();

function imgSendHandler(detail) {
	if(detail.images.length > 0){
		let data = detail.images[0];

		let nodes = comfy.graph.nodesOfType('ImageReceiver');
		for(let i in nodes) {
			let is_linked = false;
			let link_id_widget = nodes[i].widgets.at(1);

			if(link_id_widget?.isHidden()) {
				let input = nodes[i].inputs.byName('link_id');
				let src = input?.source();
				if(src) {
					let src_node = comfy.graph.node(src.nodeId);
					if(src_node?.type == 'ImpactInt' || src_node?.type == 'PrimitiveNode') {
						is_linked = true;
					}
				}
			}
			else if(link_id_widget?.getValue() == detail.link_id) {
				is_linked = true;
			}

			if(is_linked) {
				let image_widget = nodes[i].widgets.at(0);
				if(data.subfolder)
					image_widget.setValue(`${data.subfolder}/${data.filename} [${data.type}]`);
				else
					image_widget.setValue(`${data.filename} [${data.type}]`);

				let img = new Image();
				showReceivedImage(nodes[i], img);
				img.src = comfy.backend.url(`/view?filename=${data.filename}&type=${data.type}&subfolder=${data.subfolder}`);
			}
		}
	}
}


function latentSendHandler(detail) {
	let data = detail.asset || detail.images?.[0];
	if(data){
		let preview = detail.images?.[0];

		let nodes = comfy.graph.nodesOfType('LatentReceiver');
		for(let i in nodes) {
			if(nodes[i].widgets.at(1)?.getValue() == detail.link_id) {
				let image_widget = nodes[i].widgets.at(0);
				if(data.subfolder)
					image_widget.setValue(`${data.subfolder}/${data.filename} [${data.type}]`);
				else
					image_widget.setValue(`${data.filename} [${data.type}]`);

				if (preview) {
					let img = new Image();
					showReceivedImage(nodes[i], img);
					img.src = comfy.backend.url(`/view?filename=${preview.filename}&type=${preview.type}&subfolder=${preview.subfolder}`);
				}
			}
		}
	}
}


function valueSendHandler(detail) {
	let nodes = comfy.graph.nodesOfType('ImpactValueReceiver');
	for(let i in nodes) {
		if(nodes[i].widgets.at(2)?.getValue() == detail.link_id) {
			nodes[i].widgets.at(1).setValue(detail.value);

			let typ = typeof detail.value;
			let type_widget = nodes[i].widgets.at(0);
			if(typ == 'string') {
				type_widget.setValue("STRING");
			}
			else if(typ == "boolean") {
				type_widget.setValue("BOOLEAN");
			}
			else if(typ != "number") {
				type_widget.setValue(typeof detail.value);
			}
			else if(Number.isInteger(detail.value)) {
				type_widget.setValue("INT");
			}
			else {
				type_widget.setValue("FLOAT");
			}
		}
	}
}


const impactProgressBadge = new ImpactProgressBadge();

comfy.backend.on("stop-iteration", () => {
	comfy.queue.disableAutoQueue();
});
comfy.backend.on("value-send", valueSendHandler);
comfy.backend.on("img-send", imgSendHandler);
comfy.backend.on("latent-send", latentSendHandler);

// Update wildcard status after workflow execution (on-demand mode)
comfy.backend.on("executed", async (detail) => {
	const sends = detail?.output?.secure_send;
	if (Array.isArray(sends)) {
		for (const send of sends) {
			if (send?.kind === 'image') imgSendHandler(send);
			else if (send?.kind === 'latent') latentSendHandler(send);
		}
	}
	const actions = detail?.output?.secure_actions;
	if (Array.isArray(actions)) {
		for (const action of actions) {
			if (action?.kind === 'value') valueSendHandler(action);
		}
		await applySecureWorkflowActions(actions);
	}
	if (wildcard_status.on_demand_mode) {
		await load_wildcard_status();
		await load_wildcards();
	}
});

comfy.commands.register({
	id: 'Impact.refresh-impact-wildcard',
	label: 'Impact: Refresh Wildcard',
	run: async () => {
		await Promise.all([load_wildcards(), load_wildcard_status()]);
		comfy.commands.notify({
			severity: 'info',
			summary: 'Secure wildcard mode',
			detail: 'Named files resolve from the declared pack catalogue. Enter __folder/name__ directly.',
			life: 3000
		});
	}
});

comfy.ui.addActionBarButton({
	id: 'Impact.refresh-impact-wildcard-button',
	icon: 'icon-[lucide--refresh-cw]',
	tooltip: 'Refresh Impact wildcard list',
	run: () => void comfy.commands.run('Impact.refresh-impact-wildcard')
});

// COSMETIC: wildcard refresh is in the action bar and command palette instead
// of being placed in the host's Edit menu.

comfy.defs.extend(["IterativeLatentUpscale", "IterativeImageUpscale", "RegionalSampler", "RegionalSamplerAdvanced"], (b) => {
	impactProgressBadge.addStatusHandler();
	b.onCreated((node) => {
		impactProgressBadge.attach(node);
	});
	b.onRemoved((node) => {
		impactProgressBadge.release(node);
	});
});

comfy.defs.extend("ImpactControlBridge", (b) => {
	b.onConnectionsChanged((node, event) => {
		const input0 = node.inputs.at(0);
		const output0 = node.outputs.at(0);
		if(event.index != 0 || !input0 || !output0 || input0.type != '*')
			return;

		// assign type
		let slot_type = '*';

		if(event.side == 'output') {
			slot_type = output0.links()[0]?.type ?? '*';
		}
		else {
			const link = input0.link();
			const origin = link ? comfy.graph.node(link.sourceNodeId) : undefined;
			slot_type = origin?.outputs.at(link.sourceIndex)?.type ?? '*';
		}

		input0.modify({ type: slot_type });
		output0.modify({ type: slot_type, label: slot_type });
	});
});

comfy.defs.extend(["ImpactConditionalBranch", "ImpactConditionalBranchSelMode"], (b) => {
	b.onConnectionsChanged((node, event) => {
		const input0 = node.inputs.at(0);
		const input1 = node.inputs.at(1);
		const output0 = node.outputs.at(0);
		if(!input0 || !output0 || input0.type != '*')
			return;

		if(event.index >= 2)
			return;

		// assign type
		let slot_type = '*';

		if(event.side == 'output') {
			slot_type = output0.links()[0]?.type ?? '*';
		}
		else {
			const link = node.inputs.at(event.index)?.link();
			const origin = link ? comfy.graph.node(link.sourceNodeId) : undefined;
			slot_type = origin?.outputs.at(link.sourceIndex)?.type ?? '*';
		}

		input0.modify({ type: slot_type });
		if(input1)
			input1.modify({ type: slot_type });
		output0.modify({ type: slot_type, label: slot_type });
	});
});

comfy.defs.extend("ImpactCompare", (b) => {
	b.onConnectionsChanged((node, event) => {
		const input0 = node.inputs.at(0);
		const input1 = node.inputs.at(1);
		if(!input0 || input0.type != '*' || event.side == 'output')
			return;

		// assign type
		const link = node.inputs.at(event.index)?.link();
		const origin = link ? comfy.graph.node(link.sourceNodeId) : undefined;
		let slot_type = origin?.outputs.at(link.sourceIndex)?.type;
		if(slot_type == undefined)
			return;

		input0.modify({ type: slot_type });
		if(input1)
			input1.modify({ type: slot_type });
	});
});

comfy.defs.extend("ImpactSelectNthItemOfAnyList", (b) => {
	b.onConnectionsChanged((node, event) => {
		const input0 = node.inputs.at(0);
		const output0 = node.outputs.at(0);
		if(!input0 || !output0 || input0.type != '*')
			return;

		if(event.index >= 2)
			return;

		// assign type
		let slot_type = '*';

		if(event.side == 'output') {
			slot_type = output0.links()[0]?.type ?? '*';
		}
		else {
			const link = node.inputs.at(event.index)?.link();
			const origin = link ? comfy.graph.node(link.sourceNodeId) : undefined;
			slot_type = origin?.outputs.at(link.sourceIndex)?.type ?? '*';
		}

		input0.modify({ type: slot_type });
		output0.modify({ type: slot_type, label: slot_type });
	});
});

const inversedSwitchReady = new Set();

function updateInversedSwitch(node) {
	let index = 1;
	for (const output of node.outputs.all()) {
		output.modify({ name: `output${index}` });
		index++;
	}

	const count = node.widgets.at(0);
	if (!count) {
		return;
	}
	const max = node.inputs.byName('select') ? node.outputs.length - 1 : node.outputs.length;
	count.setOption('max', max);
	count.setValue(Math.min(Number(count.getValue()) || 0, max));
	if (max > 0 && count.getValue() == 0) {
		count.setValue(1);
	}
}

comfy.defs.extend('ImpactInversedSwitch', (builder) => {
	builder.onCreated((node, event) => {
		if (!event.restored) {
			for (const output of node.outputs.all()) {
				node.outputs.remove(output.id);
			}
			node.outputs.add('output1', '*');
		}
		updateInversedSwitch(node);
		inversedSwitchReady.add(node.id);
	});

	builder.onConnectionsChanged((node, event) => {
		if (!inversedSwitchReady.has(node.id)) {
			return;
		}
		const output0 = node.outputs.at(0);
		if (!output0) {
			return;
		}

		if (event.side === 'input') {
			if (!event.connected || event.peerNodeId === undefined || event.peerIndex === undefined) {
				return;
			}
			const input = node.inputs.at(event.index);
			const origin = comfy.graph.node(event.peerNodeId);
			const originOutput = origin?.outputs.at(event.peerIndex);
			if (!input || !originOutput) {
				return;
			}
			if (origin?.type === 'Reroute') {
				input.disconnect();
				return;
			}
			if (node.inputs.at(0)?.type === '*') {
				for (const candidate of node.inputs.all()) {
					if (candidate.name !== 'select') {
						candidate.modify({ type: originOutput.type });
					}
				}
				output0.modify({ type: originOutput.type, name: 'output1' });
			}
			return;
		}

		const output = node.outputs.at(event.index);
		if (!event.connected) {
			const outputId = output?.id;
			queueMicrotask(() => {
				if (!inversedSwitchReady.has(node.id) || !outputId) {
					return;
				}
				const current = node.outputs.byId(outputId);
				if (current && !current.isConnected && node.outputs.length > 1) {
					node.outputs.remove(outputId);
				}
				updateInversedSwitch(node);
			});
			return;
		}

		const link = output?.links().find((candidate) =>
			candidate.targetNodeId === event.peerNodeId && candidate.targetIndex === event.peerIndex
		);
		const target = event.peerNodeId === undefined ? undefined : comfy.graph.node(event.peerNodeId);
		const targetInput = event.peerIndex === undefined ? undefined : target?.inputs.at(event.peerIndex);
		if (!output || !link || !targetInput) {
			return;
		}
		if (target?.type === 'Reroute' || (link.type === '*' && targetInput.type !== '*')) {
			targetInput.disconnect();
			return;
		}
		if (output0.type === '*') {
			output0.modify({ type: link.type, name: link.type });
			for (const input of node.inputs.all()) {
				if (input.name !== 'select') {
					input.modify({ type: link.type });
				}
			}
		}
		if (output.isConnected && output.index === node.outputs.length - 1) {
			node.outputs.add(`output${node.outputs.length + 1}`, output0.type);
		}
		updateInversedSwitch(node);
	});

	builder.onRemoved((node) => inversedSwitchReady.delete(node.id));
});

const dynamicInputNodesReady = new Set();

comfy.defs.extend(['ImpactMakeImageList', 'ImpactMakeImageBatch', 'ImpactMakeMaskList', 'ImpactMakeMaskBatch',
	'ImpactMakeAnyList', 'CombineRegionalPrompts', 'ImpactCombineConditionings', 'ImpactConcatConditionings',
	'ImpactSEGSConcat'], (b) => {
	var input_name = "input";

	switch(b.def.type) {
	case 'ImpactMakeImageList':
	case 'ImpactMakeImageBatch':
		input_name = "image";
		break;

	case 'ImpactMakeMaskList':
	case 'ImpactMakeMaskBatch':
		input_name = "mask";
		break;

	case 'ImpactMakeAnyList':
		input_name = "value";
		break;

	case 'ImpactSEGSConcat':
		input_name = "segs";
		break;

	case 'CombineRegionalPrompts':
		input_name = "regional_prompts";
		break;

	case 'ImpactCombineConditionings':
	case 'ImpactConcatConditionings':
		input_name = "conditioning";
		break;

	case 'LatentSwitch':
		input_name = "input";
		break;

	case 'SEGSSwitch':
		input_name = "input";
		break;

	case 'ImpactSwitch':
		input_name = "input";
	}

	const dynamicInputs = (node) => node.inputs.all().filter(
		(input) => input.name !== 'select' && input.name !== 'sel_mode'
	);
	const updateInputs = (node, rename = true) => {
		const inputs = dynamicInputs(node);
		if (rename) {
			inputs.forEach((input, index) => input.modify({ name: `${input_name}${index + 1}` }));
		}
		const count = node.widgets.at(0);
		if (count) {
			const max = Math.max(0, inputs.length - 1);
			count.setOption('max', max);
			count.setValue(Math.min(Number(count.getValue()) || 0, max));
		}
	};

	b.onCreated((node, event) => {
		if (!event.restored && dynamicInputs(node).length === 0) {
			node.inputs.add(`${input_name}1`, node.outputs.at(0)?.type ?? '*');
		}
		updateInputs(node, !event.restored);
		dynamicInputNodesReady.add(node.id);
	});

	b.onConnectionsChanged((node, event) => {
		if (!dynamicInputNodesReady.has(node.id)) {
			return;
		}
		const output0 = node.outputs.at(0);
		if (!output0) {
			return;
		}

		if (event.side === 'output') {
			if (!event.connected || event.index !== 0 || event.peerNodeId === undefined || event.peerIndex === undefined) {
				return;
			}
			const target = comfy.graph.node(event.peerNodeId);
			const targetInput = target?.inputs.at(event.peerIndex);
			const link = output0.links().find((candidate) =>
				candidate.targetNodeId === event.peerNodeId && candidate.targetIndex === event.peerIndex
			);
			if (!targetInput || !link) {
				return;
			}
			if (node.comfyClass === 'ImpactSwitch' && target?.type === 'Reroute') {
				targetInput.disconnect();
				return;
			}
			if (output0.type === '*') {
				if (link.type === '*' && targetInput.type !== '*') {
					targetInput.disconnect();
					return;
				}
				output0.modify({ type: link.type, label: link.type, name: link.type });
				for (const input of dynamicInputs(node)) {
					input.modify({ type: link.type });
				}
			}
			return;
		}

		const input = node.inputs.at(event.index);
		if (!input || input.name === 'select' || input.name === 'sel_mode') {
			return;
		}
		if (!event.connected) {
			const inputId = input.id;
			queueMicrotask(() => {
				if (!dynamicInputNodesReady.has(node.id)) {
					return;
				}
				const current = node.inputs.byId(inputId);
				if (current && !current.isConnected && dynamicInputs(node).length > 1) {
					node.inputs.remove(inputId);
				}
				updateInputs(node);
			});
			return;
		}
		if (event.peerNodeId === undefined || event.peerIndex === undefined) {
			return;
		}

		const origin = comfy.graph.node(event.peerNodeId);
		const originOutput = origin?.outputs.at(event.peerIndex);
		if (!originOutput) {
			return;
		}
		if (node.comfyClass === 'ImpactSwitch' && origin?.type === 'Reroute') {
			input.disconnect();
			return;
		}
		if (node.inputs.at(0)?.type === '*') {
			const originType = originOutput.type;
			for (const candidate of dynamicInputs(node)) {
				candidate.modify({ type: originType });
			}
			output0.modify({ type: originType, label: originType, name: originType });
		}

		const inputs = dynamicInputs(node);
		if (input.isConnected && inputs.at(-1)?.id === input.id) {
			node.inputs.add(`${input_name}${inputs.length + 1}`, output0.type);
		}
		updateInputs(node);
	});

	b.onRemoved((node) => dynamicInputNodesReady.delete(node.id));
});

comfy.defs.extend("MaskPainter", (b) => {
	b.onExecuted((node, result) => {
		if (result.raw?.aux) {
			maskPainterStates.set(node.id, {
				imageHash: result.raw.aux[0],
				forward: result.raw.aux[1]?.[0]
			});
		}
	});

	b.onCreated((node, event) => {
		const editMask = node.widgets.add({ type: "button", name: "Edit mask", value: null });
		editMask.on('activate', () => {
			// The command edits the selected node, which is what copyToClipspace +
			// clipspace_return_node arranged; selecting is now the way to say which.
			comfy.graph.select([node]);
			void comfy.commands.run('Comfy.MaskEditor.OpenMaskEditor');
		});

		const image = node.widgets.at(0);
		if (!event.restored && image && !image.getValue()) {
			image.setValue('#placeholder');
		}
		image?.on('beforeSerialize', (serializeEvent) => {
			const value = image.getValue();
			if (value === '#placeholder' || (value && typeof value === 'object')) {
				return;
			}
			const state = maskPainterStates.get(node.id);
			const output = node.getOutputImages()[node.getDisplayedImageIndex() ?? 0];
			if (!state?.forward || !output) {
				return;
			}
			const url = new URL(output, window.location.href);
			const filename = url.searchParams.get('filename');
			if (!filename) {
				return;
			}
			serializeEvent.setSerializedValue({
				filename,
				subfolder: url.searchParams.get('subfolder') ?? '',
				type: url.searchParams.get('type') ?? 'input',
				image_hash: state.imageHash,
				forward_filename: state.forward.filename,
				forward_subfolder: state.forward.subfolder,
				forward_type: state.forward.type
			});
		});
	});

	b.onRemoved((node) => maskPainterStates.delete(node.id));
});

comfy.defs.extend(["ToDetailerPipe", "ToDetailerPipeSDXL", "BasicPipeToDetailerPipe", "BasicPipeToDetailerPipeSDXL",
	"EditDetailerPipe", "FaceDetailer", "DetailerForEach", "DetailerForEachDebug", "DetailerForEachPipe",
	"DetailerForEachDebugPipe"], (b) => {
	b.onCreated((node) => {
		for(const widget of node.widgets.all()) {
			if(widget.widgetType === "customtext") {
				widget.setOption('placeholder', "wildcard spec: if kept empty, this option will be ignored");
				widget.on('beforeSerialize', (event) => {
					if (event.context !== 'workflow') {
						event.setSerializedValue(widget.getValue());
					}
				});
			}
		}
	});
});

comfy.defs.extend(["ImpactSEGSLabelFilter", "SEGSLabelFilterDetailerHookProvider"], (b) => {
	b.onCreated((node) => {
		const picker = node.widgets.at(0);
		const target = node.widgets.at(1);
		if(!picker || !target)
			return;

		picker.on('change', (value) => {
			if(target.getValue().trim() != "" && !target.getValue().trim().endsWith(","))
				target.setValue(target.getValue() + ", ");

			target.setValue(target.getValue() + value);
		});
	});
});

const detectorBadgeRemovers = new Map();

comfy.defs.extend('UltralyticsDetectorProvider', (builder) => {
	builder.onCreated((node) => {
		const model = node.widgets.get('model_name');
		if (!model) {
			return;
		}
		detectorBadgeRemovers.set(node.id, node.addBadge(() => {
			const name = String(model.getValue() ?? '');
			const isSegmentation = name.startsWith('segm/') || name.includes('-seg');
			return isSegmentation
				? { text: '' }
				: { text: 'Mask output needs a segmentation model', bgColor: 'red' };
		}));
	});
	builder.onRemoved((node) => {
		detectorBadgeRemovers.get(node.id)?.();
		detectorBadgeRemovers.delete(node.id);
	});
});

// COSMETIC: the invalid-segmentation warning is a native title badge instead
// of a red cross painted over the mask output socket.

// Handles hold no arbitrary properties, so the per-node picker widget lives here
// and is dropped in onRemoved.
const wildcard_nodes = new Map();

function refresh_wildcard_widgets() {
	for(const state of wildcard_nodes.values()) {
		state.wildcard_widget.setOption("values", wildcards_list);
		state.wildcard_widget.setValue(get_wildcard_label());
	}
}

comfy.defs.extend(["ImpactWildcardEncode", "ImpactWildcardProcessor", "ToDetailerPipe", "ToDetailerPipeSDXL",
	"EditDetailerPipe", "EditDetailerPipeSDXL", "BasicPipeToDetailerPipe", "BasicPipeToDetailerPipeSDXL"], (b) => {
	b.onCreated((node) => {
		var tbox_id = 0;
		var combo_id = 3;
		var has_lora = true;

		switch(node.comfyClass){
			case "ImpactWildcardEncode":
				tbox_id = 0;
				combo_id = 3;
				break;

			case "ImpactWildcardProcessor":
				tbox_id = 0;
				combo_id = 4;
				has_lora = false;
				break;

			case "ToDetailerPipe":
			case "ToDetailerPipeSDXL":
			case "EditDetailerPipe":
			case "EditDetailerPipeSDXL":
			case "BasicPipeToDetailerPipe":
			case "BasicPipeToDetailerPipeSDXL":
				tbox_id = 0;
				combo_id = 1;
				break;
		}

		const tbox = node.widgets.at(tbox_id);
		const wildcard_widget = node.widgets.at(combo_id+1);
		if(!tbox || !wildcard_widget)
			return;

		// The picker never keeps its selection: the combo shows a label again as
		// soon as one is made, which is what the old `value` accessor faked.
		wildcard_widget.setOption("values", wildcards_list);
		wildcard_widget.setValue(get_wildcard_label());
		wildcard_nodes.set(node.id, { wildcard_widget });

		wildcard_widget.on('change', async (value) => {
			if(is_wildcard_label(value))
				return;

			if(tbox.getValue() != '')
				tbox.setValue(tbox.getValue() + ', ');

			tbox.setValue(tbox.getValue() + value);
			wildcard_widget.setValue(get_wildcard_label());

			// Reload wildcard status to update loaded count
			if (wildcard_status.on_demand_mode) {
				await load_wildcard_status();
				await load_wildcards();
			}
		});

		if(has_lora) {
			const lora_widget = node.widgets.at(combo_id);
			if(!lora_widget)
				return;

			lora_widget.setValue("Select the LoRA to add to the text");

			lora_widget.on('change', (value) => {
				if(value === "Select the LoRA to add to the text")
					return;

				let lora_name = value;
				if(lora_name.endsWith('.safetensors')) {
					lora_name = lora_name.slice(0, -12);
				}

				tbox.setValue(tbox.getValue() + `<lora:${lora_name}>`);
				lora_widget.setValue("Select the LoRA to add to the text");
			});
		}
	});

	b.onRemoved((node) => {
		wildcard_nodes.delete(node.id);
	});
});

comfy.defs.extend(["ImpactWildcardProcessor", "ImpactWildcardEncode"], (b) => {
	// The old `mode` accessor normalised the legacy boolean toggle to the string
	// the backend expects, and mirrored it onto the populated_text field.
	function applyMode(node) {
		const populated_text_widget = node.widgets.get('populated_text');
		const mode_widget = node.widgets.get('mode');
		if(!populated_text_widget || !mode_widget)
			return;

		const value = mode_widget.getValue();
		const mode_value = value === true ? "populate" : value === false ? "fixed" : value;
		if(mode_value !== value)
			mode_widget.setValue(mode_value);

		populated_text_widget.setDisabled(mode_value == 'populate');
	}

	b.onCreated((node) => {
		node.widgets.at(0).setOption('placeholder', "Wildcard Prompt (User input)");
		node.widgets.at(1).setOption('placeholder', "Populated Prompt (Will be generated automatically)");
		node.widgets.at(1).setDisabled(true);

		const mode_widget = node.widgets.get('mode');
		if(mode_widget)
			mode_widget.on('change', () => applyMode(node));

		applyMode(node);
	});

	b.onConfigured((node) => applyMode(node));
});

// Initialize only after every module-scoped store above exists. Calling the
// async helpers near the imports executes their synchronous prefixes before
// `wildcard_nodes` is initialized and leaves an unhandled ReferenceError.
void Promise.all([load_wildcards(), load_wildcard_status()]);
