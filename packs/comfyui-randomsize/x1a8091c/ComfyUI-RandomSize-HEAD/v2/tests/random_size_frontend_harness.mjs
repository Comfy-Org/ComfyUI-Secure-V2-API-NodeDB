import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|\/scripts\/api\.js|\/scripts\/widgets\.js/,
  /LiteGraph|app\.graph|app\.canvas|requestAnimationFrame/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|innerHTML/,
  /addEventListener|removeEventListener/,
]) assert.doesNotMatch(source, forbidden);


class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.style = {};
    this.attributes = {};
    this.textContent = "";
  }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(name, value) { this.attributes[name] = value; }
}

const ownerDocument = {
  createElement(tagName) { return new FakeElement(tagName, ownerDocument); },
};

class MountedValue {
  constructor(value) {
    this.value = structuredClone(value);
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
}

class Widget {
  constructor(value) {
    this.value = value;
    this.options = {};
    this.listeners = new Set();
    this.unsubscribeCalls = 0;
  }
  getValue() { return this.value; }
  setValue(value) {
    this.value = value;
    for (const listener of [...this.listeners]) listener(value);
  }
  setOption(name, value) { this.options[name] = value; }
  on(event, listener) {
    assert.equal(event, "change");
    this.listeners.add(listener);
    return () => {
      this.unsubscribeCalls += 1;
      this.listeners.delete(listener);
    };
  }
}

const definitions = [];
const comfy = {
  defs: {
    extend(selector, configure) {
      const hooks = {};
      configure({
        onCreated(callback) { hooks.created = callback; },
        onConfigured(callback) { hooks.configured = callback; },
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
const cache = new Map();
async function loadModule(filename) {
  const resolved = path.resolve(filename);
  if (cache.has(resolved)) return cache.get(resolved);
  const module = new vm.SourceTextModule(fs.readFileSync(resolved, "utf8"), {
    context,
    identifier: pathToFileURL(resolved).href,
  });
  cache.set(resolved, module);
  await module.link(async (specifier) => {
    if (specifier === "/comfy/api/v2.js") {
      const stub = new vm.SyntheticModule(["comfy"], function () {
        this.setExport("comfy", comfy);
      }, { context });
      await stub.link(() => {});
      return stub;
    }
    assert.equal(specifier, "./presets.js");
    return loadModule(path.join(path.dirname(resolved), specifier));
  });
  return module;
}

const module = await loadModule(entry);
await module.evaluate();
const definition = definitions.find(({ selector }) => selector === "JOJR_RandomSize");
assert.ok(definition, "Random Size uses the V2 definition API");

function makeNode({
  preset = "Preset",
  seed = 0,
  saved = { version: 1, preset: "Preset", selected: "" },
} = {}) {
  const presetWidget = new Widget(preset);
  const seedWidget = new Widget(seed);
  const mounted = new MountedValue(saved);
  const container = new FakeElement("div", ownerDocument);
  const heights = [];
  let mountDef;
  const node = {
    constraints: [],
    widgets: {
      get(name) {
        if (name === "preset") return presetWidget;
        if (name === "seed") return seedWidget;
        return undefined;
      },
      mount(options) {
        mountDef = options;
        options.render(container, mounted);
        return { setHeight(value) { heights.push(value); } };
      },
    },
    setSizeConstraints(value) { this.constraints.push(value); },
  };
  definition.hooks.created(node);
  return { node, presetWidget, seedWidget, mounted, container, heights,
    get mountDef() { return mountDef; } };
}

function text(view) {
  assert.equal(view.container.children.length, 1);
  const output = view.container.children[0];
  assert.equal(output.tagName, "PRE");
  return output.textContent;
}

function json(value) {
  return JSON.parse(JSON.stringify(value));
}

const initial = makeNode();
assert.deepEqual(json(initial.node.constraints), [
  { minWidth: 220, minHeight: 220, autoHeight: true },
]);
assert.equal(initial.mountDef.serialize, true);
assert.equal(initial.mountDef.sendToPrompt, false);
assert.equal(initial.mountDef.hideOnZoom, false);
assert.equal(initial.seedWidget.options.max, 8);
assert.match(text(initial), /^Sizes in present:\n320x768/);
assert.doesNotMatch(text(initial), /\*/);
assert.ok(initial.heights[0] >= 120);

initial.seedWidget.setValue(999);
initial.presetWidget.setValue("FLUX.yaml");
assert.equal(initial.seedWidget.options.max, 12);
assert.equal(initial.seedWidget.getValue(), 12);
assert.match(text(initial), /1920x1088/);
assert.doesNotMatch(text(initial), /320x768/);

definition.hooks.executed(initial.node, {
  raw: {
    preset: ["FLUX.yaml"],
    selected: ["1024x1024"],
    sizes: ["1920x1088", "*1024x1024*"],
  },
});
assert.match(text(initial), /\*1024x1024\*/);
assert.deepEqual(json(initial.mounted.setCalls.at(-1)), {
  version: 1, preset: "FLUX.yaml", selected: "1024x1024",
});

const serialized = structuredClone(initial.mounted.get());
const restored = makeNode({ preset: "FLUX.yaml", seed: 4, saved: serialized });
assert.match(text(restored), /\*1024x1024\*/,
  "selected size survives workflow reload");
definition.hooks.configured(restored.node);
assert.match(text(restored), /\*1024x1024\*/);

restored.presetWidget.setValue("512.yaml");
assert.doesNotMatch(text(restored), /\*/,
  "changing presets clears the old selected marker");
assert.equal(restored.seedWidget.options.max, 8);

for (const bad of [null, {}, { version: 1, preset: "<script>x</script>",
  selected: "<img onerror=x>" }]) {
  const malformed = makeNode({ saved: bad });
  assert.match(text(malformed), /^Sizes in present:\n320x768/);
  assert.equal(malformed.container.children[0].children.length, 0,
    "display is textContent, never parsed markup");
  malformed.mountDef.destroy();
}

const oldContainer = initial.container;
const presetListeners = initial.presetWidget.listeners.size;
assert.equal(presetListeners, 1);
initial.mountDef.destroy();
assert.equal(oldContainer.children.length, 0);
assert.equal(initial.presetWidget.unsubscribeCalls, 1);
assert.equal(initial.mounted.unsubscribeCalls, 1);
initial.presetWidget.setValue("Preset");
assert.equal(oldContainer.children.length, 0);
definition.hooks.removed(initial.node);
assert.equal(initial.presetWidget.unsubscribeCalls, 1,
  "teardown is idempotent");

assert.deepEqual(
  JSON.parse(JSON.stringify(module.namespace.normalizeState({
    version: 1, preset: "SDXL.yaml", selected: "1024x1024",
  }))),
  { version: 1, preset: "SDXL.yaml", selected: "1024x1024" },
);
assert.equal(module.namespace.validPreset("../../secret"), "Preset");
assert.ok(module.namespace.displayHeight({
  version: 1, preset: "1024.yaml", selected: "",
}) <= 360);

console.log("PASS: secure Random Size mounted state, safety, and teardown");
