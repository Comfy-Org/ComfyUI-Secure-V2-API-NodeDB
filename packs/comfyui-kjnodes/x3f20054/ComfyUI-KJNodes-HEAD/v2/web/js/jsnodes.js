import { comfy } from '/comfy/api/v2.js';

// ─── Dynamic input slot management for *Multi nodes ───
// Adds an "Update inputs" button that rebuilds prefix_1..prefix_N slots to match the count widget.
//
// The rebuild also has to run for an API-format load, which carries widget values but no
// slots. The old code detected that by chaining the count widget's callback and testing
// whether litegraph had passed a canvas — present for an interactive scrub, absent for a
// programmatic write. widget.on("change") carries no such tell, and it is the wrong
// question anyway: what is being asked is "has a graph just finished loading", which
// onWorkflowLoaded answers directly and never fires while the user drags a number.
const dynamicRebuilds = new Map();

comfy.onWorkflowLoaded(() => {
    for (const rebuild of dynamicRebuilds.values()) rebuild();
});

function setupDynamicInputs(node, { type, prefix, countWidget = "inputcount", slotOptions } = {}) {
    const rebuild = () => {
        const countW = node.widgets.get(countWidget);
        if (!countW) return;
        const target = countW.getValue();
        const current = node.inputs.all().filter(i => i.name?.startsWith(prefix)).length;
        if (target === current) return;
        if (target < current) {
            for (let i = 0; i < current - target; i++) node.inputs.remove({ index: node.inputs.length - 1 });
        } else {
            for (let i = current + 1; i <= target; i++) node.inputs.add(`${prefix}${i}`, type, slotOptions);
        }
    };
    node.widgets.add({ type: "button", name: "Update inputs", value: null }).on("activate", rebuild);
    dynamicRebuilds.set(node.id, rebuild);
    return rebuild;
}

// Handles hold no arbitrary properties, so this per-node value lives here.
const inputsOffset = new Map();

comfy.defs.extend("ConditioningMultiCombine", (b) => {
	b.onCreated((node) => {
		inputsOffset.set(node.id, node.type.includes("selective") ? 1 : 0);
		setupDynamicInputs(node, { type: "CONDITIONING", prefix: "conditioning_" });
	});
	b.onRemoved((node) => { inputsOffset.delete(node.id); dynamicRebuilds.delete(node.id); });
});

comfy.defs.extend(["ImageBatchMulti", "ImageAddMulti", "CrossFadeImagesMulti", "TransitionImagesMulti"], (b) => {
	b.onCreated((node) => {
		setupDynamicInputs(node, { type: "IMAGE", prefix: "image_", slotOptions: { shape: 'optional' } });
	});
	b.onRemoved((node) => dynamicRebuilds.delete(node.id));
});

// Dynamic slots accept MASK too; name-prefix counting handles the mixed types.
comfy.defs.extend("ImageConcatMulti", (b) => {
	b.onCreated((node) => {
		setupDynamicInputs(node, { type: "IMAGE,MASK", prefix: "image_", slotOptions: { shape: 'optional' } });
	});
	b.onRemoved((node) => dynamicRebuilds.delete(node.id));
});

comfy.defs.extend("MaskBatchMulti", (b) => {
	b.onCreated((node) => {
		setupDynamicInputs(node, { type: "MASK", prefix: "mask_" });
	});
	b.onRemoved((node) => dynamicRebuilds.delete(node.id));
});

