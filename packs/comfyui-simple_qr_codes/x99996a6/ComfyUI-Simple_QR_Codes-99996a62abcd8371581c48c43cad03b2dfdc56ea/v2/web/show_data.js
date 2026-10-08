import { comfy } from '/comfy/api/v2.js';
// Upstream ships no ./js. Migrate only its own data-widget event intent.
comfy.defs.extend('🎭 ShowData', builder => {
  builder.onExecuted((node, result) => {
    const text = result?.raw?.data;
    if (typeof text !== 'string' || new TextEncoder().encode(text).length > 65536)
      throw new Error('ShowData received an invalid bounded text result');
    const widget = node.widgets.get('data');
    if (!widget) throw new Error('ShowData owning data widget is unavailable');
    widget.setValue(text);
  });
});
