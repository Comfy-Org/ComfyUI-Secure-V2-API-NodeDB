import { comfy } from '/comfy/api/v2.js';
import { readout, textPayload } from './utils.js';


comfy.defs.extend('SDParameterExtractor', (builder) => {
  builder.onCreated((node) => readout(node, 'value_display'));
  builder.onExecuted((node, result) => {
    const text = textPayload(result);
    const values = Array.isArray(text[0]) ? text[0].map(String) : [];
    const parameter = node.widgets.get('parameter');
    node.widgets.get('value_display')?.setValue(String(text[1] ?? ''));
    parameter?.setOption('values', values);
    if (parameter?.getValue() === 'parameters not loaded' && values.length) {
      parameter.setValue(values[0]);
    }
  });
});
