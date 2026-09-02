import { comfy } from '/comfy/api/v2.js';


export const FRONTEND_INTENTS = Object.freeze([
  'bounded-diagnostic-readouts',
  'stale-readout-reconciliation',
  'typed-link-rendering-host-owned',
]);


const HARD_LIMIT = 100;
const FIELDS = Object.freeze([
  ['type', 'type', 'text'],
  ['len()', 'len', 'text'],
  ['shape', 'shape', 'text'],
  ['type of first iter() item', 'firstIterItem', 'text'],
  ['value', 'value', 'textarea'],
]);
const ownedNames = new Map();


function nodeKey(node) {
  return `${node.graphId ?? ''}:${node.id ?? ''}`;
}


function removeOwned(node) {
  const key = nodeKey(node);
  for (const name of ownedNames.get(key) ?? []) {
    node.widgets.remove(name);
  }
  ownedNames.delete(key);
}


function safeText(value) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}


function setReadouts(node, result) {
  const items = result?.raw?.items;
  removeOwned(node);
  node.setSerializeWidgets(false);
  if (!Array.isArray(items)) return;

  const visible = items.slice(0, HARD_LIMIT);
  const multi = items.length > 1;
  const names = [];
  for (let index = 0; index < visible.length; index += 1) {
    const item = visible[index];
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    for (const [label, field, widgetType] of FIELDS) {
      const name = multi ? `${label} ${index}` : label;
      const raw = item[field];
      const widget = node.widgets.add({
          type: widgetType,
          name,
          value: safeText(raw),
          disabled: raw == null,
          options: widgetType === 'textarea'
            ? { multiline: true, read_only: true }
            : { read_only: true },
          serialize: false,
        });
      widget.setValue(safeText(raw));
      widget.setDisabled(raw == null);
      names.push(name);
    }
  }
  ownedNames.set(nodeKey(node), names);
  node.setSizeConstraints({ autoHeight: true });
}


comfy.defs.extend('WTFDebugNode', (builder) => {
  builder.onExecuted((node, result) => setReadouts(node, result));
  builder.onRemoved((node) => removeOwned(node));
});


// The legacy extension rewrote wildcard link records to preserve their
// colours.  V2 exposes typed, host-rendered links and keeps this serialized
// graph concern outside the guest extension.
