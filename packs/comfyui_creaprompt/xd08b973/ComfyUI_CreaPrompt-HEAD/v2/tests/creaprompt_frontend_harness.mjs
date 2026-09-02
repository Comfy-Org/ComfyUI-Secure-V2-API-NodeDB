import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const JS = path.resolve(HERE, '../js/dynamique-ui.js');
const CATALOG_JS = path.resolve(HERE, '../js/catalog.js');

function check(condition, message) {
  if (!condition) throw new Error(message);
}

async function drain() {
  for (let index = 0; index < 12; index += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

class Widget {
  constructor(def) {
    this.name = def.name;
    this.value = def.value;
    this.type = def.type;
    this.options = { ...(def.options ?? {}) };
    this.serialize = def.serialize;
    this.hidden = Boolean(def.hidden);
    this.listeners = new Map();
  }
  getValue() { return this.value; }
  setValue(value) {
    this.value = value;
    for (const listener of this.listeners.get('change') ?? []) listener(value);
  }
  setHidden(value) { this.hidden = Boolean(value); }
  setOption(key, value) { this.options[key] = value; }
  on(event, listener) {
    const listeners = this.listeners.get(event) ?? [];
    listeners.push(listener);
    this.listeners.set(event, listeners);
  }
  activate(event = { clientX: 10, clientY: 20 }) {
    for (const listener of this.listeners.get('activate') ?? []) listener(event);
  }
}

function makeNode(id, json = '{}') {
  const items = [new Widget({ type: 'text', name: '__csv_json', value: json })];
  return {
    id,
    graphId: 'graph-1',
    widgets: {
      get(name) { return items.find((item) => item.name === name); },
      add(def) {
        check(!items.some((item) => item.name === def.name), `duplicate widget ${def.name}`);
        const item = new Widget(def);
        items.push(item);
        return item;
      },
      remove(name) {
        const index = items.findIndex((item) => item.name === name);
        if (index < 0) return false;
        items.splice(index, 1);
        return true;
      },
      names() { return items.map((item) => item.name); },
      all() { return [...items]; },
    },
  };
}

const storage = new Map();
const menus = [];
const promptAnswers = [];
const hooks = {};
let selector;
const comfy = {
  defs: {
    extend(value, apply) {
      selector = value;
      apply({
        onCreated(fn) { hooks.created = fn; },
        onConfigured(fn) { hooks.configured = fn; },
        onRemoved(fn) { hooks.removed = fn; },
      });
    },
  },
  storage: {
    async get(key) { return storage.get(key); },
    async set(key, value) { storage.set(key, value); },
    async remove(key) { storage.delete(key); },
  },
  ui: {
    async prompt() { return promptAnswers.shift(); },
    showMenu(def) { menus.push(def); return { close() {} }; },
  },
};

const context = vm.createContext({ console, Date, encodeURIComponent, setImmediate });
const facade = new vm.SyntheticModule(
  ['comfy'],
  function initialize() { this.setExport('comfy', comfy); },
  { context, identifier: '/comfy/api/v2.js' },
);
const modules = new Map();
async function moduleFor(filename) {
  if (modules.has(filename)) return modules.get(filename);
  const source = fs.readFileSync(filename, 'utf8');
  const module = new vm.SourceTextModule(source, { context, identifier: filename });
  modules.set(filename, module);
  await module.link(async (specifier, referencing) => {
    if (specifier === '/comfy/api/v2.js') return facade;
    if (specifier === './catalog.js') return moduleFor(CATALOG_JS);
    throw new Error(`unexpected import ${specifier} from ${referencing.identifier}`);
  });
  return module;
}

await (await moduleFor(JS)).evaluate();
check(selector === 'CreaPrompt_0', 'wrong frontend selector');
for (const name of ['created', 'configured', 'removed']) {
  check(typeof hooks[name] === 'function', `missing ${name} hook`);
}
for (const name of [
  'window', 'parent', 'document', 'fetch', 'XMLHttpRequest', 'WebSocket',
  'app', 'api', 'LiteGraph', 'prompt', 'confirm', 'alert',
]) {
  check(vm.runInContext(`typeof ${name}`, context) === 'undefined', `${name} leaked`);
}

const node = makeNode('1');
hooks.created(node, { restored: false, loading: false });
const jsonWidget = node.widgets.get('__csv_json');
check(jsonWidget.hidden, 'serialized JSON widget remained visible');
const defaults = [
  'Woman', 'Haircuts_Thomas_Buyle', 'Haircolors_Thomas_Buyle',
  'Woman_Dress_Malapris_PJ', 'Places', 'Image_Quality', 'Cameras', 'Lighting',
];
for (const name of defaults) check(node.widgets.get(name), `missing default ${name}`);
check(node.widgets.names().filter((name) => name.includes('Categories Preset')).length === 3,
  'preset button census changed');
check(Object.keys(JSON.parse(jsonWidget.getValue())).length === 8, 'default JSON changed');

const woman = node.widgets.get('Woman');
woman.setValue('portrait subject');
check(JSON.parse(jsonWidget.getValue()).Woman === 'portrait subject', 'combo did not commit');

node.widgets.get('➕ Add Category').activate();
let menu = menus.pop();
const action = menu.items.find((item) => item.label === 'Animals');
check(action, 'Animals add action missing');
action.run();
check(node.widgets.get('Animals'), 'category was not added');
check(JSON.parse(jsonWidget.getValue()).Animals === 'disabled', 'added value changed');

node.widgets.get('➖ Remove Category').activate();
menu = menus.pop();
menu.items.find((item) => item.label === 'Animals').run();
check(!node.widgets.get('Animals'), 'category was not removed');

promptAnswers.push('Portrait choices');
node.widgets.get('💾 Save Categories Preset').activate();
await drain();
const index = JSON.parse(storage.get('ComfyUI.CreaPrompt/presets/index.json'));
const [[presetId, presetName]] = Object.entries(index);
check(presetName === 'Portrait choices', 'preset name changed');
check(JSON.parse(storage.get(`ComfyUI.CreaPrompt/presets/${presetId}.json`)).Woman
  === 'portrait subject', 'preset body changed');

woman.setValue('temporary');
node.widgets.get('📂 Load Categories Preset').activate();
await drain();
menu = menus.pop();
await menu.items[0].run();
check(node.widgets.get('Woman').getValue() === 'portrait subject', 'preset did not load');

node.widgets.get('🗑️ Delete Categories Preset').activate();
await drain();
menu = menus.pop();
await menu.items[0].run();
check(!storage.has(`ComfyUI.CreaPrompt/presets/${presetId}.json`), 'preset body remained');
check(Object.keys(JSON.parse(storage.get('ComfyUI.CreaPrompt/presets/index.json'))).length === 0,
  'preset index remained');

node.widgets.get('🧹 Remove All').activate();
menu = menus.pop();
menu.items[0].run();
check(Object.keys(JSON.parse(jsonWidget.getValue())).length === 0, 'remove all failed');

const restored = makeNode('2', JSON.stringify({ Places: 'studio', Woman: 'restored' }));
hooks.created(restored, { restored: false, loading: true });
check(!restored.widgets.get('Places'), 'load barrier mutated a partial node');
hooks.configured(restored, {});
check(restored.widgets.get('Places').getValue() === 'studio', 'restored Places changed');
check(restored.widgets.get('Woman').getValue() === 'restored', 'restored Woman changed');
check(Object.keys(JSON.parse(restored.widgets.get('__csv_json').getValue())).length === 2,
  'restored JSON changed');

hooks.removed(node);
hooks.removed(restored);
console.log('creaprompt frontend harness: PASS');
