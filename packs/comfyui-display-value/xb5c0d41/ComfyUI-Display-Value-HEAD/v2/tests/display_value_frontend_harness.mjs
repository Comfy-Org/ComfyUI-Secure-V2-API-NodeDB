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

const definition = definitions.find(({ selector }) => selector === "DisplayValue");
assert.ok(definition, "DisplayValue uses the V2 definition API");

function makeNode(saved = { version: 1, preview: "" }) {
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
      mount(options) {
        assert.equal(options.name, "preview");
        mountDef = options;
        options.render(container, mounted);
        unmount = () => options.destroy?.();
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
      mountDef.render(next, value);
      return { container: next, destroy: () => mountDef.destroy?.() };
    },
  };
}

function preview(container) {
  assert.equal(container.children.length, 1);
  return container.children[0].value;
}

function json(value) {
  return JSON.parse(JSON.stringify(value));
}

const restored = makeNode({ version: 1, preview: "saved\nvalue" });
assert.deepEqual(json(restored.node.constraints), [
  { minWidth: 240, minHeight: 96, autoHeight: true },
]);
assert.equal(restored.mountDef.serialize, true);
assert.equal(restored.mountDef.sendToPrompt, false);
assert.equal(restored.mountDef.hideOnZoom, false);
assert.deepEqual(json(restored.mountDef.defaultValue), { version: 1, preview: "" });
assert.equal(preview(restored.container), "saved\nvalue");
assert.equal(restored.container.children[0].tagName, "TEXTAREA");
assert.equal(restored.container.children[0].readOnly, true);
assert.equal(restored.container.children[0].attributes["aria-label"],
  "Display Value output");
assert.equal(restored.heightWrites.length, 1);

definition.hooks.executed(restored.node, { raw: { value: ["replacement"] } });
assert.equal(preview(restored.container), "replacement");
assert.deepEqual(json(restored.mounted.setCalls.at(-1)), {
  version: 1, preview: "replacement",
});
assert.equal(restored.container.children.length, 1,
  "execution replaces rather than appends the display");

const sameHeightWrites = restored.heightWrites.length;
definition.hooks.executed(restored.node, { raw: { value: ["again"] } });
assert.equal(restored.heightWrites.length, sameHeightWrites,
  "equal computed height does not create a resize loop");
definition.hooks.executed(restored.node, {
  raw: { value: ["one\ntwo\nthree\nfour\nfive\nsix"] },
});
assert.ok(restored.heightWrites.at(-1) > restored.heightWrites[0]);
assert.ok(restored.heightWrites.at(-1) <= 360);

definition.hooks.executed(restored.node, { raw: { value: [] } });
assert.equal(preview(restored.container), "one\ntwo\nthree\nfour\nfive\nsix",
  "the pinned frontend retains its prior preview for a falsy execution value");

const hostile = '<img src=x onerror="globalThis.pwned=1"><script>bad()</script>';
definition.hooks.executed(restored.node, { raw: { value: [hostile] } });
assert.equal(preview(restored.container), hostile);
assert.equal(restored.container.children[0].children.length, 0,
  "hostile text remains a textarea value rather than markup");

const serialized = structuredClone(restored.mounted.get());
const reloaded = makeNode(serialized);
assert.equal(preview(reloaded.container), hostile,
  "mounted state restores on workflow reload");

for (const bad of [null, { version: 2, preview: "x" },
  { version: 1, preview: 4 }]) {
  const malformed = makeNode(bad);
  assert.equal(preview(malformed.container), "");
  malformed.unmount();
}

const staleValue = restored.mounted;
const oldContainer = restored.container;
restored.unmount();
assert.equal(staleValue.unsubscribeCalls, 1);
assert.equal(oldContainer.children.length, 0);
staleValue.restore({ version: 1, preview: "stale" });
assert.equal(oldContainer.children.length, 0);

const freshValue = new MountedValue({ version: 1, preview: "remounted" });
const remounted = restored.remount(freshValue);
assert.equal(preview(remounted.container), "remounted");
definition.hooks.executed(restored.node, { raw: { value: ["live again"] } });
assert.equal(preview(remounted.container), "live again");
definition.hooks.removed(restored.node);
assert.equal(freshValue.unsubscribeCalls, 1);
assert.equal(remounted.container.children.length, 0);
remounted.destroy();
assert.equal(freshValue.unsubscribeCalls, 1, "teardown is idempotent");

assert.equal(module.namespace.normalizeExecutionValue(["a", "b"]), "a\nb");
assert.equal(module.namespace.normalizeExecutionValue([], "old"), "old");
assert.equal(module.namespace.normalizeState({ version: 1, preview: "ok" }), "ok");
assert.equal(module.namespace.displayHeight("x\n".repeat(1000)), 360);

console.log("PASS: secure Display Value state, safety, sizing, and teardown");
