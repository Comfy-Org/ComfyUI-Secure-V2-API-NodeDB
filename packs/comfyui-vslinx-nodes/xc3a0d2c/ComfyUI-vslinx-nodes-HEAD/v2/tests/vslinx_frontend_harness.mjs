import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sources = [
  'web/js/anima_tiled_sampler.js',
  'web/js/bypass_helper.js',
  'web/js/combo_type_fix.js',
  'web/js/group_bookmarks.js',
  'web/js/impact_multiline_wildcard_text.js',
  'web/js/interactive_detailer.js',
  'web/js/load_last_generated.js',
  'web/js/select_images_from_folder.js',
  'web/services/lora_hover_preview.js',
];

class Element {
  constructor(tag, document) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = document;
    this.children = [];
    this.style = {};
    this.listeners = new Map();
    this.textContent = '';
    this.value = '';
    this.hidden = false;
    this.files = [];
    this.width = 320;
    this.height = 200;
    this.naturalWidth = 320;
    this.naturalHeight = 200;
  }

  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  addEventListener(name, fn) { this.listeners.set(name, fn); }
  removeAttribute(name) { delete this[name]; }
  focus() { this.focused = true; }
  click() { this.listeners.get('click')?.({ clientX: 0, clientY: 0 }); }
  getBoundingClientRect() { return { left: 0, top: 0, width: 320, height: 200 }; }
  getContext() {
    return {
      drawImage() {}, strokeRect() {}, fillText() {},
      set strokeStyle(_value) {}, set lineWidth(_value) {},
      set fillStyle(_value) {}, set font(_value) {},
    };
  }
  set src(value) {
    this._src = value;
    if (this.tagName === 'IMG') this.listeners.get('load')?.();
  }
  get src() { return this._src; }
}

class Document {
  createElement(tag) { return new Element(tag, this); }
}

const documentForContainers = new Document();
const registrations = new Map();
const sidebarTabs = [];
const previewRegistrations = [];
const backendEvents = new Map();
const backendCalls = [];
const beforeRun = [];
const interrupted = [];
const executingChanged = [];
const workflowLoaded = [];
const nodeChanged = [];
const timers = new Map();
let timerSequence = 0;
const graphNodes = new Map();
const plain = (value) => JSON.parse(JSON.stringify(value));

function builderFor(type) {
  const hooks = {};
  const builder = {
    onCreated(fn) { hooks.created = fn; },
    onConfigured(fn) { hooks.configured = fn; },
    onConnectionsChanged(fn) { hooks.connections = fn; },
    onRemoved(fn) { hooks.removed = fn; },
    onBeforeConnect(fn) { hooks.beforeConnect = fn; },
    onPropertyChanged(fn) { hooks.propertyChanged = fn; },
  };
  registrations.set(type, hooks);
  return builder;
}

class Widget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.listeners = new Map();
    this.options = {};
    this.hidden = false;
  }
  getValue() { return this.value; }
  setValue(value) {
    if (Object.is(this.value, value)) return;
    this.value = value;
    for (const fn of this.listeners.get('change') ?? []) fn(value);
  }
  setHidden(value) { this.hidden = Boolean(value); }
  setLabel(value) { this.label = value; }
  setOption(name, value) { this.options[name] = value; }
  on(event, fn) {
    const list = this.listeners.get(event) ?? [];
    list.push(fn);
    this.listeners.set(event, list);
    return () => {
      const current = this.listeners.get(event) ?? [];
      this.listeners.set(event, current.filter((item) => item !== fn));
    };
  }
  listenerCount(event) { return (this.listeners.get(event) ?? []).length; }
  activate() { for (const fn of this.listeners.get('activate') ?? []) fn(); }
}

class Widgets {
  constructor(values = {}) {
    this.values = new Map(Object.entries(values).map(
      ([name, value]) => [name, new Widget(name, value)],
    ));
    this.mounted = [];
  }
  get(name) { return this.values.get(name); }
  all() { return [...this.values.values()]; }
  add(def) {
    const widget = new Widget(def.name, def.value);
    widget.options = { ...(def.options ?? {}) };
    this.values.set(def.name, widget);
    return widget;
  }
  move() {}
  mount(def) {
    const widget = new Widget(def.name, undefined);
    this.values.set(def.name, widget);
    const container = new Element('div', documentForContainers);
    def.render(container);
    this.mounted.push({ def, container });
    return widget;
  }
}

function port(index, name, type = '*') {
  return {
    index, name, type, connectedType: undefined, isConnected: false,
    modify(values) { Object.assign(this, values); },
    source() { return this._source; },
    resolvedSource() { return this._resolvedSource ?? this._source; },
    targets() { return this._targets ?? []; },
  };
}

function collection(values) {
  return {
    at(index) { return values[index]; },
    all() { return values; },
  };
}

