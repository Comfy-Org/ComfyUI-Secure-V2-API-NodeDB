import { comfy } from '/comfy/api/v2.js';

const MAX_TEXTS = 64;
comfy.defs.extend('Batch String', builder => {
  builder.addMenuItem({label: 'add input', order: 0, run(node) {
    const slots = node.inputs.all();
    if (slots.length >= MAX_TEXTS) throw new RangeError('Batch String supports at most64 inputs');
    node.inputs.add(`text${slots.length + 1}`, 'STRING');
  }});
  builder.addMenuItem({label: 'remove input', order: 1, run(node) {
    const slots = node.inputs.all();
    if (slots.length) node.inputs.remove(slots[slots.length - 1].id);
  }});
});
