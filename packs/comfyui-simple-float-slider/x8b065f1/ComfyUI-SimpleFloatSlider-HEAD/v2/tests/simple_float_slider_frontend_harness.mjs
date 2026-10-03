import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error('frontend source path is required');

class FakeStyle {
  constructor() { this.values = {}; }
  setProperty(name, value) { this.values[name] = String(value); }
}

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.style = new FakeStyle();
    this.children = [];
    this.parent = undefined;
    this.listeners = new Map();
    this.attributes = new Map();
    this.textContent = '';
    this.value = '';
    this.type = '';
    this.step = '';
    this.min = '';
    this.max = '';
  }
  append(...children) {
    for (const child of children) {
      child.parent = this;
      this.children.push(child);
    }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parent = undefined;
    this.children = [];
    this.append(...children);
  }
  replaceWith(next) {
    if (!this.parent) return;
    const index = this.parent.children.indexOf(this);
    if (index >= 0) {
      this.parent.children[index] = next;
      next.parent = this.parent;
      this.parent = undefined;
    }
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  focus() { this.focused = true; }
  select() { this.selected = true; }
  dispatch(type, values = {}) {
    const event = {
      type,
      key: values.key,
      deltaY: values.deltaY ?? 0,
      defaultPrevented: false,
      propagationStopped: false,
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.propagationStopped = true; },
    };
    for (const listener of this.listeners.get(type) ?? []) listener(event);
    return event;
  }
}

class FakeDocument {
  constructor() { this.created = []; }
  createElement(tagName) {
    const element = new FakeElement(tagName, this);
    this.created.push(element);
    return element;
  }
}

