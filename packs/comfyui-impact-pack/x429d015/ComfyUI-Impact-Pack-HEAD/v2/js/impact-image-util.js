import { comfy } from '/comfy/api/v2.js';
import { onNodeFeedback } from './common.js';

function getFileItem(baseType, path) {
	if (typeof path !== 'string' || !path) return null;

	const annotated = /\s*\[(output|input|temp)\]$/.exec(path);
	const type = annotated?.[1] ?? baseType;
	if (annotated) path = path.slice(0, annotated.index);

	const separator = path.lastIndexOf('/');
	return {
		filename: path.slice(separator + 1),
		subfolder: separator < 0 ? '' : path.slice(0, separator),
		type
	};
}

function viewUrl(item) {
	return comfy.backend.url(`/view?${new URLSearchParams(item)}`);
}

async function loadImageFromUrl(image, nodeId, value) {
	const item = getFileItem('temp', value);
	if (!item) return `$${nodeId}-0`;
	// The old pb_id table lived in process-global Python server state. Keep the
	// catalogue value itself and render it through ComfyUI's authenticated view.
	image.src = viewUrl(item);
	return value;
}

async function loadImageFromId(image, value) {
	// Legacy $node-slot ids depended on that same global table and cannot be
	// resolved across sealed executions.
	return false;
}

const previews = new Map();

function previewFor(node, onDraw) {
	let preview = previews.get(node.id);
	if (!preview) {
		preview = { image: null, surface: null, onDraw };
		preview.surface = node.widgets.canvas({
			name: 'impact-image-preview',
			height: 200,
			draw: (ctx, [width, height]) => {
				preview.onDraw?.();
				if (preview.image?.complete && preview.image.naturalWidth) {
					ctx.drawImage(preview.image, 0, 0, width, height);
				}
			}
		});
		previews.set(node.id, preview);
		node.setSizeConstraints({ minHeight: 200, autoHeight: true });
	} else if (onDraw) {
		preview.onDraw = onDraw;
	}
	return preview;
}

function showImage(node, image, onLoad) {
	const preview = previewFor(node);
	preview.image = image;
	const loaded = () => {
		preview.surface.redraw();
		onLoad?.();
	};
	if (image.complete && image.naturalWidth) {
		loaded();
	} else {
		image.addEventListener('load', loaded, { once: true });
	}
}

function encodeImage(image) {
	try {
		const canvas = document.createElement('canvas');
		canvas.width = image.naturalWidth || image.width;
		canvas.height = image.naturalHeight || image.height;
		canvas.getContext('2d')?.drawImage(image, 0, 0);
		return canvas.toDataURL('image/png');
	} catch {
		return '';
	}
}

const previewBridgeStates = new Map();

async function applyPreviewBridgeValue(node, widget, state, rawValue) {
	if (state.lock) return;

	const request = ++state.request;
	const value = typeof rawValue === 'string' ? rawValue : '';
	state.observedValue = value;
	const image = new Image();
	if (value.startsWith('$')) {
		if (await loadImageFromId(image, value) && request === state.request) {
			showImage(node, image);
		} else if (request === state.request) {
			const fallback = `$${node.id}-0`;
			if (widget.getValue() !== fallback) {
				state.lock = true;
				state.observedValue = fallback;
				widget.setValue(fallback);
				state.lock = false;
			}
		}
		return;
	}

	const id = await loadImageFromUrl(image, node.id, value);
	if (request !== state.request) return;
	state.observedValue = id;
	state.lock = true;
	try {
		widget.setValue(id);
		if (image.src) showImage(node, image);
	} finally {
		state.lock = false;
	}
}

comfy.defs.extend(['PreviewBridge', 'PreviewBridgeLatent'], (builder) => {
	builder.onCreated((node, event) => {
		const widget = node.widgets.get('image');
		if (!widget) return;

		const state = { lock: false, request: 0, observedValue: undefined };
		state.apply = (value) => applyPreviewBridgeValue(node, widget, state, value);
		previewBridgeStates.set(node.id, state);
		widget.on('change', (value) => void state.apply(value));
		previewFor(node, () => {
			const value = widget.getValue();
			if (value !== state.observedValue) {
				void state.apply(value);
			}
		});

		const value = widget.getValue();
		if (!event.restored || typeof value !== 'string' || !value) {
			widget.setValue(`$${node.id}-0`);
		}
		void state.apply(widget.getValue());
	});

	builder.onRemoved((node) => {
		previewBridgeStates.delete(node.id);
		previews.delete(node.id);
	});
});

onNodeFeedback(({ node, detail, changed }) => {
	if (!changed && detail.widget_name === 'image') {
		const state = previewBridgeStates.get(node.id);
		if (state) {
			void state.apply(detail.value);
		}
	}
});

const imageReceiverStates = new Map();

export function showReceivedImage(node, image) {
	const state = imageReceiverStates.get(node.id);
	showImage(node, image, state ? () => {
		state.base64 = encodeImage(image);
		state.dataWidget.setValue('[IMAGE DATA]');
	} : undefined);
}

function showPathImage(node, value) {
	const item = getFileItem('temp', value);
	if (!item) return;
	const image = new Image();
	showReceivedImage(node, image);
	image.src = viewUrl(item);
}

comfy.defs.extend('ImageReceiver', (builder) => {
	builder.onCreated((node) => {
		const pathWidget = node.widgets.get('image');
		const dataWidget = node.widgets.get('image_data');
		const saveWidget = node.widgets.get('save_to_workflow');
		if (!dataWidget || !saveWidget) return;

		const saved = dataWidget.getValue();
		const state = {
			base64: typeof saved === 'string' && saved !== '[IMAGE DATA]' ? saved : '',
			dataWidget,
			observedPath: pathWidget?.getValue()
		};
		imageReceiverStates.set(node.id, state);
		dataWidget.setValue(saved ? '[IMAGE DATA]' : '');
		dataWidget.on('beforeSerialize', (event) => {
			if (event.context === 'workflow') {
				event.setSerializedValue('[IMAGE DATA]');
			} else {
				event.setSerializedValue(saveWidget.getValue() ? state.base64 : '');
			}
		});

		if (state.base64) {
			const image = new Image();
			showReceivedImage(node, image);
			image.src = state.base64;
		} else if (pathWidget?.getValue()) {
			showPathImage(node, pathWidget.getValue());
		}
		const applyPath = (value) => {
			state.observedPath = value;
			showPathImage(node, value);
		};
		pathWidget?.on('change', applyPath);
		previewFor(node, () => {
			const value = pathWidget?.getValue();
			if (value !== state.observedPath) {
				applyPath(value);
			}
		});
	});

	builder.onRemoved((node) => {
		imageReceiverStates.delete(node.id);
		previews.delete(node.id);
	});
});

comfy.defs.extend('LatentReceiver', (builder) => {
	builder.onRemoved((node) => previews.delete(node.id));
});
