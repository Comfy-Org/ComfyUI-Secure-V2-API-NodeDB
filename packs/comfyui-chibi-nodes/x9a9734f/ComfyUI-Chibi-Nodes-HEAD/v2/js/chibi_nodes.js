import { comfy } from '/comfy/api/v2.js';

// Readouts write workflow-owned widgets; no shared cache, timers or node map.
const MAX_TEXT_BYTES = 1024 * 1024;
comfy.defs.extend('Textbox', builder => {
  builder.onExecuted((node, result) => {
    const value = result?.text;
    if (value === undefined) return;
    const text = Array.isArray(value) ? value.join('') : value;
    if (typeof text !== 'string' || new TextEncoder().encode(text).length > MAX_TEXT_BYTES)
      throw new RangeError('Textbox execution text exceeds the bounded string contract');
    node.widgets.get('text')?.setValue(text);
  });
});
comfy.defs.extend('ImageSizeInfo', builder => {
  builder.addWidget({ type: 'INT', name: 'width', value: 0 });
  builder.addWidget({ type: 'INT', name: 'height', value: 0 });
  builder.onExecuted((node, result) => {
    for (const name of ['width', 'height']) {
      const value = result?.[name]?.[0];
      if (!Number.isSafeInteger(value) || value < 0 || value > 32768)
        throw new RangeError('ImageSizeInfo execution dimensions exceed the bounded scalar contract');
      node.widgets.get(name)?.setValue(value);
    }
  });
});
