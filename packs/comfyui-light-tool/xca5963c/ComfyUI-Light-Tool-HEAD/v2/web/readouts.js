import { comfy } from '/comfy/api/v2.js';

// Readouts belong to this node. The worker uses widget handles only.
comfy.defs.extend('Light_Tool__ShowText_e50e80d2eddf1f698f3de946', (b) => {
  b.onExecuted((node, result) => {
    for (const widget of node.widgets.all()) node.widgets.remove(widget.name);
    const values = [...result.text];
    if (!values[0]) values.shift();
    for (let i = 0; i < values.length; i++) {
      node.widgets.add({name: `text2_${i}`, type: 'STRING', value: values[i],
        options: {multiline: true}, disabled: true, serialize: true});
    }
    node.setSizeConstraints({autoHeight: true});
  });
});
comfy.defs.extend('Light_Tool__ShowAnything_ccee18ec28ae9a83a98ccb75', (b) => {
  b.onExecuted((node, result) => {
    for (const widget of node.widgets.all()) node.widgets.remove(widget.name);
    const text = result.text;
    const displayText = Array.isArray(text) && text.length > 0
      ? text[0] : typeof text === 'string' ? text : String(text);
    node.widgets.add({name: 'output', type: 'STRING', value: displayText || '',
      options: {multiline: true}, disabled: true, serialize: true});
    node.setSizeConstraints({autoHeight: true});
  });
});