comfy.defs.extend(["FluxBlockLoraSelect", "HunyuanVideoBlockLoraSelect", "Wan21BlockLoraSelect", "LTX2BlockLoraSelect"], (b) => {
	b.onCreated((node) => {
		node.widgets.add({ type: "button", name: "Set all", value: null }).on("activate", () => {
			const userInput = prompt("Enter the values to set for widgets (e.g., s0,1,2-7=2.0, d0,1,2-7=2.0, or 1.0):", "");
			if (userInput) {
				const regex = /([sd])?(\d+(?:,\d+|-?\d+)*?)?=(\d+(\.\d+)?)/;
				const match = userInput.match(regex);
				if (match) {
					const type = match[1];
					const indicesPart = match[2];
					const value = parseFloat(match[3]);

					let targetWidgets = [];
					if (type === 's') {
						targetWidgets = node.widgets.all().filter(widget => widget.name.includes("single"));
					} else if (type === 'd') {
						targetWidgets = node.widgets.all().filter(widget => widget.name.includes("double"));
					} else {
						targetWidgets = node.widgets.all(); // No type specified, all widgets
					}

					if (indicesPart) {
						const indices = indicesPart.split(',').flatMap(part => {
							if (part.includes('-')) {
								const [start, end] = part.split('-').map(Number);
								return Array.from({ length: end - start + 1 }, (_, i) => start + i);
							}
							return Number(part);
						});

						for (const index of indices) {
							if (index < targetWidgets.length) {
								targetWidgets[index].setValue(value);
							}
						}
					} else {
						// No indices provided, set value for all target widgets
						for (const widget of targetWidgets) {
							widget.setValue(value);
						}
					}
				} else if (!isNaN(parseFloat(userInput))) {
					// Single value provided, set it for all widgets
					const value = parseFloat(userInput);
					for (const widget of node.widgets.all()) {
						widget.setValue(value);
					}
				} else {
					alert("Invalid input format. Please use the format s0,1,2-7=2.0, d0,1,2-7=2.0, or 1.0");
				}
			} else {
				alert("Invalid input. Please enter a value.");
			}
		});
	});
});

comfy.defs.extend("GetMaskSizeAndCount", (b) => {
	b.onConnectionsChanged((node, event) => {
		if (event.side !== "input" || !event.connected) return;
		node.outputs.at(1).modify({ label: "width" });
		node.outputs.at(2).modify({ label: "height" });
		node.outputs.at(3).modify({ label: "count" });
	});
	b.onExecuted((node, result) => {
		let values = result.text.toString().split('x').map(Number);
		node.outputs.at(1).modify({ label: values[1] + " width" });
		node.outputs.at(2).modify({ label: values[2] + " height" });
		node.outputs.at(3).modify({ label: values[0] + " count" });
	});
});

comfy.defs.extend("GetImageSizeAndCount", (b) => {
	b.onConnectionsChanged((node, event) => {
		console.log(node)
		if (event.side !== "input" || !event.connected) return;
		node.outputs.at(1).modify({ label: "width" });
		node.outputs.at(2).modify({ label: "height" });
		node.outputs.at(3).modify({ label: "count" });
	});
	b.onExecuted((node, result) => {
		console.log(node)
		let values = result.text.toString().split('x').map(Number);
		console.log(values)
		node.outputs.at(1).modify({ label: values[1] + " width" });
		node.outputs.at(2).modify({ label: values[2] + " height" });
		node.outputs.at(3).modify({ label: values[0] + " count" });
	});
});

comfy.defs.extend("GetLatentSizeAndCount", (b) => {
	b.onConnectionsChanged((node, event) => {
		console.log(node)
		if (event.side !== "input" || !event.connected) return;
		node.outputs.at(1).modify({ label: "batch_size" });
		node.outputs.at(2).modify({ label: "channels" });
		node.outputs.at(3).modify({ label: "frames" });
		node.outputs.at(4).modify({ label: "height" });
		node.outputs.at(5).modify({ label: "width" });
	});
	b.onExecuted((node, result) => {
		console.log(node)
		let values = result.text.toString().split('x').map(Number);
		console.log(values)
		node.outputs.at(1).modify({ label: values[0] + " batch" });
		node.outputs.at(2).modify({ label: values[1] + " channels" });
		node.outputs.at(3).modify({ label: values[2] + " frames" });
		node.outputs.at(4).modify({ label: values[3] + " height" });
		node.outputs.at(5).modify({ label: values[4] + " width" });
	});
});

comfy.defs.extend("PreviewAnimation", (b) => {
	b.onConnectionsChanged((node, event) => {
		if (event.side !== "input" || !event.connected) return;
		node.setTitle("Preview Animation");
	});
	b.onExecuted((node, result) => {
		let values = result.text.toString();
		node.setTitle("Preview Animation " + values);
	});
});

