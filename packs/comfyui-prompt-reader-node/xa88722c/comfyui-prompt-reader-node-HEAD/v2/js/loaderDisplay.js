import { comfy } from '/comfy/api/v2.js';
import { readout, textPayload } from './utils.js';


comfy.defs.extend('SDBatchLoader', (builder) => {
  builder.onCreated((node) => readout(node, 'fileList'));
  builder.onExecuted((node, result) => {
    const text = textPayload(result);
    node.widgets.get('fileList')?.setValue(String(text[0] ?? ''));
  });
});
