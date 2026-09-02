/** Iframe-realm behavior harness for the converted TTP Smart Tile frontend. */
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';


const HERE = path.dirname(fileURLToPath(import.meta.url));
const PACK_JS = path.resolve(HERE, '../web/js/ttp_smart_tile_interactive.js');
const INTERACTIVE = 'TTP_Smart_Tile_Interactive_Crop_Experimental';
const LOOP_SOURCE = 'TTP_Smart_Tile_Loop_Source_Experimental';
const LOOP_COLLECT = 'TTP_Smart_Tile_Loop_Collect_Experimental';

function assert(condition, message) {
  if (!condition) throw new Error(`ASSERT: ${message}`);
}

class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName;
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.listeners = new Map();
    this.style = {};
    this.textContent = '';
    this.value = '';
    this.width = 400;
    this.height = 230;
    this._context = null;
  }
  appendChild(item) { this.children.push(item); return item; }
  append(...items) { this.children.push(...items); }
  addEventListener(name, callback) {
    const values = this.listeners.get(name) ?? [];
    values.push(callback);
    this.listeners.set(name, values);
  }
  dispatch(name, values = {}) {
    for (const callback of this.listeners.get(name) ?? []) {
      callback({ clientX: 10, clientY: 10, pointerId: 1, shiftKey: false, ...values });
    }
  }
  getBoundingClientRect() { return { left: 0, top: 0, width: 400, height: 230 }; }
  setPointerCapture() {}
  releasePointerCapture() {}
  getContext() {
    if (!this._context) this._context = new CanvasContext();
    return this._context;
  }
  toDataURL() { return 'data:image/png;base64,c2FmZQ=='; }
}

class CanvasContext {
  clearRect() {}
  fillRect() {}
  strokeRect() {}
  beginPath() {}
  moveTo() {}
  lineTo() {}
  stroke() {}
  fill() {}
  arc() {}
  drawImage() {}
  fillText() {}
  getImageData() {
    const data = new Uint8ClampedArray(400 * 230 * 4);
    data[3] = 255;
    return { data };
  }
}

const document = {
  createElement(tagName) { return new Element(tagName, this); },
};

class Widgets {
  constructor(initial) {
    this.values = new Map(Object.entries(initial).map(([name, value]) => [name, {
      name,
      value,
      hidden: false,
      listeners: new Map(),
      getValue() { return this.value; },
      setValue(next) { this.value = next; },
      setHidden(next) { this.hidden = next; },
      on(event, callback) {
        this.listeners.set(event, callback);
        return () => this.listeners.delete(event);
      },
    }]));
    this.mounts = [];
  }
  get(name) { return this.values.get(name); }
  mount(spec) { this.mounts.push(spec); return spec; }
}

function makeNode(type, id, initial) {
  return {
    type,
    id,
    graphId: 'root',
    widgets: new Widgets(initial),
    setSizeConstraints(value) { this.constraints = value; },
  };
}

const records = new Map();
const nodes = new Map();
const queued = [];
const comfy = {
  defs: {
    extend(type, configure) {
      const record = { created: [], configured: [], executed: [], removed: [] };
      records.set(type, record);
      const builder = {
        onCreated(fn) { record.created.push(fn); return this; },
        onConfigured(fn) { record.configured.push(fn); return this; },
        onExecuted(fn) { record.executed.push(fn); return this; },
        onRemoved(fn) { record.removed.push(fn); return this; },
      };
      configure(builder);
    },
  },
  backend: { url(value) { return `/safe${value}`; } },
  graph: { node(id) { return nodes.get(String(id)); } },
  queue: { async run(options) { queued.push(options); return true; } },
};

function descendants(root) {
  return [root, ...root.children.flatMap(descendants)];
}

function buttonNamed(root, name) {
  return descendants(root).find((item) => item.tagName === 'button' && item.textContent === name);
}

