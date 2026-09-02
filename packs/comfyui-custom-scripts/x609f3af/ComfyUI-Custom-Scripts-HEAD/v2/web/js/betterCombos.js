import { comfy } from '/comfy/api/v2.js';

const CHECKPOINT_LOADER = "CheckpointLoader|pysssss";
const LORA_LOADER = "LoraLoader|pysssss";

function getType(node) {
	if (node.comfyClass === CHECKPOINT_LOADER) {
		return "checkpoints";
	}
	return "loras";
}

function encodeRFC3986URIComponent(str) {
	return encodeURIComponent(str).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

// Previously rebuilt the model picker after the host had drawn it: init() hung a
// MutationObserver on document.body, waited for a `.litecontextmenu` to be
// inserted, walked its `.litemenu-entry` children into a folder tree or a
// thumbnail grid, attached hover handlers that fetched a preview from
// /pysssss/view, and moved the menu. It injected CSS matching those same class
// names, read the cursor from app.canvas.last_mouse and the widget under it from
// getWidgetAtCursor, and wrapped app.refreshComboInNodes to reload its preview
// index.
//
// REFUSED, not a pending gap: rewriting the host's rendered menu in the DOM.
// `.litecontextmenu` and `.litemenu-entry` are the legacy canvas renderer's
// markup — the renderer is ours to replace, and Nodes 2.0 does not produce them —
// so a pack matching on them breaks on a rename it cannot see, and every pack
// doing it races over the same element. Observing document.body for somebody
// else's element and then rebuilding its children is reach-in, not extension.
//
// DROPPED: the folder tree, the thumbnail grid and the hover preview, and with
// them the "🐍 Lora & Checkpoint loader display mode" setting that chose between
// them and the imagesByType index they read. Choosing how a combo's values are
// presented is a reasonable thing to want and it has no published surface;
// decorating the drawn menu is not the way to ask for it.

// "Save as Preview" on any node showing images: writes the one the user is
// looking at over a loader's preview thumbnail.
//
// LIMITATION: the original unshifted this to the top of the node menu; pack
// entries accumulate after core's own, and where they sit relative to those is
// the host's to decide.
comfy.defs.extend(/./, (b) => {
	b.addMenuItem({
		label: "Save as Preview",
		// undefined means the user has neither selected nor hovered an image, which
		// is exactly when the original built no entry rather than picking one.
		when: (node) => node.getDisplayedImageIndex() !== undefined,
		items: () =>
			comfy.graph
				.nodes()
				.filter((n) => n.comfyClass === CHECKPOINT_LOADER || n.comfyClass === LORA_LOADER)
				.map((loader) => ({
					label: loader.widgets.at(0).getValue(),
					run: (node) => {
						const src = node.getOutputImages()[node.getDisplayedImageIndex()];
						if (src === undefined) {
							return;
						}
						const url = new URL(src, location.href);
						const model = loader.widgets.at(0).getValue();
						comfy.backend
							.fetch("/pysssss/save/" + encodeRFC3986URIComponent(`${getType(loader)}/${model}`), {
								method: "POST",
								body: JSON.stringify({
									filename: url.searchParams.get("filename"),
									subfolder: url.searchParams.get("subfolder"),
									type: url.searchParams.get("type"),
								}),
								headers: {
									"content-type": "application/json",
								},
							})
							.catch((error) => console.error("[pysssss] save preview failed", error));
					},
				})),
	});
});

// The old code hung listExamples off the node CLASS as "pysssss.updateExamples",
// so every loader node overwrote it and modelInfo.js reached the last one created
// whichever node it meant. Handles hold no arbitrary properties, and a Map keyed
// by graph and node id is the published shape for per-node state — it is also the
// fix: the right node's list refreshes. modelInfo.js and common/modelInfoDialog.js
// import this rather than reading a property off somebody else's object; they are
// files in this pack, so a module export is the channel.
const exampleRefreshers = new Map();
const refresherKey = (node) => `${node.graphId}:${node.id}`;

export function refreshExamples(node) {
	if (node) exampleRefreshers.get(refresherKey(node))?.();
}

comfy.defs.extend([CHECKPOINT_LOADER, LORA_LOADER], (b) => {
	b.onRemoved((node) => exampleRefreshers.delete(refresherKey(node)));
	b.onCreated((node) => {
		const exampleList = node.widgets.add({
			type: "combo",
			name: "example",
			value: "",
			options: { values: [""] },
		});
		node.widgets.get("prompt").setHidden(true);
		let exampleEl;

		const get = async (route, suffix) => {
			const url = encodeRFC3986URIComponent(`${getType(node)}${suffix || ""}`);
			return await comfy.backend.fetch(`/pysssss/${route}/${url}`);
		};

		const getExample = async () => {
			if (exampleList.getValue() === "[none]") {
				if (exampleEl) {
					node.widgets.remove("example_text");
					exampleEl = null;
					node.widgets.get("prompt").setValue("");
				}
				return;
			}

			const v = node.widgets.at(0).getValue();
			const pos = v.lastIndexOf(".");
			const name = v.substr(0, pos);
			let exampleName = exampleList.getValue();
			let viewPath = `/${name}`;
			if (exampleName === "notes") {
				viewPath += ".txt";
			} else {
				viewPath += `/${exampleName}`;
			}
			// Mounted before the fetch, not after: two overlapping selections would
			// both find it missing and mount twice, which now throws on the name.
			if (!exampleEl) {
				exampleEl = document.createElement("textarea");
				exampleEl.readOnly = true;
				exampleEl.style.opacity = 0.6;
				exampleEl.style.width = "100%";
				exampleEl.style.height = "100%";
				node.widgets.mount({
					name: "example_text",
					render: (container) => container.append(exampleEl),
				});
			}
			const example = await (await get("view", viewPath)).text();
			exampleEl.value = example;
			// The old code added a SECOND widget also named "prompt", which won the
			// name lookup while the prompt was built and so carried the example text
			// to the backend. Widget values are name-keyed now, so the definition's
			// own (hidden) prompt widget holds it instead: same input, same value.
			node.widgets.get("prompt").setValue(example);
		};

		exampleList.on("change", () => {
			getExample();
		});

		const listExamples = async () => {
			exampleList.setDisabled(true);
			exampleList.setOption("values", ["[none]"]);
			exampleList.setValue("[none]");
			let examples = [];
			if (node.widgets.at(0).getValue()) {
				try {
					examples = await (await get("examples", `/${node.widgets.at(0).getValue()}`)).json();
				} catch (error) {}
			}
			const values = ["[none]", ...examples];
			exampleList.setOption("values", values);
			// setValue notifies, so getExample runs off the change rather than off an
			// explicit callback() call — including the reset to "[none]" above, which
			// is what clears a stale example when the new model has none.
			exampleList.setValue(values[+!!examples.length]);
			exampleList.setDisabled(!examples.length);
		};

		// Expose function to update examples
		exampleRefreshers.set(refresherKey(node), listExamples);

		const modelWidget = node.widgets.at(0);
		let prev = undefined;
		modelWidget.on("change", (v) => {
			if (typeof v === "object" && "content" in v) {
				modelWidget.setValue(v.content);
				return;
			}
			if (prev !== v) {
				prev = v;
				listExamples();
			}
		});
		setTimeout(() => {
			prev = modelWidget.getValue();
			listExamples();
		}, 30);
	});
});
