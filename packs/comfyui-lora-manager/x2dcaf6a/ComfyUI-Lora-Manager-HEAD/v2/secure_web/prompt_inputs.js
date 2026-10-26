// Pinned Prompt dynamic sockets over the published typed node API.
// Registered by lm_frontends.js (rev 10); browser activation proof is the rev 10 BART smoke.
// Also migrates an original-format save ([meta, text], placed shifted by core) onto the text widget by name; on live the
// text input is a socket, so there is no widget and nothing happens.
import { definitionOff } from './guest_compat.js';
import { originalAutocompleteLayout } from './original_layout.js';

const TYPE = 'Prompt (LoraManager)';
const PREFIX = 'trigger_words';

/** @param {import('../comfy-api').NodeHandle} node */
function inputs(node) {
  const slots = node.inputs.all();
  return slots;
}

/** @param {readonly import('../comfy-api').InputSlotHandle[]} slots */
function renumber(slots) {
  let ordinal = 1;
  for (const slot of slots) {
    if (!slot.name.startsWith(PREFIX)) continue;
    const name = `${PREFIX}${ordinal++}`;
    if (slot.name !== name) slot.modify({ name });
  }
}

/** @param {import('../comfy-api').Comfy} comfy */
export function registerPromptInputs(comfy) {
  let disposed = false;
  const unsubscribe = definitionOff(comfy.defs.extend(TYPE, builder => {
    builder.onConfigured((node, data) => {
      if (disposed || node.isDeleted) return;
      const saved = originalAutocompleteLayout(data, false);
      const text = saved && node.widgets.get('text');
      if (text && text.getValue() !== saved.text) text.setValue(saved.text);
    });
    builder.onConnectionsChanged((node, event) => {
      if (disposed || node.isDeleted || event.reconstructing || event.side !== 'input') return;
      if (event.peerNodeId === undefined) return;
      const slots = inputs(node);
      const slot = slots[event.index];
      if (!slot || !slot.name.startsWith(PREFIX)) return;
      const count = slots.filter(input => input.name.startsWith(PREFIX)).length;
      const last = slots.findLastIndex(input => input.name.startsWith(PREFIX));
      const adding = event.connected && (event.index === count || event.index === last);
      renumber(slots);
      // forceInput and tooltip have no published SlotOptions field in this
      // declaration. Preserve the socket as STRING; record this declaration
      // gap rather than inventing options or touching renderer prototypes.
      if (adding) node.inputs.add(`${PREFIX}${count + 1}`, 'STRING');
      if (!event.connected && count > 1 && event.index !== last && !slot.isConnected) {
        node.inputs.remove(slot.id);
        renumber(node.inputs.all());
      }
    });
  }));
  return () => {
    if (disposed) return;
    disposed = true;
    unsubscribe();
  };
}