class FakeWidget {
  constructor(name, value, widgetType = 'number') {
    this.name = name;
    this.value = value;
    this.widgetType = widgetType;
    this.hidden = false;
    this.listeners = new Set();
  }
  getValue() { return this.value; }
  setValue(value) {
    if (Object.is(this.value, value)) return;
    const oldValue = this.value;
    this.value = value;
    for (const listener of [...this.listeners]) listener(value, oldValue);
  }
  loadValue(value) { this.value = value; }
  setHidden(value) { this.hidden = Boolean(value); }
  isHidden() { return this.hidden; }
  on(event, listener) {
    assert.equal(event, 'change');
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

class MountedValue {
  constructor(value) {
    this.value = value;
    this.listeners = new Set();
  }
  get() { return this.value; }
  set(value) {
    if (Object.is(this.value, value)) return;
    this.value = value;
    for (const listener of [...this.listeners]) listener(value);
  }
  externalLoad(value) { this.set(value); }
  onChange(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

const extensions = new Map();
const comfy = {
  defs: {
    extend(type, callback) {
      const hooks = {};
      callback({
        onCreated(fn) { hooks.created = fn; },
        onConfigured(fn) { hooks.configured = fn; },
        onRemoved(fn) { hooks.removed = fn; },
      });
      extensions.set(type, hooks);
    },
  },
};

const context = vm.createContext({ console });
const module = new vm.SourceTextModule(fs.readFileSync(sourcePath, 'utf8'), {
  context,
  identifier: sourcePath,
});
await module.link(async (specifier) => {
  assert.equal(specifier, '/comfy/api/v2.js');
  const api = new vm.SyntheticModule(['comfy'], function initialize() {
    this.setExport('comfy', comfy);
  }, { context });
  await api.link(() => {});
  await api.evaluate();
  return api;
});
await module.evaluate();

assert.deepEqual([...extensions.keys()].sort(), [
  'ConfigurableFloatSlider', 'ConfigurableIntSlider', 'SimpleFloatSlider',
]);

function makeNode(type, id, values, graphId = 'root') {
  const doc = new FakeDocument();
  const widgets = Object.entries(values).map(([name, value]) => new FakeWidget(name, value));
  const mounts = new Map();
  const collection = {
    items: widgets,
    get(name) { return this.items.find((widget) => widget.name === name); },
    all() { return [...this.items]; },
    names() { return this.items.map((widget) => widget.name); },
    remove(name) {
      const index = this.items.findIndex((widget) => widget.name === name);
      if (index < 0) return false;
      this.items.splice(index, 1);
      return true;
    },
    move(name, toIndex) {
      const index = this.items.findIndex((widget) => widget.name === name);
      assert.ok(index >= 0);
      const [widget] = this.items.splice(index, 1);
      this.items.splice(toIndex, 0, widget);
    },
    mount(definition) {
      assert.equal(this.get(definition.name), undefined);
      const value = new MountedValue(definition.defaultValue);
      const container = doc.createElement('div');
      const handle = new FakeWidget(definition.name, definition.defaultValue, 'mounted');
      handle.getValue = () => value.get();
      handle.setValue = (next) => value.set(next);
      handle.definition = definition;
      handle.mountedValue = value;
      handle.container = container;
      handle.destroy = () => definition.destroy?.();
      this.items.push(handle);
      mounts.set(definition.name, handle);
      definition.render(container, value);
      return handle;
    },
  };
  const node = {
    id: String(id),
    type,
    comfyClass: type,
    graphId,
    widgets: collection,
    mounts,
    constraints: undefined,
    setSizeConstraints(value) { this.constraints = value; },
  };
  extensions.get(type).created(node);
  return node;
}

function byAria(node, label) {
  return node.mounts.get('value').container.ownerDocument.created.find(
    (element) => element.attributes.get('aria-label') === label && element.parent,
  );
}

function currentEditor(node) {
  return node.mounts.get('value').container.ownerDocument.created.find(
    (element) => element.type === 'number' && element.parent,
  );
}

const simple = makeNode('SimpleFloatSlider', 'simple', { value: 0.5 });
const simpleMount = simple.mounts.get('value');
assert.equal(simple.widgets.names()[0], 'value');
assert.equal(simple.widgets.all().filter((widget) => widget.name === 'value').length, 1);
assert.equal(simpleMount.definition.serialize, true);
assert.equal(simpleMount.definition.sendToPrompt, true);
assert.equal(simpleMount.definition.defaultValue, 0.5);
assert.equal(simple.constraints.minWidth, 220);
assert.equal(simple.constraints.autoHeight, true);

const simpleSlider = byAria(simple, 'Slider value');
const simpleDisplay = byAria(simple, 'Edit slider value');
simpleSlider.value = '0.734';
simpleSlider.dispatch('input');
assert.equal(simpleMount.getValue(), 0.73);
simpleSlider.dispatch('change');
const wheel = simpleDisplay.dispatch('wheel', { deltaY: -1 });
assert.equal(simpleMount.getValue(), 0.74);
assert.equal(wheel.defaultPrevented, true);
assert.equal(wheel.propagationStopped, true);

simpleDisplay.dispatch('click');
let editor = currentEditor(simple);
editor.value = '0.337';
const enter = editor.dispatch('keydown', { key: 'Enter' });
assert.equal(simpleMount.getValue(), 0.34);
assert.equal(enter.defaultPrevented, true);
assert.equal(enter.propagationStopped, true);
simpleDisplay.dispatch('click');
editor = currentEditor(simple);
editor.value = '0.91';
const escape = editor.dispatch('keydown', { key: 'Escape' });
assert.equal(simpleMount.getValue(), 0.34);
assert.equal(escape.defaultPrevented, true);
assert.equal(escape.propagationStopped, true);

// Workflow values can arrive before their saved configuration. The authored
// off-grid 7.5 must survive the default max=1 and restore once max=10 arrives.
const configurable = makeNode('ConfigurableFloatSlider', 'float', {
  value: 0.5, min_value: 0, max_value: 1, precision: 2, step: 0.01,
});
const floatMount = configurable.mounts.get('value');
floatMount.mountedValue.externalLoad(7.5);
assert.equal(floatMount.getValue(), 7.5);
configurable.widgets.get('min_value').loadValue(0);
configurable.widgets.get('max_value').setValue(2); // may notify before load settles
assert.equal(floatMount.getValue(), 2);
configurable.widgets.get('max_value').loadValue(10);
configurable.widgets.get('precision').loadValue(2);
configurable.widgets.get('step').loadValue(2);
extensions.get('ConfigurableFloatSlider').configured(configurable);
assert.equal(floatMount.getValue(), 7.5);
assert.equal(byAria(configurable, 'Edit slider value').textContent, '7.50');

// Narrowing clamps the active value but retains the authored raw value;
// widening restores it. Changing step, unlike restoration, re-grids from min.
configurable.widgets.get('max_value').setValue(1);
assert.equal(floatMount.getValue(), 1);
configurable.widgets.get('max_value').setValue(10);
assert.equal(floatMount.getValue(), 7.5);
const floatDisplay = byAria(configurable, 'Edit slider value');
floatDisplay.dispatch('click');
editor = currentEditor(configurable);
editor.value = '3.7';
editor.dispatch('keydown', { key: 'Enter' });
assert.equal(floatMount.getValue(), 3.7);
const floatSlider = byAria(configurable, 'Slider value');
floatSlider.value = '5.9';
floatSlider.dispatch('input');
assert.equal(floatMount.getValue(), 5.7); // drag steps from typed 3.7
floatSlider.dispatch('change');
configurable.widgets.get('step').setValue(4);
assert.equal(floatMount.getValue(), 4); // step edit re-grids from min=0

const configWidgets = ['min_value', 'max_value', 'precision', 'step'];
assert.ok(configWidgets.every((name) => configurable.widgets.get(name).isHidden()));
const toggle = configurable.mounts.get('value').container.ownerDocument.created.find(
  (element) => element.textContent === '▾ configure',
);
toggle.dispatch('click');
assert.ok(configWidgets.every((name) => !configurable.widgets.get(name).isHidden()));
toggle.dispatch('click');
assert.ok(configWidgets.every((name) => configurable.widgets.get(name).isHidden()));

const integer = makeNode('ConfigurableIntSlider', 'int', {
  value: 37, min_value: 0, max_value: 100, step: 5,
});
const intMount = integer.mounts.get('value');
const intSlider = byAria(integer, 'Slider value');
intSlider.value = '43';
intSlider.dispatch('input');
assert.equal(intMount.getValue(), 42); // drag step is anchored at typed 37
intSlider.dispatch('change');
integer.widgets.get('step').setValue(10);
assert.equal(intMount.getValue(), 40); // editing step re-grids from min=0

// Identical node ids in separate graphs remain isolated. Removal and remount
// tear down subscriptions instead of duplicating listeners.
const otherGraph = makeNode('ConfigurableIntSlider', 'int', {
  value: 9, min_value: 0, max_value: 20, step: 1,
}, 'subgraph');
integer.widgets.get('max_value').setValue(30);
assert.equal(otherGraph.mounts.get('value').getValue(), 9);
const oldStep = integer.widgets.get('step');
assert.ok(oldStep.listeners.size > 0);
extensions.get('ConfigurableIntSlider').removed(integer);
assert.equal(oldStep.listeners.size, 0);
integer.mounts.get('value').destroy();
const remounted = makeNode('ConfigurableIntSlider', 'int', {
  value: 12, min_value: 0, max_value: 20, step: 2,
});
assert.equal(remounted.mounts.get('value').getValue(), 12);
assert.equal(extensions.size, 3);

console.log('PASS: SimpleFloatSlider restoration, stepping, scoping, and lifecycle');