const context = vm.createContext({
  console,
  URLSearchParams,
  Uint8ClampedArray,
  Math,
  Number,
  String,
  Boolean,
  JSON,
  Map,
  Set,
  Array,
  Object,
  Promise,
});
for (const forbidden of [
  'document', 'window', 'parent', 'top', 'app', 'comfyAPI', 'LiteGraph',
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
  assert(!/\b(?:window|parent|globalThis|fetch|XMLHttpRequest|WebSocket|alert)\b/.test(source),
    'active module contains ambient browser authority');
  assert(!/\.prototype\./.test(source), 'active module mutates a prototype');
  const module = new vm.SourceTextModule(source, {
    context,
    identifier: pathToFileURL(PACK_JS).href,
  });
  await module.link((specifier) => {
    assert(specifier === '/comfy/api/v2.js', `forbidden import ${specifier}`);
    return api;
  });
  await module.evaluate();

  assert([...records.keys()].join('|') === [INTERACTIVE, LOOP_SOURCE, LOOP_COLLECT].join('|'),
    'exact three V2 node hooks were not registered');

  const interactive = makeNode(INTERACTIVE, 'crop-1', {
    image: '',
    layout_json: '',
    default_pad: 128,
    default_blend: 64,
    auto_detect_request: 0,
    auto_detect_mode: 'none',
    auto_paint_mask: '',
  });
  nodes.set(interactive.id, interactive);
  records.get(INTERACTIVE).created[0](interactive);
  assert(interactive.widgets.mounts.length === 1, 'interactive editor was not mounted');
  assert(interactive.widgets.get('layout_json').hidden, 'layout JSON was not hidden');
  const editorContainer = new Element('container', document);
  interactive.widgets.mounts[0].render(editorContainer);
  const editorRoot = editorContainer.children[0];
  assert(buttonNamed(editorRoot, 'Set grid'), 'grid control missing');
  assert(buttonNamed(editorRoot, 'Grid in selected'), 'nested grid control missing');
  assert(buttonNamed(editorRoot, 'Merge selected'), 'merge control missing');
  assert(buttonNamed(editorRoot, 'Fill gaps'), 'gap fill control missing');
  assert(buttonNamed(editorRoot, 'Brush') && buttonNamed(editorRoot, 'Erase'),
    'paint controls missing');
  assert(buttonNamed(editorRoot, 'Auto Tile') && buttonNamed(editorRoot, 'Auto SAM'),
    'auto-layout controls missing');
  buttonNamed(editorRoot, 'Add tile').dispatch('click');
  let layout = JSON.parse(interactive.widgets.get('layout_json').value);
  assert(layout.tiles.length === 5, 'Add tile did not persist the layout');
  buttonNamed(editorRoot, 'Set grid').dispatch('click');
  layout = JSON.parse(interactive.widgets.get('layout_json').value);
  assert(layout.tiles.length === 4, 'Set grid did not persist a 2x2 grid');
  buttonNamed(editorRoot, 'Brush').dispatch('click');
  const canvas = descendants(editorRoot).find((item) => item.tagName === 'canvas');
  canvas.dispatch('pointerdown', { clientX: 50, clientY: 50 });
  canvas.dispatch('pointerup', { clientX: 50, clientY: 50 });
  assert(interactive.widgets.get('auto_paint_mask').value.includes('data:image/png'),
    'paint mask did not serialize through a hidden widget');
  buttonNamed(editorRoot, 'Auto SAM').dispatch('click');
  await Promise.resolve();
  assert(interactive.widgets.get('auto_detect_mode').value === 'sam3.1',
    'Auto SAM did not select the bounded SAM mode');
  assert(interactive.widgets.get('auto_detect_request').value === 1,
    'Auto SAM did not increment its cache-busting request');
  assert(queued.length === 1, 'Auto SAM did not use the V2 queue facade');

  const backendLayout = JSON.stringify({
    version: 1,
    type: 'ttp_smart_tile_interactive_layout',
    tiles: [{ name: 'detected', x0: 0.1, y0: 0.2, x1: 0.8, y1: 0.9 }],
  });
  records.get(INTERACTIVE).executed[0](interactive, {
    raw: { ttp_smart_tile_layout: [{ ok: true, message: 'detected', layout_json: backendLayout }] },
  });
  assert(JSON.parse(interactive.widgets.get('layout_json').value).tiles.length === 1,
    'backend auto-layout result was not applied');

  const loopNode = makeNode(LOOP_SOURCE, 'loop-1', {
    restart_request: 0,
    loop_request: 0,
  });
  nodes.set(loopNode.id, loopNode);
  records.get(LOOP_SOURCE).created[0](loopNode);
  assert(loopNode.widgets.get('restart_request').hidden && loopNode.widgets.get('loop_request').hidden,
    'loop request counters were not hidden');
  const loopContainer = new Element('container', document);
  loopNode.widgets.mounts[0].render(loopContainer);
  const loopRoot = loopContainer.children[0];
  buttonNamed(loopRoot, 'Start Loop / Process All Tiles').dispatch('click');
  await Promise.resolve();
  assert(loopNode.widgets.get('restart_request').value === 1,
    'loop start did not increment restart request');
  assert(loopNode.widgets.get('loop_request').value === 1,
    'loop start did not increment loop request');
  assert(queued.length === 2, 'loop start was not queued');

  records.get(LOOP_COLLECT).executed[0](null, {
    raw: { ttp_smart_tile_loop: [{ source_node_id: loopNode.id, index: 1, count: 3, done: false }] },
  });
  await Promise.resolve();
  assert(loopNode.widgets.get('loop_request').value === 2,
    'loop result did not queue the next tile');
  assert(queued.length === 3, 'next loop step was not queued');
  records.get(LOOP_SOURCE).executed[0](loopNode, {
    raw: { ttp_smart_tile_loop: [{ source_node_id: loopNode.id, index: 2, count: 3, done: true }] },
  });
  await Promise.resolve();
  assert(queued.length === 3, 'completed loop queued an extra step');

  buttonNamed(loopRoot, 'Stop').dispatch('click');
  records.get(INTERACTIVE).removed[0](interactive);
  records.get(LOOP_SOURCE).removed[0](loopNode);
  console.log('PASS: TTP V2 frontend behaviors run inside an iframe-safe realm');
}

main().catch((error) => { console.error(error); process.exit(1); });
