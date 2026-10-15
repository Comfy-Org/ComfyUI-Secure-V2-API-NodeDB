// All eleven native setting declarations; template command lifecycle pending.
const DECLARATIONS = [
  {
    "id": "loramanager.trigger_word_wheel_sensitivity",
    "name": "Trigger Word Wheel Sensitivity",
    "type": "slider",
    "attrs": {
      "min": 0.01,
      "max": 0.1,
      "step": 0.01
    },
    "defaultValue": 0.02,
    "tooltip": "Mouse wheel sensitivity for adjusting trigger word strength (default: 0.02)",
    "category": [
      "LoRA Manager",
      "Trigger Word Toggle",
      "Wheel Sensitivity"
    ]
  },
  {
    "id": "loramanager.auto_path_correction",
    "name": "Auto path correction",
    "type": "boolean",
    "defaultValue": true,
    "tooltip": "Automatically update model paths to their current file locations.",
    "category": [
      "LoRA Manager",
      "Automation",
      "Auto path correction"
    ]
  },
  {
    "id": "loramanager.prompt_tag_autocomplete",
    "name": "Enable Tag Autocomplete in Prompt Nodes",
    "type": "boolean",
    "defaultValue": true,
    "tooltip": "When enabled, typing in a Prompt (LoraManager) node triggers tag autocomplete suggestions. You can also toggle it by typing /autocomplete or /noautocomplete in the node, or from the node's right-click menu. Slash commands (e.g., /character, /artist) always work regardless of this setting.",
    "category": [
      "LoRA Manager",
      "Autocomplete",
      "Prompt"
    ]
  },
  {
    "id": "loramanager.lora_active_filters_autocomplete",
    "name": "Search LoRA autocomplete within active filters",
    "type": "boolean",
    "defaultValue": false,
    "tooltip": "When enabled, LoRA autocomplete suggestions respect the active filters (folder/base model/tags) set in the LoRA Manager page. You can also toggle it by typing /activefilters or /noactivefilters in the LoRA field, or from the node's right-click menu.",
    "category": [
      "LoRA Manager",
      "Autocomplete",
      "LoRA Active Filters"
    ]
  },
  {
    "id": "loramanager.autocomplete_append_comma",
    "name": "Append comma after autocomplete",
    "type": "boolean",
    "defaultValue": true,
    "tooltip": "When enabled, accepted autocomplete suggestions append ', ' to the inserted text.",
    "category": [
      "LoRA Manager",
      "Autocomplete",
      "Append comma"
    ]
  },
  {
    "id": "loramanager.autocomplete_auto_format",
    "name": "Auto format autocomplete text on blur",
    "type": "boolean",
    "defaultValue": true,
    "tooltip": "When enabled, leaving an autocomplete textarea removes duplicate commas and collapses unnecessary spaces.",
    "category": [
      "LoRA Manager",
      "Autocomplete",
      "Auto Format"
    ]
  },
  {
    "id": "loramanager.autocomplete_accept_key",
    "name": "Autocomplete accept key",
    "type": "combo",
    "options": [
      "Tab or Enter",
      "Tab only",
      "Enter only"
    ],
    "defaultValue": "Tab or Enter",
    "tooltip": "Choose which key accepts the selected autocomplete suggestion. Keys not selected here keep their normal textarea behavior.",
    "category": [
      "LoRA Manager",
      "Autocomplete",
      "Accept key"
    ]
  },
  {
    "id": "loramanager.tag_space_replacement",
    "name": "Replace underscores with spaces in tags",
    "type": "boolean",
    "defaultValue": false,
    "tooltip": "When enabled, tag names with underscores will have them replaced with spaces when inserted (e.g., 'blonde_hair' becomes 'blonde hair').",
    "category": [
      "LoRA Manager",
      "Autocomplete",
      "Tag Formatting"
    ]
  },
  {
    "id": "loramanager.usage_statistics",
    "name": "Enable usage statistics tracking",
    "type": "boolean",
    "defaultValue": true,
    "tooltip": "When enabled, LoRA Manager will track model usage statistics during workflow execution. Disabling this will prevent unnecessary disk writes.",
    "category": [
      "LoRA Manager",
      "Statistics",
      "Usage Tracking"
    ]
  },
  {
    "id": "loramanager.new_tab_template",
    "name": "New Tab Template Workflow",
    "type": "combo",
    "options": {
      "dynamic_source": "getWorkflowOptions"
    },
    "defaultValue": "Default",
    "tooltip": "Choose a template workflow to load when creating a new workflow tab. 'Default (Blank)' keeps ComfyUI's original blank workflow behavior.",
    "category": [
      "LoRA Manager",
      "Workflow",
      "New Tab Template"
    ]
  },
  {
    "id": "loramanager.strength_step",
    "name": "Strength Adjustment Step",
    "type": "slider",
    "attrs": {
      "min": 0.01,
      "max": 0.1,
      "step": 0.01
    },
    "defaultValue": 0.05,
    "tooltip": "Step size for adjusting LoRA strength via arrow buttons or keyboard (default: 0.05)",
    "category": [
      "LoRA Manager",
      "LoRA Widget",
      "Strength Step"
    ]
  }
];

