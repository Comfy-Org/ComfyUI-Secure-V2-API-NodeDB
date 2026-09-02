import { comfy } from '/comfy/api/v2.js';


const TYPES = [
  'Ratio Calculator',
  'Sequence Generator',
  'Display UI',
];


function ensureReadout(node) {
  const existing = node.widgets.get('text_box');
  if (existing) return existing;
  const widget = node.widgets.add({
    type: 'textarea',
    name: 'text_box',
    value: '',
    disabled: true,
    options: { multiline: true, read_only: true },
    serialize: true,
  });
  widget.setDisabled(true);
  return widget;
}


function textValue(node, result) {
  const raw = result?.raw?.text ?? result?.text ?? '';
  if (node.type === 'Display UI' && Array.isArray(raw)) {
    return raw.map((line) => `${line}\n`).join('\n');
  }
  return Array.isArray(raw) ? raw.join('') : String(raw ?? '');
}


comfy.defs.extend(TYPES, (builder) => {
  builder.onCreated((node) => {
    ensureReadout(node);
  });
  builder.onExecuted((node, result) => {
    ensureReadout(node).setValue(textValue(node, result));
    node.setSizeConstraints({ autoHeight: true });
  });
});
