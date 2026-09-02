import { comfy } from '/comfy/api/v2.js';

/**
 * The frontend slice of rgthree's former custom server API.
 *
 * Secure packs do not execute arbitrary Python route registration. The one
 * runtime dependency the converted nodes need—the LoRA catalogue—is already a
 * core authenticated route. Model-info mutation was tied to rgthree-owned files
 * and intentionally reports unavailable instead of probing dead endpoints.
 */
class RgthreeApi {
    constructor() {
        this.getLorasPromise = null;
    }
    async fetchJson(route, options) {
        const response = await comfy.backend.fetch(route, options);
        if (!response.ok) {
            throw new Error(`Backend request failed (${response.status}) for ${route}`);
        }
        return response.json();
    }
    getLoras(force = false) {
        if (!this.getLorasPromise || force) {
            this.getLorasPromise = this.fetchJson("/models/loras", {
                cache: "no-store",
            }).then((files) => (Array.isArray(files) ? files : [])
                .map((file) => ({ file: String(file) })));
        }
        return this.getLorasPromise;
    }
    async getModelsInfo() {
        return [];
    }
    async getLorasInfo() {
        return [];
    }
    async getCheckpointsInfo() {
        return [];
    }
    async refreshModelsInfo() {
        return [];
    }
    async refreshLorasInfo() {
        return [];
    }
    async refreshCheckpointsInfo() {
        return [];
    }
    async clearModelsInfo() {
        return null;
    }
    async clearLorasInfo() {
        return null;
    }
    async clearCheckpointsInfo() {
        return null;
    }
    async saveModelInfo() {
        return null;
    }
    async saveLoraInfo() {
        return null;
    }
    async saveCheckpointsInfo() {
        return null;
    }
    fetchComfyApi(route, options) {
        return comfy.backend.fetch(route, options);
    }
    print(messageType) {
        console.warn(`[rgthree-comfy] ${messageType}`);
    }
}

export const rgthreeApi = new RgthreeApi();
