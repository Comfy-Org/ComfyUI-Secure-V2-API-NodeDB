import { comfy } from '/comfy/api/v2.js';
const subscriptions = new Map();
function applySlotCount(node, value) {
  const count = Math.max(1, Math.min(20, value ?? 5));
  const slots = node.inputs.all().filter(input => /^input_\d+$/.test(input.name));
  if (slots.length < count) {
    for (let i = slots.length; i < count; i++) node.inputs.add(`input_${i}`, '*', { shape: 'optional' });
  } else if (slots.length > count) {
    for (const input of [...node.inputs.all()].reverse()) {
      const match = input.name.match(/^input_(\d+)$/);
      if (match && Number(match[1]) >= count) node.inputs.remove(input.id);
    }
  }
  node.setSize(node.getMinimumSize());
}
comfy.defs.extend('SwitchImmacTools', definition => {
  definition.onCreated(node => {
    subscriptions.get(node.id)?.();
    const widget = node.widgets.get('num_inputs');
    if (widget) {
      subscriptions.set(node.id, widget.on('change', value => applySlotCount(node, value)));
      applySlotCount(node, widget.getValue());
    }
  });
  definition.onConfigured(node => applySlotCount(node, node.widgets.get('num_inputs')?.getValue()));
  definition.onRemoved(node => { subscriptions.get(node.id)?.(); subscriptions.delete(node.id); });
});
