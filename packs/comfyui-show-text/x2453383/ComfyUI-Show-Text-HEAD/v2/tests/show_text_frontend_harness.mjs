import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|\/scripts\/widgets\.js/,
  /LiteGraph|app\.graph|app\.canvas|requestAnimationFrame/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|FileReader|innerHTML/,
]) assert.doesNotMatch(source, forbidden);


class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.style = {};
    this.attributes = {};
    this.value = "";
    this.readOnly = false;
  }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(name, value) { this.attributes[name] = value; }
}

const ownerDoc = {
  createElement(tagName) { return new FakeElement(tagName, ownerDoc); },
};

class MountedValue {
  constructor(value) {
    this.value = value;
    this.listeners = new Set();
    this.setCalls = [];
    this.unsubscribeCalls = 0;
  }
  get() { return this.value; }
  set(value) {
    this.value = structuredClone(value);
    this.setCalls.push(structuredClone(value));
    for (const listener of [...this.listeners]) listener(this.value);
  }
  onChange(listener) {
    this.listeners.add(listener);
    return () => {
      this.unsubscribeCalls += 1;
      this.listeners.delete(listener);
    };
  }
  restore(value) {
    this.value = structuredClone(value);
    for (const listener of [...this.listeners]) listener(this.value);
  }
}

const definitions = [];
const comfy = {
  defs: {
    extend(selector, configure) {
      const hooks = {};
      configure({
        onCreated(callback) { hooks.created = callback; },
        onExecuted(callback) { hooks.executed = callback; },
        onRemoved(callback) { hooks.removed = callback; },
      });
      definitions.push({ selector, hooks });
    },
  },
};

const context = vm.createContext({
  console, Promise, Math, Number, Object, String, Array, JSON,
});
const module = new vm.SourceTextModule(source, {
  context,
  identifier: pathToFileURL(entry).href,
});
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  const stub = new vm.SyntheticModule(["comfy"], function () {
    this.setExport("comfy", comfy);
  }, { context });
  await stub.link(() => {});
  return stub;
});
await module.evaluate();

const definition = definitions.find(({ selector }) => selector === "ShowText");
assert.ok(definition, "ShowText is extended exactly through the V2 definition API");

function makeNode(saved = { version: 1, texts: [] }) {
  const mounted = new MountedValue(saved);
  const container = new FakeElement("div", ownerDoc);
  const heightWrites = [];
  let mountDef;
  let unmount;
  const widgetHandle = {
    setHeight(value) { heightWrites.push(value); },
  };
  const node = {
    constraints: [],
    widgets: {
      mount(name, options) {
        assert.equal(name, "show_text_display");
        mountDef = options;
        unmount = options.render(container, mounted);
        return widgetHandle;
      },
    },
    setSizeConstraints(value) { this.constraints.push(value); },
  };
  definition.hooks.created(node);
  return {
    node, mounted, container, heightWrites,
    get mountDef() { return mountDef; },
    unmount() { unmount?.(); },
    remount(value = mounted) {
      const next = new FakeElement("div", ownerDoc);
      const destroy = mountDef.render(next, value);
      return { container: next, destroy };
    },
  };
}

function values(container) {
  return container.children.map((child) => child.value);
}

function json(value) {
  return JSON.parse(JSON.stringify(value));
}

const restored = makeNode({ version: 1, texts: ["saved", "line one\nline two"] });
assert.deepEqual(json(restored.node.constraints), [
  { minWidth: 280, minHeight: 80, autoHeight: true },
]);
assert.equal(restored.mountDef.serialize, true);
assert.equal(restored.mountDef.sendToPrompt, false);
assert.equal(restored.mountDef.hideOnZoom, false);
assert.deepEqual(json(restored.mountDef.defaultValue), { version: 1, texts: [] });
assert.deepEqual(values(restored.container), ["saved", "line one\nline two"]);
assert.ok(restored.container.children.every((child) =>
  child.tagName === "TEXTAREA" && child.readOnly &&
  child.attributes["aria-label"] === "Show Text output"));
