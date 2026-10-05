import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";

const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
assert.match(source, /from ["']\/comfy\/api\/v2\.js["']/);
for (const forbidden of [
  /app\.registerExtension/, /addWidget/, /addDOMWidget/, /localStorage/,
  /sessionStorage/, /\bwindow\b/, /\bdocument\./, /\bfetch\s*\(/,
  /_nodes/, /_groups/, /setDirtyCanvas/, /LiteGraph/,
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
    this.type = "";
    this.value = "";
    this.checked = false;
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(callback);
  }
  dispatch(name, event = {}) {
    for (const callback of this.listeners.get(name) ?? []) callback(event);
  }
}
const ownerDocument = { createElement(tag) { return new Element(tag, ownerDocument); } };

function node(id, type, title, graphId = "root") {
  let mode = "always";
  const properties = {};
  let mountDefinition;
  let mountHandle;
  return {
    id, type, comfyClass: type, graphId, properties,
    getTitle() { return title; },
    setTitle(value) { title = value; },
    getMode() { return mode; },
    setMode(value) { mode = value; },
    getProperty(name) { return properties[name]; },
    setProperty(name, value) { properties[name] = value; },
    setSizeConstraints(value) { this.constraints = value; },
    widgets: {
      mount(definition) {
        mountDefinition = definition;
        mountHandle = { heights: [], setHeight(value) { this.heights.push(value); } };
        return mountHandle;
      },
    },
    get mountDefinition() { return mountDefinition; },
    get mountHandle() { return mountHandle; },
  };
}

function group(id, title, members) {
  return { id, getTitle() { return title; }, nodes() { return members; } };
}

const tagA = node("a", "Other", "First [[DEFAULT:A]]");
const tagB = node("b", "Other", "Second [[DEFAULT:B]]");
const tagNested = node("nested", "Other", "Nested [[DEFAULT:A]]", "subgraph");
const ignored = node("ignored", "Other", "Ignored [[OTHER:C]]");
const bypassController = node("ctl-b", "OrchestratorNodeToogle", "Bypass");
const muteController = node("ctl-m", "OrchestratorNodeMuter", "Muter");
const groupBypass = node("ctl-gb", "OrchestratorNodeGroupBypasser", "Group bypass");
const groupMute = node("ctl-gm", "OrchestratorNodeGroupMuter", "Group mute");
const oneA = node("one-a", "Other", "One A");
const oneB = node("one-b", "Other", "One B");
const two = node("two", "Other", "Two");
const groups = [group("g1", "One", [oneA, oneB]), group("g2", "Two", [two])];
const allNodes = [tagA, tagB, tagNested, ignored, bypassController, muteController, groupBypass, groupMute, oneA, oneB, two];

const registrations = new Map();
const nodeChanged = new Set();
const workflowLoaded = new Set();
const intervals = new Map();
let nextInterval = 1;
let batchCount = 0;
const comfy = {
  graph: {
    queryNodes() { return allNodes; },
    groups() { return groups; },
    batch(callback) { batchCount += 1; callback(); },
  },
  sameEntity(left, right) {
    return left.id === right.id && left.graphId === right.graphId;
  },
  defs: {
    extend(type, callback) {
      const registration = { created: [], configured: [], properties: [], removed: [] };
      callback({
        onCreated(fn) { registration.created.push(fn); },
        onConfigured(fn) { registration.configured.push(fn); },
        onPropertyChanged(fn) { registration.properties.push(fn); },
        onRemoved(fn) { registration.removed.push(fn); },
      });
      registrations.set(type, registration);
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
  setInterval(callback) { const id = nextInterval++; intervals.set(id, callback); return id; },
  clearInterval(id) { intervals.delete(id); },
});
const comfyModule = new vm.SyntheticModule(["comfy"], function () {
  this.setExport("comfy", comfy);
}, { context, identifier: "secure:comfy-api-v2" });
const module = new vm.SourceTextModule(source, {
  context, identifier: pathToFileURL(entry).href,
});
await comfyModule.link(() => {});
await comfyModule.evaluate();
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  return comfyModule;
});
await module.evaluate();

assert.deepEqual([...registrations.keys()], [
  "OrchestratorNodeToogle", "OrchestratorNodeMuter",
  "OrchestratorNodeGroupBypasser", "OrchestratorNodeGroupMuter",
]);
for (const registration of registrations.values()) {
  assert.equal(registration.created.length, 1);
  assert.equal(registration.configured.length, 1);
  assert.equal(registration.properties.length, 1);
  assert.equal(registration.removed.length, 1);
}

function mount(target) {
  const container = new Element("div", ownerDocument);
  target.mountDefinition.render(container);
  return container;
}
const buttonNamed = (container, label) => container.children.find(
  (child) => child.tagName === "BUTTON" && child.textContent === label,
);
const rowNamed = (container, label) => container.children.find(
  (child) => child.tagName === "LABEL" && child.children[0]?.textContent === label,
);

const bypassRegistration = registrations.get("OrchestratorNodeToogle");
bypassRegistration.created[0](bypassController);
assert.deepEqual(
  JSON.parse(JSON.stringify(bypassController.constraints)),
  { minWidth: 190, autoHeight: true },
);
assert.equal(bypassController.properties.workflow_id, "default_workflow");
assert.equal(bypassController.properties.group_id, "DEFAULT");
assert.equal(bypassController.properties.node_mode, true);
assert.equal(bypassController.mountDefinition.serialize, false);
assert.equal(bypassController.mountDefinition.sendToPrompt, false);
let bypassView = mount(bypassController);
assert.ok(buttonNamed(bypassView, "A"));
assert.ok(buttonNamed(bypassView, "B"));
assert.equal(nodeChanged.size, 1);
assert.equal(workflowLoaded.size, 1);
assert.equal(intervals.size, 1);

// Exclusive selection changes every matching root/subgraph node and not another group.
buttonNamed(bypassView, "A").dispatch("click");
assert.equal(tagA.getMode(), "bypass");
assert.equal(tagNested.getMode(), "bypass");
assert.equal(tagB.getMode(), "bypass");
buttonNamed(bypassView, "B").dispatch("click");
assert.equal(tagA.getMode(), "bypass");
assert.equal(tagNested.getMode(), "bypass");
assert.equal(tagB.getMode(), "always");
assert.equal(ignored.getMode(), "always");

// Multiple mode and Active All retain independent tag switches.
const exclusive = rowNamed(bypassView, "Exclusive").children[1];
exclusive.checked = false;
exclusive.dispatch("change");
assert.equal(bypassController.properties.node_mode, false);
buttonNamed(bypassView, "Active All").dispatch("click");
assert.equal(tagA.getMode(), "always");
assert.equal(tagNested.getMode(), "always");
assert.equal(tagB.getMode(), "always");
assert.ok(batchCount >= 3);

// The muter uses never, while preserving the same discovery semantics.
const muteRegistration = registrations.get("OrchestratorNodeMuter");
muteRegistration.created[0](muteController);
const muteView = mount(muteController);
buttonNamed(muteView, "A").dispatch("click");
assert.equal(tagA.getMode(), "never");
assert.equal(tagNested.getMode(), "never");

// Group controllers are radio selectors and use bypass vs never exactly.
const groupBypassRegistration = registrations.get("OrchestratorNodeGroupBypasser");
groupBypassRegistration.created[0](groupBypass);
const groupBypassView = mount(groupBypass);
buttonNamed(groupBypassView, "Two").dispatch("click");
assert.equal(oneA.getMode(), "bypass");
assert.equal(oneB.getMode(), "bypass");
assert.equal(two.getMode(), "always");
assert.equal(groupBypass.properties.selected_group, "g2");
buttonNamed(groupBypassView, "Two").dispatch("click");
assert.equal(two.getMode(), "always", "the active radio group cannot be disabled");

const groupMuteRegistration = registrations.get("OrchestratorNodeGroupMuter");
groupMuteRegistration.created[0](groupMute);
const groupMuteView = mount(groupMute);
buttonNamed(groupMuteView, "Two").dispatch("click");
assert.equal(oneA.getMode(), "never");
assert.equal(two.getMode(), "always");

// A title change refreshes through typed events; all instances share observers/timer.
tagA.setTitle("Renamed [[DEFAULT:Z]]");
for (const callback of nodeChanged) callback({ node: tagA, graphId: "root", property: "title" });
assert.ok(buttonNamed(bypassView, "Z"));
assert.equal(nodeChanged.size, 1);
assert.equal(workflowLoaded.size, 1);
assert.equal(intervals.size, 1);

// Same-key replacement disposes the old state, then final removal releases everything.
const replacement = node("ctl-b", "OrchestratorNodeToogle", "replacement");
allNodes[allNodes.indexOf(bypassController)] = replacement;
bypassRegistration.created[0](replacement);
mount(replacement);
bypassRegistration.removed[0](replacement);
muteRegistration.removed[0](muteController);
groupBypassRegistration.removed[0](groupBypass);
groupMuteRegistration.removed[0](groupMute);
assert.equal(nodeChanged.size, 0);
assert.equal(workflowLoaded.size, 0);
assert.equal(intervals.size, 0);
bypassController.mountDefinition.destroy();
replacement.mountDefinition.destroy();
assert.equal(nodeChanged.size, 0);
assert.equal(intervals.size, 0);

console.log("PASS: Custom Switch typed tag/group controllers and lifecycle");
