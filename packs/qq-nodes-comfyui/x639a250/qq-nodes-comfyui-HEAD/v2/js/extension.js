import { comfy } from '/comfy/api/v2.js';

const states = new Map();

function updateLabel(state) {
  const index = Number(state.index.getValue() ?? 0);
  const suffix = state.total === undefined ? '' : ` of ${state.total}`;
  state.button.setLabel(index === 0 && state.total === undefined ? 'Reset' : `Reset - ${index}${suffix}`);
}

comfy.defs.extend('XY Grid Helper', (builder) => {
  builder.hideWidget('index');
  builder.onCreated((node) => {
    const index = node.widgets.get('index');
    if (!index) throw new Error('XY Grid Helper is missing its index widget');
    const button = node.widgets.add({
      type: 'button',
      name: 'qq_reset',
      value: null,
      serialize: false,
    });
    const state = { index, button, total: undefined };
    states.set(String(node.id), state);
    button.on('activate', () => {
      state.index.setValue(0);
      state.total = undefined;
      updateLabel(state);
    });
    updateLabel(state);
  });
  builder.onExecuted((node, result) => {
    const state = states.get(String(node.id));
    const values = result.raw?.total_images;
    if (!state || !Array.isArray(values) || values.length !== 1) return;
    const total = Number(values[0]);
    if (!Number.isSafeInteger(total) || total < 0) return;
    state.total = total;
    updateLabel(state);
  });
  builder.onRemoved((node) => states.delete(String(node.id)));
});

comfy.queue.onAfterRun((event) => {
  const accepted = Array.isArray(event.promptIds) ? event.promptIds.length : 0;
  if (accepted < 1) return;
  for (const state of states.values()) {
    state.index.setValue(Number(state.index.getValue() ?? 0) + accepted);
    updateLabel(state);
  }
});
