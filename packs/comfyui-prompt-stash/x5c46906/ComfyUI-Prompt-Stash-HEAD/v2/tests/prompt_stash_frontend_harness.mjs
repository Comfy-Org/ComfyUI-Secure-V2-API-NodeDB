import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';


function check(condition, message) {
  if (!condition) throw new Error(message);
}


async function drain() {
  for (let index = 0; index < 30; index += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}


class FakeWidget {
  constructor(name, value, type = 'text', options = {}) {
    this.name = name;
    this.value = value;
    this.widgetType = type;
    this.options = { ...options };
    this.listeners = new Map();
    this.disabled = false;
    this.label = name;
  }

  getValue() { return this.value; }
  setValue(value) {
    if (Object.is(this.value, value)) return;
    const previous = this.value;
    this.value = value;
    for (const listener of this.listeners.get('change') ?? []) {
      listener(value, previous);
    }
  }
  getOptions() { return structuredClone(this.options); }
  setOption(name, value) { this.options[name] = structuredClone(value); }
  setLabel(value) { this.label = value; }
  setDisabled(value) { this.disabled = Boolean(value); }
  on(event, listener) {
    const listeners = this.listeners.get(event) ?? [];
    listeners.push(listener);
    this.listeners.set(event, listeners);
    return () => this.listeners.set(
      event, (this.listeners.get(event) ?? []).filter((item) => item !== listener),
    );
  }
  activate() {
    for (const listener of this.listeners.get('activate') ?? []) listener();
  }
}


const storage = new Map();
const storageWrites = [];
const downloads = [];
const notifications = [];
const fetches = [];
const extensions = new Map();
const backendListeners = new Map();
let interrupted;
let picked;

const graphNodes = new Map();
const comfy = {
  defs: {
    extend(selector, apply) {
      const hooks = {};
      apply({
        onPromptSerialize(run) { hooks.promptSerialize = run; },
        onCreated(run) { hooks.created = run; },
        onExecuted(run) { hooks.executed = run; },
        onRemoved(run) { hooks.removed = run; },
      });
      extensions.set(selector, hooks);
    },
  },
  storage: {
    async get(key) { return storage.get(key); },
    async set(key, value) {
      storageWrites.push([key, value]);
      storage.set(key, value);
    },
  },
  files: {
    async pick() { return picked; },
    async download(value) { downloads.push(value); },
  },
  commands: { notify(value) { notifications.push(value); } },
  graph: { node(id) { return graphNodes.get(String(id)); } },
  backend: {
    on(event, run) { backendListeners.set(event, run); return () => {}; },
    async fetch(route, init) {
      fetches.push([route, init]);
      return { ok: true, status: 200 };
    },
  },
  queue: { onInterrupted(run) { interrupted = run; return () => {}; } },
};


const context = vm.createContext({
  console,
  Date,
  JSON,
  Object,
  Promise,
  RangeError,
  TextDecoder,
  TextEncoder,
  TypeError,
  Uint8Array,
  structuredClone,
});
const facade = new vm.SyntheticModule(
  ['comfy'],
  function initialize() { this.setExport('comfy', comfy); },
  { context, identifier: '/comfy/api/v2.js' },
);
const sourcePath = path.resolve(process.env.TARGET_JS);
const source = fs.readFileSync(sourcePath, 'utf8');
const module = new vm.SourceTextModule(source, { context, identifier: sourcePath });
await module.link(async (specifier) => {
  if (specifier === '/comfy/api/v2.js') return facade;
  throw new Error(`unexpected import: ${specifier}`);
});
await module.evaluate();

check([...extensions.keys()].join(',') ===
  'PromptStashSaver,PromptStashPassthrough,PromptStashManager',
'frontend node census changed');
check(typeof backendListeners.get('secure-node-interaction') === 'function',
  'interaction listener missing');
check(typeof interrupted === 'function', 'interrupt cleanup missing');
for (const name of [
  'window', 'parent', 'document', 'fetch', 'XMLHttpRequest', 'WebSocket',
  'localStorage', 'app', 'LiteGraph',
]) {
  check(vm.runInContext(`typeof ${name}`, context) === 'undefined', `${name} leaked`);
}


function makeNode(type, values, id) {
  const widgetList = Object.entries(values).map(
    ([name, value]) => new FakeWidget(name, value),
  );
  const slots = new Map(Object.keys(values).map((name) => [name, {
    name,
    changes: [],
    modify(value) { this.changes.push(value); },
    source() { return undefined; },
  }]));
  const node = {
    id: String(id),
    comfyClass: type,
    widgetList,
    widgets: {
      get(name) { return widgetList.find((item) => item.name === name); },
      at(index) { return widgetList[index]; },
      add(definition) {
        const item = new FakeWidget(
          definition.name, definition.value, definition.type,
          definition.options,
        );
        item.definition = definition;
        widgetList.push(item);
        return item;
      },
    },
    inputs: { byName(name) { return slots.get(name); } },
  };
  graphNodes.set(node.id, node);
  return node;
}


const saverHooks = extensions.get('PromptStashSaver');
const saver = makeNode('PromptStashSaver', {
  use_input_text: false,
  text: '',
  prompt_text: '',
  save_as_key: '',
  load_saved: 'None',
  prompt_lists: 'default',
}, 11);
saverHooks.created(saver);
await drain();
check(storageWrites.length === 1, 'default library was not initialized once');
const initial = JSON.parse(storage.values().next().value);
check(Object.keys(initial.lists).join(',') === 'default,characters,backgrounds',
  'default library census changed');
check(JSON.stringify(saverHooks.promptSerialize(saver)) ===
  JSON.stringify({ omitInputs: ['text'] }), 'inactive input was not projected');
saver.widgets.get('use_input_text').setValue(true);
check(JSON.stringify(saverHooks.promptSerialize(saver)) ===
  JSON.stringify({ omitInputs: [] }), 'active input was projected away');

const save = saver.widgets.get('Save Prompt');
const remove = saver.widgets.get('Delete Selected');
check(save?.definition.serialize === false, 'save button became workflow state');
check(remove?.definition.serialize === false, 'delete button became workflow state');
saver.widgets.get('use_input_text').setValue(false);
saver.widgets.get('save_as_key').setValue('portrait');
saver.widgets.get('prompt_text').setValue('dramatic portrait');
save.activate();
await drain();
let library = JSON.parse(storage.values().next().value);
check(library.lists.default.portrait === 'dramatic portrait', 'save failed');
check(saver.widgets.get('load_saved').getValue() === 'portrait',
  'saved prompt was not selected');

saver.widgets.get('prompt_text').setValue('changed locally');
await drain();
check(saver.widgets.get('load_saved').getValue() === 'None',
  'editing did not detach the selected saved prompt');
saver.widgets.get('load_saved').setValue('portrait');
await drain();
check(saver.widgets.get('prompt_text').getValue() === 'dramatic portrait',
  'saved prompt did not load');
remove.activate();
await drain();
library = JSON.parse(storage.values().next().value);
check(!Object.hasOwn(library.lists.default, 'portrait'), 'delete failed');

saverHooks.executed(saver, {
  raw: { prompt_stash: { text: 'linked result', adopt_input: true } },
});
await drain();
check(saver.widgets.get('prompt_text').getValue() === 'linked result',
  'execution UI result did not update visible prompt text');


const managerHooks = extensions.get('PromptStashManager');
const manager = makeNode('PromptStashManager', { new_list_name: '' }, 17);
managerHooks.created(manager);
await drain();
manager.widgets.get('new_list_name').setValue('favorites');
manager.widgets.get('Add List').activate();
await drain();
library = JSON.parse(storage.values().next().value);
check(Object.hasOwn(library.lists, 'favorites'), 'manager add-list failed');
check(manager.widgets.get('existing_lists').getValue() === 'favorites',
  'new list was not selected');

manager.widgets.get('Export').activate();
await drain();
check(downloads.length === 1, 'export was not downloaded');
check(downloads[0].mimeType === 'application/json', 'export MIME changed');

picked = {
  name: 'stash.json',
  bytes: new TextEncoder().encode(JSON.stringify({
    version: '1.0',
    lists: { default: { imported: 'hello' }, favorites: { one: '1' } },
  })),
};
manager.widgets.get('Import').activate();
await drain();
library = JSON.parse(storage.values().next().value);
check(library.lists.default.imported === 'hello', 'import merge failed');
check(library.lists.favorites.one === '1', 'list merge failed');
check(notifications.some((item) => item.severity === 'success'),
  'successful import was not reported');


const passthroughHooks = extensions.get('PromptStashPassthrough');
const passthrough = makeNode('PromptStashPassthrough', {
  use_input_text: false,
  text: '',
  prompt_text: '',
  pause_to_edit: true,
}, 15);
passthroughHooks.created(passthrough);
backendListeners.get('secure-node-interaction')({
  kind: 'prompt-await',
  request_id: 'req-1',
  node_id: '15',
  payload: { variant: 'prompt-stash-passthrough-v1', text: 'initial' },
});
check(passthrough.widgets.get('prompt_text').getValue() === 'initial',
  'pause text did not enter the editor');
check(passthrough.widgets.get('Continue').disabled === false,
  'continue remained disabled while paused');
passthrough.widgets.get('prompt_text').setValue('edited');
passthrough.widgets.get('Continue').activate();
await drain();
check(fetches.length === 1, 'continue did not answer the broker');
check(fetches[0][0] === '/secure-nodes/interactions/respond',
  'continue used the wrong bounded route');
const response = JSON.parse(fetches[0][1].body);
check(response.request_id === 'req-1', 'interaction request id changed');
check(JSON.stringify(response.response) ===
  JSON.stringify({ action: 'continue', text: 'edited' }),
'edited response changed');
check(passthrough.widgets.get('Continue').disabled === true,
  'continue did not disable after response');

backendListeners.get('secure-node-interaction')({
  kind: 'prompt-await', request_id: 'req-2', node_id: '15',
  payload: { variant: 'prompt-stash-passthrough-v1', text: 'next' },
});
interrupted();
check(passthrough.widgets.get('Continue').disabled === true,
  'queue interruption left a live continue action');

saverHooks.removed(saver);
managerHooks.removed(manager);
passthroughHooks.removed(passthrough);
console.log('prompt stash frontend harness: PASS');
