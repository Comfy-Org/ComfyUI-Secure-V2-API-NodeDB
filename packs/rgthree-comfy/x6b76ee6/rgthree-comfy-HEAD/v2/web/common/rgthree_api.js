import { comfy } from '/comfy/api/v2.js';
import { readModelInfo, writeModelInfo, listModelInfo, ModelMetadataUnavailableError } from './model_info_storage.js';

/**
 * The frontend slice of rgthree's former custom server API.
 *
 * Secure packs do not execute arbitrary Python route registration. The one
 * runtime dependency the converted nodes need—the LoRA catalogue—comes from the
 * public models API: the pack names the folder and the host chooses the route.
 * Authored model-info fields use public storage; metadata hydration still needs
 * an admitted provider and reports unavailable.
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
            this.getLorasPromise = comfy.models.list('loras')
                .then((files) => (Array.isArray(files) ? files : [])
                .map((file) => ({ file: String(file) })));
        }
        return this.getLorasPromise;
    }
    async getModelsInfo({ type, files } = {}) {
        return files?.length ? Promise.all(files.map((file) => readModelInfo(type, file))) : listModelInfo(type);
    }
    async getLorasInfo(options = {}) {
        return this.getModelsInfo({ type: 'loras', ...options });
    }
    async getCheckpointsInfo(options = {}) {
        return this.getModelsInfo({ type: 'checkpoints', ...options });
    }
    async refreshModelsInfo() {
        throw new ModelMetadataUnavailableError();
    }
    async refreshLorasInfo(options = {}) {
        return this.refreshModelsInfo({ type: 'loras', ...options });
    }
    async refreshCheckpointsInfo(options = {}) {
        return this.refreshModelsInfo({ type: 'checkpoints', ...options });
    }
    async clearModelsInfo() {
        throw new ModelMetadataUnavailableError();
    }
    async clearLorasInfo() {
        return this.clearModelsInfo();
    }
    async clearCheckpointsInfo() {
        return this.clearModelsInfo();
    }
    async saveModelInfo(type, file, data) {
        return writeModelInfo(type, file, data);
    }
    async saveLoraInfo(file, data) {
        return this.saveModelInfo('loras', file, data);
    }
    async saveCheckpointsInfo(file, data) {
        return this.saveModelInfo('checkpoints', file, data);
    }
    fetchComfyApi(route, options) {
        return comfy.backend.fetch(route, options);
    }
    print(messageType) {
        console.warn(`[rgthree-comfy] ${messageType}`);
    }
}

export const rgthreeApi = new RgthreeApi();