assert.equal(restored.heightWrites.length, 1, "initial height is committed after mount");

definition.hooks.executed(restored.node, { raw: { text: ["replacement"] } });
assert.deepEqual(values(restored.container), ["replacement"]);
assert.deepEqual(json(restored.mounted.setCalls.at(-1)), {
  version: 1, texts: ["replacement"],
});
assert.equal(restored.container.children.length, 1,
  "execution replaces rather than appends display widgets");

const heightWritesAfterReplacement = restored.heightWrites.length;
definition.hooks.executed(restored.node, { raw: { text: ["again"] } });
assert.deepEqual(values(restored.container), ["again"]);
assert.equal(restored.heightWrites.length, heightWritesAfterReplacement,
  "equal computed height does not create a resize feedback loop");
definition.hooks.executed(restored.node, {
  raw: { text: ["one\ntwo\nthree\nfour\nfive\nsix"] },
});
assert.ok(restored.heightWrites.at(-1) > restored.heightWrites[0]);
assert.ok(restored.heightWrites.at(-1) <= 480);

definition.hooks.executed(restored.node, { raw: { text: [] } });
assert.deepEqual(values(restored.container), []);
definition.hooks.executed(restored.node, { raw: { text: ["", "second", "third"] } });
assert.deepEqual(values(restored.container), ["second", "third"],
  "the pinned frontend drops one leading empty display item");

const hostile = '<img src=x onerror="globalThis.pwned=1"><script>bad()</script>';
definition.hooks.executed(restored.node, { raw: { text: [hostile] } });
assert.equal(restored.container.children.length, 1);
assert.equal(restored.container.children[0].value, hostile);
assert.equal(restored.container.children[0].children.length, 0,
  "adversarial text remains a textarea value rather than markup");

const serialized = structuredClone(restored.mounted.get());
const reloaded = makeNode(serialized);
assert.deepEqual(values(reloaded.container), [hostile],
  "non-prompt mounted state restores on workflow reload");

for (const bad of [null, { version: 2, texts: ["x"] },
  { version: 1, texts: "x" }, { version: 1, texts: [1] }]) {
  const malformed = makeNode(bad);
  assert.deepEqual(values(malformed.container), []);
  malformed.unmount();
}

const staleValue = restored.mounted;
const oldContainer = restored.container;
restored.unmount();
assert.equal(staleValue.unsubscribeCalls, 1);
assert.deepEqual(values(oldContainer), []);
staleValue.restore({ version: 1, texts: ["stale update"] });
assert.deepEqual(values(oldContainer), [], "destroyed DOM cannot receive state updates");

const freshValue = new MountedValue({ version: 1, texts: ["remounted"] });
const remounted = restored.remount(freshValue);
assert.deepEqual(values(remounted.container), ["remounted"]);
definition.hooks.executed(restored.node, { raw: { text: ["live again"] } });
assert.deepEqual(values(remounted.container), ["live again"]);
definition.hooks.removed(restored.node);
assert.equal(freshValue.unsubscribeCalls, 1);
assert.deepEqual(values(remounted.container), []);
remounted.destroy();
assert.equal(freshValue.unsubscribeCalls, 1, "teardown is idempotent");

assert.deepEqual(json(module.namespace.normalizeExecutionText("single")), ["single"]);
assert.deepEqual(json(module.namespace.normalizeExecutionText(["a", "b"])), ["a", "b"]);
assert.deepEqual(json(module.namespace.normalizeExecutionText(["a", 2])), []);
assert.deepEqual(json(module.namespace.visibleTexts(["", "a", "b"])), ["a", "b"]);
assert.equal(module.namespace.displayHeight(["x\n".repeat(1000)]), 480);

console.log("PASS: secure Show Text mounted display, serialization, sizing, and teardown");
