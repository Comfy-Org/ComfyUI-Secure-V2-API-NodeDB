// LoRA Manager rev 10: the one self-registering frontend entry (MERVYN m_6934bd4d0f). Like lora_info.js it registers at
// module load against the worker's comfy object; every other secure_web module only exports functions.
//
// (a) live on the current guest (c6b97a15):
//     - Prompt: the dynamic trigger_wordsN sockets;
//     - Lora Stack Combiner: the dynamic lora_stackN sockets;
//     - Save Image: the webp/jpeg widget toggling (its %token% filename expansion waits for G1);
//     - Debug Metadata: the panel showing execution metadata (restoring it from a saved workflow waits for R6-4).
// (b) the LORAS / AUTOCOMPLETE_TEXT_LORAS / AUTOCOMPLETE_TEXT_PROMPT widget types (#11, host-stack r4a), inert on live:
//     - Lora Loader and Lora Stacker: rows and text, with their text <-> rows sync;
//     - Create Hook LoRA: its text/rows sync and, since r3, its workflow-load restore;
//     - Prompt: its text;
//     - Text and WanVideo Lora Select (r3): workflow-load restore only (saved_layout_restore.js); their edit-time
//       behaviour stays held.
//     Original-format saves carry a hidden metadata value ahead of each autocomplete text, which core places shifted by
//     one; each of these nodes migrates it in onConfigured (original_layout.js).
// Held, not registered: TriggerWord Toggle (R6-4 and G1; a widget type cannot reproduce its prompt serializer exactly),
// autocomplete and the keyboard path (G3, G4, G5), node markers, manager settings, the workflow registry and templates.
//
// Each frontend registers on its own: one refusal is logged and does not stop the others. Registering twice in one worker
// is prevented.
import { registerLoraWidgetTypes } from './widget_types.js';
import { registerPromptInputs } from './prompt_inputs.js';
import { registerStackInputs } from './stack_inputs.js';
import { registerSaveImageExtraOutput } from './save_image_extra_output.js';
import { registerMetadataDisplay } from './metadata_display.js';
import { registerTextRowSync } from './text_row_sync.js';
import { registerCreateHookLora } from './create_hook_lora.js';
import { registerSavedLayoutRestore } from './saved_layout_restore.js';

const MARK = Symbol.for('loramanager.rev10.frontends');

export const FRONTENDS = Object.freeze([
  // Widget types first, so a bridged host has them before it builds nodes.
  ['widgetTypes', registerLoraWidgetTypes],
  ['promptInputs', registerPromptInputs],
  ['stackInputs', registerStackInputs],
  ['saveImage', registerSaveImageExtraOutput],
  ['metadataDisplay', registerMetadataDisplay],
  ['textRowSync', registerTextRowSync],
  ['createHook', registerCreateHookLora],
  ['savedLayouts', registerSavedLayoutRestore], // r3: appended, so the order of the others is unchanged
]);

/** @param {any} comfy */
export function registerLoraManagerFrontends(comfy) {
  const registered = {}, failed = {};
  for (const [name, register] of FRONTENDS) {
    try { registered[name] = register(comfy); }
    catch (error) {
      failed[name] = String(error?.message ?? error);
      console.error(`[LoRA Manager] the ${name} frontend was not registered:`, error);
    }
  }
  return { registered, failed };
}

const comfy = globalThis.comfy;
if (comfy && !globalThis[MARK]) {
  Object.defineProperty(globalThis, MARK, { value: registerLoraManagerFrontends(comfy), configurable: false });
}
