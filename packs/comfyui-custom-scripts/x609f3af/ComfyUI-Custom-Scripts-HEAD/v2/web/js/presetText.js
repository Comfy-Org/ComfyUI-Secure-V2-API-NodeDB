import { comfy } from '/comfy/api/v2.js';

// Allows you to manage preset tags for e.g. common negative prompt
// Also performs replacements on any text field e.g. allowing you to use preset text in CLIP Text encode fields

let replaceRegex;
const PRESET_FILE = "pysssss.PresetText/presets.json";

const getPresets = async () => {
	let items;
	try {
		items = JSON.parse(await comfy.storage.get(PRESET_FILE));
	} catch (error) {}
	if (!items || !items.length) {
		items = [{ name: "default negative", value: "worst quality" }];
	}
	return items;
};

let presets = await getPresets();

comfy.settings.declare({
	id: "pysssss.PresetText.ReplacementRegex",
	name: "🐍 Preset Text Replacement Regex",
	type: "text",
	defaultValue: "(?:^|[^\\w])(?<replace>@(?<id>[\\w-]+))",
	tooltip:
		"The regex should return two named capture groups: id (the name of the preset text to use), replace (the matched text to replace)",
	// COSMETIC: the field was rendered in a monospace face via addSetting's
	// `attrs.style`. SettingAttrs carries min/max/step only, so the regex is now
	// shown in whatever face the settings panel uses.
	onChange(value) {
		if (!value) {
			replaceRegex = null;
			return;
		}
		try {
			replaceRegex = new RegExp(value, "g");
		} catch (error) {
			alert("Error creating regex for preset text replacement, no replacements will be performed.");
			replaceRegex = null;
		}
	},
});

comfy.defs.define({
	type: "PresetText|pysssss",
	title: "Preset Text 🐍",
	category: "utils",
	outputs: [{ name: "text", type: "STRING" }],
	widgets: [
		{ type: "combo", name: "value", value: presets[0].name, options: { values: presets.map((p) => p.name) } },
		{ type: "button", name: "Manage", value: "Manage" },
	],
	execution: "frontend",
	// Was applyToGraph, which walked its own output links and wrote the preset
	// text over each downstream widget in the middle of serialization. A resolver
	// answers for its own output instead, purely, and never touches the graph.
	resolve: (view) => {
		const value = view.self.widgetValue("value");
		const preset = presets.find((p) => p.name === value);
		if (!preset) {
			const msg = `Preset text '${value}' not found. Please fix this and queue again.`;
			throw new Error(msg);
		}
		return { text: { literal: preset.value } };
	},
	onCreated: (node) => {
		node.setSerializeWidgets(true);

		const widget = node.widgets.get("value");
		// REFUSED, not a pending gap: patching the renderer and swapping a core
		// global mid-draw. A missing preset used to be shown by wrapping
		// LGraphCanvas.prototype.drawNodeWidgets and assigning
		// LiteGraph.WIDGET_BGCOLOR = "red" around the call — the renderer is ours to
		// replace, and that global is read by every node drawn during the call, not
		// only this one. The mark itself is a node decoration, which is a badge.
		let clearBadge;
		const markMissing = () => {
			clearBadge?.();
			clearBadge = presets.some((p) => p.name === widget.getValue())
				? undefined
				: node.addBadge({ text: "missing preset", bgColor: "red" });
		};
		widget.on("change", markMissing);
		markMissing();

		node.widgets.get("Manage").on("activate", () => {
			const container = document.createElement("div");
			Object.assign(container.style, {
				display: "grid",
				gridTemplateColumns: "1fr 1fr",
				gap: "10px",
			});

			const addNew = document.createElement("button");
			addNew.textContent = "Add New";
			addNew.classList.add("pysssss-presettext-addnew");
			Object.assign(addNew.style, {
				fontSize: "13px",
				gridColumn: "1 / 3",
				color: "dodgerblue",
				width: "auto",
				textAlign: "center",
			});
			addNew.onclick = () => {
				addRow({ name: "", value: "" });
			};
			container.append(addNew);

			function addRow(p) {
				const name = document.createElement("input");
				const nameLbl = document.createElement("label");
				name.value = p.name;
				nameLbl.textContent = "Name:";
				nameLbl.append(name);

				const value = document.createElement("input");
				const valueLbl = document.createElement("label");
				value.value = p.value;
				valueLbl.textContent = "Value:";
				valueLbl.append(value);

				addNew.before(nameLbl, valueLbl);
			}
			for (const p of presets) {
				addRow(p);
			}

			const help = document.createElement("span");
			help.textContent = "To remove a preset set the name or value to blank";
			help.style.gridColumn = "1 / 3";
			container.append(help);

			let dialog;
			const saveButton = document.createElement("button");
			saveButton.textContent = "SAVE";
			saveButton.onclick = async function () {
				const inputs = container.querySelectorAll("input");
				const p = [];
				for (let i = 0; i < inputs.length; i += 2) {
					const n = inputs[i];
					const v = inputs[i + 1];
					if (!n.value.trim() || !v.value.trim()) {
						continue;
					}
					p.push({ name: n.value, value: v.value });
				}

				const values = p.map((p) => p.name);
				widget.setOption("values", values);
				if (!values.includes(widget.getValue())) {
					widget.setValue(values[0]);
				}

				try {
					await comfy.storage.set(PRESET_FILE, JSON.stringify(p));
				} catch (error) {
					comfy.commands.notify({
						severity: "error",
						summary: "Preset Text",
						detail: "The presets could not be saved.",
					});
					return;
				}
				presets = p;
				markMissing();

				dialog.close();
			};

			const closeButton = document.createElement("button");
			closeButton.textContent = "CANCEL";
			closeButton.onclick = () => dialog.close();

			dialog = comfy.ui.showDialog({
				key: "pysssss.PresetText.Manage",
				title: "Preset Text 🐍",
				render(host) {
					host.append(container, saveButton, closeButton);
				},
			});
		});
	},
});

comfy.defs.extend(/./, (b) => {
	b.onCreated((node) => {
		// Locate dynamic prompt text widgets
		const widgets = node.widgets.all().filter((n) => n.widgetType === "customtext" || n.widgetType === "text");
		for (const widget of widgets) {
			// Only the queued prompt is expanded, which is what the old
			// serializeValue reached and the reason the user keeps seeing `@name`
			// in the field and in the file they save.
			widget.on("beforeSerialize", (event) => {
				if (event.context !== "prompt") return;
				let prompt = event.value;
				if (replaceRegex && typeof prompt.replace !== 'undefined') {
					prompt = prompt.replace(replaceRegex, (match, p1, p2, index, text, groups) => {
						if (!groups.replace || !groups.id) return match; // No match, bad regex?

						const preset = presets.find((p) => p.name.replaceAll(/\s/g, "-") === groups.id);
						if (!preset) return match; // Invalid name

						const pos = match.indexOf(groups.replace);
						return match.substring(0, pos) + preset.value;
					});
				}
				event.setSerializedValue(prompt);
			});
		}
	});
});
