import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
assert.match(source, /from ["']\/comfy\/api\/v2\.js["']/);
for (const forbidden of [
  /\bwindow\b/, /\bdocument\b/, /\bfetch\s*\(/, /localStorage/,
  /sessionStorage/, /MutationObserver/, /app\.registerExtension/,
  /addDOMWidget/, /_nodes/, /_groups/, /setDirtyCanvas/,
]) assert.doesNotMatch(source, forbidden);

class Element {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = doc;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.style = {};
    this.textContent = "";
    this.disabled = false;
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(callback);
  }
  dispatch(name, event = {}) {
    for (const callback of this.listeners.get(name) ?? []) callback(event);
  }
}
const ownerDocument = {
  createElement(tag) { return new Element(tag, ownerDocument); },
};

function widget(name, value, type = "combo", options = {}) {
  const listeners = new Set();
  return {
    name,
    widgetType: type,
    value,
    setCalls: [],
    getValue() { return this.value; },
    setValue(next) {
      const previous = this.value;
      this.value = next;
      this.setCalls.push(next);
      for (const listener of listeners) listener(next, previous);
    },
    getOptions() { return options; },
    on(event, listener) {
      assert.equal(event, "change");
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    listenerCount() { return listeners.size; },
  };
}

function targetNode(id, title, boolean = true) {
  const bool = boolean ? widget("enabled", true, "toggle", { type: "boolean" }) : undefined;
  let mode = "always";
  return {
    id,
    graphId: "graph-a",
    getTitle() { return title; },
    setTitle(next) { title = next; },
    getMode() { return mode; },
    setMode(next) { mode = next; },
    widgets: { all() { return bool ? [bool] : []; } },
    bool,
  };
}

function panelNode(id = "panel") {
  const mode = widget("mode", "widgets");
  let mountDefinition;
  let mountHandle;
  const properties = { switches: { legacy: true, "widgets:v3:old": true } };
  const node = {
    id,
    graphId: "graph-a",
    getTitle() { return "A"; },
    getMode() { return "always"; },
    getProperty(name) { return properties[name]; },
    setProperty(name, value) { properties[name] = value; },
    setSizeConstraints(value) { this.constraints = value; },
    widgets: {
      get(name) { return name === "mode" ? mode : undefined; },
      all() { return [mode]; },
      mount(definition) {
        mountDefinition = definition;
        mountHandle = {
          heights: [],
          setHeight(value) { this.heights.push(value); },
        };
        return mountHandle;
      },
    },
    mode,
    properties,
    get mountDefinition() { return mountDefinition; },
    get mountHandle() { return mountHandle; },
  };
  return node;
}

const alpha = targetNode("alpha", "A:Alpha");
const noBoolean = targetNode("none", "A:No Boolean", false);
const ignored = targetNode("ignored", "B:Ignored");
const memberOne = targetNode("member-one", "inside one");
const memberTwo = targetNode("member-two", "inside two");
const group = {
  id: "group-a",
  getTitle() { return "A:Group"; },
  nodes() { return [memberOne, memberTwo]; },
};
const emptyGroup = {
  id: "group-empty",
  getTitle() { return "A:Empty"; },
  nodes() { return []; },
};
const graphA = {
  id: "graph-a",
  version: 1,
  nodeList: [],
  groupList: [group, emptyGroup],
  nodes() { return this.nodeList; },
  groups() { return this.groupList; },
};
const graphBTarget = targetNode("graph-b-target", "A:Other Graph");
graphBTarget.graphId = "graph-b";
const graphB = {
  id: "graph-b",
  version: 1,
  nodeList: [graphBTarget],
  groupList: [],
  nodes() { return this.nodeList; },
  groups() { return this.groupList; },
};

const nodeChanged = new Set();
const workflowLoaded = new Set();
const intervals = new Map();
let nextInterval = 1;
let registration;
const comfy = {
  graph: graphA,
  sameEntity(left, right) {
    return left.id === right.id && left.graphId === right.graphId;
  },
  defs: {
    extend(type, callback) {
      assert.equal(type, "SolidlimeMultiBoolPanel");
      registration = { created: [], configured: [], removed: [] };
      callback({
        onCreated(fn) { registration.created.push(fn); },
        onConfigured(fn) { registration.configured.push(fn); },
        onRemoved(fn) { registration.removed.push(fn); },
      });
    },
  },
  onNodeChanged(callback) {
    nodeChanged.add(callback);
    return () => nodeChanged.delete(callback);
  },
  onWorkflowLoaded(callback) {
    workflowLoaded.add(callback);
    return () => workflowLoaded.delete(callback);
  },
};

const context = vm.createContext({
  console,
  setTimeout,
  clearTimeout,
  setInterval(callback) {
    const id = nextInterval++;
    intervals.set(id, callback);
    return id;
  },
  clearInterval(id) { intervals.delete(id); },
});
const comfyModule = new vm.SyntheticModule(["comfy"], function () {
  this.setExport("comfy", comfy);
}, { context, identifier: "secure:comfy-api-v2" });
const module = new vm.SourceTextModule(source, {
  context,
  identifier: pathToFileURL(entry).href,
});
await comfyModule.link(() => {});
await comfyModule.evaluate();
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  return comfyModule;
});
await module.evaluate();

const flush = () => new Promise((resolve) => setTimeout(resolve, 5));
const renderPanel = (panel) => {
  const container = new Element("div", ownerDocument);
  panel.mountDefinition.render(container);
  return { container, list: container.children[0] };
};
const rowByName = (list, name) => list.children.find(
  (row) => row.children?.[0]?.textContent === name,
);

assert.equal(registration.created.length, 1);
assert.equal(registration.configured.length, 1);
assert.equal(registration.removed.length, 1);

const panel = panelNode();
graphA.nodeList = [panel, alpha, noBoolean, ignored];
registration.created[0](panel);
assert.deepEqual(JSON.parse(JSON.stringify(panel.constraints)), { minWidth: 150, autoHeight: true });
assert.deepEqual(JSON.parse(JSON.stringify(panel.properties.switches)), { "widgets:v3:old": true });
assert.equal(panel.mountDefinition.serialize, false);
assert.equal(panel.mountDefinition.sendToPrompt, false);
assert.equal(nodeChanged.size, 1);
assert.equal(workflowLoaded.size, 1);
assert.equal(intervals.size, 1);

let mounted = renderPanel(panel);
assert.deepEqual(mounted.list.children.map((row) => row.children[0].textContent), [
  "Alpha", "No Boolean",
]);
assert.equal(rowByName(mounted.list, "No Boolean").children[1].disabled, true);
rowByName(mounted.list, "Alpha").children[1].dispatch("click");
assert.equal(alpha.bool.getValue(), false);
assert.equal(panel.properties.switches["widgets:v3:Alpha"], false);
assert.ok(panel.mountHandle.heights.at(-1) >= 60);

// Rename and structural updates refresh through typed events/version polling.
alpha.setTitle("A:Renamed");
graphA.version += 1;
for (const callback of nodeChanged) callback({ node: alpha, graphId: graphA.id, property: "title" });
await flush();
assert.ok(rowByName(mounted.list, "Renamed"));
const late = targetNode("late", "A:Late");
graphA.nodeList.push(late);
graphA.version += 1;
for (const callback of intervals.values()) callback();
assert.ok(rowByName(mounted.list, "Late"));

// Bypass and mute retain the upstream ON=normal, OFF=changed semantics.
panel.mode.setValue("bypass");
await flush();
assert.ok(rowByName(mounted.list, "Group"));
rowByName(mounted.list, "Renamed").children[1].dispatch("click");
assert.equal(alpha.getMode(), "bypass");
rowByName(mounted.list, "Group").children[1].dispatch("click");
assert.equal(memberOne.getMode(), "bypass");
assert.equal(memberTwo.getMode(), "bypass");
assert.equal(rowByName(mounted.list, "Empty").children[1].disabled, true);
panel.mode.setValue("mute");
await flush();
rowByName(mounted.list, "Late").children[1].dispatch("click");
assert.equal(late.getMode(), "never");

// The display remains bounded and reports overflow.
panel.mode.setValue("widgets");
for (let index = 0; index < 24; index += 1) {
  graphA.nodeList.push(targetNode(`many-${index}`, `A:Item ${String(index).padStart(2, "0")}`));
}
graphA.version += 1;
for (const callback of intervals.values()) callback();
assert.equal(mounted.list.children.length, 21);
assert.match(mounted.list.children.at(-1).textContent, /more$/);

// A different visible graph cannot be read or mutated by this panel's refresh.
const beforeOther = graphBTarget.getMode();
comfy.graph = graphB;
for (const callback of nodeChanged) callback({ node: graphBTarget, graphId: graphB.id, property: "mode" });
for (const callback of intervals.values()) callback();
await flush();
assert.equal(graphBTarget.getMode(), beforeOther);

// Recreating the same panel key disposes every old listener and timer first.
comfy.graph = graphA;
const replacement = panelNode();
graphA.nodeList[0] = replacement;
registration.created[0](replacement);
assert.equal(nodeChanged.size, 1);
assert.equal(workflowLoaded.size, 1);
assert.equal(intervals.size, 1);
assert.equal(panel.mode.listenerCount(), 0);
mounted = renderPanel(replacement);
registration.configured[0](replacement);
await flush();
const companion = panelNode("panel-two");
graphA.nodeList.push(companion);
registration.created[0](companion);
renderPanel(companion);
assert.equal(nodeChanged.size, 1, "all panels share one node-change listener");
assert.equal(workflowLoaded.size, 1, "all panels share one workflow listener");
assert.equal(intervals.size, 1, "all panels share one refresh timer");
registration.removed[0](replacement);
assert.equal(nodeChanged.size, 1, "shared observers remain for the other panel");
assert.equal(intervals.size, 1, "shared timer remains for the other panel");
registration.removed[0](companion);
assert.equal(nodeChanged.size, 0);
assert.equal(workflowLoaded.size, 0);
assert.equal(intervals.size, 0);
assert.equal(replacement.mode.listenerCount(), 0);
replacement.mountDefinition.destroy();
companion.mountDefinition.destroy();
assert.equal(nodeChanged.size, 0);
assert.equal(intervals.size, 0);

console.log("PASS: Multi Bool Panel typed graph and mounted UI behavior");
