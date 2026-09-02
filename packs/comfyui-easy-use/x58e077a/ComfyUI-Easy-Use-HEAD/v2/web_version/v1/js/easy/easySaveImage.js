import { comfy } from '/comfy/api/v2.js';

const extraNodes = ["easy imageSave", "easy fullkSampler", "easy kSampler", "easy kSamplerTiled","easy kSamplerInpainting", "easy kSamplerDownscaleUnet", "easy kSamplerSDTurbo","easy detailerFix"]

// LIMITATION: the %node.widget% / %date:…% expansion is the pack's own copy.
// It used to import core's applyTextReplacements from scripts/utils.js, which
// this migration retires, and the token syntax is shared with the backend's
// filename handling rather than owned by either side. Nothing published expands
// it, so the pack carries a second implementation and will drift from core's if
// the syntax changes. Everything it needs to READ is published — properties,
// titles, widget values and subgraph contents — so this is duplication, not a
// blocker.
const dateParts = {
	d: (d) => d.getDate(),
	M: (d) => d.getMonth() + 1,
	h: (d) => d.getHours(),
	m: (d) => d.getMinutes(),
	s: (d) => d.getSeconds(),
};
const dateToken = new RegExp(Object.keys(dateParts).map((k) => k + k + "?").join("|") + "|yyy?y?", "g");

function formatDate(text, date) {
	return text.replace(dateToken, (token) => {
		if (token === "yy") return (date.getFullYear() + "").substring(2);
		if (token === "yyyy") return date.getFullYear().toString();
		if (token[0] in dateParts) return (dateParts[token[0]](date) + "").padStart(token.length, "0");
		return token;
	});
}

function applyTextReplacements(value) {
	// Core's collectAllNodes descends into subgraphs, so a token may name a node
	// inside one; comfy.graph.nodes() is the graph on screen only.
	const allNodes = [comfy.graph, ...comfy.graph.subgraphs()].flatMap((g) => g.nodes());

	return value.replace(/%([^%]+)%/g, function (match, text) {
		const split = text.split(".");
		if (split.length !== 2) {
			if (split[0].startsWith("date:")) return formatDate(split[0].substring(5), new Date());
			// Dont warn on standard replacements
			if (text !== "width" && text !== "height") console.warn("Invalid replacement pattern", text);
			return match;
		}
		// Find node with matching S&R property name, else one with that title
		let nodes = allNodes.filter((n) => n.getProperty("Node name for S&R") === split[0]);
		if (!nodes.length) nodes = allNodes.filter((n) => n.getTitle() === split[0]);
		if (!nodes.length) { console.warn("Unable to find node", split[0]); return match; }
		if (nodes.length > 1) console.warn("Multiple nodes matched", split[0], "using first match");

		const widget = nodes[0].widgets.get(split[1]);
		if (!widget) { console.warn("Unable to find widget", split[1], "on node", split[0]); return match; }
		return ((widget.getValue() ?? "") + "").replaceAll(/[/?<>\\:*|"\x00-\x1F\x7F]/g, "_");
	});
}

// When the SaveImage node is created we want to override the serialization of the output name widget to run our S&R
comfy.defs.extend(extraNodes, (b) => {
	b.onCreated((node) => {
		const widget = node.widgets.all().find((w) => w.name === "filename_prefix" || w.name === 'save_prefix');
		widget.on('beforeSerialize', (e) => {
			// Only the queued payload, which is all the old serializeValue reached;
			// the saved workflow keeps the un-expanded template the user typed.
			if (e.context === 'prompt') e.setSerializedValue(applyTextReplacements(e.value));
		});
	});
});

// The `else` half of this extension — adding a "Node name for S&R" property to
// every OTHER node type — is not carried over, because core does exactly it:
// src/extensions/core/saveImageExtraOutput.ts adds the same property, with the
// same guard, to every type outside its own save-node list, and every easy-use
// type is outside that list. Reproducing it also meant a PREDICATE selector,
// which the published API discourages precisely because it has to run for every
// registered type — thousands of callbacks at boot to re-do core's own work.
