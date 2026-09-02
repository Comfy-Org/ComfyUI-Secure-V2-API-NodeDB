import { comfy } from '/comfy/api/v2.js';

const ASSET_ROOT = new URL("./assets/", import.meta.url);

function resolveSound(file) {
	file = String(file || "notify.mp3").trim();
	if (!file.includes("/")) file = "assets/" + file;

	const url = new URL(file, import.meta.url);
	if (!url.href.startsWith(ASSET_ROOT.href)) {
		comfy.commands.notify({
			severity: "warn",
			summary: "PlaySound",
			detail: "Secure nodes only play audio packaged with this node pack.",
		});
		return undefined;
	}
	return url;
}

comfy.defs.extend("PlaySound|pysssss", (b) => {
	b.onExecuted(async (node) => {
		if (node.widgets.at(0).getValue() === "on empty queue") {
			if (comfy.queue.pending() !== 0) {
				await new Promise((r) => setTimeout(r, 500));
			}
			if (comfy.queue.pending() !== 0) {
				return;
			}
		}
		const url = resolveSound(node.widgets.at(2).getValue());
		if (!url) return;
		await comfy.commands.playSound({
			src: url.href,
			volume: node.widgets.at(1).getValue(),
		});
	});
});
