export function textPayload(result) {
  const value = result?.raw?.text ?? result?.text;
  return Array.isArray(value) ? value : [];
}


export function readout(node, name) {
  const existing = node.widgets.get(name);
  if (existing) return existing;
  const widget = node.widgets.add({
    type: 'textarea',
    name,
    value: '',
    disabled: true,
    options: { multiline: true, read_only: true },
    serialize: false,
  });
  widget.setDisabled(true);
  return widget;
}
