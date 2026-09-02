import { comfy } from '/comfy/api/v2.js';

// The secure loader does not execute rgthree's Python bootstrap, so its former
// generated-config and writable-config routes do not exist.
// These are the converted features that still have an effect under V2; the host
// owns their persistence, presentation, and cross-tab updates.
const SETTINGS = {
    "log_level": {
        name: "Browser console log level",
        type: "combo",
        options: ["IMPORTANT", "ERROR", "WARN", "INFO", "DEBUG", "DEV"],
        defaultValue: "WARN",
        category: ["rgthree-comfy", "Advanced"],
    },
    "features.import_individual_nodes.enabled": {
        name: "Import matching node widgets on drop",
        type: "boolean",
        defaultValue: false,
        category: ["rgthree-comfy", "Features"],
    },
    "features.comfy_top_bar_menu.enabled": {
        name: "Show rgthree action-bar buttons",
        type: "boolean",
        defaultValue: true,
        category: ["rgthree-comfy", "Menus"],
    },
    "features.comfy_top_bar_menu.button_bookmarks.enabled": {
        name: "Show workflow bookmarks action",
        type: "boolean",
        defaultValue: true,
        category: ["rgthree-comfy", "Menus"],
    },
    "features.menu_queue_selected_nodes": {
        name: "Show Queue Selected Output Nodes",
        type: "boolean",
        defaultValue: true,
        category: ["rgthree-comfy", "Menus"],
    },
    "features.menu_bookmarks.enabled": {
        name: "Show bookmarks in rgthree menu",
        type: "boolean",
        defaultValue: true,
        category: ["rgthree-comfy", "Menus"],
    },
};

const settingId = (key) => `rgthree.${key}`;
for (const [key, definition] of Object.entries(SETTINGS)) {
    comfy.settings.declare({ id: settingId(key), ...definition });
}

class ConfigService extends EventTarget {
    getConfigValue(key, fallback) {
        const definition = SETTINGS[key];
        if (!definition) return fallback;
        const value = comfy.settings.get(settingId(key));
        return value === undefined
            ? (fallback === undefined ? definition.defaultValue : fallback)
            : value;
    }
    getFeatureValue(key, fallback) {
        return this.getConfigValue(`features.${key.replace(/^features\./, "")}`, fallback);
    }
    async setConfigValues(changed) {
        const entries = Object.entries(changed);
        if (entries.some(([key]) => !SETTINGS[key])) return false;
        await Promise.all(entries.map(([key, value]) =>
            comfy.settings.set(settingId(key), value)));
        for (const [key, value] of entries) {
            this.dispatchEvent(new CustomEvent("config-change", { detail: { key, value } }));
        }
        return true;
    }
}

export const SERVICE = new ConfigService();
