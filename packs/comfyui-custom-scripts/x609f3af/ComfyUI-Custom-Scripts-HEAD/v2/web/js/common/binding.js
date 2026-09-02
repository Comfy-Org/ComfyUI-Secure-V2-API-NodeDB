// @ts-check
import { comfy } from '/comfy/api/v2.js';

const PathHelper = {
	get(obj, path) {
		if (typeof path !== "string") {
			// Hardcoded value
			return path;
		}

		if (path[0] === '"' && path[path.length - 1] === '"') {
			// Hardcoded string
			return JSON.parse(path);
		}

		// Evaluate the path
		path = path.split(".").filter(Boolean);
		for (const p of path) {
			const k = isNaN(+p) ? p : +p;
			obj = obj[k];
		}

		return obj;
	},
	set(obj, path, value) {
		// https://stackoverflow.com/a/54733755
		if (Object(obj) !== obj) return obj; // When obj is not an object
		// If not yet an array, get the keys from the string-path
		if (!Array.isArray(path)) path = path.toString().match(/[^.[\]]+/g) || [];
		path.slice(0, -1).reduce(
			(
				a,
				c,
				i // Iterate all of them except the last one
			) =>
				Object(a[c]) === a[c] // Does the key exist and is its value an object?
					? // Yes: then follow that path
					  a[c]
					: // No: create the key. Is the next key a potential array-index?
					  (a[c] =
							Math.abs(path[i + 1]) >> 0 === +path[i + 1]
								? [] // Yes: assign a new array object
								: {}), // No: assign a new plain object
			obj
		)[path[path.length - 1]] = value; // Finally assign the value to the last key
		return obj; // Return the top-level object to allow chaining
	},
};

// LIMITATION: `$this` and `$source` used to be the live widget objects, so a
// binding could name any property on one and PathHelper would reach it. A widget
// handle carries a fixed surface, so the vocabulary is bound to it explicitly
// here: `.name`, `.value`, `.disabled` and `.options.values` — every path this
// pack's own node definitions declare. A binding naming anything else now reads
// undefined and writes nowhere, where it used to reach the raw widget object.
const bindable = (widget) => ({
	name: widget.name,
	get value() {
		return widget.getValue();
	},
	set value(v) {
		widget.setValue(v);
	},
	get disabled() {
		return widget.isDisabled();
	},
	set disabled(v) {
		widget.setDisabled(v);
	},
	options: {
		get values() {
			return widget.getOptions()?.values;
		},
		set values(v) {
			widget.setOption("values", v);
		},
	},
});

/***
	@typedef { {
		left: string;
		op: "eq" | "ne",
		right: string
	} } IfCondition

	@typedef { {
		type: "if",
		condition: Array<IfCondition>,
		true?: Array<BindingCallback>,
		false?: Array<BindingCallback>
	} } IfCallback

	@typedef { {
		type: "fetch",
		url: string,
		then: Array<BindingCallback>
	} } FetchCallback

	@typedef { {
		type: "set",
		target: string,
		value: string
	} } SetCallback

	@typedef { {
		type: "validate-combo",
	} } ValidateComboCallback

	@typedef { IfCallback | FetchCallback | SetCallback | ValidateComboCallback } BindingCallback

	@typedef { {
		source: string,
		callback: Array<BindingCallback>
	} } Binding
***/

/**
 * @param {IfCondition} condition
 */
function evaluateCondition(condition, state) {
	const left = PathHelper.get(state, condition.left);
	const right = PathHelper.get(state, condition.right);

	let r;
	if (condition.op === "eq") {
		r = left === right;
	} else {
		r = left !== right;
	}

	return r;
}

/**
 * @type { Record<BindingCallback["type"], (cb: any, state: Record<string, any>) => Promise<void>> }
 */
const callbacks = {
	/**
	 * @param {IfCallback} cb
	 */
	async if(cb, state) {
		// For now only support ANDs
		let success = true;
		for (const condition of cb.condition) {
			const r = evaluateCondition(condition, state);
			if (!r) {
				success = false;
				break;
			}
		}

		for (const m of cb[success + ""] ?? []) {
			await invokeCallback(m, state);
		}
	},
	/**
	 * @param {FetchCallback} cb
	 */
	async fetch(cb, state) {
		const url = cb.url.replace(/\{([^\}]+)\}/g, (m, v) => {
			return PathHelper.get(state, v);
		});
		const res = await (await comfy.backend.fetch(url)).json();
		state["$result"] = res;
		for (const m of cb.then) {
			await invokeCallback(m, state);
		}
	},
	/**
	 * @param {SetCallback} cb
	 */
	async set(cb, state) {
		const value = PathHelper.get(state, cb.value);
		PathHelper.set(state, cb.target, value);
	},
	async "validate-combo"(cb, state) {
		const w = state["$this"];
		const valid = w.options.values.includes(w.value);
		if (!valid) {
			w.value = w.options.values[0];
		}
	},
};

async function invokeCallback(callback, state) {
	if (callback.type in callbacks) {
		// @ts-ignore
		await callbacks[callback.type](callback, state);
	} else {
		console.warn(
			"%c[🐍 pysssss]",
			"color: limegreen",
			`[binding ${state.$node.comfyClass}.${state.$this.name}]`,
			"unsupported binding callback type:",
			callback.type
		);
	}
}

const hasBinding = (def) => def.inputs.some((i) => i.options?.["pysssss.binding"]);

comfy.defs.extend(hasBinding, (b) => {
	const inputs = Object.fromEntries(b.def.inputs.map((i) => [i.name, i.options]));

	b.onCreated((node) => {
		for (const widget of node.widgets.all()) {
			const bindings = inputs[widget.name]?.["pysssss.binding"];
			if (!bindings) continue;

			for (const binding of bindings) {
				const source = node.widgets.get(binding.source);
				if (!source) {
					console.warn(
						"%c[🐍 pysssss]",
						"color: limegreen",
						`[binding ${node.comfyClass}.${widget.name}]`,
						"unable to find source binding widget:",
						binding.source,
						binding
					);
					continue;
				}

				let lastValue;
				async function valueChanged() {
					const state = {
						$this: bindable(widget),
						$source: bindable(source),
						$node: node,
					};

					for (const callback of binding.callback) {
						await invokeCallback(callback, state);
					}
				}

				source.on("change", (v) => {
					if (v !== lastValue) {
						lastValue = v;
						valueChanged();
					}
				});

				lastValue = source.getValue();
				valueChanged();
			}
		}
	});
});