comfy.defs.extend("VRAM_Debug", (b) => {
	b.onConnectionsChanged((node, event) => {
		if (event.side !== "input" || !event.connected) return;
		node.outputs.at(3).modify({ label: "freemem_before" });
		node.outputs.at(4).modify({ label: "freemem_after" });
	});
	b.onExecuted((node, result) => {
		let values = result.text.toString().split('x');
		node.outputs.at(3).modify({ label: values[0] + "   freemem_before" });
		node.outputs.at(4).modify({ label: values[1] + "      freemem_after" });
	});
});

comfy.defs.extend("JoinStringMulti", (b) => {
	b.onCreated((node) => {
		setupDynamicInputs(node, { type: "STRING", prefix: "string_", slotOptions: { shape: 'optional' } });
	});
});

comfy.defs.extend("SoundReactive", (b) => {
	b.onCreated((node) => {
		let audioContext;
		let microphoneStream;
		let animationFrameId;
		let analyser;
		let dataArray;
		let startRangeHz;
    	let endRangeHz;
		let smoothingFactor = 0.5;
		let smoothedSoundLevel = 0;
	
		// Function to update the widget value in real-time
		const updateWidgetValueInRealTime = () => {
			// Ensure analyser and dataArray are defined before using them
			if (analyser && dataArray) {
				analyser.getByteFrequencyData(dataArray);

				const startRangeHzWidget = node.widgets.get("start_range_hz");
				if (startRangeHzWidget) startRangeHz = startRangeHzWidget.getValue();
				const endRangeHzWidget = node.widgets.get("end_range_hz");
				if (endRangeHzWidget) endRangeHz = endRangeHzWidget.getValue();
				const smoothingFactorWidget = node.widgets.get("smoothing_factor");
				if (smoothingFactorWidget) smoothingFactor = smoothingFactorWidget.getValue();

				// Calculate frequency bin width (frequency resolution)
				const frequencyBinWidth = audioContext.sampleRate / analyser.fftSize;	
				// Convert the widget values from Hz to indices
				const startRangeIndex = Math.floor(startRangeHz / frequencyBinWidth);
				const endRangeIndex = Math.floor(endRangeHz / frequencyBinWidth);

				// Function to calculate the average value for a frequency range
				const calculateAverage = (start, end) => {
					const sum = dataArray.slice(start, end).reduce((acc, val) => acc + val, 0);
					const average = sum / (end - start);

					// Apply exponential moving average smoothing
    				smoothedSoundLevel = (average * (1 - smoothingFactor)) + (smoothedSoundLevel * smoothingFactor);
					return smoothedSoundLevel;
				};
				// Calculate the average levels for each frequency range
				const soundLevel = calculateAverage(startRangeIndex, endRangeIndex);
				
				// Update the widget values

				const lowLevelWidget = node.widgets.get("sound_level");
				if (lowLevelWidget) lowLevelWidget.setValue(soundLevel);

				animationFrameId = requestAnimationFrame(updateWidgetValueInRealTime);
			}
		};
	
		// Function to start capturing audio from the microphone
		const startMicrophoneCapture = () => {
			// Only create the audio context and analyser once
			if (!audioContext) {
				audioContext = new (window.AudioContext || window.webkitAudioContext)();
				// Access the sample rate of the audio context
				console.log(`Sample rate: ${audioContext.sampleRate}Hz`);
				analyser = audioContext.createAnalyser();
				analyser.fftSize = 2048;
				dataArray = new Uint8Array(analyser.frequencyBinCount);
				// Get the range values from widgets (assumed to be in Hz)
				const lowRangeWidget = node.widgets.get("low_range_hz");
				if (lowRangeWidget) startRangeHz = lowRangeWidget.getValue();
	
				const midRangeWidget = node.widgets.get("mid_range_hz");
				if (midRangeWidget) endRangeHz = midRangeWidget.getValue();
			}
			
			navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
				microphoneStream = stream;
				const microphone = audioContext.createMediaStreamSource(stream);
				microphone.connect(analyser);
				updateWidgetValueInRealTime();
			}).catch(error => {
				console.error('Access to microphone was denied or an error occurred:', error);
			});
		};
	
		// Function to stop capturing audio from the microphone
		const stopMicrophoneCapture = () => {
			if (animationFrameId) {
				cancelAnimationFrame(animationFrameId);
			}
			if (microphoneStream) {
				microphoneStream.getTracks().forEach(track => track.stop());
			}
			if (audioContext) {
				audioContext.close();
				// Reset audioContext to ensure it can be created again when starting
				audioContext = null;
			}
		};
	
		// Add start button
		node.widgets.add({ type: "button", name: "Start mic capture", value: null }).on("activate", startMicrophoneCapture);
	
		// Add stop button
		node.widgets.add({ type: "button", name: "Stop mic capture", value: null }).on("activate", stopMicrophoneCapture);
	});
});

