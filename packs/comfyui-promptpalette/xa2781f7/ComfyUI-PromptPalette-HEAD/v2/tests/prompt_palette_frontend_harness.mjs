import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath, pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const web = path.dirname(entry);
const allSource = ["main.js", "palette.js", "line.js", "text_lines.js"]
  .map((name) => fs.readFileSync(path.join(web, name), "utf8"))
  .join("\n");
for (const forbidden of [
  /\/scripts\/app\.js/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|FileReader|innerHTML/,
  /addEventListener\s*\(\s*["']key/,
]) assert.doesNotMatch(allSource, forbidden);


class Element {
  constructor(tag, owner) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = owner;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.style = {};
    this.textContent = "";
    this.title = "";
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = [...items]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  addEventListener(name, listener) {
    const values = this.listeners.get(name) || [];
    values.push(listener);
    this.listeners.set(name, values);
  }
  dispatch(name) {
    for (const listener of this.listeners.get(name) || []) listener({ type: name });
  }
}

const ownerDocument = {
  createElement(tag) { return new Element(tag, ownerDocument); },
};

function descendants(element) {
  return [element, ...element.children.flatMap(descendants)];
}

function find(element, attr, value) {
  return descendants(element).find((item) => item.attributes.get(attr) === value);
}

function findAll(element, attr, value) {
  return descendants(element).filter((item) => item.attributes.get(attr) === value);
}

class Widget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.hidden = false;
    this.listeners = new Set();
    this.commits = [];
  }
  getValue() { return this.value; }
  setValue(value) {
    if (Object.is(this.value, value)) return;
    const oldValue = this.value;
    this.value = value;
    this.commits.push(value);
    for (const listener of [...this.listeners]) listener(value, oldValue);
  }
  setHidden(value) { this.hidden = value; }
  on(event, listener) {
    assert.equal(event, "change");
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

let extension;
const comfy = { defs: { extend(selector, callback) {
  const hooks = {};
  callback({
    onCreated(fn) { hooks.created = fn; },
    onConfigured(fn) { hooks.configured = fn; },
    onResized(fn) { hooks.resized = fn; },
    onRemoved(fn) { hooks.removed = fn; },
  });
  extension = { selector, hooks };
} } };

const context = vm.createContext({ console, Math, Number, Object, String });
const modules = new Map();
async function load(filename) {
  const absolute = path.resolve(filename);
  if (modules.has(absolute)) return modules.get(absolute);
  const module = new vm.SourceTextModule(fs.readFileSync(absolute, "utf8"), {
    context, identifier: pathToFileURL(absolute).href,
  });
  modules.set(absolute, module);
  await module.link(async (specifier, referencing) => {
    if (specifier === "/comfy/api/v2.js") {
      const stub = new vm.SyntheticModule(["comfy"], function () {
        this.setExport("comfy", comfy);
      }, { context });
      await stub.link(() => {});
      return stub;
    }
    return load(path.resolve(path.dirname(fileURLToPath(referencing.identifier)), specifier));
  });
  return module;
}

await (await load(entry)).evaluate();
assert.equal(extension.selector, "PromptPalette");

const lineApi = modules.get(path.join(web, "line.js")).namespace;
const textApi = modules.get(path.join(web, "text_lines.js")).namespace;
assert.equal(new lineApi.Line("  (fox:1.25), // tail").displayText, "fox // tail");
assert.equal(new lineApi.Line("  (fox:1.25), // tail").weightText, "1.25");
assert.equal(new lineApi.Line("<img src=x onerror=bad>").displayText,
  "<img src=x onerror=bad>");
const cycles = new textApi.TextLines("fox");
for (let index = 0; index < 25; index += 1) cycles.adjustWeightAt(0, 0.1);
assert.equal(cycles.toString(), "(fox:2)");
for (let index = 0; index < 30; index += 1) cycles.adjustWeightAt(0, -0.1);
assert.equal(cycles.toString(), "(fox:0.1)");
for (let index = 0; index < 9; index += 1) cycles.adjustWeightAt(0, 0.1);
assert.equal(cycles.toString(), "fox", "repeated +/- cycles return exactly to 1.0");

function makeNode(textValue, delimiterValue = "comma", lineBreakValue = true) {
  const controls = new Map([
    ["text", new Widget("text", textValue)],
    ["delimiter", new Widget("delimiter", delimiterValue)],
    ["line_break", new Widget("line_break", lineBreakValue)],
    ["prefix", new Widget("prefix", "linked prefix")],
  ]);
  let mountDef;
  let mountCount = 0;
  const node = {
    widgets: {
      get(name) { return controls.get(name); },
      mount(def) {
        mountDef = def;
        mountCount += 1;
        const handle = new Widget(def.name, undefined);
        controls.set(def.name, handle);
        return handle;
      },
    },
    setSizeConstraints(value) { this.constraints = value; },
  };
  return { node, controls, get mountDef() { return mountDef; }, get mountCount() { return mountCount; } };
}

const hostile = "cat\n// dog\n<img src=x onerror=bad> // <script>bad()</script>\n";
const first = makeNode(hostile);
extension.hooks.created(first.node);
extension.hooks.created(first.node);
assert.equal(first.mountCount, 1, "node creation is idempotent");
assert.equal(JSON.stringify(first.node.constraints), JSON.stringify({ minWidth: 320, minHeight: 220 }));
assert.equal(first.mountDef.height, 260);
assert.equal(first.mountDef.serialize, false);
assert.equal(first.mountDef.sendToPrompt, false);

const container = new Element("div", ownerDocument);
first.mountDef.render(container);
const root = container.children[0];
assert.equal(first.controls.get("text").hidden, true);
assert.equal(first.controls.get("delimiter").hidden, true);
assert.equal(first.controls.get("line_break").hidden, true);
assert.equal(first.controls.get("prefix").hidden, false, "linked prefix remains visible");
assert.equal(findAll(root, "data-line-index", "0").length, 1);
assert.equal(find(root, "data-line-index", "1").children[1].textContent, "dog");
const hostilePhrase = find(root, "data-line-index", "2").children[1];
assert.equal(hostilePhrase.textContent, "<img src=x onerror=bad> // <script>bad()</script>");
assert.equal(descendants(root).some((item) => ["IMG", "SCRIPT"].includes(item.tagName)), false,
  "authored text never becomes markup");

find(root, "data-action", "toggle-edit").dispatch("click");
assert.equal(first.controls.get("text").hidden, false);
assert.equal(first.controls.get("delimiter").hidden, false);
assert.equal(first.controls.get("line_break").hidden, false);
assert.equal(find(root, "data-action", "toggle-edit").textContent, "Save");
assert.equal(first.controls.get("text").getValue(), hostile, "edit transition preserves text");
find(root, "data-action", "toggle-edit").dispatch("click");
assert.equal(find(root, "data-action", "toggle-edit").textContent, "Edit");

find(root, "data-line-index", "0").children[0].dispatch("click");
assert.ok(first.controls.get("text").getValue().startsWith("// cat\n"));
find(find(root, "data-line-index", "0"), "data-action", "weight-plus").dispatch("click");
assert.ok(first.controls.get("text").getValue().startsWith("// (cat:1.1)\n"));
find(find(root, "data-line-index", "0"), "data-action", "weight-minus").dispatch("click");
assert.ok(first.controls.get("text").getValue().startsWith("// cat\n"));

first.controls.get("delimiter").value = "corrupt";
first.controls.get("line_break").value = "yes";
extension.hooks.configured(first.node, {});
assert.equal(first.controls.get("delimiter").getValue(), "comma");
assert.equal(first.controls.get("line_break").getValue(), true);

const serializedText = first.controls.get("text").getValue();
extension.hooks.resized(first.node);
assert.equal(first.controls.get("text").getValue(), serializedText, "resize cannot mutate state");
first.mountDef.destroy();
extension.hooks.removed(first.node);
assert.equal(container.children.length, 0);
assert.equal(first.controls.get("text").listeners.size, 0, "teardown unsubscribes host listeners");
assert.equal(first.controls.get("text").hidden, false);

const restored = makeNode(serializedText, "space", false);
extension.hooks.created(restored.node);
const restoredContainer = new Element("div", ownerDocument);
restored.mountDef.render(restoredContainer);
extension.hooks.configured(restored.node, { widgets_values: [serializedText, "space", false] });
const restoredRoot = restoredContainer.children[0];
assert.equal(restored.controls.get("text").getValue(), serializedText);
assert.ok(find(restoredRoot, "data-line-index", "0").children[1].textContent.includes("cat"));

restored.controls.get("text").setValue("");
assert.equal(find(restoredRoot, "data-role", "empty").style.display, "flex");
restored.mountDef.destroy();

console.log("PASS: secure PromptPalette parsing, mounted UI, state, safety, and teardown");
