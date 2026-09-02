import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';


function check(condition, message) {
  if (!condition) throw new Error(message);
}

class FakeWidget {
  constructor(definition) {
    this.definition = definition;
    this.disabled = Boolean(definition.disabled);
    this.listeners = new Map();
  }

  setDisabled(value) { this.disabled = Boolean(value); }
  isDisabled() { return this.disabled; }
  on(event, listener) {
    this.listeners.set(event, listener);
    return () => this.listeners.delete(event);
  }
  activate() { this.listeners.get('activate')?.(null); }
}

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = String(tagName).toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.listeners = new Map();
    this.style = { cssText: '' };
    this.textContent = '';
    this.focused = false;
  }

  append(...items) { this.children.push(...items); }
  addEventListener(event, listener) { this.listeners.set(event, listener); }
  click() { this.listeners.get('click')?.({ target: this }); }
  focus() { this.focused = true; }
}

const documentFactory = {
  created: [],
  createElement(tagName) {
    const element = new FakeElement(tagName, this);
    this.created.push(element);
    return element;
  },
};

const requests = [];
const notifications = [];
const dialogs = [];
const eventListeners = new Map();
let interrupted;
let selector;
const hooks = {};
let audioPlays = 0;

const node = {
  id: '17',
  comfyClass: 'PauseWorkflowNodeWithSound',
  background: '#222222',
  widgetList: [],
  getBgColor() { return this.background; },
  setBgColor(value) { this.background = value; },
  widgets: {
    add(definition) {
      const widget = new FakeWidget(definition);
      node.widgetList.push(widget);
      return widget;
    },
  },
};

const comfy = {
  defs: {
    extend(value, apply) {
      selector = value;
      apply({
        onCreated(callback) { hooks.created = callback; },
        onRemoved(callback) { hooks.removed = callback; },
      });
    },
  },
  graph: {
    node(id) { return String(id) === node.id ? node : undefined; },
  },
  backend: {
    on(event, listener) { eventListeners.set(event, listener); return () => {}; },
    async fetch(url, init) {
      requests.push({ url, init });
      return { ok: true, status: 200 };
    },
  },
  commands: {
    notify(definition) { notifications.push(definition); },
  },
  queue: {
    onInterrupted(listener) { interrupted = listener; return () => {}; },
  },
  ui: {
    showDialog(definition) {
      const container = new FakeElement('div', documentFactory);
      definition.render(container);
      let closed = false;
      const handle = {
        close() {
          if (closed) return;
          closed = true;
          definition.destroy?.();
        },
      };
      dialogs.push({ definition, container, handle });
      return handle;
    },
  },
};

class FakeAudio {
  constructor(source) { this.source = source; }
  async play() { audioPlays += 1; }
}

const context = vm.createContext({
  Audio: FakeAudio,
  URL,
  console,
});
const facade = new vm.SyntheticModule(
  ['comfy'],
  function initialize() { this.setExport('comfy', comfy); },
  { context, identifier: '/comfy/api/v2.js' },
);
const sourcePath = path.resolve(process.env.TARGET_JS);
const source = fs.readFileSync(sourcePath, 'utf8');
const module = new vm.SourceTextModule(source, {
  context,
  identifier: sourcePath,
  initializeImportMeta(meta, target) {
    meta.url = pathToFileURL(target.identifier).href;
  },
});
await module.link(async (specifier) => {
  if (specifier === '/comfy/api/v2.js') return facade;
  throw new Error(`unexpected import: ${specifier}`);
});
await module.evaluate();

check(
  JSON.stringify(selector) === JSON.stringify([
    'PauseWorkflowNode', 'PauseWorkflowNodeWithSound',
  ]),
  'wrong node definition selector',
);
check(typeof hooks.created === 'function', 'missing created lifecycle');
check(typeof hooks.removed === 'function', 'missing removed lifecycle');
check(typeof interrupted === 'function', 'missing queue interruption lifecycle');
check(
  typeof eventListeners.get('secure-node-interaction') === 'function',
  'missing secure interaction listener',
);
for (const name of ['window', 'parent', 'app', 'fetch', 'XMLHttpRequest', 'WebSocket']) {
  check(vm.runInContext(`typeof ${name}`, context) === 'undefined', `${name} leaked`);
}

hooks.created(node);
check(node.widgetList.length === 2, 'expected exactly two node buttons');
check(node.widgetList.every((widget) => widget.isDisabled()), 'buttons start enabled');
check(node.widgetList.every((widget) => widget.definition.serialize === false), 'buttons serialize');

const emit = eventListeners.get('secure-node-interaction');
emit({ kind: 'image-choice', request_id: 'ignored', node_id: '17', payload: {} });
emit({
  kind: 'prompt-await', request_id: 'ignored-variant', node_id: '17',
  payload: { variant: 'other' },
});
check(dialogs.length === 0, 'foreign interaction was handled');

emit({
  kind: 'prompt-await',
  request_id: 'continue-token',
  node_id: '17',
  payload: {
    variant: 'wywywywy-workflow-pause-v1',
    sound: true,
    title: 'Pause Workflow (Sound)',
  },
});
check(dialogs.length === 1, 'pause dialog was not opened');
check(audioPlays === 1, 'sound node did not play its bundled notification');
check(node.background === '#8b6914', 'paused node color was not applied');
check(node.widgetList.every((widget) => !widget.isDisabled()), 'pause buttons not enabled');
node.widgetList[0].activate();
await new Promise((resolve) => setImmediate(resolve));
check(requests.length === 1, 'continue did not post exactly once');
check(requests[0].url === '/secure-nodes/interactions/respond', 'wrong response route');
check(JSON.parse(requests[0].init.body).request_id === 'continue-token', 'wrong token');
check(JSON.parse(requests[0].init.body).response.action === 'continue', 'wrong action');
check(node.background === '#222222', 'node color was not restored');
check(node.widgetList.every((widget) => widget.isDisabled()), 'buttons not disabled');

emit({
  kind: 'prompt-await',
  request_id: 'cancel-token',
  node_id: '17',
  payload: { variant: 'wywywywy-workflow-pause-v1', sound: false },
});
interrupted();
await new Promise((resolve) => setImmediate(resolve));
check(requests.length === 2, 'queue interruption did not cancel exactly once');
check(JSON.parse(requests[1].init.body).response.action === 'cancel', 'interrupt action');
check(notifications.length === 0, 'successful requests emitted an error');

hooks.removed(node);
console.log('wywywywy-pause frontend harness: PASS');