// ─── filename_prefix token substitution ───
// The pack's own save nodes expand %Node.widget% and %date:...% in filename_prefix,
// exactly as core does for its own save nodes. Core's list of node types is hardcoded
// and does not include these, so the substitution is genuinely the pack's to do.
//
// widget.serializeValue is the retired half: on("beforeSerialize") is its published
// replacement, and it is scoped to context === "prompt" because that is the only
// destination serializeValue ever reached. The saved workflow keeps what the user
// typed, which is what makes the token survive a reload — so the wire format is
// unchanged in both directions.
//
// LIMITATION: applyTextReplacements is not published, so the grammar below is this
// pack's copy of core's. It matches core today (%Node name for S&R.widget%, falling
// back to node title, plus %date:fmt% over yy/yyyy/M/d/h/m/s); if core extends the
// grammar this copy will not follow.
const dateParts = {
	d: (d) => d.getDate(),
	M: (d) => d.getMonth() + 1,
	h: (d) => d.getHours(),
	m: (d) => d.getMinutes(),
	s: (d) => d.getSeconds(),
};
const dateFormat = Object.keys(dateParts).map((k) => k + k + "?").join("|") + "|yyy?y?";

function formatDate(text, date) {
	return text.replace(new RegExp(dateFormat, "g"), (token) => {
		if (token === "yy") return (date.getFullYear() + "").substring(2);
		if (token === "yyyy") return date.getFullYear().toString();
		if (token[0] in dateParts) return (dateParts[token[0]](date) + "").padStart(token.length, "0");
		return token;
	});
}

// The visible graph plus every subgraph definition, so a referenced node nested in a
// subgraph is still found — which is what core's collectAllNodes walks.
function allNodes() {
	return [...comfy.graph.nodes(), ...comfy.graph.subgraphs().flatMap((sg) => sg.nodes())];
}

function applyTextReplacements(value) {
	return String(value ?? "").replace(/%([^%]+)%/g, (match, text) => {
		const split = text.split(".");
		if (split.length !== 2) {
			if (split[0].startsWith("date:")) return formatDate(split[0].substring(5), new Date());
			if (text !== "width" && text !== "height") console.warn("Invalid replacement pattern", text);
			return match;
		}

		const nodes = allNodes();
		let matched = nodes.filter((n) => n.getProperty("Node name for S&R") === split[0]);
		if (!matched.length) matched = nodes.filter((n) => n.getTitle() === split[0]);
		if (!matched.length) {
			console.warn("Unable to find node", split[0]);
			return match;
		}
		if (matched.length > 1) console.warn("Multiple nodes matched", split[0], "using first match");

		const widget = matched[0].widgets.get(split[1]);
		if (!widget) {
			console.warn("Unable to find widget", split[1], "on node", split[0]);
			return match;
		}
		return ((widget.getValue() ?? "") + "").replaceAll(/[/?<>\\:*|"\x00-\x1F\x7F]/g, "_");
	});
}

comfy.defs.extend([
	"SaveImageKJ",
	"SaveImageWithAlpha",
	"SaveStringKJ",
	"DecodeAndSaveVideo",
	"ModelSaveKJ",
	"LoraExtractKJ",
], (b) => {
	b.onCreated((node) => {
		node.widgets.get("filename_prefix")?.on("beforeSerialize", (event) => {
			if (event.context !== "prompt") return;
			event.setSerializedValue(applyTextReplacements(event.value));
		});
	});
});
