import { comfy } from '/comfy/api/v2.js';


const LAST_SEED_LABEL = '(Use last queued seed)';
const SPECIAL_RANDOM = -1;
const SPECIAL_INCREMENT = -2;
const SPECIAL_DECREMENT = -3;
const SPECIAL = new Set([SPECIAL_RANDOM, SPECIAL_INCREMENT, SPECIAL_DECREMENT]);
const controls = new Map();


function randomSeed(widget) {
  const options = widget.getOptions();
  const maximum = Math.min(1125899906842624, Number(options.max));
  const minimum = Math.max(0, Number(options.min));
  const quantum = (Number(options.step) || 10) / 10;
  const count = Math.max(1, Math.floor((maximum - minimum) / quantum));
  return Math.floor(Math.random() * count) * quantum + minimum;
}


function chooseSeed(state) {
  const input = Number(state.seed.getValue());
  let value;
  if (input === SPECIAL_INCREMENT && Number.isFinite(state.lastSeed)) {
    value = state.lastSeed + 1;
  } else if (input === SPECIAL_DECREMENT && Number.isFinite(state.lastSeed)) {
    value = state.lastSeed - 1;
  } else if (SPECIAL.has(input)) {
    value = randomSeed(state.seed);
  } else {
    value = input;
  }
  state.lastSeed = value;
  state.lastButton.setLabel(String(value));
  state.lastButton.setDisabled(false);
  return value;
}


function install(node) {
  const seed = node.widgets.get('seed');
  if (!seed) throw new Error('SDParameterGenerator is missing its seed widget');
  seed.setValue(SPECIAL_RANDOM);
  const randomEach = node.widgets.add({
    type: 'button', name: 'Randomize seed each time', value: null,
    options: { serialize: false }, serialize: false,
  });
  const fixed = node.widgets.add({
    type: 'button', name: 'New fixed random seed', value: null,
    options: { serialize: false }, serialize: false,
  });
  const lastButton = node.widgets.add({
    type: 'button', name: LAST_SEED_LABEL, value: null,
    options: { serialize: false }, serialize: false,
  });
  const state = { seed, lastButton, lastSeed: undefined, queuedSeed: undefined };
  lastButton.setDisabled(true);
  randomEach.on('activate', () => seed.setValue(SPECIAL_RANDOM));
  fixed.on('activate', () => seed.setValue(randomSeed(seed)));
  lastButton.on('activate', () => {
    if (Number.isFinite(state.lastSeed)) seed.setValue(state.lastSeed);
    lastButton.setLabel(LAST_SEED_LABEL);
    lastButton.setDisabled(true);
  });
  seed.on('beforeSerialize', (event) => {
    if (event.context === 'workflow') return;
    if (state.queuedSeed === undefined) state.queuedSeed = chooseSeed(state);
    event.setSerializedValue(state.queuedSeed);
  });
  controls.set(node.id, state);
}


comfy.queue.onBeforeRun(() => {
  for (const state of controls.values()) state.queuedSeed = undefined;
  return () => {
    for (const state of controls.values()) state.queuedSeed = undefined;
  };
});


comfy.defs.extend('SDParameterGenerator', (builder) => {
  builder.onCreated((node) => install(node));
  builder.onRemoved((node) => controls.delete(node.id));
  builder.addMenuItem({
    label: 'Randomize seed each time',
    run: (node) => controls.get(node.id)?.seed.setValue(SPECIAL_RANDOM),
  });
  builder.addMenuItem({
    label: 'Use last queued seed',
    run: (node) => {
      const state = controls.get(node.id);
      if (state && Number.isFinite(state.lastSeed)) state.seed.setValue(state.lastSeed);
    },
  });
});
