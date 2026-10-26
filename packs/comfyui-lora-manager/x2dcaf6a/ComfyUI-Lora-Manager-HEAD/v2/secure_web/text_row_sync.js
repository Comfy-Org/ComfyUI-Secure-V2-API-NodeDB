// LoRA Manager rev 10: Lora Loader and Lora Stacker text <-> rows sync over the widgets the #11 types create, using widget
// handles only (getValue, setValue, on('change')). The semantics are the retained editors' (loader_text_editor.js and
// stacker_editor.js), which are the literal pinned native behaviour:
// - a text edit merges into the rows with mergeLoras: existing matching rows keep their authored strengths and order;
// - a row edit rewrites the text with applyLoraValuesToText after the native 80 ms debounce;
// - a workflow load (onConfigured) re-merges the restored text into the restored rows without rewriting the text, as the
//   native loadedGraphNode does. An original-format save ([meta, text, rows], which core places shifted by one) is first
//   re-placed by name from the saved array, inside that same re-merge: each widget is written once, and the rows keep their
//   saved flags rather than being rebuilt from the text.
// With the widgets present it also adds the optional sockets the native nodes add at creation (Loader: clip, lora_stack;
// Stacker: lora_stack), after the retained editors' check that a reconstructed socket of that name is unique and of the
// right type. Without both widgets (the live guest before r4a, where these inputs are sockets) nothing is changed or wired.
import { normalizeRows } from './catalogue_selection.js';
import { mergeLoras } from './stacker_merge.js';
import { applyLoraValuesToText, debounce } from './stacker_syntax.js';
import { definitionOff } from './guest_compat.js';
import { originalAutocompleteLayout } from './original_layout.js';

export const TEXT_ROW_TYPES = Object.freeze(['Lora Loader (LoraManager)', 'Lora Stacker (LoraManager)']);
// web/comfyui/lora_loader.js 176-187 and lora_stacker.js 17-24 (pinned x2dcaf6a): addInput(..., { shape: 7 }).
const NATIVE_SOCKETS = Object.freeze({
  'Lora Loader (LoraManager)': Object.freeze([['clip', 'CLIP'], ['lora_stack', 'LORA_STACK']]),
  'Lora Stacker (LoraManager)': Object.freeze([['lora_stack', 'LORA_STACK']]),
});
const keyOf = node => JSON.stringify([node.graphId, node.id]);

/** @param {any} comfy */
export function registerTextRowSync(comfy) {
  const states = new Map();
  let disposed = false;
  const off = definitionOff(comfy.defs.extend([...TEXT_ROW_TYPES], builder => {
    builder.onCreated(node => attach(node));
    builder.onConfigured((node, data) => states.get(keyOf(node))?.restore(data));
    builder.onRemoved(node => {
      const state = states.get(keyOf(node));
      if (state && (state.node === node || state.node.isDeleted)) state.dispose();
    });
  }));

  function attach(node) {
    if (disposed || node.isDeleted) return;
    const key = keyOf(node);
    states.get(key)?.dispose();
    const text = node.widgets.get('text'), rows = node.widgets.get('loras');
    if (!text || !rows) return; // sockets, not widgets: nothing to keep in sync
    // Check every reconstructed socket before the first change; never drop links or replace a mismatching socket.
    const sockets = NATIVE_SOCKETS[node.comfyClass] ?? [];
    const slots = node.inputs.all();
    for (const [name, type] of sockets) {
      const matching = slots.filter(slot => slot.name === name);
      if (matching.length > 1 || (matching.length === 1 && matching[0].type !== type))
        throw new Error(`Existing ${name} socket is ambiguous/incompatible`);
    }
    node.setSerializeWidgets(true);
    for (const [name, type] of sockets) if (!node.inputs.byName(name)) node.inputs.add(name, type, { shape: 'optional' });
    let alive = true, restoring = false;
    let observedRows = JSON.stringify(normalizeRows(rows.getValue()));
    const active = () => alive && !disposed && !node.isDeleted;
    const currentText = () => { const value = text.getValue(); return typeof value === 'string' ? value : ''; };
    // `saved`: a migrated original-format save. Its text and rows replace the shifted values in this one merge.
    const mergeText = (saved = null) => {
      const current = normalizeRows(saved ? saved.rows : rows.getValue());
      const nextText = saved ? saved.text : currentText();
      const merged = normalizeRows(mergeLoras(nextText, current));
      const signature = JSON.stringify(merged);
      // Our own merge's change echo must not re-enter the row path and rewrite the text. Recorded before the write, so the
      // guard holds whether the host delivers the echo synchronously or later (the retained editor records it after the
      // write, which assumes asynchronous delivery).
      observedRows = signature;
      if (saved || signature !== JSON.stringify(current)) rows.setValue(merged);
      if (saved && text.getValue() !== nextText) text.setValue(nextText);
    };
    const rowsToText = debounce(value => {
      if (!active() || restoring) return;
      const next = applyLoraValuesToText(currentText(), value);
      if (next !== currentText()) text.setValue(next);
    });
    const offs = [
      text.on('change', () => {
        if (!active()) return;
        rowsToText.cancel();
        try { mergeText(); } catch (error) { console.error('[LoRA Manager] LoRA text merge failed:', error); }
      }),
      rows.on('change', value => {
        if (!active()) return;
        let normalized;
        try { normalized = normalizeRows(value); } catch (error) { console.error('[LoRA Manager] LoRA rows rejected:', error); return; }
        const signature = JSON.stringify(normalized);
        if (signature === observedRows) return;
        observedRows = signature;
        if (!restoring) rowsToText(normalized);
      }),
    ];
    const state = {
      node,
      restore(data) {
        if (!active()) return;
        rowsToText.cancel(); restoring = true;
        try {
          // The migration runs first, feeding the re-merge; older and rev 10 saves are not matched.
          const saved = originalAutocompleteLayout(data, true);
          mergeText(saved);
        } catch (error) { console.error('[LoRA Manager] LoRA restore merge failed:', error); }
        finally { restoring = false; }
      },
      dispose() {
        if (!alive) return;
        alive = false; rowsToText.cancel();
        offs.splice(0).forEach(fn => fn());
        if (states.get(key) === state) states.delete(key);
      },
    };
    states.set(key, state);
  }

  return () => {
    if (disposed) return;
    disposed = true;
    off();
    [...states.values()].forEach(state => state.dispose());
  };
}