/** @param {import('../comfy-api').Comfy} comfy */
export function registerManagerSettings(comfy, workflowOptions = ['Default']) {
  if (!Array.isArray(workflowOptions) ||
      workflowOptions.some(value => typeof value !== 'string'))
    throw new Error('Workflow template options must be strings');
  for (const original of DECLARATIONS) {
    const definition = { ...original };
    if (definition.options?.dynamic_source === 'getWorkflowOptions')
      definition.options = [...workflowOptions];
    comfy.settings.declare(definition);
  }
}

/** @param {import('../comfy-api').Comfy} comfy */
export function createManagerPreferences(comfy) {
  const TRIGGER_WORD_WHEEL_SENSITIVITY_ID = "loramanager.trigger_word_wheel_sensitivity";
  const TRIGGER_WORD_WHEEL_SENSITIVITY_DEFAULT = 0.02;
  const AUTO_PATH_CORRECTION_SETTING_ID = "loramanager.auto_path_correction";
  const AUTO_PATH_CORRECTION_DEFAULT = true;
  const PROMPT_TAG_AUTOCOMPLETE_SETTING_ID = "loramanager.prompt_tag_autocomplete";
  const PROMPT_TAG_AUTOCOMPLETE_DEFAULT = true;
  const AUTOCOMPLETE_APPEND_COMMA_SETTING_ID = "loramanager.autocomplete_append_comma";
  const AUTOCOMPLETE_APPEND_COMMA_DEFAULT = true;
  const AUTOCOMPLETE_AUTO_FORMAT_SETTING_ID = "loramanager.autocomplete_auto_format";
  const AUTOCOMPLETE_AUTO_FORMAT_DEFAULT = true;
  const AUTOCOMPLETE_ACCEPT_KEY_SETTING_ID = "loramanager.autocomplete_accept_key";
  const AUTOCOMPLETE_ACCEPT_KEY_DEFAULT = "both";
  const AUTOCOMPLETE_ACCEPT_KEY_OPTION_BOTH = "Tab or Enter";
  const AUTOCOMPLETE_ACCEPT_KEY_OPTION_TAB_ONLY = "Tab only";
  const AUTOCOMPLETE_ACCEPT_KEY_OPTION_ENTER_ONLY = "Enter only";
  const TAG_SPACE_REPLACEMENT_SETTING_ID = "loramanager.tag_space_replacement";
  const TAG_SPACE_REPLACEMENT_DEFAULT = false;
  const USAGE_STATISTICS_SETTING_ID = "loramanager.usage_statistics";
  const USAGE_STATISTICS_DEFAULT = true;
  const NEW_TAB_TEMPLATE_ID = "loramanager.new_tab_template";
  const NEW_TAB_TEMPLATE_DEFAULT = "Default";
  const NEW_TAB_ZOOM_LEVEL = 0.8;
  const STRENGTH_STEP_SETTING_ID = "loramanager.strength_step";
  const STRENGTH_STEP_DEFAULT = 0.05;
  const LORA_ACTIVE_FILTERS_AUTOCOMPLETE_SETTING_ID = "loramanager.lora_active_filters_autocomplete";
  const LORA_ACTIVE_FILTERS_AUTOCOMPLETE_DEFAULT = false;
  const getWheelSensitivity = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, using default wheel sensitivity.");
                  settingsUnavailableLogged = true;
              }
              return TRIGGER_WORD_WHEEL_SENSITIVITY_DEFAULT;
          }
  
          try {
              const value = settingManager.get(TRIGGER_WORD_WHEEL_SENSITIVITY_ID);
              return value ?? TRIGGER_WORD_WHEEL_SENSITIVITY_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read wheel sensitivity setting, using default.", error);
                  settingsUnavailableLogged = true;
              }
              return TRIGGER_WORD_WHEEL_SENSITIVITY_DEFAULT;
          }
      };
  })();
  const getAutoPathCorrectionPreference = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, defaulting auto path correction to enabled.");
                  settingsUnavailableLogged = true;
              }
              return AUTO_PATH_CORRECTION_DEFAULT;
          }
  
          try {
              const value = settingManager.get(AUTO_PATH_CORRECTION_SETTING_ID);
              return value ?? AUTO_PATH_CORRECTION_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read auto path correction setting, defaulting to enabled.", error);
                  settingsUnavailableLogged = true;
              }
              return AUTO_PATH_CORRECTION_DEFAULT;
          }
      };
  })();
  const getPromptTagAutocompletePreference = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, using default tag autocomplete setting.");
                  settingsUnavailableLogged = true;
              }
              return PROMPT_TAG_AUTOCOMPLETE_DEFAULT;
          }
  
          try {
              const value = settingManager.get(PROMPT_TAG_AUTOCOMPLETE_SETTING_ID);
              return value ?? PROMPT_TAG_AUTOCOMPLETE_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read tag autocomplete setting, using default.", error);
                  settingsUnavailableLogged = true;
              }
              return PROMPT_TAG_AUTOCOMPLETE_DEFAULT;
          }
      };
  })();
  const getAutocompleteAppendCommaPreference = (() => {
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
  })();
  const getAutocompleteAutoFormatPreference = (() => {
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
  })();
  const getAutocompleteAcceptKeyPreference = (() => {
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
  })();
  const getTagSpaceReplacementPreference = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, using default tag space replacement setting.");
                  settingsUnavailableLogged = true;
              }
              return TAG_SPACE_REPLACEMENT_DEFAULT;
          }
  
          try {
              const value = settingManager.get(TAG_SPACE_REPLACEMENT_SETTING_ID);
              return value ?? TAG_SPACE_REPLACEMENT_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read tag space replacement setting, using default.", error);
                  settingsUnavailableLogged = true;
              }
              return TAG_SPACE_REPLACEMENT_DEFAULT;
          }
      };
  })();
  const getUsageStatisticsPreference = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, using default usage statistics setting.");
                  settingsUnavailableLogged = true;
              }
              return USAGE_STATISTICS_DEFAULT;
          }
  
          try {
              const value = settingManager.get(USAGE_STATISTICS_SETTING_ID);
              return value ?? USAGE_STATISTICS_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read usage statistics setting, using default.", error);
                  settingsUnavailableLogged = true;
              }
              return USAGE_STATISTICS_DEFAULT;
          }
      };
  })();
  const getNewTabTemplatePreference = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, using default new tab template.");
                  settingsUnavailableLogged = true;
              }
              return NEW_TAB_TEMPLATE_DEFAULT;
          }
  
          try {
              const value = settingManager.get(NEW_TAB_TEMPLATE_ID);
              return value ?? NEW_TAB_TEMPLATE_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read new tab template setting, using default.", error);
                  settingsUnavailableLogged = true;
              }
              return NEW_TAB_TEMPLATE_DEFAULT;
          }
      };
  })();
  const getStrengthStepPreference = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, using default strength step.");
                  settingsUnavailableLogged = true;
              }
              return STRENGTH_STEP_DEFAULT;
          }
  
          try {
              const value = settingManager.get(STRENGTH_STEP_SETTING_ID);
              return value ?? STRENGTH_STEP_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read strength step setting, using default.", error);
                  settingsUnavailableLogged = true;
              }
              return STRENGTH_STEP_DEFAULT;
          }
      };
  })();
  const getLoraActiveFiltersAutocompletePreference = (() => {
      let settingsUnavailableLogged = false;
  
      return () => {
          const settingManager = comfy?.settings;
          if (!settingManager || typeof settingManager.get !== "function") {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: settings API unavailable, using default lora active filters autocomplete setting.");
                  settingsUnavailableLogged = true;
              }
              return LORA_ACTIVE_FILTERS_AUTOCOMPLETE_DEFAULT;
          }
  
          try {
              const value = settingManager.get(LORA_ACTIVE_FILTERS_AUTOCOMPLETE_SETTING_ID);
              return value ?? LORA_ACTIVE_FILTERS_AUTOCOMPLETE_DEFAULT;
          } catch (error) {
              if (!settingsUnavailableLogged) {
                  console.warn("LoRA Manager: unable to read lora active filters autocomplete setting, using default.", error);
                  settingsUnavailableLogged = true;
              }
              return LORA_ACTIVE_FILTERS_AUTOCOMPLETE_DEFAULT;
          }
      };
  })();
  return { getWheelSensitivity, getAutoPathCorrectionPreference, getPromptTagAutocompletePreference, getAutocompleteAppendCommaPreference, getAutocompleteAutoFormatPreference, getAutocompleteAcceptKeyPreference, getTagSpaceReplacementPreference, getUsageStatisticsPreference, getNewTabTemplatePreference, getStrengthStepPreference, getLoraActiveFiltersAutocompletePreference };
}

/** @param {import('../comfy-api').Comfy} comfy */
export async function setManagerPreference(comfy, id, value) {
  if (!DECLARATIONS.some(definition => definition.id === id))
    throw new Error('Unknown LoRA Manager setting');
  await comfy.settings.set(id, value);
  return true;
}
