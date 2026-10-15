// Typed consumer of the published host-captured reconstruction context.
// Dynamic tooltips have no public SlotOptions field yet; this is not a full
// frontend certificate. Never inspect host globals, stack traces or graph paths.
const TYPE = 'Lora Stack Combiner (LoraManager)';
const PATTERN = /^lora_stack\d+$/;

/** @param {import('../comfy-api').NodeHandle} node */
function slots(node) {
  const result = node.inputs.all();
  return result;
}

/** @param {readonly import('../comfy-api').InputSlotHandle[]} inputs */
function renumber(inputs) {
  let ordinal = 1;
  for (const input of inputs) {
    if (!PATTERN.test(input.name)) continue;
    const name = `lora_stack${ordinal++}`;
    if (input.name !== name) input.modify({ name });
  }
}

/** @param {import('../comfy-api').Comfy} comfy */
export function registerStackInputs(comfy) {
  let disposed = false;
  const unsubscribe = comfy.defs.extend(TYPE, builder => {
    builder.onCreated(node => {
      if (disposed || node.isDeleted) return;
      const inputs = slots(node);
      if (inputs.some(slot => slot.name === 'lora_stack_a' || slot.name === 'lora_stack_b')) return;
      const count = inputs.filter(slot => PATTERN.test(slot.name)).length;
      for (let ordinal = count + 1; ordinal <= 2; ordinal++)
        node.inputs.add(`lora_stack${ordinal}`, 'LORA_STACK');
    });
    builder.onConnectionsChanged((node, event) => {
      if (disposed || event.reconstructing || node.isDeleted || event.side !== 'input') return;
      // Native LiteGraph link-bearing callbacks expose the peer even on
      // disconnect via this dispatcher. No-link notifications are left alone,
      // just like the pinned link_info guard; no peer graph lookup is needed.
      if (event.peerNodeId === undefined) return;
      const inputs = slots(node);
      const input = inputs[event.index];
      if (!input || !PATTERN.test(input.name)) return;
      const count = inputs.filter(slot => PATTERN.test(slot.name)).length;
      const adding = event.connected && (event.index === count ||
        event.index === inputs.findLastIndex(slot => PATTERN.test(slot.name)));
      renumber(inputs);
      if (adding) node.inputs.add(`lora_stack${count + 1}`, 'LORA_STACK');
      if (!event.connected && count > 2) {
        const current = node.inputs.all();
        if (event.index !== current.findLastIndex(slot => PATTERN.test(slot.name))) {
          node.inputs.remove(input.id);
          renumber(node.inputs.all());
        }
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
