import { comfy } from '/comfy/api/v2.js';

comfy.defs.extend("SystemNotification|pysssss", (b) => {
	b.onExecuted(async (node, result) => {
		const { message, mode } = result.raw;

		if (mode === "on empty queue") {
			if (comfy.queue.pending() !== 0) {
				await new Promise((r) => setTimeout(r, 500));
			}
			if (comfy.queue.pending() !== 0) {
				return;
			}
		}
		comfy.commands.notify({
			severity: "info",
			summary: "ComfyUI",
			detail: message ?? "Your notification has triggered.",
		});
	});
});
