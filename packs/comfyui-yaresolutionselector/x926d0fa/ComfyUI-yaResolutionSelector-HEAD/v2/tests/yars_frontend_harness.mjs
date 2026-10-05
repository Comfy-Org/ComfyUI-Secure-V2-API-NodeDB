import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|\/scripts\/widgets\.js/,
  /app\.registerExtension|LiteGraph|app\.graph|app\.canvas/,
  /(?:^|[^A-Za-z])document\s*\./m, /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|innerHTML|setTimeout|setInterval/,
]) assert.doesNotMatch(source, forbidden);


class Widget {
  constructor(name, value, options = {}) {
    this.name = name;
    this.value = value;
    this.options = options;
    this.hidden = false;
  }
  getValue() { return this.value; }
  setValue(value) { this.value = value; }
  getOptions() { return this.options; }
  setHidden(value) { this.hidden = value; }
}


function makeContainer() {
  const field = {
    value: "", readOnly: false, style: {}, attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
  };
  return {
    child: undefined,
    ownerDocument: { createElement(tag) { assert.equal(tag, "textarea"); return field; } },
    replaceChildren(child) { this.child = child; },
    field,
  };
}


function makeNode({
  id, comfyClass, position = { x: 500, y: 100 }, connect = true,
  existingInputs = false,
}) {
  const widgets = new Map([
    ["width", new Widget("width", 512, { default: 512 })],
    ["height", new Widget("height", 512, { default: 512 })],
  ]);
  const inputs = new Map();
  if (existingInputs) {
    inputs.set("width", { name: "width" });
    inputs.set("height", { name: "height" });
  }
  const links = [];
  const outputs = new Map(["width", "height"].map((name) => [name, {
    connectTo(targetId, inputName) {
      links.push([name, targetId, inputName]);
      return connect ? { id: `${name}-link` } : undefined;
    },
    disconnect(targetId) { this.disconnected = targetId; return true; },
  }]));
  const mounted = new Map();
  const node = {
    id, comfyClass, removed: false, constraints: undefined, size: undefined,
    widgets: {
      get(name) { return mounted.get(name)?.widget ?? widgets.get(name); },
      mount(name, options) {
        let value = options.defaultValue;
        const listeners = new Set();
        const widget = new Widget(name, value);
        widget.setValue = (next) => {
          value = next;
          widget.value = next;
          for (const listener of [...listeners]) listener(next);
        };
        const mountedValue = {
          get: () => value,
          onChange(listener) { listeners.add(listener); return () => listeners.delete(listener); },
        };
        const container = makeContainer();
        const cleanup = options.render(container, mountedValue);
        const handle = { widget, container, cleanup, setHeight(height) { this.height = height; } };
        mounted.set(name, handle);
        return handle;
      },
    },
    inputs: {
      byName(name) { return inputs.get(name); },
      add(name, type, options) { const value = { name, type, options }; inputs.set(name, value); return value; },
      remove(name) { return inputs.delete(name); },
    },
    outputs: { byName(name) { return outputs.get(name); } },
    getPosition() { return position; },
    setSize(value) { this.size = value; },
    setSizeConstraints(value) { this.constraints = value; },
    remove() { this.removed = true; },
    _widgets: widgets, _inputs: inputs, _outputs: outputs, _links: links, _mounted: mounted,
  };
  return node;
}


const definitions = [];
const added = [];
const selected = [];
let connectNext = true;
const comfy = {
  defs: {
    extend(selector, configure) {
      const hooks = { menus: [] };
      configure({
        onCreated(callback) { hooks.created = callback; },
        onExecuted(callback) { hooks.executed = callback; },
        addMenuItem(item) { hooks.menus.push(item); },
      });
      definitions.push({ selector, hooks });
    },
  },
  graph: {
    add(type, init) {
      const node = makeNode({ id: `new-${added.length}`, comfyClass: type, connect: connectNext });
      connectNext = true;
      added.push({ type, init, node });
      return node;
    },
    select(nodes) { selected.push(nodes); },
  },
};


const context = vm.createContext({ console, Number, String, Object, Array, Math });
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


const yars = definitions.find(({ selector }) => Array.isArray(selector) && selector[0] === "YARS");
const targets = definitions.find(({ selector }) => Array.isArray(selector) && selector[0] === "EmptyLatentImage");
assert.deepEqual([...yars.selector], ["YARS", "YARSAdv"]);
assert.deepEqual([...targets.selector], ["EmptyLatentImage", "ImageScale", "LatentUpscale"]);
assert.equal(targets.hooks.menus.length, 2);

const display = makeNode({ id: "display", comfyClass: "YARS" });
yars.hooks.created(display);
assert.equal(
  JSON.stringify(display.constraints),
  JSON.stringify({ minWidth: 260, minHeight: 120, autoHeight: true }),
);
assert.equal(display._mounted.get("resolution_printout").height, 68);
yars.hooks.executed(display, { raw: { width: [1024], height: [768], ratio: [4 / 3] } });
const readout = display._mounted.get("resolution_printout");
assert.equal(readout.widget.value, "resolution: 1024x768 (~0.75 Mpx)\nratio: ~1.33");
assert.equal(readout.container.field.value, readout.widget.value);
assert.equal(readout.container.field.readOnly, true);

const target = makeNode({ id: "target", comfyClass: "EmptyLatentImage" });
targets.hooks.menus[0].run(target);
assert.equal(added[0].type, "YARS");
assert.equal(
  JSON.stringify(added[0].init.position),
  JSON.stringify({ x: 210, y: 100 }),
);
assert.equal(
  JSON.stringify(added[0].node.size),
  JSON.stringify({ width: 260, height: 180 }),
);
assert.deepEqual(added[0].node._links, [
  ["width", "target", "width"], ["height", "target", "height"],
]);
assert.equal(target._widgets.get("width").hidden, true);
assert.equal(target._widgets.get("height").hidden, true);
assert.equal(selected.at(-1)[0], added[0].node);

const existing = makeNode({ id: "existing", comfyClass: "ImageScale", existingInputs: true });
targets.hooks.menus[1].run(existing);
assert.equal(added[1].type, "YARSAdv");
assert.equal(existing._widgets.get("width").hidden, false);
assert.equal(existing._widgets.get("height").hidden, false);

const failure = makeNode({ id: "failure", comfyClass: "LatentUpscale" });
connectNext = false;
const failed = module.namespace.prependSelector(failure);
assert.equal(failed, undefined);
assert.equal(added.at(-1).node.removed, true);
assert.equal(failure._inputs.size, 0);
assert.equal(failure._widgets.get("width").hidden, false);
assert.equal(failure._widgets.get("height").hidden, false);

console.log("PASS: yaResolutionSelector readout, quick nodes, rollback, and security");
