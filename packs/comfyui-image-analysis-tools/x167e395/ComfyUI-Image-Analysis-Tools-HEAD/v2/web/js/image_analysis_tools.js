import { comfy } from "/comfy/api/v2.js";

// Startup-only legacy extension: no node definitions or graph mutations.
const EXTENSION_ID = "comfyui.image_analysis_tools";
comfy.onReady(() => {
    console.log("ComfyUI Image Analysis Tools Loaded");
});
export { EXTENSION_ID };