function makeNode(type, id, widgetValues = {}) {
  const inputs = [port(0, 'any', '*'), port(1, 'boolean', 'BOOLEAN')];
  const outputs = [port(0, 'out', '*')];
  const node = {
    type, id: String(id), graphId: 'graph', widgets: new Widgets(widgetValues),
    inputs: collection(inputs), outputs: collection(outputs), properties: {},
    mode: 'always', title: type, isDeleted: false,
    getProperty(name) { return this.properties[name]; },
    setProperty(name, value) { this.properties[name] = value; },
    getMode() { return this.mode; },
    setMode(value) { this.mode = value; },
    getTitle() { return this.title; },
    setSizeConstraints(values) { this.sizeConstraints = values; },
    setSerializeWidgets(value) { this.serializeWidgets = value; },
  };
  graphNodes.set(node.id, node);
  return node;
}

const graph = {
  id: 'graph',
  root() { return this; },
  subgraphs() { return []; },
  node(id) { return graphNodes.get(String(id)); },
  queryNodes({ type } = {}) {
    const values = [...graphNodes.values()];
    return type ? values.filter((node) => node.type === type) : values;
  },
  groups() { return []; },
  nodes() { return [...graphNodes.values()]; },
  centerOn(value) { this.centered = value; },
  select(values) { this.selected = values; },
};

const comfy = {
  defs: {
    extend(type, configure) { configure(builderFor(type)); },
    isTypeCompatible(first, second) {
      return first === '*' || second === '*' || first === second;
    },
  },
  graph,
  widgets: {
    registerComboPreview(options) {
      previewRegistrations.push(options);
      return () => { options.unregistered = true; };
    },
  },
  settings: {
    declarations: [],
    declare(value) { this.declarations.push(value); },
    get(id) { return id === 'vslinx.modelHoverPreviews'; },
  },
  backend: {
    url(value) { return `managed:${value}`; },
    on(name, fn) { backendEvents.set(name, fn); return () => backendEvents.delete(name); },
    async fetch(route, options = {}) {
      backendCalls.push([route, options]);
      if (route === '/impact/wildcards/list') {
        return { ok: true, async json() { return ['__animal__', '__style__']; } };
      }
      if (route.startsWith('/secure-nodes/assets/output')) {
        return { ok: true, async json() { return ['folder/last.png', 'old.png']; } };
      }
      if (route === '/upload/image') {
        return { ok: true, async json() { return { name: 'picked.png', subfolder: '' }; } };
      }
      return { ok: true, async json() { return {}; } };
    },
  },
  ui: {
    addSidebarTab(value) { sidebarTabs.push(value); },
    showDialog(options) {
      const container = new Element('div', documentForContainers);
      options.render(container);
      const handle = { options, container, closed: false, close() { this.closed = true; } };
      return handle;
    },
  },
  files: { async pick() { return undefined; } },
  queue: {
    onBeforeRun(fn) { beforeRun.push(fn); },
    onInterrupted(fn) { interrupted.push(fn); },
    run() {},
  },
  onWorkflowLoaded(fn) { workflowLoaded.push(fn); },
  onNodeChanged(fn) { nodeChanged.push(fn); return () => {}; },
  onExecutingNodeChanged(fn) { executingChanged.push(fn); return () => {}; },
};

const context = vm.createContext({
  console,
  URLSearchParams,
  FormData,
  Blob,
  setInterval(fn) { const id = ++timerSequence; timers.set(id, fn); return id; },
  clearInterval(id) { timers.delete(id); },
});

const apiModule = new vm.SyntheticModule(
  ['comfy'],
  function initialize() { this.setExport('comfy', comfy); },
  { context, identifier: '/comfy/api/v2.js' },
);
await apiModule.link(() => { throw new Error('mock API has no imports'); });
await apiModule.evaluate();

for (const relative of sources) {
  const filename = path.join(root, relative);
  const module = new vm.SourceTextModule(fs.readFileSync(filename, 'utf8'), {
    context,
    identifier: filename,
  });
  await module.link(async (specifier) => {
    assert.equal(specifier, '/comfy/api/v2.js');
    return apiModule;
  });
  await module.evaluate();
}

assert.equal('window' in context, false);
assert.equal('document' in context, false);
assert.equal('parent' in context, false);
assert.equal(sources.length, 9);
assert.deepEqual([...registrations.keys()].sort(), [
  'vsLinx_AnimaLLLiteTiledSampler',
  'vsLinx_BypassMuteOnState',
  'vsLinx_BypassOnBool',
  'vsLinx_GroupBookmarks',
  'vsLinx_ImpactMultilineWildcardText',
  'vsLinx_LoadLastGeneratedImage',
  'vsLinx_LoadSelectedImagesBatch',
  'vsLinx_LoadSelectedImagesList',
  'vsLinx_MuteOnBool',
].sort());

