import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { TextEncoder } from 'node:util';

const source = fs.readFileSync(new URL('../web/main.js', import.meta.url), 'utf8');
assert.equal((source.match(/comfy\.defs\.extend\(/g) || []).length, 1);
for (const forbidden of ['document.body', 'window.', 'localStorage', 'fetch(', 'innerHTML', 'prototype', 'registerNodeType']) assert.ok(!source.includes(forbidden), forbidden);
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.events = new Map(); this.textContent = ''; this.value = ''; this.checked = false; this.ownerDocument = { createElement: tag => new Element(tag) }; }
  append(...items) { this.children.push(...items); }
  addEventListener(name, fn) { if (!this.events.has(name)) this.events.set(name, new Set()); this.events.get(name).add(fn); }
  removeEventListener(name, fn) { this.events.get(name)?.delete(fn); }
  fire(name) { for (const fn of this.events.get(name) || []) fn({ target: this }); }
}
const hooks = {}, menus = [], commands = [], dialogs = [];
let selection = [];
const comfy = {
  defs: { extend(type, build) {
    assert.equal(type, 'jupo.JoinPrompt.JoinPrompt');
    const builder = { hideWidget(name) { assert.equal(name, 'options'); }, addMenuItem(item) { menus.push(item); } };
    for (const name of ['onCreated', 'onConfigured', 'onRemoved', 'onSerialize', 'onPropertyChanged']) builder[name] = fn => { hooks[name] = fn; };
    build(builder);
  } },
  commands: { register(command) { commands.push(command); } },
  graph: { selection: () => selection },
  ui: { showDialog(def) {
    const container = new Element('container');
    const dialog = { def, container, closed: false, close() { if (!this.closed) { this.closed = true; def.destroy?.(); } } };
    dialogs.push(dialog); def.render(container); return dialog;
  } },
};
vm.runInNewContext(source.replace(/^import .*;\n/, ''), { comfy, TextEncoder, Map, JSON, encodeURIComponent });
function node(graphId, id, properties = {}, options = '') {
  const widget = { value: options, hidden: false, getValue() { return this.value; }, setValue(v) { this.value = v; }, setHidden(v) { this.hidden = v; } };
  const n = { graphId, id, type: 'jupo.JoinPrompt.JoinPrompt', properties: { ...properties }, live: true,
    getProperties() { return this.properties; }, getProperty(name) { return this.properties[name]; },
    setProperty(name, value) { this.properties[name] = value; }, snapshot() { return this.live ? {} : undefined; },
    widgets: { get(name) { return name === 'options' ? widget : undefined; } },
    inputs: { socket: { id: 'options-slot' }, byName(name) { return name === 'options' ? this.socket : undefined; }, remove(id) { assert.equal(id, 'options-slot'); this.socket = undefined; } },
  }; return n;
}
const a = node('graph-a', '1'), b = node('graph-b', '1');
hooks.onCreated(a); hooks.onCreated(b);
assert.ok(a.widgets.get('options').hidden); assert.equal(a.inputs.socket, undefined);
assert.deepEqual(JSON.parse(a.widgets.get('options').value), { delimiter: '', cleanup: false });
assert.equal(menus.length, 1); assert.equal(commands.length, 1);
assert.ok(menus[0].when(a)); assert.ok(!menus[0].when({ type: 'jupo.JoinPrompt.JoinStrings' }));
assert.equal(commands[0].scope, 'canvas'); assert.equal(commands[0].id, 'jupo.JoinPrompt.OpenConfigDialog');
selection = [{ type: 'Other' }]; commands[0].run(); assert.equal(dialogs.length, 0);
selection = [{ type: 'Other' }, a, b]; commands[0].run();
let dialog = dialogs.at(-1);
let input = dialog.container.children[0].children[0], checkbox = dialog.container.children[1].children[0];
input.value = '  \\n<script>雪'; input.fire('change'); checkbox.checked = true; checkbox.fire('change');
assert.deepEqual(JSON.parse(a.widgets.get('options').value), { delimiter: '  \\n<script>雪', cleanup: true });
assert.equal(b.properties.delimiter, '');
input.value = '🙂'.repeat(16385); input.fire('change'); assert.equal(input.value, a.properties.delimiter);
input.value = '"'.repeat(32768); input.fire('change'); assert.equal(input.value, a.properties.delimiter);
const saved = JSON.parse(JSON.stringify(hooks.onSerialize(a)));
assert.deepEqual(saved, { jupoJoinPrompt: { delimiter: a.properties.delimiter, cleanup: true } });
dialog.def.onKeyDown({ key: 'z', ctrlKey: true }); assert.ok(!dialog.closed);
dialog.def.onKeyDown({ key: 'Escape' }); assert.ok(dialog.closed);
assert.equal(input.events.get('change').size, 0); assert.equal(checkbox.events.get('change').size, 0);
input.value = 'stale'; input.fire('change'); assert.equal(a.properties.delimiter, saved.jupoJoinPrompt.delimiter);
const restored = node('restored-graph', '1'); hooks.onCreated(restored); hooks.onConfigured(restored, saved);
assert.deepEqual(JSON.parse(restored.widgets.get('options').value), saved.jupoJoinPrompt);
const legacy = node('legacy-graph', '1'); hooks.onCreated(legacy);
hooks.onConfigured(legacy, { properties: { delimiter: ', ', cleanup: true } });
assert.deepEqual(JSON.parse(legacy.widgets.get('options').value), { delimiter: ', ', cleanup: true });
const widgetOnly = node('options-only', '1', {}, '{"delimiter":"|","cleanup":true}'); hooks.onCreated(widgetOnly);
assert.equal(widgetOnly.properties.delimiter, '|');
menus[0].run(restored); const removedDialog = dialogs.at(-1);
const removedInput = removedDialog.container.children[0].children[0];
restored.live = false; hooks.onRemoved(restored); assert.ok(removedDialog.closed);
removedInput.value = 'after-remove'; removedInput.fire('change'); assert.equal(restored.properties.delimiter, saved.jupoJoinPrompt.delimiter);
menus[0].run(restored); assert.equal(dialogs.at(-1), removedDialog);
const replacement = node('restored-graph', '1'); hooks.onCreated(replacement); menus[0].run(replacement);
assert.equal(dialogs.at(-1).container.children[0].children[0].value, '');
const previous = dialogs.at(-1); menus[0].run(replacement); assert.ok(previous.closed);
dialogs.at(-1).container.children[2].fire('click'); assert.ok(dialogs.at(-1).closed);
let rejected = false;
hooks.onPropertyChanged(a, { name: 'delimiter', value: '🙂'.repeat(16385), reject() { rejected = true; } }); assert.ok(rejected);
hooks.onPropertyChanged(a, { name: 'delimiter', value: '\\t', reject() { assert.fail(); } });
assert.equal(a.properties.delimiter, '\\t');
hooks.onPropertyChanged(a, { name: 'cleanup', value: false, reject() { assert.fail(); } });
assert.deepEqual(JSON.parse(a.widgets.get('options').value), { delimiter: '\\t', cleanup: false });
for (const n of [a, b, legacy, widgetOnly, replacement]) { n.live = false; hooks.onRemoved(n); }
console.log('Join Prompt frontend: selection/menu/config/reload/isolation/cleanup/bounds assertions passed (recording typed facade + DOM, not browser chrome).');
