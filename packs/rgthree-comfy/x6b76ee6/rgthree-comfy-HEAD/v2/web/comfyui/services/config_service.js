import { comfy } from '/comfy/api/v2.js';

// The secure loader does not execute rgthree's Python bootstrap, so its former
// generated-config and writable-config routes do not exist.
// These are the converted features that still have an effect under V2; the host
// owns their persistence, presentation, and cross-tab updates.
const SETTINGS = {
    "features.progress_bar.enabled": {
        name: "Show rgthree execution progress", type: "boolean", defaultValue: true,
        category: ["rgthree-comfy", "Features"],
    },
    "unreleased.power_conductor.enabled": {
        name: "Enable Power Conductor (reload required)", type: "boolean", defaultValue: false,
        category: ["rgthree-comfy", "Experimental"],
    },
    "nodes.reroute.default_width": {
        name: "Reroute default width", type: "number", defaultValue: 40,
        attrs: { min: 10, max: 8192, step: 10 }, category: ["rgthree-comfy", "Reroute"],
    },
    "nodes.reroute.default_height": {
        name: "Reroute default height", type: "number", defaultValue: 30,
        attrs: { min: 10, max: 8192, step: 10 }, category: ["rgthree-comfy", "Reroute"],
    },
    "nodes.reroute.default_resizable": {
        name: "Allow resizing new Reroutes", type: "boolean", defaultValue: false,
        category: ["rgthree-comfy", "Reroute"],
    },
    "nodes.reroute.default_layout": {
        name: "Reroute default connections layout", type: "combo", defaultValue: "Left -> Right",
        options: ["Left", "Right", "Top", "Bottom"].flatMap((input) =>
            ["Left", "Right", "Top", "Bottom"].filter((output) => output !== input).map((output) => `${input} -> ${output}`)),
        category: ["rgthree-comfy", "Reroute"],
    },
    "nodes.power_lora_loader.show_info_badge": {
        name: "Show LoRA model info action", type: "boolean", defaultValue: true,
        category: ["rgthree-comfy", "Power Lora Loader"],
    },
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
        return true;
    }
}

export const SERVICE = new ConfigService();
// Changes from the host settings screen and another tab must reach the same
// pack listeners as changes made through rgthree's own settings dialog.
for (const key of Object.keys(SETTINGS)) {
    comfy.settings.onChange(settingId(key), (value) => {
        SERVICE.dispatchEvent(new CustomEvent('config-change', { detail: { key, value } }));
    });
}
