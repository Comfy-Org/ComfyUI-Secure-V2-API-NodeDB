import { comfy } from '/comfy/api/v2.js';

const subscriptions = new Map();
const key = node => `${node.graphId ?? ''}:${node.id}`;
function bounded(value) {
  if (typeof value !== 'string') throw new TypeError('AivParam text must be a string');
  if (new TextEncoder().encode(value).byteLength > 64 * 1024) throw new RangeError('AivParam text exceeds 64KiB');
  return value;
}
function display(value) {
  if (typeof value !== 'string') throw new TypeError('AivParam text must be a string');
  if (new TextEncoder().encode(value).byteLength > 128 * 1024) throw new RangeError('AivParam restored text exceeds 128KiB');
  return bounded(value.replace(/\\([{}])/g, '$1'));
}
function serialized(value) {
  return bounded(value).replace(/{/g, '\\{').replace(/}/g, '\\}');
}
function dispose(node) {
  const id = key(node);
  subscriptions.get(id)?.();
  subscriptions.delete(id);
}
function attach(node) {
  dispose(node);
  const widget = node.widgets.get('text_param');
  if (!widget) return;
  // Source setters clean restored values; editing remains in the native widget.
  const value = widget.getValue();
  if (typeof value === 'string' && new TextEncoder().encode(value).byteLength <= 128 * 1024) {
    const cleaned = value.replace(/\\([{}])/g, '$1');
    if (new TextEncoder().encode(cleaned).byteLength <= 64 * 1024 && cleaned !== value) widget.setValue(display(value));
  }
  subscriptions.set(key(node), widget.on('beforeSerialize', event => {
    event.setSerializedValue(serialized(event.value));
  }));
}
comfy.onWorkflowLoaded(() => {
  for (const unsubscribe of subscriptions.values()) unsubscribe();
  subscriptions.clear();
});
comfy.defs.extend('AivParam', builder => {
  builder.onCreated(attach);
  builder.onConfigured(attach);
  builder.onRemoved(dispose);
});
