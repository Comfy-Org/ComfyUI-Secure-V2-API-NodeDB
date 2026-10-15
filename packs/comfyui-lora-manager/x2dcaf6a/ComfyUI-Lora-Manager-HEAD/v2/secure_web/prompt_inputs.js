// Pinned Prompt dynamic sockets over the published typed node API.
// Source candidate: browser activation and serialization proof remain pending.
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
  const unsubscribe = comfy.defs.extend(TYPE, builder => {
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
  });
  if (typeof unsubscribe !== 'function') throw new Error('Definition unsubscribe contract is unavailable');
  return () => {
    if (disposed) return;
    disposed = true;
    unsubscribe();
  };
}
