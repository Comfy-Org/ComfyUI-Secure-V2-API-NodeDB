import { comfy } from '/comfy/api/v2.js';
import { readout, textPayload } from './utils.js';


comfy.defs.extend('SDPromptReader', (builder) => {
  builder.onCreated((node) => {
    readout(node, 'positive');
    readout(node, 'negative');
    readout(node, 'setting');
    const size = node.getSize();
    node.setSize({ width: size.width, height: size.height * 3 });
  });
  builder.onExecuted((node, result) => {
    const text = textPayload(result);
    node.widgets.get('positive')?.setValue(String(text[0] ?? ''));
    node.widgets.get('negative')?.setValue(String(text[1] ?? ''));
    node.widgets.get('setting')?.setValue(String(text[2] ?? ''));
  });
});
