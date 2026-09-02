/** Iframe-safe behavior harness for the real converted WD14 frontend module. */
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const PACK_JS = path.resolve(HERE, '../js/wd14tagger.js');
const TAGGER = 'WD14Tagger|pysssss';

function assert(condition, message) {
  if (!condition) throw new Error(`ASSERT: ${message}`);
}

const definitions = [
  { type: TAGGER, outputs: [{ type: 'STRING' }] },
  { type: 'PreviewImage', outputs: [{ type: 'IMAGE' }] },
  { type: 'TextNode', outputs: [{ type: 'STRING' }] },
];
const registrations = new Map();
const dialogs = [];
const queued = [];
let createdTagger;

function builderFor(type) {
  const record = registrations.get(type) ?? { executed: [], menus: [] };
  registrations.set(type, record);
  return {
    onExecuted(callback) { record.executed.push(callback); return this; },
    addMenuItem(item) { record.menus.push(item); return this; },
  };
}

class Collection {
  constructor(values = []) { this.values = [...values]; }
  all() { return [...this.values]; }
  names() { return this.values.map((item) => item.name); }
  add(spec) { const item = { ...spec }; this.values.push(item); return item; }
  remove(name) {
    const index = this.values.findIndex((item) => item.name === name);
    if (index >= 0) this.values.splice(index, 1);
  }
}

function makeNode(type, id, outputs = []) {
  const properties = new Map();
  const node = {
    id,
    type,
    graphId: 'root',
    widgets: new Collection(),
    outputs: new Collection(outputs),
    position: { x: 10, y: 20 },
    size: { width: 180, height: 120 },
    getPosition() { return this.position; },
    setPosition(value) { this.position = value; },
    getSize() { return this.size; },
    getProperty(key) { return properties.get(key); },
    setProperty(key, value) { properties.set(key, value); },
    setSizeConstraints(value) { this.constraints = value; },
    remove() { this.removed = true; },
  };
  return node;
}

const comfy = {
  defs: {
    extend(selector, configure) {
      for (const definition of definitions) {
        const matches = typeof selector === 'function'
          ? selector(definition)
          : selector === definition.type;
        if (matches) configure(builderFor(definition.type));
      }
    },
  },
  graph: {
    add(type) {
      createdTagger = makeNode(type, 'tagger-1');
      return createdTagger;
    },
    select(nodes) { this.selected = [...nodes]; },
  },
  queue: {
    async run(options) { queued.push(options); return true; },
  },
  ui: {
    showDialog(definition) {
      const container = { children: [], appendChild(child) { this.children.push(child); } };
      definition.render(container);
      dialogs.push({ definition, container });
      return { close() {} };
    },
  },
};

const document = {
  createElement(tagName) {
    return { tagName, style: {}, textContent: '' };
  },
};

const context = vm.createContext({ console, document });
for (const forbidden of [
  'window', 'parent', 'top', 'app', 'comfyAPI', 'LiteGraph',
  'fetch', 'XMLHttpRequest', 'WebSocket',
]) {
  assert(context[forbidden] === undefined, `${forbidden} leaked into iframe realm`);
}

const api = new vm.SyntheticModule(
  ['comfy'],
  function expose() { this.setExport('comfy', comfy); },
  { context, identifier: '/comfy/api/v2.js' },
);

async function main() {
  const source = readFileSync(PACK_JS, 'utf8');
  assert(!/\b(?:window|parent|top|fetch|XMLHttpRequest|WebSocket|alert)\b/.test(source),
    'active module contains an ambient authority');
  const module = new vm.SourceTextModule(source, {
    context,
    identifier: pathToFileURL(PACK_JS).href,
  });
  await module.link((specifier) => {
    assert(specifier === '/comfy/api/v2.js', `forbidden import ${specifier}`);
    return api;
  });
  await module.evaluate();

  const taggerRecord = registrations.get(TAGGER);
  assert(taggerRecord?.executed.length === 1, 'tag readout hook not registered');
  const previewRecord = registrations.get('PreviewImage');
  assert(previewRecord?.menus.length === 1, 'image menu action not registered');
  assert(!registrations.get('TextNode'), 'menu registered on a non-image node');

  const linkCalls = [];
  const output = {
    name: 'image',
    type: 'IMAGE',
    connectTo(nodeId, slot) {
      linkCalls.push({ nodeId, slot });
      return { id: 'link-1' };
    },
  };
  const preview = makeNode('PreviewImage', 'preview-1', [output]);
  previewRecord.menus[0].run(preview);
  await Promise.resolve();
  assert(createdTagger?.type === TAGGER, 'menu did not create a WD14 node');
  assert(createdTagger.position.x === 220 && createdTagger.position.y === 20,
    'created tagger was not placed beside the source');
  assert(linkCalls.length === 1 && linkCalls[0].nodeId === createdTagger.id,
    'source image output was not connected to the tagger');
  assert(linkCalls[0].slot.index === 0, 'image was not connected to input zero');
  assert(queued.length === 1 && queued[0].nodes[0] === createdTagger,
    'quick tagger was not partially queued');

  taggerRecord.executed[0](createdTagger, {
    raw: { tags: ['hatsune_miku, 1girl', 'solo'] },
  });
  const widgets = createdTagger.widgets.all();
  assert(widgets.length === 2, 'one readout was not created per batch item');
  assert(widgets.every((item) => item.type === 'textarea' && item.disabled),
    'tag readouts are not disabled textareas');
  assert(widgets.every((item) => item.options?.serialize === false),
    'tag readouts would leak into workflow widgets_values');
  assert(dialogs.length === 1, 'quick interrogation did not show its result');
  assert(dialogs[0].container.children[0].textContent ===
    'hatsune_miku, 1girl\n\nsolo', 'quick result dialog changed tag text');
  assert(createdTagger.constraints.autoHeight === true,
    'tag readouts did not request automatic node height');

  taggerRecord.executed[0](createdTagger, { raw: { tags: ['second'] } });
  assert(createdTagger.widgets.all().length === 1,
    're-execution stacked stale tag widgets');
  assert(createdTagger.widgets.all()[0].value === 'second',
    're-execution did not refresh the tag readout');
  assert(dialogs.length === 1, 'ordinary re-execution reopened the quick dialog');

  console.log('PASS: WD14 V2 frontend behaviors run inside an iframe-safe realm');
}

main().catch((error) => { console.error(error); process.exit(1); });
