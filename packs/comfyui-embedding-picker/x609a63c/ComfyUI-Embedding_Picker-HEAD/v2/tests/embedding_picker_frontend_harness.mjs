import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js/,
  /LiteGraph|app\.graph|app\.canvas/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|FileReader|innerHTML/,
]) assert.doesNotMatch(source, forbidden);


class Widget {
  constructor(name, value, options = {}) {
    this.name = name;
    this.value = value;
    this.options = options;
    this.hidden = false;
    this.optionWrites = [];
    this.valueWrites = [];
  }
  getValue() { return this.value; }
  setValue(value) { this.value = value; this.valueWrites.push(value); }
  getOptions() { return this.options; }
  setOption(key, value) { this.options[key] = value; this.optionWrites.push([key, value]); }
  setHidden(value) { this.hidden = value; }
}

function collection(values, add) {
  return {
    byName(name) { return values.get(name); },
    get(name) { return values.get(name); },
    add,
    remove(name) { return values.delete(name); },
  };
}

function makeNode({
  id,
  comfyClass,
  text = "",
  embedding,
  position = { x: 500, y: 100 },
  size = { width: 240, height: 180 },
  color = "#123",
  bgColor = "#456",
  existingTextInput = false,
  connect = true,
}) {
  const widgets = new Map([
    ["text", new Widget("text", text, { multiline: true })],
    ["embedding", new Widget("embedding", embedding)],
  ]);
  const inputs = new Map();
  const inputAdds = [];
  if (existingTextInput) inputs.set("text", { name: "text", isWidgetInput: true });
  const links = [];
  const outputs = new Map([
    ["text", {
      connectTo(targetNodeId, input) {
        links.push([targetNodeId, input]);
        return connect ? { id: "link-1" } : undefined;
      },
    }],
  ]);
  return {
    id,
    comfyClass,
    removed: false,
    widgets: collection(widgets),
    inputs: collection(inputs, (name, type, options) => {
      const input = { name, type, options };
      inputs.set(name, input);
      inputAdds.push(input);
      return input;
    }),
    outputs: collection(outputs),
    getPosition() { return position; },
    getSize() { return size; },
    setSize(value) { size = value; this.sizeWrite = value; },
    getColor() { return color; },
    setColor(value) { color = value; this.colorWrite = value; },
    getBgColor() { return bgColor; },
    setBgColor(value) { bgColor = value; this.bgColorWrite = value; },
    remove() { this.removed = true; },
    _widgets: widgets,
    _inputs: inputs,
    _inputAdds: inputAdds,
    _links: links,
  };
}

const definitions = [];
const added = [];
const selected = [];
let modelCalls = 0;
let allowNextConnection = true;
const comfy = {
  models: {
    async list(folder) {
      modelCalls += 1;
      assert.equal(folder, "embeddings");
      return ["EasyNegative.pt", "nested/detail.safetensors"];
    },
  },
  graph: {
    add(type, init) {
      const node = makeNode({
        id: `picker-${added.length + 1}`,
        comfyClass: type,
        size: { width: 210, height: 118 },
        connect: allowNextConnection,
      });
      allowNextConnection = true;
      added.push({ type, init, node });
      return node;
    },
    select(nodes) { selected.push(nodes); },
  },
  defs: {
    extend(selector, configure) {
      const hooks = {};
      configure({
        onCreated(callback) { hooks.created = callback; },
        addMenuItem(item) { hooks.menu = item; },
      });
      definitions.push({ selector, hooks });
    },
  },
};

const context = vm.createContext({ console, Promise, Math, Number, Object, String });
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

const pickerDef = definitions.find(({ selector }) => selector === "EmbeddingPicker");
const menuDef = definitions.find(({ selector }) => Array.isArray(selector));
assert.ok(pickerDef);
assert.deepEqual([...menuDef.selector], ["EmbeddingPicker", "CLIPTextEncode"]);
assert.equal(menuDef.hooks.menu.label, "Prepend Embedding Picker");
assert.equal(menuDef.hooks.menu.order, -100);

