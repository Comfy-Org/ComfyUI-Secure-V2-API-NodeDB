import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const dynamicEntry = path.resolve(process.argv[2]);
const toggleEntry = path.resolve(process.argv[3]);
const dynamicSource = fs.readFileSync(dynamicEntry, "utf8");
const toggleSource = fs.readFileSync(toggleEntry, "utf8");

for (const source of [dynamicSource, toggleSource]) {
  assert.match(source, /from ["']\/comfy\/api\/v2\.js["']/);
  for (const forbidden of [
    /\bwindow\s*\./, /\bdocument\s*\./, /localStorage/, /sessionStorage/,
    /MutationObserver/, /app\.registerExtension/, /LiteGraph/, /app\.graph/,
    /\._nodes/, /\bfetch\s*\(/,
  ]) assert.doesNotMatch(source, forbidden);
}

class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.style = {};
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.textContent = "";
    this.title = "";
    this.type = "";
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  click() { this.listeners.get("click")?.({}); }
}

const doc = { createElement: (tag) => new Element(tag, doc) };
const extensions = new Map();
const definitions = new Map();
const nodeChangeListeners = new Set();
let batchCount = 0;

function entity(graphId, id, title, color, bgcolor, mode = "always") {
  return {
    graphId, id: String(id), type: "Target", comfyClass: "Target",
    mode, centers: 0, modeWrites: [],
    getTitle() { return title; },
    getColor() { return color; },
    getBgColor() { return bgcolor; },
    getMode() { return this.mode; },
    setMode(value) { this.modeWrites.push(value); this.mode = value; },
    centerOn() { this.centers += 1; },
  };
}

const rootAlpha = entity("root", 1, "Alpha", "#red-dark", "#111", "always");
const nestedBeta = entity("sub", 1, "Beta", "#333", "bright-red", "never");
const rootBlue = entity("root", 2, "Alpha Blue", "blue", "#111", "always");
const allTargets = [rootAlpha, nestedBeta, rootBlue];
const comfy = {
  defs: {
    extend(type, callback) {
      const hooks = extensions.get(type) ?? {};
      callback({
        onCreated(fn) { hooks.onCreated = fn; },
        onConfigured(fn) { hooks.onConfigured = fn; },
        onConnectionsChanged(fn) { hooks.onConnectionsChanged = fn; },
        onResized(fn) { hooks.onResized = fn; },
      });
      extensions.set(type, hooks);
    },
    define(definition) { definitions.set(definition.type, definition); },
  },
  graph: {
    queryNodes({ scope }) {
      return scope === "visible"
        ? allTargets.filter((node) => node.graphId === "root")
        : [...allTargets];
    },
    batch(callback) { batchCount += 1; callback(); },
  },
  sameEntity(left, right) {
    return left.id === right.id && left.graphId === right.graphId;
  },
  onNodeChanged(listener, options) {
    assert.deepEqual(JSON.parse(JSON.stringify(options)), { scope: "document" });
    nodeChangeListeners.add(listener);
    return () => nodeChangeListeners.delete(listener);
  },
};

async function evaluate(entry, source) {
  const context = vm.createContext({
    console, Error, Map, Number, Object, RegExp, Set, String,
    clearTimeout, queueMicrotask, setTimeout,
  });
  const comfyModule = new vm.SyntheticModule(["comfy"], function () {
    this.setExport("comfy", comfy);
  }, { context, identifier: `secure:comfy-api-v2:${entry}` });
  const module = new vm.SourceTextModule(source, {
    context,
    identifier: pathToFileURL(entry).href,
  });
  await module.link(async (specifier) => {
    assert.equal(specifier, "/comfy/api/v2.js");
    return comfyModule;
  });
  await comfyModule.evaluate();
  await module.evaluate();
}

await evaluate(dynamicEntry, dynamicSource);
await evaluate(toggleEntry, toggleSource);

assert.ok(extensions.has("DynamicTextConcatenate"));
assert.ok(extensions.has("Wireless Master Toggle"));
assert.ok(definitions.has("Wireless Master Toggle"));

function slot(index, connected = false) {
  return { id: `text_${index}`, name: `text_${index}`, isConnected: connected };
}

function dynamicNode(count = 10) {
  const slots = Array.from({ length: count }, (_, index) => slot(index + 1));
  return {
    inputs: {
      all: () => slots,
      at: (index) => slots[index],
      remove(ref) {
        const index = slots.findIndex((item) => item.id === ref);
        if (index < 0) return false;
        slots.splice(index, 1);
        return true;
      },
      add(name, type, options) {
        assert.equal(type, "STRING");
        assert.equal(options.shape, "optional");
        const added = { id: name, name, isConnected: false };
        slots.push(added);
        return added;
      },
    },
  };
}

const dynamicHooks = extensions.get("DynamicTextConcatenate");
const growing = dynamicNode();
dynamicHooks.onCreated(growing);
await Promise.resolve();
assert.deepEqual(growing.inputs.all().map((item) => item.name), ["text_1", "text_2"]);
growing.inputs.all()[0].isConnected = true;
growing.inputs.all()[1].isConnected = true;
dynamicHooks.onConnectionsChanged(growing, { side: "input", index: 1, connected: true });
await Promise.resolve();
assert.deepEqual(growing.inputs.all().map((item) => item.name), ["text_1", "text_2", "text_3"]);
growing.inputs.all()[1].isConnected = false;
dynamicHooks.onConnectionsChanged(growing, { side: "input", index: 1, connected: false });
await Promise.resolve();
assert.deepEqual(growing.inputs.all().map((item) => item.name), ["text_1", "text_2"]);
for (let expected = 3; expected <= 10; expected += 1) {
  for (const item of growing.inputs.all()) item.isConnected = true;
  dynamicHooks.onConnectionsChanged(growing, { side: "input", index: 0, connected: true });
  await Promise.resolve();
  assert.equal(growing.inputs.all().length, expected);
}
for (const item of growing.inputs.all()) item.isConnected = true;
dynamicHooks.onConnectionsChanged(growing, { side: "input", index: 0, connected: true });
await Promise.resolve();
assert.equal(growing.inputs.all().length, 10, "dynamic inputs stop at ten");

const restored = dynamicNode(5);
restored.inputs.all()[4].isConnected = true;
dynamicHooks.onConfigured(restored);
await Promise.resolve();
assert.equal(restored.inputs.all().length, 5, "configuration retains a linked trailing slot");

function masterNode(properties = {}) {
  const container = new Element("div", doc);
  const node = {
    graphId: "root", id: "99", type: "Wireless Master Toggle",
    properties: new Map(Object.entries(properties)),
    constraints: undefined, serializedWidgets: undefined, mount: undefined,
    getProperty(name) { return this.properties.get(name); },
    setProperty(name, value) { this.properties.set(name, value); },
    setSerializeWidgets(value) { this.serializedWidgets = value; },
    setSizeConstraints(value) { this.constraints = value; },
    widgets: {
      mount(definition) {
        const handle = {
          heights: [],
          setHeight(value) { this.heights.push(value); },
        };
        node.mount = { definition, handle, container };
        definition.render(container);
        return handle;
      },
    },
  };
  return node;
}

function elements(root, predicate, result = []) {
  if (predicate(root)) result.push(root);
  for (const child of root.children ?? []) elements(child, predicate, result);
  return result;
}

function button(root, label) {
  return elements(root, (item) => item.getAttribute?.("aria-label") === label)[0];
}

function rowLabels(root) {
  return elements(root, (item) => item.tagName === "SPAN").map((item) => item.textContent);
}

const definition = definitions.get("Wireless Master Toggle");
const master = masterNode({
  matchTitle: "Alpha|Beta",
  matchColors: "red",
  toggleRestriction: "max one",
  userWidth: 240,
});
definition.onCreated(master);
assert.equal(master.getProperty("matchTitle"), "Alpha|Beta", "saved properties survive creation");
assert.equal(master.constraints.minWidth, 240);
assert.equal(master.serializedWidgets, false);
assert.equal(nodeChangeListeners.size, 1);
assert.deepEqual(rowLabels(master.mount.container), ["Alpha", "Beta"]);

// Duplicate node ids in different graphs must never cross-deliver a mode change.
button(master.mount.container, "Toggle Beta").click();
assert.equal(rootAlpha.mode, "never");
assert.equal(nestedBeta.mode, "always");
assert.deepEqual(rootAlpha.modeWrites.at(-1), "never");
assert.deepEqual(nestedBeta.modeWrites.at(-1), "always");
assert.ok(batchCount >= 1);

// Always-one rejects disabling the final target and repairs externally-empty state.
master.setProperty("toggleRestriction", "always one");
definition.onPropertyChanged(master, {});
await new Promise((resolve) => setTimeout(resolve, 120));
button(master.mount.container, "Toggle Beta").click();
assert.equal(nestedBeta.mode, "always");
rootAlpha.mode = "never";
nestedBeta.mode = "never";
for (const listener of [...nodeChangeListeners]) listener({ node: nestedBeta });
await new Promise((resolve) => setTimeout(resolve, 120));
assert.equal(rootAlpha.mode, "always", "always-one repairs a zero-enabled set");
assert.equal(nestedBeta.mode, "never");

// Title and color are an intersection. Invalid title regex preserves color-only matching.
master.setProperty("matchTitle", "Beta");
master.setProperty("matchColors", "blue");
definition.onPropertyChanged(master, {});
await new Promise((resolve) => setTimeout(resolve, 120));
assert.deepEqual(rowLabels(master.mount.container), []);
master.setProperty("matchTitle", "[");
master.setProperty("matchColors", "red");
definition.onPropertyChanged(master, {});
await new Promise((resolve) => setTimeout(resolve, 120));
assert.deepEqual(rowLabels(master.mount.container), ["Alpha", "Beta"]);
master.setProperty("matchColors", "");
definition.onPropertyChanged(master, {});
await new Promise((resolve) => setTimeout(resolve, 120));
assert.deepEqual(rowLabels(master.mount.container), []);

// Visible scope excludes nested graphs and alphanumeric sorting is stable.
master.setProperty("matchTitle", "Alpha|Beta");
master.setProperty("matchColors", "");
master.setProperty("showAllGraphs", false);
master.setProperty("sort", "alphanumeric");
definition.onPropertyChanged(master, {});
await new Promise((resolve) => setTimeout(resolve, 120));
assert.deepEqual(rowLabels(master.mount.container), ["Alpha", "Alpha Blue"]);
button(master.mount.container, "Navigate to Alpha").click();
assert.equal(rootAlpha.centers, 1);

// Width is persisted through the typed resize hook.
extensions.get("Wireless Master Toggle").onResized(master, { width: 333, height: 90 });
assert.equal(master.getProperty("userWidth"), 333);

// Re-creation and both teardown paths are idempotent and do not leak listeners.
const replacement = masterNode({ matchTitle: "Alpha" });
replacement.id = master.id;
definition.onCreated(replacement);
assert.equal(nodeChangeListeners.size, 1, "same graph-qualified identity replaces its observer");
definition.onRemoved(replacement);
assert.equal(nodeChangeListeners.size, 0);
replacement.mount.definition.destroy();
assert.equal(nodeChangeListeners.size, 0);

console.log("PASS: ToggleMaster dynamic inputs, matching, graph isolation, restrictions, and teardown");
