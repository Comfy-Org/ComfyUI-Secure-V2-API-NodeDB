// One source-owned autocomplete preference; no library/service/search authority.
const AUTOCOMPLETE_AUTO_FORMAT_SETTING_ID = "loramanager.autocomplete_auto_format";
const AUTOCOMPLETE_AUTO_FORMAT_DEFAULT = true;

export function declareAutoFormatPreference(comfy) {
  comfy.settings.declare({
    id: AUTOCOMPLETE_AUTO_FORMAT_SETTING_ID,
    name: "Auto format autocomplete text on blur",
    type: "boolean",
    defaultValue: AUTOCOMPLETE_AUTO_FORMAT_DEFAULT,
    tooltip: "When enabled, leaving an autocomplete textarea removes duplicate commas and collapses unnecessary spaces.",
    category: ["LoRA Manager", "Autocomplete", "Auto Format"],
  });
}

export function createAutoFormatPreference(comfy) {
    let settingsUnavailableLogged = false;

    return () => {
        const settingManager = comfy?.settings;
        if (!settingManager || typeof settingManager.get !== "function") {
            if (!settingsUnavailableLogged) {
                console.warn("LoRA Manager: settings API unavailable, using default autocomplete auto format setting.");
                settingsUnavailableLogged = true;
            }
            return AUTOCOMPLETE_AUTO_FORMAT_DEFAULT;
        }

        try {
            const value = settingManager.get(AUTOCOMPLETE_AUTO_FORMAT_SETTING_ID);
            return value ?? AUTOCOMPLETE_AUTO_FORMAT_DEFAULT;
        } catch (error) {
            if (!settingsUnavailableLogged) {
                console.warn("LoRA Manager: unable to read autocomplete auto format setting, using default.", error);
                settingsUnavailableLogged = true;
            }
            return AUTOCOMPLETE_AUTO_FORMAT_DEFAULT;
        }
    };
}

const LORA_TAG_PATTERN = /(<lora:[^:>]+:[^:>]+(?::[^:>]+)?>)/gi;

function normalizeAutocompleteSegment(segment = '') {
    // Collapse whitespace only outside <lora:...> tags: names inside the tags
    // may legitimately contain repeated spaces (e.g. "test -  0021"), and
    // collapsing them breaks file resolution at runtime.
    return segment
        .split(LORA_TAG_PATTERN)
        .map((part, index) => (index % 2 === 1 ? part : part.replace(/\s+/g, ' ')))
        .join('')
        .trim();
}

export function formatAutocompleteTextOnBlur(text = '') {
    if (typeof text !== 'string') {
        return '';
    }

    return text
        .split('\n')
        .map((line) => {
            if (!line.trim()) {
                return '';
            }

            const cleanedSegments = line
                .split(',')
                .map(normalizeAutocompleteSegment)
                .filter(Boolean);

            return cleanedSegments.join(', ');
        })
        .join('\n');
}