const emptyPicker = makeNode({ id: "empty", comfyClass: "EmbeddingPicker" });
const restoredPicker = makeNode({
  id: "restored", comfyClass: "EmbeddingPicker", embedding: "retired.pt",
});
pickerDef.hooks.created(emptyPicker);
pickerDef.hooks.created(restoredPicker);
await new Promise((resolve) => setImmediate(resolve));
assert.equal(modelCalls, 1, "the closed catalogue is shared across picker instances");
assert.equal(emptyPicker._widgets.get("embedding").getValue(), "EasyNegative.pt");
assert.equal(
  JSON.stringify(emptyPicker._widgets.get("embedding").options.values),
  JSON.stringify(["EasyNegative.pt", "nested/detail.safetensors"]),
);
assert.equal(
  JSON.stringify(restoredPicker._widgets.get("embedding").options.values),
  JSON.stringify(["retired.pt", "EasyNegative.pt", "nested/detail.safetensors"]),
  "a saved logical name remains representable if the local model was removed",
);
assert.equal(restoredPicker._widgets.get("embedding").valueWrites.length, 0);

const clip = makeNode({
  id: "clip-1", comfyClass: "CLIPTextEncode", text: "cinematic prompt",
  position: { x: 600, y: 250 }, size: { width: 260, height: 210 },
  color: "#abc", bgColor: "#def",
});
menuDef.hooks.menu.run(clip);
assert.equal(added[0].type, "EmbeddingPicker");
assert.equal(JSON.stringify(added[0].init.position), JSON.stringify({ x: 270, y: 270 }));
const newPicker = added[0].node;
assert.equal(JSON.stringify(newPicker.sizeWrite), JSON.stringify({ width: 300, height: 200 }));
assert.equal(newPicker.colorWrite, "#abc");
assert.equal(newPicker.bgColorWrite, "#def");
assert.equal(newPicker._widgets.get("text").getValue(), "cinematic prompt");
assert.equal(clip._widgets.get("text").hidden, true);
assert.equal(clip._inputAdds.length, 1);
assert.equal(clip._inputAdds[0].type, "STRING");
assert.equal(clip._inputAdds[0].options.widget, "text");
assert.equal(JSON.stringify(clip._inputAdds[0].options.widgetConfig),
  JSON.stringify({ type: "STRING", options: { multiline: true } }));
assert.deepEqual(newPicker._links, [["clip-1", "text"]]);
assert.equal(JSON.stringify(clip.sizeWrite), JSON.stringify({ width: 260, height: 120 }));
assert.equal(selected.at(-1)[0], newPicker);

const chained = makeNode({
  id: "picker-existing", comfyClass: "EmbeddingPicker", text: "second",
  existingTextInput: true, position: { x: 100, y: 40 }, size: { width: 300, height: 118 },
});
menuDef.hooks.menu.run(chained);
assert.equal(JSON.stringify(added[1].init.position), JSON.stringify({ x: -230, y: 40 }));
assert.equal(chained._inputAdds.length, 0, "existing converted inputs are reused");
assert.equal(chained._widgets.get("text").hidden, false,
  "an already converted input is not mutated again");
assert.equal(chained.sizeWrite, undefined, "short nodes are not forcibly resized");

const failing = makeNode({
  id: "failure", comfyClass: "CLIPTextEncode", text: "keep",
});
allowNextConnection = false;
const failedPicker = module.namespace.prependEmbeddingPicker(failing);
assert.equal(failedPicker, undefined);
assert.equal(added.at(-1).node.removed, true, "a failed connection leaves no orphan node");
assert.equal(failing._inputs.has("text"), false, "failure rolls back the added input");
assert.equal(failing._widgets.get("text").hidden, false, "failure restores the text widget");
assert.equal(failing.sizeWrite, undefined, "failure cannot resize the target");
assert.notEqual(selected.at(-1)[0], added.at(-1).node, "failure cannot change selection");

console.log("PASS: secure Embedding Picker catalogue, prepend workflow, and failure cleanup");
