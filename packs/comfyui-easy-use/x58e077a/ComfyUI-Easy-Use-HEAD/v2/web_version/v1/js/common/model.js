import { comfy } from "/comfy/api/v2.js";
import { $el } from "./utils.js";
import { $t } from "./i18n.js";

// Model paths, metadata, and previews are host-owned in Secure Nodes. The
// upstream dialog queried pack routes and Civitai, then downloaded remote
// previews in the browser. This version keeps the useful menu affordance while
// showing only the sealed catalogue value already present on the node.
let openInfoDialog = null;
let openMetadataDialog = null;

class MetadataDialog {
	close() {
		this.handle?.close();
	}

	show(metadata) {
		openMetadataDialog?.close();
		openMetadataDialog = this;
		this.handle = comfy.ui.showDialog({
			key: "easyuse.modelMetadata",
			render: (container) => {
				container.classList.add("easyuse-model-metadata");
				container.append(
					$el(
						"div",
						Object.entries(metadata).map(([name, value]) =>
							$el("div", [
								$el("label", { textContent: name }),
								$el("span", { textContent: String(value) }),
							])
						)
					)
				);
			},
		});
	}
}

export class ModelInfoDialog {
	constructor(name) {
		this.name = name;
	}

	close() {
		this.handle?.close();
	}

	async show(type, value) {
		this.type = type;
		this.metadata = {
			name: String(value),
			catalogue: String(type),
			status: "Model metadata and previews are managed by the secure host.",
		};

		this.info = $el("div", { style: { flex: "auto" } });
		this.content = $el("div.easyuse-model-content", [
			$el("div.easyuse-model-header", [
				$el("h2", { textContent: this.name }),
			]),
			$el("main", { style: { display: "flex" } }, [this.info]),
		]);

		openInfoDialog?.close();
		openInfoDialog = this;
		this.handle = comfy.ui.showDialog({
			key: "easyuse.modelInfo",
			render: (container) => {
				container.classList.add("easyuse-model-info");
				container.append(this.content, $el(
					"div.easyuse-model-buttons", this.createButtons()
				));
			},
		});

		await this.addInfo();
	}

	async addInfo() {
		this.info.replaceChildren(
			$el("p", [
				$el("label", { textContent: `${$t("Catalogue")}: ` }),
				$el("span", { textContent: this.type }),
			]),
			$el("p", [
				$el("label", { textContent: `${$t("Model")}: ` }),
				$el("span", { textContent: this.name }),
			]),
			$el("p", {
				textContent: $t(
					"External metadata and preview downloads are disabled in secure mode."
				),
			})
		);
	}

	createButtons() {
		return [
			$el("button", {
				type: "button",
				textContent: $t("View raw metadata"),
				onclick: () => new MetadataDialog().show(this.metadata),
			}),
		];
	}
}

export class CheckpointInfoDialog extends ModelInfoDialog {}

export class LoraInfoDialog extends ModelInfoDialog {}
