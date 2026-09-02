import { comfy } from '/comfy/api/v2.js';

const NODE = 'vsLinx_ImpactMultilineWildcardText';
let catalogue;

async function wildcards() {
  if (catalogue) return catalogue;
  try {
    const response = await comfy.backend.fetch('/impact/wildcards/list');
    const value = await response.json();
    const source = Array.isArray(value) ? value : value?.data ?? value?.list ?? [];
    catalogue = Array.isArray(source)
      ? source.map(String).filter((item) => item.length <= 1024).slice(0, 4096)
      : [];
  } catch (error) {
    console.warn('[vsLinx] Impact wildcard catalogue is unavailable', error);
    catalogue = [];
  }
  return catalogue;
}

function appendWildcard(node, value, picker) {
  if (!value || value === 'Select wildcard' || value === '<no wildcards found>') return;
  const text = node.widgets.get('text');
  if (!text) return;
  const current = String(text.getValue() ?? '');
  const separator = current.trim() && !current.trimEnd().endsWith(',') ? ', ' : '';
  text.setValue(`${current}${separator}${value}`);
  picker.setValue('Select wildcard');
}

comfy.defs.extend(NODE, (builder) => {
  builder.onCreated((node) => {
    const picker = node.widgets.add({
      type: 'combo',
      name: 'Add wildcard',
      value: 'Select wildcard',
      options: { values: ['Select wildcard'] },
      serialize: false,
    });
    picker.on('change', (value) => appendWildcard(node, String(value ?? ''), picker));
    void wildcards().then((items) => {
      picker.setOption('values', [
        'Select wildcard',
        ...(items.length ? items : ['<no wildcards found>']),
      ]);
      picker.setValue('Select wildcard');
    });
  });
});
