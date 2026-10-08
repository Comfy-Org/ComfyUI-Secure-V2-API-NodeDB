import { comfy } from '/comfy/api/v2.js';

const subscriptions = new Map();
function refresh(node, value = node.widgets.get('steps')?.getValue()) {
  if (!Number.isInteger(value) || value < 1 || value > 25) return;
  for (let index = 0; index <= 25; index++) {
    node.widgets.get(`sigma_${index}`)?.setHidden(index > value);
  }
  // Preserve all original widget values/serialization; layout is host-owned.
  node.setSizeConstraints({ autoHeight: true });
}
function dispose(node) {
  subscriptions.get(node.id)?.();
  subscriptions.delete(node.id);
}
function attach(node) {
  dispose(node);
  const steps = node.widgets.get('steps');
  if (!steps) return;
  subscriptions.set(node.id, steps.on('change', value => refresh(node, value)));
  refresh(node);
}
comfy.defs.extend('CustomScheduler', builder => {
  builder.onCreated(attach);
  builder.onConfigured(attach);
  builder.onRemoved(dispose);
});
