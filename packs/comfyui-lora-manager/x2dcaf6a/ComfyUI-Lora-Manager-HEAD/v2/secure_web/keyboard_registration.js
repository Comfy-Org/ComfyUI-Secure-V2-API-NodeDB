// Explicit private compatibility entry. Replaces predecessor entry exclusively.
// No automatic registration or runtime profile is inferred from this export.
import { declareAutoFormatPreference } from './autocomplete_blur.js';
import { declareKeyboardPreferences, createAcceptKeyPreference, createAppendCommaPreference } from './keyboard_preferences.js';
import { createKeyboardProducer } from './keyboard_producer.js';
import { registerLoaderTextEditor } from './loader_text_editor.js';
import { registerStackerEditor } from './stacker_editor.js';
export { LoraActiveFilterState, buildActiveFiltersPayload } from './active_filter_state.js';
export { createSyntaxSelection, planLoraInsertion } from './autocomplete_insert.js';
const installed = new WeakSet();
export function registerKeyboardValidationCandidate(comfy, selected) {
  if (installed.has(comfy)) throw new Error('This private Loader/Stacker entry is already mounted');
  comfy.require('ui.editable-keyboard'); // Candidate-only availability, not publication.
  const producer = createKeyboardProducer(comfy, selected); // Before widget mutations.
  declareAutoFormatPreference(comfy); declareKeyboardPreferences(comfy);
  const getMode = createAcceptKeyPreference(comfy), getAppend = createAppendCommaPreference(comfy);
  const options = { producer, preferences: () => ({ mode: getMode(), appendComma: getAppend() }),
    observePreferences(callback) {
      const first = comfy.settings.onChange('loramanager.autocomplete_accept_key', callback);
      let second;
      try { second = comfy.settings.onChange('loramanager.autocomplete_append_comma', callback); }
      catch (error) { first(); throw error; }
      return () => { try { second(); } finally { first(); } };
    }
  };
  const offLoader = registerLoaderTextEditor(comfy, options);
  let offStacker;
  try { offStacker = registerStackerEditor(comfy); }
  catch (error) { offLoader(); throw error; }
  installed.add(comfy);
  let disposed = false;
  return () => {
    if (disposed) return;
    disposed = true;
    try { offStacker(); } finally { offLoader(); installed.delete(comfy); }
  };
}
