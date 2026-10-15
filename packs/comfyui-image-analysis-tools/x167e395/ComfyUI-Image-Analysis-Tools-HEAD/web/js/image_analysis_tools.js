import { app } from "../../scripts/app.js";

app.registerExtension({
	name: "comfyui.image_analysis_tools",
	async setup() {
		console.log("ComfyUI Image Analysis Tools Loaded");
	},
});
