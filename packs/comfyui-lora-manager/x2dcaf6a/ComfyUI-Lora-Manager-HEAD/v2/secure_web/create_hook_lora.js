// Opt-in source adapter; backend HookGroup creation and trigger routing held.
import { debounce } from './stacker_syntax.js';
import { createHookRowsFromText, createHookTextFromRows, createHookActiveNames,
  restoreCreateHookRows, planCreateHookInput, sameCreateHookRows } from './create_hook_logic.js';

const TYPE = 'Create Hook LoRA (LoraManager)';
const keyOf = node => JSON.stringify([node.graphId, node.id]);

// onActiveNames is an optional pack-owned bridge, not an SDK/provider stand-in.
// No default route, fabricated metadata or guessed graph traversal is supplied.
export function registerCreateHookLora(comfy, { onActiveNames } = {}) {
  const states = new Map();
  let disposed = false;
  const unsubscribe = comfy.defs.extend(TYPE, builder => {
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
      const setRows = next => {
        if (sameCreateHookRows(rows.getValue(), next)) return;
        ownRows = next;
        rows.setValue(next);
      };
      offs.push(rows.on('change', value => {
        if (!active()) return;
        if (ownRows && sameCreateHookRows(value, ownRows)) { ownRows = null; return; }
        if (updating) return;
        updating = true;
        try { publish(value); } finally { updating = false; }
        syncText(value);
      }));
      offs.push(text.on('change', value => {
        if (!active()) return;
        if (ownText !== null && value === ownText) { ownText = null; return; }
        if (updating) return;
        updating = true;
        try {
          setRows(createHookRowsFromText(value, rows.getValue() || []));
          publish(rows.getValue());
        } finally { updating = false; }
      }));
      const state = {
        restore(savedValue) {
          if (!active()) return false;
          // Native loadedGraphNode merges values without invoking callbacks.
          updating = true;
          try { setRows(restoreCreateHookRows(text.getValue(), savedValue)); }
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
    builder.onRemoved(node => states.get(keyOf(node))?.dispose());
  });
  return {
    restore(node, savedValue) { return states.get(keyOf(node))?.restore(savedValue) || false; },
    activeNames(node) { return states.get(keyOf(node))?.activeNames() ?? new Set(); },
    dispose() {
      if (disposed) return;
      disposed = true; unsubscribe(); [...states.values()].forEach(state => state.dispose());
    },
  };
}