assert.equal(previewRegistrations.length, 1);
assert.deepEqual(plain(previewRegistrations[0]), {
  id: 'vslinx.modelHoverPreviews',
  modelCategories: ['loras', 'checkpoints', 'unet', 'diffusion_models'],
  extensions: ['safetensors', 'sft', 'pt', 'ckpt', 'gguf'],
  candidatePolicy: 'adjacent-model-preview-v1',
  media: ['image/png', 'image/webp', 'image/jpeg', 'video/mp4', 'video/webm'],
});
assert.equal(comfy.settings.declarations[0].id, 'vslinx.modelHoverPreviews');
assert.equal(sidebarTabs[0].id, 'vslinx.groupBookmarks');
assert.equal(backendEvents.has('secure-node-interaction'), true);

const anima = makeNode('vsLinx_AnimaLLLiteTiledSampler', 'anima', {
  sampling_mode: 'per_tile', vae_decode_tiled: false, vae_decode_tile_size: 512,
});
registrations.get(anima.type).created(anima);
assert.equal(anima.widgets.get('vae_decode_tiled').hidden, true);
anima.widgets.get('sampling_mode').setValue('multidiffusion');
assert.equal(anima.widgets.get('vae_decode_tiled').hidden, false);

const target = makeNode('Target', 'target');
const bypass = makeNode('vsLinx_BypassOnBool', 'bypass', { bypass: true });
bypass.inputs.at(0).connectedType = 'IMAGE';
bypass.outputs.at(0)._targets = [{ nodeId: target.id, inputIndex: 0 }];
registrations.get(bypass.type).created(bypass);
assert.equal(target.mode, 'bypass');
assert.equal(bypass.widgets.get('bypass').listenerCount('change'), 1);
registrations.get(bypass.type).configured(bypass);
assert.equal(bypass.widgets.get('bypass').listenerCount('change'), 1);
assert.equal(timers.size, 1);
registrations.get(bypass.type).removed(bypass);
assert.equal(bypass.widgets.get('bypass').listenerCount('change'), 0);
assert.equal(timers.size, 0);

const wildcard = makeNode('vsLinx_ImpactMultilineWildcardText', 'wild', { text: 'base' });
registrations.get(wildcard.type).created(wildcard);
await new Promise((resolve) => setTimeout(resolve, 0));
const picker = wildcard.widgets.get('Add wildcard');
assert.deepEqual(plain(picker.options.values), ['Select wildcard', '__animal__', '__style__']);
picker.setValue('__animal__');
assert.equal(wildcard.widgets.get('text').getValue(), 'base, __animal__');

const bookmarks = makeNode('vsLinx_GroupBookmarks', 'bookmarks');
registrations.get(bookmarks.type).created(bookmarks);
assert.ok(bookmarks.widgets.get('Manage Bookmarks'));
const sidebarContainer = new Element('div', documentForContainers);
sidebarTabs[0].render(sidebarContainer);
assert.ok(sidebarContainer.children.length > 0);

const last = makeNode('vsLinx_LoadLastGeneratedImage', 'last', {
  image: '', auto_refresh: true,
});
registrations.get(last.type).created(last);
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(last.widgets.get('image').hidden, true);
assert.deepEqual(plain(last.widgets.get('select_image').options.values), [
  'folder/last.png', 'old.png',
]);
assert.equal(last.widgets.mounted[0].container.ownerDocument, documentForContainers);

for (const type of ['vsLinx_LoadSelectedImagesList', 'vsLinx_LoadSelectedImagesBatch']) {
  const selected = makeNode(type, type, {
    selected_paths: '["a.png"]', fail_if_empty: true,
    filename_handling: 'full filename',
  });
  selected.properties.selected_paths = '["a.png"]';
  registrations.get(type).created(selected);
  assert.equal(selected.widgets.get('selected_paths').hidden, true);
  assert.equal(selected.widgets.mounted[0].container.ownerDocument, documentForContainers);
  assert.equal(selected.widgets.get('selected_paths').getValue(), '["a.png"]');
}

backendEvents.get('secure-node-interaction')({
  kind: 'prompt-await', request_id: 'request-1', node_id: 'detailer',
  payload: {
    variant: 'vslinx-segment-prompts-v1', node_id: 'detailer',
    overview: { preview: { filename: 'overview.png', type: 'temp' }, scale: 1 },
    segments: [{
      index: 0, label: 'face', confidence: 0.9, bbox: [1, 1, 10, 10],
      preview: { filename: 'face.png', type: 'temp' },
    }],
  },
});
assert.ok(backendCalls.every(([route]) => typeof route === 'string'));
assert.ok(beforeRun.length === 1);
assert.ok(interrupted.length === 1);
assert.ok(executingChanged.length >= 2);

const comboSource = fs.readFileSync(path.join(root, 'web/js/combo_type_fix.js'), 'utf8');
assert.equal(comboSource.includes('registerExtension'), false);
assert.equal(comboSource.includes('prototype.'), false);
assert.equal(comboSource.includes('/vslinx/combo_type_fix'), false);

console.log('PASS: vsLinx V2 frontend behaviors');
