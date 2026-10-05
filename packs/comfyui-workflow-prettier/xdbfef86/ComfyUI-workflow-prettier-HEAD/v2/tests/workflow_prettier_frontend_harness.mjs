import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = path.resolve(process.argv[2]);
const mainPath = path.join(root, "web", "main.js");
const layoutPath = path.join(root, "web", "layout.js");

class Element {
  constructor(tag, ownerDocument) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.style = {};
    this.children = [];
    this.listeners = new Map();
    this.textContent = "";
    this.type = "";
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = [...items]; }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  click() { for (const listener of this.listeners.get("click") ?? []) listener({}); }
}

class Document {
  constructor() { this.created = []; }
  createElement(tag) { const item = new Element(tag, this); this.created.push(item); return item; }
}

class Widget {
  constructor(name, value) { this.name = name; this.value = value; this.listeners = new Set(); }
  getValue() { return this.value; }
  setValue(value) {
    const old = this.value; this.value = value;
    for (const listener of [...this.listeners]) listener(value, old);
  }
  on(event, listener) {
    assert.equal(event, "change"); this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

class FakeNode {
  constructor(id, type = "Other", graphId = "root") {
    this.id = String(id); this.type = type; this.comfyClass = type; this.graphId = graphId;
    this.position = { x: 0, y: 0 }; this.size = { width: 100, height: 60 };
    this.doc = new Document(); this.mounts = new Map();
    const widgets = new Map(type === "WorkflowPrettifier" ? [
      ["layout", new Widget("layout", "Layered (Vertical Stacks)")],
      ["direction", new Widget("direction", "Left to Right")],
      ["group_handling", new Widget("group_handling", "Auto (Respect Groups)")],
      ["horizontal_spacing", new Widget("horizontal_spacing", 100)],
      ["vertical_spacing", new Widget("vertical_spacing", 100)],
      ["group_padding", new Widget("group_padding", 100)],
    ] : []);
    this.widgets = {
      get: (name) => widgets.get(name),
      mount: (definition) => {
        const container = this.doc.createElement("div");
        const handle = { definition, container };
        this.mounts.set(definition.name, handle);
        definition.render(container);
        return handle;
      },
      _map: widgets,
    };
  }
  getPosition() { return { ...this.position }; }
  setPosition(value) { this.position = { ...value }; }
  getSize() { return { ...this.size }; }
  setSize(value) { this.size = { ...value }; }
  setColor(value) { this.color = value; }
  setBgColor(value) { this.bgColor = value; }
}

class Graph {
  constructor(id, nodes) {
    this.id = id; this._nodes = nodes; this._selection = []; this.batchCalls = 0;
  }
  nodes() { return [...this._nodes]; }
  node(id) { return this._nodes.find((node) => node.id === id); }
  links() { return []; }
  groups() { return []; }
  selection() { return [...this._selection]; }
  groupSelection() { return []; }
  batch(run) { this.batchCalls += 1; return run(); }
  pointerPosition() { return { x: 22, y: 33 }; }
  add(type, options) {
    const node = new FakeNode(`new-${this._nodes.length}`, type);
    node.position = { ...options.position };
    this._nodes.push(node);
    return node;
  }
  select(nodes) { this._selection = [...nodes]; }
}

const commands = new Map();
const extensions = [];
const actionButtons = [];
const documentClosed = [];
const stops = [];
const prettier = new FakeNode("prettier", "WorkflowPrettifier");
const a = new FakeNode("a");
const b = new FakeNode("b");
a.position = { x: 400, y: 400 }; b.position = { x: 800, y: 800 };
const graph = new Graph("root", [prettier, a, b]);
const comfy = {
  graph,
  workflow: { documentId: () => "doc-one" },
  commands: { register(definition) { assert.ok(!commands.has(definition.id)); commands.set(definition.id, definition); } },
  ui: {
    addActionBarButton(definition) {
      const handle = { definition, removed: false, update() {}, remove() { this.removed = true; } };
      actionButtons.push(handle); return handle;
    },
  },
  defs: {
    extend(selector, apply) {
      const hooks = { selector, menus: [] };
      apply({
        onCreated(callback) { hooks.onCreated = callback; },
        onRemoved(callback) { hooks.onRemoved = callback; },
        addMenuItem(item) { hooks.menus.push(item); },
      });
      extensions.push(hooks);
      const stop = () => { hooks.stopped = true; };
      stops.push(stop); return stop;
    },
  },
  onDocumentClosed(listener) { documentClosed.push(listener); return () => { listener.stopped = true; }; },
};

const context = vm.createContext({ console, Map, Set, WeakMap, Object, Number, Math });
const cache = new Map();
async function load(file) {
  if (cache.has(file)) return cache.get(file);
  const module = new vm.SourceTextModule(fs.readFileSync(file, "utf8"), { context, identifier: file });
  cache.set(file, module);
  await module.link(async (specifier, referencing) => {
    if (specifier === "/comfy/api/v2.js") {
      const synthetic = new vm.SyntheticModule(["comfy"], function initialize() {
        this.setExport("comfy", comfy);
      }, { context });
      await synthetic.link(() => {}); await synthetic.evaluate(); return synthetic;
    }
    return load(path.resolve(path.dirname(referencing.identifier), specifier));
  });
  return module;
}

const module = await load(mainPath);
await module.evaluate();
const namespace = module.namespace;
assert.equal(commands.size, 15);
assert.equal(actionButtons.length, 1);
assert.equal(extensions.length, 2);
assert.equal(namespace.installWorkflowPrettier(comfy), namespace.workflowPrettier);
assert.equal(commands.size, 15, "idempotent install must not duplicate commands");

const nodeExtension = extensions.find((item) => item.selector === "WorkflowPrettifier");
const menuExtension = extensions.find((item) => typeof item.selector === "function");
assert.ok(nodeExtension?.onCreated && nodeExtension?.onRemoved);
assert.equal(menuExtension.menus.length, 1);

nodeExtension.onCreated(prettier);
assert.equal(prettier.color, "#2a363b");
assert.equal(prettier.bgColor, "#1a252a");
assert.equal(prettier.size.width, 340);
const mount = prettier.mounts.get("workflow_prettier_controls");
assert.ok(mount);
const clickByText = (text) => {
  const found = prettier.doc.created.find((item) => item.textContent === text);
  assert.ok(found, `missing ${text}`); found.click(); return found;
};
clickByText("Prettify!");
assert.ok(a.position.x < b.position.x || a.position.y !== b.position.y);
assert.equal(graph.batchCalls, 1);
assert.equal(namespace.workflowPrettier.undo.depth("doc-one", graph), 1);
clickByText("Undo");
assert.deepEqual(a.position, { x: 400, y: 400 });
assert.deepEqual(b.position, { x: 800, y: 800 });

graph._selection = [a, b];
assert.equal(menuExtension.menus[0].when(a), true);
menuExtension.menus[0].items[0].run(a);
assert.equal(a.position.x, b.position.x);
graph._selection = [prettier, a];
assert.equal(menuExtension.menus[0].when(a), false);

// Remounting the same node tears down old widget subscriptions.
const watched = prettier.widgets._map.get("layout");
assert.equal(watched.listeners.size, 1);
nodeExtension.onCreated(prettier);
assert.equal(watched.listeners.size, 1);
nodeExtension.onRemoved(prettier);
assert.equal(watched.listeners.size, 0);

namespace.workflowPrettier.undo.clearDocument("doc-one");
namespace.workflowPrettier.undo.push("doc-one", graph);
assert.equal(namespace.workflowPrettier.undo.depth("doc-one", graph), 1);
documentClosed[0]({ id: "doc-one" });
assert.equal(namespace.workflowPrettier.undo.depth("doc-one", graph), 0);

commands.get("workflow-prettier.addNode").run();
assert.equal(graph._nodes.at(-1).type, "WorkflowPrettifier");
assert.deepEqual(graph._nodes.at(-1).position, { x: 22, y: 33 });
assert.deepEqual(graph._selection.map((node) => node.id), [graph._nodes.at(-1).id]);

namespace.workflowPrettier.remove();
assert.equal(actionButtons[0].removed, true);
assert.ok(extensions.every((item) => item.stopped));

console.log("workflow prettier frontend lifecycle: PASS");
