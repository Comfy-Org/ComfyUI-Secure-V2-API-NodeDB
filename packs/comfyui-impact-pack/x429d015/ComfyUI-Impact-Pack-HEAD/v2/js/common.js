import { comfy } from '/comfy/api/v2.js';

export function customAlert(message) {
	try {
		comfy.commands.notify({ severity: 'warn', summary: message });
	}
	catch {
		alert(message);
	}
}

export function isBeforeFrontendVersion(compareVersion) {
    try {
        const frontendVersion = window['__COMFYUI_FRONTEND_VERSION__'];
        if (typeof frontendVersion !== 'string') {
            return false;
        }

        function parseVersion(versionString) {
            const parts = versionString.split('.').map(Number);
            return parts.length === 3 && parts.every(part => !isNaN(part)) ? parts : null;
        }

        const currentVersion = parseVersion(frontendVersion);
        const comparisonVersion = parseVersion(compareVersion);

        if (!currentVersion || !comparisonVersion) {
            return false;
        }

        for (let i = 0; i < 3; i++) {
            if (currentVersion[i] > comparisonVersion[i]) {
                return false;
            } else if (currentVersion[i] < comparisonVersion[i]) {
                return true;
            }
        }

        return false;
    } catch {
        return true;
    }
}

// REFUSED: replacing the host-wide dialog handler to suppress the pack's
// "IMPACT-PACK-SIGNAL: STOP CONTROL BRIDGE" exception. The control bridge
// still applies node modes and queues its continuation from backend events;
// only suppression of the host's error message is omitted.


const nodeFeedbackListeners = new Set();

export function onNodeFeedback(listener) {
	nodeFeedbackListeners.add(listener);
	return () => nodeFeedbackListeners.delete(listener);
}

function nodeFeedbackHandler(detail) {
	let node = comfy.graph.node(String(detail.node_id));
	if(node) {
		const w = node.widgets.get(detail.widget_name);
		if(w) {
			const changed = w.getValue() !== detail.value;
			w.setValue(detail.value);
			for (const listener of nodeFeedbackListeners) {
				listener({ node, widget: w, detail, changed });
			}
		}
	}
}

comfy.backend.on("impact-node-feedback", nodeFeedbackHandler);


function setMuteState(detail) {
	let node = comfy.graph.node(String(detail.node_id));
	if(node) {
		if(detail.is_active)
			node.setMode('always');
		else
			node.setMode('never');
	}
}

comfy.backend.on("impact-node-mute-state", setMuteState);


async function bridgeContinue(detail) {
	let node = comfy.graph.node(String(detail.node_id));
	if(node) {
		const mutes = new Set(detail.mutes);
		const actives = new Set(detail.actives);
		const bypasses = new Set(detail.bypasses);

		for(const this_node of comfy.graph.nodes()) {
			if(mutes.has(this_node.id)) {
				this_node.setMode('never');
			}
			else if(actives.has(this_node.id)) {
				this_node.setMode('always');
			}
			else if(bypasses.has(this_node.id)) {
				this_node.setMode('bypass');
			}
		}

		await comfy.queue.run();
	}
}

comfy.backend.on("impact-bridge-continue", bridgeContinue);


function addQueue(detail) {
	void comfy.queue.run();
}

comfy.backend.on("impact-add-queue", addQueue);


function downstreamNonRerouteNodes(controlNode) {
	const result = [];
	const pending = [];
	const seen = new Set();
	for (const link of controlNode?.outputs.at(0)?.links() ?? []) {
		pending.push(link.targetNodeId);
	}

	while (pending.length && seen.size < 4096) {
		const nodeId = String(pending.shift());
		if (seen.has(nodeId)) continue;
		seen.add(nodeId);
		const node = comfy.graph.node(nodeId);
		if (!node) continue;
		if (node.type === 'Reroute' || node.comfyClass === 'Reroute') {
			for (const output of node.outputs.all()) {
				for (const link of output.links()) pending.push(link.targetNodeId);
			}
			continue;
		}
		result.push(node);
	}
	return result;
}

/**
 * Apply the closed workflow-action vocabulary emitted by converted nodes.
 * The sandbox cannot name a command or execute script: each action is reduced
 * to one bounded operation implemented here in the trusted extension code.
 */
