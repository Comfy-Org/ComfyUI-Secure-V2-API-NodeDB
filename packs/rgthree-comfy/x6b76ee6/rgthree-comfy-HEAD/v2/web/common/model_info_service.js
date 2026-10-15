import { readModelInfo, writeModelInfo, ModelMetadataUnavailableError } from './model_info_storage.js';

class ModelInfoService extends EventTarget {
    constructor(kind) { super(); this.kind = kind; this.fileToInfo = new Map(); }
    async getInfo(file, refresh = false, light = false) {
        if (refresh) return this.refreshInfo(file);
        if (this.fileToInfo.has(file)) return structuredClone(this.fileToInfo.get(file));
        const info = await readModelInfo(this.kind, file);
        if (!light) this.fileToInfo.set(file, structuredClone(info));
        return info;
    }
    async refreshInfo() { throw new ModelMetadataUnavailableError(); }
    async clearFetchedInfo() {
        // Clearing fetched provider cache must never delete the user's notes.
        throw new ModelMetadataUnavailableError();
    }
    async savePartialInfo(file, changes) {
        const info = await writeModelInfo(this.kind, file, changes);
        this.setFreshInfo(file, info);
        this.dispatchEvent(new CustomEvent('info-change', { detail: { file, info: structuredClone(info) } }));
        return info;
    }
    setFreshInfo(file, info) {
        if (!info || info.file !== file) throw new Error('Model metadata identity mismatch.');
        this.fileToInfo.set(file, structuredClone(info));
    }
}

export const LORA_INFO_SERVICE = new ModelInfoService('loras');
export const CHECKPOINT_INFO_SERVICE = new ModelInfoService('checkpoints');
