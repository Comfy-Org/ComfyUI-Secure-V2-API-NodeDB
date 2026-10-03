import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';

const entry = process.argv[2];
assert.ok(entry, 'pass the converted frontend entrypoint');
const source = fs.readFileSync(entry, 'utf8');
assert.doesNotMatch(source, /\bwindow\b|\bdocument\b|\bfetch\s*\(/);
assert.doesNotMatch(source, /https?:\/\/(?:cdn|unpkg|registry\.)/i);
assert.doesNotMatch(source, /comfy\.backend/);
assert.doesNotMatch(source, /addEventListener\s*\(\s*['"]keydown/);
assert.match(source, /comfy\.models\.list/);
assert.match(source, /comfy\.models\.readSidecar/);

const settings = new Map();
const storage = new Map([['mdnotes/notes.json', JSON.stringify({
  'loras/art/model.md': '# Existing\nhello',
})]]);
const catalogs = new Map([
  ['checkpoints', ['base/model.safetensors']],
  ['loras', [
    'art/model.safetensors',
    'blank/model.safetensors',
    'large/model.safetensors',
  ]],
  ['unet', []],
  ['diffusion_models', ['video/model.safetensors']],
]);
const sidecars = new Map([
  ['checkpoints\0base/model.safetensors\0.md', '# Checkpoint sidecar\nread only'],
  ['diffusion_models\0video/model.safetensors\0.md', '# Diffusion sidecar'],
  ['loras\0large/model.safetensors\0.md', 'x'.repeat(64 * 1024 + 1)],
]);
const modelCalls = [];
const declarations = [];
const dialogs = [];
const notices = [];
let extension;
let failNextStorageWrite = false;

class Element {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = doc;
    this.children = [];
    this.listeners = Object.create(null);
    this.style = {};
    this.value = '';
    this.textContent = '';
    this.selectionStart = 0;
    this.selectionEnd = 0;
  }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.append(item); return item; }
  replaceChildren(...items) { this.children = [...items]; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  dispatchEvent(event) { this.listeners[event.type]?.(event); }
  focus() { this.focused = true; }
  setRangeText(value, start, end) {
    this.value = this.value.slice(0, start) + value + this.value.slice(end);
    this.selectionStart = start;
    this.selectionEnd = start + value.length;
  }
}

const ownerDocument = {
  createElement(tag) { return new Element(tag, ownerDocument); },
  createTextNode(text) { return { nodeType: 3, textContent: text }; },
};

function descendants(root) {
  return [root, ...(root.children || []).flatMap(descendants)];
}

const comfy = {
  settings: {
    declare(def) {
      declarations.push(def);
      if (!settings.has(def.id)) settings.set(def.id, def.defaultValue);
    },
    get(id) { return settings.get(id); },
  },
  storage: {
    async get(key) { return storage.get(key); },
    async set(key, value) {
      if (failNextStorageWrite) {
        failNextStorageWrite = false;
        throw new Error('storage quota exceeded');
      }
      storage.set(key, value);
    },
  },
  models: {
    async list(folder) {
      modelCalls.push(['list', folder]);
      assert.ok(catalogs.has(folder), `unexpected model folder ${folder}`);
      return [...catalogs.get(folder)];
    },
    async readSidecar(folder, modelName, suffix) {
      modelCalls.push(['readSidecar', folder, modelName, suffix]);
      assert.equal(suffix, '.md');
      const content = sidecars.get(`${folder}\0${modelName}\0${suffix}`);
      if (content !== undefined
          && new TextEncoder().encode(content).length > 64 * 1024)
        throw new Error('model sidecar exceeds 65536 bytes');
      return content;
    },
  },
  defs: {
    extend(selector, callback) {
      const builder = {
        addMenuItem(item) { extension = { selector, item }; },
      };
      callback(builder);
    },
  },
  commands: { notify(value) { notices.push(value); } },
  ui: {
    showDialog(def) {
      const container = new Element('div', ownerDocument);
      const handle = {
        closed: false,
        close() {
          if (this.closed) return;
          this.closed = true;
          def.destroy?.();
        },
      };
      dialogs.push({ def, container, handle });
      def.render(container);
      return handle;
    },
  },
};

const context = vm.createContext({
  console,
  URL,
  TextEncoder,
  Event: class Event {
    constructor(type, options = {}) { this.type = type; this.bubbles = options.bubbles; }
  },
});
const module = new vm.SourceTextModule(source, {
  context,
  identifier: pathToFileURL(entry).href,
  initializeImportMeta(meta) { meta.url = pathToFileURL(entry).href; },
});
await module.link(async (specifier) => {
  assert.equal(specifier, '/comfy/api/v2.js');
  const stub = new vm.SyntheticModule(['comfy'], function () {
    this.setExport('comfy', comfy);
  }, { context });
  await stub.link(() => {});
  await stub.evaluate();
  return stub;
});
await module.evaluate();

assert.deepEqual(declarations.map((item) => item.id), [
  'comfyui-mdnotes.savingOptions.saveOnClose',
  'comfyui-mdnotes.markdownEditor.similarityThreshold',
]);
assert.equal(String(extension.selector), '/./');

const widgets = [
  { name: 'lora_name', getValue: () => 'art/model.safetensors', isHidden: () => false },
  { name: 'lora_name_2', getValue: () => 'None', isHidden: () => false },
  { name: 'ckpt_name', getValue: () => 'base/model.safetensors', isHidden: () => false },
  { name: 'unet_name', getValue: () => 'video/model.safetensors', isHidden: () => false },
  { name: 'seed', getValue: () => 1, isHidden: () => false },
  { name: 'hidden_lora_name', getValue: () => 'hidden.safetensors', isHidden: () => true },
];
const node = { widgets: { all: () => widgets } };
assert.equal(extension.item.when(node), true);
const items = extension.item.items(node);
assert.deepEqual(Array.from(items, (item) => item.label), [
  'Show note of lora 1',
  'Show note of checkpoint',
  'Show note of unet',
]);

// A private authored note wins over the model sidecar and remains editable.
items[0].run();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(dialogs.length, 1);
const authored = dialogs[0];
assert.match(authored.def.key, /^endericedragon\.mdnotes\.lora\./);
const authoredShell = authored.container.children[0];
const authoredToolbar = authoredShell.children[0];
const authoredTextarea = authoredShell.children[1];
const authoredPreview = authoredShell.children[2];
assert.equal(authoredTextarea.value, '# Existing\nhello');
assert.ok(descendants(authoredPreview).some((item) => item.tagName === 'H1'));
assert.deepEqual(modelCalls, [['list', 'loras']]);

// Toolbar actions update the editor and its live preview without parsing HTML.
authoredTextarea.selectionStart = 11;
authoredTextarea.selectionEnd = 16;
authoredToolbar.children[0].listeners.click();
assert.match(authoredTextarea.value, /\*\*hello\*\*/);
authoredTextarea.value += '\n<img src=x onerror=alert(1)>\n[site](https://example.com)';
authoredTextarea.dispatchEvent(new context.Event('input'));
assert.equal(descendants(authoredPreview).some((item) => item.tagName === 'IMG'), false);
const link = descendants(authoredPreview).find((item) => item.tagName === 'A');
assert.equal(link.href, 'https://example.com');
assert.equal(link.rel, 'noopener noreferrer');

// Ctrl/Cmd+S is delivered through the dialog's scoped key hook.
await authored.def.onKeyDown({ ctrlKey: true, metaKey: false, repeat: false, key: 's' });
await new Promise((resolve) => setImmediate(resolve));
assert.match(JSON.parse(storage.get('mdnotes/notes.json'))['loras/art/model.md'],
  /onerror=alert/);
assert.equal(notices.at(-1).severity, 'success');

// Exact checkpoint sidecars are read only after the model is found in its catalogue.
items[1].run();
await new Promise((resolve) => setImmediate(resolve));
const checkpoint = dialogs[1];
const checkpointShell = checkpoint.container.children[0];
const checkpointTextarea = checkpointShell.children[1];
assert.equal(checkpointTextarea.value, '# Checkpoint sidecar\nread only');
assert.deepEqual(modelCalls.slice(-2), [
  ['list', 'checkpoints'],
  ['readSidecar', 'checkpoints', 'base/model.safetensors', '.md'],
]);
assert.equal(notices.at(-1).severity, 'info');

// Save-on-close writes a private override; it never mutates the model sidecar.
settings.set('comfyui-mdnotes.savingOptions.saveOnClose', true);
checkpointTextarea.value += '\nprivate edit';
checkpointTextarea.dispatchEvent(new context.Event('input'));
const checkpointControls = checkpointShell.children[3];
checkpointControls.children[0].listeners.click();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(JSON.parse(storage.get('mdnotes/notes.json'))[
  'checkpoints/base/model.md'], '# Checkpoint sidecar\nread only\nprivate edit');
assert.equal(sidecars.get('checkpoints\0base/model.safetensors\0.md'),
  '# Checkpoint sidecar\nread only');

// UNET lookup preserves the upstream fallback to diffusion_models.
items[2].run();
await new Promise((resolve) => setImmediate(resolve));
assert.deepEqual(modelCalls.slice(-3), [
  ['list', 'unet'],
  ['list', 'diffusion_models'],
  ['readSidecar', 'diffusion_models', 'video/model.safetensors', '.md'],
]);
assert.equal(dialogs[2].container.children[0].children[1].value,
  '# Diffusion sidecar');

// A stale widget value cannot probe arbitrary files and opens no dialog.
const sidecarReadsBeforeStale = modelCalls.filter(
  ([method]) => method === 'readSidecar').length;
const stale = { widgets: { all: () => [{
  name: 'ckpt_name', getValue: () => '../secret.safetensors',
  isHidden: () => false,
}] } };
extension.item.items(stale)[0].run();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(dialogs.length, 3);
assert.equal(notices.at(-1).severity, 'error');
assert.match(notices.at(-1).detail, /managed catalogue/);
assert.equal(modelCalls.filter(([method]) => method === 'readSidecar').length,
  sidecarReadsBeforeStale);

// Missing sidecars create a blank private note through the explicit Save button.
const blankSidecar = { widgets: { all: () => [{
  name: 'lora_name', getValue: () => 'blank/model.safetensors',
  isHidden: () => false,
}] } };
extension.item.items(blankSidecar)[0].run();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(dialogs.length, 4);
const blank = dialogs[3];
const blankShell = blank.container.children[0];
const blankTextarea = blankShell.children[1];
assert.equal(blankTextarea.value, '');
assert.equal(notices.at(-1).severity, 'warning');
blankTextarea.value = '# My private note';
blankTextarea.dispatchEvent(new context.Event('input'));
await blankShell.children[3].children[1].listeners.click();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(JSON.parse(storage.get('mdnotes/notes.json'))[
  'loras/blank/model.md'], '# My private note');

// The host's 64 KiB sidecar ceiling fails closed without opening a dialog.
const oversizedSidecar = { widgets: { all: () => [{
  name: 'lora_name', getValue: () => 'large/model.safetensors',
  isHidden: () => false,
}] } };
extension.item.items(oversizedSidecar)[0].run();
await new Promise((resolve) => setImmediate(resolve));
assert.equal(dialogs.length, 4);
assert.equal(notices.at(-1).severity, 'error');
assert.match(notices.at(-1).detail, /65536 bytes/);

// Storage quota failures and the pack's 512 KiB note ceiling remain visible.
settings.set('comfyui-mdnotes.savingOptions.saveOnClose', false);
const diffusion = dialogs[2];
const diffusionTextarea = diffusion.container.children[0].children[1];
diffusionTextarea.value += '\nquota edit';
diffusionTextarea.dispatchEvent(new context.Event('input'));
failNextStorageWrite = true;
await diffusion.def.onKeyDown({
  ctrlKey: true, metaKey: false, repeat: false, key: 's',
});
await new Promise((resolve) => setImmediate(resolve));
assert.equal(notices.at(-1).severity, 'error');
assert.match(notices.at(-1).detail, /quota exceeded/);
assert.equal(JSON.parse(storage.get('mdnotes/notes.json'))[
  'diffusion_models/video/model.md'], undefined);

diffusionTextarea.value = 'x'.repeat(512 * 1024 + 1);
diffusionTextarea.dispatchEvent(new context.Event('input'));
await diffusion.def.onKeyDown({
  ctrlKey: false, metaKey: true, repeat: false, key: 's',
});
await new Promise((resolve) => setImmediate(resolve));
assert.equal(notices.at(-1).severity, 'error');
assert.match(notices.at(-1).detail, /512 KiB/);
assert.equal(JSON.parse(storage.get('mdnotes/notes.json'))[
  'diffusion_models/video/model.md'], undefined);

assert.equal(context.window, undefined);
assert.equal(context.document, undefined);
assert.equal(context.fetch, undefined);
console.log('PASS: MDNotes catalogued sidecars, private editing, safe modal UI');