export async function applySecureWorkflowActions(actions) {
	if (!Array.isArray(actions)) return;
	if (actions.length > 256) {
		console.warn('[Impact Pack] ignored oversized secure workflow action list');
		return;
	}

	let queueRequested = false;
	for (const action of actions) {
		if (!action || typeof action !== 'object') continue;
		if (action.kind === 'queue') {
			queueRequested = true;
		}
		else if (action.kind === 'stop-iteration') {
			comfy.queue.disableAutoQueue();
		}
		else if (action.kind === 'widget') {
			if (typeof action.widget_name !== 'string' || action.widget_name.length > 256) continue;
			nodeFeedbackHandler({
				node_id: String(action.node_id),
				widget_name: action.widget_name,
				type: action.value_type,
				value: action.value
			});
		}
		else if (action.kind === 'mute') {
			setMuteState({
				node_id: String(action.node_id),
				is_active: action.is_active === true
			});
		}
		else if (action.kind === 'bridge') {
			if (action.behavior !== 'Mute' && action.behavior !== 'Bypass') continue;
			const control = comfy.graph.node(String(action.node_id));
			const desired = action.mode === true
				? 'always'
				: (action.behavior === 'Mute' ? 'never' : 'bypass');
			let changed = false;
			for (const node of downstreamNonRerouteNodes(control)) {
				if (node.getMode() !== desired) {
					node.setMode(desired);
					changed = true;
				}
			}
			queueRequested ||= changed;
		}
	}
	if (queueRequested) await comfy.queue.run();
}


// Handles hold no arbitrary properties, so the per-node preview surface lives
// here, keyed by node id.
const previews = new Map();

function refreshPreview(detail) {
	let node_id = detail.node_id;
	let item = detail.item;
	let img = new Image();
	img.src = comfy.backend.url(`/view?filename=${item.filename}&subfolder=${item.subfolder}&type=${item.type}&no-cache=${Date.now()}`);
	let node = comfy.graph.node(String(node_id));
	if(node) {
		let preview = previews.get(node.id);
		if(!preview || !node.widgets.get("impact-preview")) {
			preview = { image: null };
			preview.surface = node.widgets.canvas({
				name: "impact-preview",
				height: 200,
				draw: (ctx, [w, h]) => {
					if(preview.image?.complete)
						ctx.drawImage(preview.image, 0, 0, w, h);
				}
			});
			previews.set(node.id, preview);
		}
		preview.image = img;
		img.onload = () => preview.surface.redraw();
	}
}

comfy.backend.on("impact-preview", refreshPreview);


// ============================================================================
// MaskRectArea Shared Utilities
// ============================================================================

/**
 * Reads a numeric value from a connected link by inspecting the origin node widget.
 * More reliable than getInputData() in ComfyUI's frontend execution model.
 *
 * @param {NodeHandle} node - Published node handle
 * @param {string} inputName - Name of the input to read
 * @returns {number|null} The numeric value or null if not available
 */
export function readLinkedNumber(node, inputName) {
    try {
        if (!node) {
            return null;
        }
        const inp = node.inputs.byName(inputName);
        const src = inp?.source();
        if (!src) {
            return null;
        }

        const originNode = comfy.graph.node(src.nodeId);
        if (!originNode || originNode.widgets.length === 0) {
            return null;
        }

        const w = originNode.widgets.get("value") ?? originNode.widgets.at(0);
        const v = w ? w.getValue() : null;

        return (typeof v === "number") ? v : null;
    } catch (e) {
        return null;
    }
}

export function setDefaultProperties(node, defaults) {
    for (const [name, value] of Object.entries(defaults)) {
        if (node.getProperty(name) === undefined) {
            node.setProperty(name, value);
        }
    }
}

export function watchLinkedNumbers(node, inputNames, onChange) {
    const widgets = new Set();
    const unsubscribe = [];

    for (const inputName of inputNames) {
        const source = node.inputs.byName(inputName)?.source();
        const origin = source ? comfy.graph.node(source.nodeId) : undefined;
        const widget = origin?.widgets.get("value") ?? origin?.widgets.at(0);
        if (widget && !widgets.has(widget)) {
            widgets.add(widget);
            unsubscribe.push(widget.on('change', onChange));
        }
    }

    return () => {
        for (const stop of unsubscribe) {
            stop();
        }
    };
}

/**
 * Generates a color based on percentage using HSL color space.
 *
 * @param {number} percent - Value between 0 and 1
 * @param {string} alpha - Hex alpha value (e.g., "ff", "80")
 * @returns {string} Hex color string with alpha (e.g., "#ff8040ff")
 */
export function getDrawColor(percent, alpha) {
    let h = 360 * percent;
    let s = 50;
    let l = 50;
    l /= 100;
    const a = s * Math.min(l, 1 - l) / 100;
    const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}${alpha}`;
}

/**
 * Declares how the node may be sized so the preview canvas fits.
 *
 * @param {NodeHandle} node - Published node handle
 * @param {[number, number]} size - Unused; kept so call sites are unchanged
 * @param {number} minHeight - Minimum canvas height (REQUIRED)
 * @param {number} minWidth - Minimum canvas width (REQUIRED)
 * @returns {void}
 */
export function computeCanvasSize(node, size, minHeight, minWidth) {
    // Validate required parameters
    if (typeof minHeight !== 'number' || typeof minWidth !== 'number') {
        console.warn('[computeCanvasSize] minHeight and minWidth are required parameters');
        return;
    }

    node.setSizeConstraints({ minWidth, minHeight, autoHeight: true });
}
