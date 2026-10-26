// LoRA Manager rev 10 r3 (review LORA10-B1): workflow-load restore for the two other nodes the shared widget types
// activate on r4a, Text (LoraManager) and WanVideo Lora Select (LoraManager). Registered by lm_frontends.js. Load only:
// their edit-time behaviour (Wan's text <-> rows sync, autocomplete) stays held.
// - Text: an original-format save [meta, text] is re-placed by name (as Prompt in prompt_inputs.js). The original Text
//   node has no loadedGraphNode, so nothing else happens on load.
// - WanVideo Lora Select: the native loadedGraphNode merge (web/comfyui/wanvideo_lora_select.js 117-132): the saved rows,
//   read by name, become mergeLoras(text, savedRows). An original-format save [low_mem_load, merge_loras, meta, text, rows]
//   feeds that merge with its saved text and rows; core already placed the two BOOLEANs correctly, so they are not touched.
// On live c6b97a15 the text/loras inputs are sockets, so there are no widgets and nothing happens. Values that are not a
// string text and a row array are left as placed (the text widget refuses them visibly).
import { normalizeRows } from './catalogue_selection.js';
import { mergeLoras } from './stacker_merge.js';
import { definitionOff } from './guest_compat.js';
import { originalAutocompleteLayout, originalWanLayout } from './original_layout.js';

const TEXT = 'Text (LoraManager)';
const WAN = 'WanVideo Lora Select (LoraManager)';

function restoreText(node, data) {
  const saved = originalAutocompleteLayout(data, false);
  const text = saved && node.widgets.get('text');
  if (text && text.getValue() !== saved.text) text.setValue(saved.text);
}

function restoreWan(node, data) {
  const text = node.widgets.get('text'), rows = node.widgets.get('loras');
  if (!text || !rows) return;
  const saved = originalWanLayout(data);
  const savedText = saved ? saved.text : text.getValue();
  const savedRows = (saved ? saved.rows : rows.getValue()) ?? [];
  if (typeof savedText !== 'string' || !Array.isArray(savedRows)) return;
  // The LORAS widget's native setter normalizes, as for the Loader; each widget is written at most once, rows first.
  const merged = normalizeRows(mergeLoras(savedText, normalizeRows(savedRows)));
  if (saved || JSON.stringify(merged) !== JSON.stringify(normalizeRows(savedRows))) rows.setValue(merged);
  if (saved && text.getValue() !== savedText) text.setValue(savedText);
}

/** @param {any} comfy */
export function registerSavedLayoutRestore(comfy) {
  let disposed = false;
  const guard = restore => (node, data) => {
    if (disposed || node.isDeleted) return;
    try { restore(node, data); }
    catch (error) { console.error('[LoRA Manager] saved-layout restore failed:', error); }
  };
  const offText = definitionOff(comfy.defs.extend(TEXT, builder => { builder.onConfigured(guard(restoreText)); }));
  const offWan = definitionOff(comfy.defs.extend(WAN, builder => { builder.onConfigured(guard(restoreWan)); }));
  return () => {
    if (disposed) return;
    disposed = true;
    offText(); offWan();
  };
}
