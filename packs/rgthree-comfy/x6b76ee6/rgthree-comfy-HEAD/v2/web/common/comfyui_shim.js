import { comfy } from '/comfy/api/v2.js';
// The dynamic-import fallback is now the only path: `window.comfyAPI.pnginfo` was
// the branch this module existed to prefer, and the pack already ships its own
// copy of that module beside this one.
export { getPngMetadata, getWebpMetadata } from "./comfyui_shim_pnginfo.js";
