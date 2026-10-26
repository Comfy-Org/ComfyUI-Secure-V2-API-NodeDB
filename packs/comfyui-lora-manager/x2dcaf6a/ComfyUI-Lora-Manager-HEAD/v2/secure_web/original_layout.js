// LoRA Manager rev 10: recognising the original pack's saved widget layout, so onConfigured can migrate it.
//
// The current original saves every node with an AUTOCOMPLETE_TEXT_* input with a hidden __lm_autocomplete_meta_text widget
// value ahead of the text: createAutocompleteTextWidgetFactory adds it immediately before each text widget
// (web/comfyui/vue-widgets/lora-manager-widgets.js 16723-16758, 16852-16860, pinned x2dcaf6a): {"version":1,"textWidgetName":"text"}.
// - Loader, Stacker and Create Hook LoRA: [meta, text, rows].
// - Prompt and Text: [meta, text].
// - WanVideo Lora Select: [low_mem_load, merge_loras, meta, text, rows] (originalWanLayout).
// Deployed core restores widgets_values by position (LiteGraph.namedValuesRestore is off, and these saves carry no
// names), so on rev 10's widgets ([text, loras] and [text]) they land shifted. onConfigured(node, data) receives the saved
// node object, widgets_values included (host-stack r4a test W1). Older saves ([text, rows] / [text]) and rev 10's own saves
// align already and are not matched.

const isPlainObject = value =>
  !!value && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;

/**
 * The saved text (and rows) when `data.widgets_values` is exactly the original's metadata-first layout, else null.
 * @param {unknown} data the onConfigured data (the saved node object)
 * @param {boolean} withRows Loader/Stacker (true: [meta, text, rows]) or Prompt (false: [meta, text])
 * @returns {{text: string, rows?: unknown[]} | null}
 */
export function originalAutocompleteLayout(data, withRows) {
  const values = isPlainObject(data) ? data.widgets_values : undefined;
  if (!Array.isArray(values) || values.length !== (withRows ? 3 : 2)) return null;
  const meta = values[0];
  if (!isPlainObject(meta) || Object.keys(meta).length !== 2 || meta.version !== 1 || typeof meta.textWidgetName !== 'string')
    return null;
  if (typeof values[1] !== 'string') return null;
  if (!withRows) return { text: values[1] };
  if (!Array.isArray(values[2])) return null;
  return { text: values[1], rows: values[2] };
}

/**
 * WanVideo Lora Select (r3, review LORA10-B1): the original saves [low_mem_load, merge_loras, meta, text, rows], i.e. its
 * two BOOLEAN widgets ahead of the same metadata-first text/rows layout. Core places the BOOLEANs correctly; only the rest is
 * shifted. Returns the saved text and rows when the layout matches exactly, else null.
 * @param {unknown} data the onConfigured data (the saved node object)
 * @returns {{text: string, rows: unknown[]} | null}
 */
export function originalWanLayout(data) {
  const values = isPlainObject(data) ? data.widgets_values : undefined;
  if (!Array.isArray(values) || values.length !== 5) return null;
  if (typeof values[0] !== 'boolean' || typeof values[1] !== 'boolean') return null;
  return /** @type {{text: string, rows: unknown[]} | null} */ (originalAutocompleteLayout({ widgets_values: values.slice(2) }, true));
}
