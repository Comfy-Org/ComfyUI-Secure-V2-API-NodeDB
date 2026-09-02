// rgthree's model metadata service read and mutated pack-owned sidecar files
// through custom Python routes. Secure packs do not register those routes.
// Keep the imported service shape so Power Lora Loader remains loadable, while
// making the retired badge data explicitly absent and side-effect free.
class UnavailableModelInfoService extends EventTarget {
    async getInfo() { return null; }
    async refreshInfo() { return null; }
    async clearFetchedInfo() { return null; }
    async savePartialInfo() { return null; }
    setFreshInfo() {}
}

export const LORA_INFO_SERVICE = new UnavailableModelInfoService();
export const CHECKPOINT_INFO_SERVICE = new UnavailableModelInfoService();
