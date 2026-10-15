// Native two field declarations/getters; only app settings authority is rebound.
const AUTOCOMPLETE_APPEND_COMMA_SETTING_ID = "loramanager.autocomplete_append_comma";
const AUTOCOMPLETE_APPEND_COMMA_DEFAULT = true;
const AUTOCOMPLETE_ACCEPT_KEY_SETTING_ID = "loramanager.autocomplete_accept_key";
const AUTOCOMPLETE_ACCEPT_KEY_DEFAULT = "both";
const AUTOCOMPLETE_ACCEPT_KEY_OPTION_BOTH = "Tab or Enter";
const AUTOCOMPLETE_ACCEPT_KEY_OPTION_TAB_ONLY = "Tab only";
const AUTOCOMPLETE_ACCEPT_KEY_OPTION_ENTER_ONLY = "Enter only";

export function createAppendCommaPreference(comfy) {
    let settingsUnavailableLogged = false;

    return () => {
        const settingManager = comfy?.settings;
        if (!settingManager || typeof settingManager.get !== "function") {
            if (!settingsUnavailableLogged) {
                console.warn("LoRA Manager: settings API unavailable, using default append comma setting.");
                settingsUnavailableLogged = true;
            }
            return AUTOCOMPLETE_APPEND_COMMA_DEFAULT;
        }

        try {
            const value = settingManager.get(AUTOCOMPLETE_APPEND_COMMA_SETTING_ID);
            return value ?? AUTOCOMPLETE_APPEND_COMMA_DEFAULT;
        } catch (error) {
            if (!settingsUnavailableLogged) {
                console.warn("LoRA Manager: unable to read append comma setting, using default.", error);
                settingsUnavailableLogged = true;
            }
            return AUTOCOMPLETE_APPEND_COMMA_DEFAULT;
        }
    };
}

export function createAcceptKeyPreference(comfy) {
    let settingsUnavailableLogged = false;

    return () => {
        const settingManager = comfy?.settings;
        if (!settingManager || typeof settingManager.get !== "function") {
            if (!settingsUnavailableLogged) {
                console.warn("LoRA Manager: settings API unavailable, using default autocomplete accept key setting.");
                settingsUnavailableLogged = true;
            }
            return AUTOCOMPLETE_ACCEPT_KEY_DEFAULT;
        }

        try {
            const value = settingManager.get(AUTOCOMPLETE_ACCEPT_KEY_SETTING_ID);
            if (value === AUTOCOMPLETE_ACCEPT_KEY_OPTION_TAB_ONLY) {
                return "tab_only";
            }
            if (value === AUTOCOMPLETE_ACCEPT_KEY_OPTION_ENTER_ONLY) {
                return "enter_only";
            }
            if (value === AUTOCOMPLETE_ACCEPT_KEY_OPTION_BOTH || value == null) {
                return AUTOCOMPLETE_ACCEPT_KEY_DEFAULT;
            }
            return value;
        } catch (error) {
            if (!settingsUnavailableLogged) {
                console.warn("LoRA Manager: unable to read autocomplete accept key setting, using default.", error);
                settingsUnavailableLogged = true;
            }
            return AUTOCOMPLETE_ACCEPT_KEY_DEFAULT;
        }
    };
}

export function declareKeyboardPreferences(comfy) {
 comfy.settings.declare({
            id: AUTOCOMPLETE_APPEND_COMMA_SETTING_ID,
            name: "Append comma after autocomplete",
            type: "boolean",
            defaultValue: AUTOCOMPLETE_APPEND_COMMA_DEFAULT,
            tooltip: "When enabled, accepted autocomplete suggestions append ', ' to the inserted text.",
            category: ["LoRA Manager", "Autocomplete", "Append comma"],
        });
 comfy.settings.declare({
            id: AUTOCOMPLETE_ACCEPT_KEY_SETTING_ID,
            name: "Autocomplete accept key",
            type: "combo",
            options: [
                AUTOCOMPLETE_ACCEPT_KEY_OPTION_BOTH,
                AUTOCOMPLETE_ACCEPT_KEY_OPTION_TAB_ONLY,
                AUTOCOMPLETE_ACCEPT_KEY_OPTION_ENTER_ONLY,
            ],
            defaultValue: AUTOCOMPLETE_ACCEPT_KEY_OPTION_BOTH,
            tooltip: "Choose which key accepts the selected autocomplete suggestion. Keys not selected here keep their normal textarea behavior.",
            category: ["LoRA Manager", "Autocomplete", "Accept key"],
        });
}
