// Source adapter registered by lm_frontends.js (rev 10); backend HookGroup creation and trigger routing held.
// Its text/loras widgets exist only once the #11 widget types register (r4a); until then widgets.get returns nothing and it
// stays inert.
// r3 (review LORA10-B1): a workflow load now runs the native loadedGraphNode merge from onConfigured, fed by an
// original-format save ([meta, text, rows], which core places shifted by one) when there is one. The listeners ignore
// values of the wrong shape, which only a shifted placement or corruption produces.
// r4 (review of r3): every rows write passes through the shared LORAS setter's normalization, as the original's do.
import { debounce } from './stacker_syntax.js';
import { normalizeRows } from './catalogue_selection.js';
import { definitionOff } from './guest_compat.js';
import { originalAutocompleteLayout } from './original_layout.js';
import { createHookRowsFromText, createHookTextFromRows, createHookActiveNames,
  restoreCreateHookRows, planCreateHookInput, sameCreateHookRows } from './create_hook_logic.js';

const TYPE = 'Create Hook LoRA (LoraManager)';
const keyOf = node => JSON.stringify([node.graphId, node.id]);

// onActiveNames is an optional pack-owned bridge, not an SDK/provider stand-in.
// No default route, fabricated metadata or guessed graph traversal is supplied.
export function registerCreateHookLora(comfy, { onActiveNames } = {}) {
  const states = new Map();
  let disposed = false;
  const unsubscribe = definitionOff(comfy.defs.extend(TYPE, builder => {
    builder.onCreated(node => {
      if (disposed || node.isDeleted) return;
      const key = keyOf(node);
      states.get(key)?.dispose();
      const inputPlan = planCreateHookInput(node.inputs.all());
      node.setSerializeWidgets(true);
      if (inputPlan) node.inputs.add(inputPlan.name, inputPlan.type, { shape: inputPlan.shape });
      const text = node.widgets.get('text'), rows = node.widgets.get('loras');
      if (!text || !rows) {
        console.warn('LoRA Manager: text/loras widgets not found for Create Hook LoRA');
        return;
      }
      let alive = true, updating = false;
      let ownText = null, ownRows = null;
      const offs = [];
      const active = () => alive && !disposed && !node.isDeleted;
      const publish = value => onActiveNames?.(node, createHookActiveNames(value));
      const syncText = debounce(value => {
        if (!active()) return;
        updating = true;
        try {
          const next = createHookTextFromRows(text.getValue(), value);
          if (text.getValue() !== next) { ownText = next; text.setValue(next); }
        } finally { updating = false; }
      }); // Native 80ms debounce; not a queue-time serialization hook.
      // r4: every native Hook row write goes through the shared LORAS widget setter (web/comfyui/loras_widget.js 812-834;
      // its LORAS factory serves Create Hook too): the last duplicate is kept, clipStrength || strength, and expanded and
      // locked get their defaults. normalizeRows is that setter, as the Loader and WanVideo use it, plus the owned row
      // bounds, and it throws on rows outside them.
      const setRows = next => {
        const normalized = normalizeRows(next);
        if (sameCreateHookRows(rows.getValue(), normalized)) return;
        ownRows = normalized;
        rows.setValue(normalized);
      };
      offs.push(rows.on('change', value => {
        if (!active()) return;
        if (!Array.isArray(value)) return; // not rows: nothing to publish or write back
        if (ownRows && sameCreateHookRows(value, ownRows)) { ownRows = null; return; }
        if (updating) return;
        updating = true;
        try { publish(value); } finally { updating = false; }
        syncText(value);
      }));
      offs.push(text.on('change', value => {
        if (!active()) return;
        if (typeof value !== 'string') return; // not text: nothing to merge into the rows
        if (ownText !== null && value === ownText) { ownText = null; return; }
        if (updating) return;
        updating = true;
        try {
          setRows(createHookRowsFromText(value, rows.getValue() || []));
          publish(rows.getValue());
        } catch (error) { console.error('[LoRA Manager] Create Hook text merge failed:', error); }
        finally { updating = false; }
      }));
      const state = {
        restore(savedValue) {
          if (!active()) return false;
          // Native loadedGraphNode merges values without invoking callbacks.
          updating = true;
          try { setRows(restoreCreateHookRows(text.getValue(), savedValue)); }
          catch (error) { console.error('[LoRA Manager] Create Hook restore failed:', error); return false; }
          finally { updating = false; }
          return true;
        },
        configure(data) {
          // The automatic load path: web/comfyui/create_hook_lora.js 117-135 reads the saved rows by name and assigns
          // mergeLoras(text, savedRows) through the LORAS setter (setRows). An original-format save supplies both values
          // (migration first). A value that is not a string text and a row array, or rows outside the owned bounds, is left as
          // placed.
          if (!active()) return false;
          syncText.cancel();
          const saved = originalAutocompleteLayout(data, true);
          const savedText = saved ? saved.text : text.getValue();
          const savedRows = (saved ? saved.rows : rows.getValue()) ?? [];
          if (typeof savedText !== 'string' || !Array.isArray(savedRows)) return false;
          updating = true;
          try {
            setRows(restoreCreateHookRows(savedText, savedRows));
            if (saved && text.getValue() !== savedText) { ownText = savedText; text.setValue(savedText); }
          } catch (error) { console.error('[LoRA Manager] Create Hook restore failed:', error); return false; }
          finally { updating = false; }
          return true;
        },
        activeNames() { return createHookActiveNames(rows.getValue() || []); },
        dispose() {
          if (!alive) return;
          alive = false; syncText.cancel(); offs.splice(0).forEach(off => off());
          ownText = ownRows = null;
          if (states.get(key) === state) states.delete(key);
        },
      };
      states.set(key, state);
      // Caller restores the exact saved row cell. Automatic workflow slot
      // addressing and asynchronous delivery still require host/browser proof.
    });
    builder.onConfigured((node, data) => states.get(keyOf(node))?.configure(data));
    builder.onRemoved(node => states.get(keyOf(node))?.dispose());
  }));
  return {
    restore(node, savedValue) { return states.get(keyOf(node))?.restore(savedValue) || false; },
    activeNames(node) { return states.get(keyOf(node))?.activeNames() ?? new Set(); },
    dispose() {
      if (disposed) return;
      disposed = true; unsubscribe(); [...states.values()].forEach(state => state.dispose());
    },
  };
}
