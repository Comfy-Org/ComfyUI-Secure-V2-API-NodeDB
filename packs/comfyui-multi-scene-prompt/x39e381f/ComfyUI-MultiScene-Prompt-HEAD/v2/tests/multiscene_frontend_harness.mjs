import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|sessionStorage|indexedDB|fetch\s*\(|XMLHttpRequest|WebSocket/,
  /innerHTML|outerHTML|insertAdjacentHTML/,
  /addEventListener\s*\(\s*["']key/,
]) assert.doesNotMatch(source, forbidden);


class Element {
  constructor(tag, owner) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = owner;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.style = {};
    this.textContent = "";
    this.value = "";
    this.title = "";
    this.disabled = false;
    this.scrollLeft = 0;
    this.scrolls = 0;
  }
  get lastElementChild() { return this.children.at(-1); }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.children.push(item); return item; }
  replaceChildren(...items) { this.children = [...items]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  addEventListener(name, listener) {
    const values = this.listeners.get(name) || [];
    values.push(listener);
    this.listeners.set(name, values);
  }
  removeEventListener(name, listener) {
    const values = this.listeners.get(name) || [];
    this.listeners.set(name, values.filter((candidate) => candidate !== listener));
  }
  dispatch(name, extras = {}) {
    let prevented = false;
    const event = {
      type: name,
      preventDefault() { prevented = true; },
      ...extras,
    };
    for (const listener of [...(this.listeners.get(name) || [])]) listener(event);
    return prevented;
  }
  scrollIntoView() { this.scrolls += 1; }
}

const ownerDocument = {
  createElement(tag) { return new Element(tag, ownerDocument); },
};

function descendants(element) {
  return [element, ...element.children.flatMap(descendants)];
}

function buttons(root, text) {
  return descendants(root).filter(
    (item) => item.tagName === "BUTTON" && item.textContent === text,
  );
}

class Widget {
  constructor(name, value, type = "string") {
    this.name = name;
    this.value = value;
    this.widgetType = type;
    this.height = undefined;
  }
  getValue() { return this.value; }
  setHeight(value) { this.height = value; }
}

class MountedValue {
  constructor(value) {
    this.value = value;
    this.listeners = new Set();
    this.sets = [];
  }
  get() { return this.value; }
  set(value) {
    this.value = value;
    this.sets.push(value);
  }
  onChange(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
  restore(value) {
    this.value = value;
    for (const listener of [...this.listeners]) listener(value);
  }
}

let extension;
const comfy = { defs: { extend(selector, callback) {
  const hooks = {};
  callback({
    onCreated(fn) { hooks.created = fn; },
    onRemoved(fn) { hooks.removed = fn; },
  });
  extension = { selector, hooks };
} } };

const timers = new Map();
let nextTimer = 1;
function setTimeoutFake(callback) {
  const id = nextTimer++;
  timers.set(id, callback);
  return id;
}
function clearTimeoutFake(id) { timers.delete(id); }
function flushTimers() {
  while (timers.size) {
    const pending = [...timers.values()];
    timers.clear();
    for (const callback of pending) callback();
  }
}

const context = vm.createContext({
  console, JSON, Math, Object, String, WeakMap, WeakSet,
  setTimeout: setTimeoutFake, clearTimeout: clearTimeoutFake,
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
assert.equal(extension.selector, "MultiScenePrompt");

function makeNode(initial) {
  const controls = [
    new Widget("common_prompt", "shared"),
    new Widget("scenes_json", initial),
  ];
  let mountDef;
  let mountCount = 0;
  const node = {
    widgets: {
      get(name) { return controls.find((widget) => widget.name === name); },
      remove(name) {
        const index = controls.findIndex((widget) => widget.name === name);
        if (index < 0) return false;
        controls.splice(index, 1);
        return true;
      },
      mount(def) {
        mountDef = def;
        mountCount += 1;
        const handle = new Widget(def.name, def.defaultValue, "mounted");
        controls.push(handle);
        return handle;
      },
      move(name, index) {
        const old = controls.findIndex((widget) => widget.name === name);
        const [widget] = controls.splice(old, 1);
        controls.splice(index, 0, widget);
      },
    },
    setSizeConstraints(value) { this.constraints = value; },
  };
  return {
    node,
    controls,
    get mountDef() { return mountDef; },
    get mountCount() { return mountCount; },
  };
}

const hostile = '<img src=x onerror="bad()"><script>bad()</script>';
const fixture = makeNode(JSON.stringify([hostile, "second"]));
extension.hooks.created(fixture.node);
extension.hooks.created(fixture.node);
assert.equal(fixture.mountCount, 1, "creation is idempotent");
assert.deepEqual(fixture.controls.map((widget) => widget.name), [
  "common_prompt", "scenes_json",
]);
assert.equal(fixture.mountDef.height, 148);
assert.equal(fixture.mountDef.hideOnZoom, false);
assert.equal(fixture.mountDef.serialize, true);
assert.equal(fixture.mountDef.sendToPrompt, true);
assert.equal(fixture.mountDef.defaultValue, JSON.stringify([hostile, "second"]));
assert.equal(JSON.stringify(fixture.node.constraints), JSON.stringify({
  minWidth: 400, minHeight: 230, autoHeight: true,
}));

const mounted = new MountedValue(fixture.mountDef.defaultValue);
const container = new Element("div", ownerDocument);
fixture.mountDef.render(container, mounted);
flushTimers();
const root = container.children[0];
const textarea = descendants(root).find((item) => item.tagName === "TEXTAREA");
assert.equal(textarea.value, hostile);
assert.equal(descendants(root).some((item) => ["IMG", "SCRIPT"].includes(item.tagName)), false,
  "authored scene text never becomes markup");
assert.equal(buttons(root, "场景1").length, 1);
assert.equal(buttons(root, "场景2").length, 1);

buttons(root, "+")[0].dispatch("click");
flushTimers();
assert.equal(JSON.parse(mounted.value).length, 3);
assert.equal(textarea.value, "");
textarea.value = "third scene";
textarea.dispatch("input");
assert.deepEqual(JSON.parse(mounted.value), [hostile, "second", "third scene"]);

buttons(root, "场景2")[0].dispatch("click");
flushTimers();
assert.equal(textarea.value, "second");
textarea.value = "edited second";
textarea.dispatch("input");
assert.equal(JSON.parse(mounted.value)[1], "edited second");
buttons(root, "×")[1].dispatch("click");
flushTimers();
assert.deepEqual(JSON.parse(mounted.value), [hostile, "third scene"]);

const tabStrip = descendants(root).find((item) => item.style.overflowX === "auto");
assert.equal(tabStrip.dispatch("wheel", { deltaY: 25 }), true,
  "wheel ownership is scoped to the mounted tab strip");
assert.equal(tabStrip.scrollLeft, 25);

mounted.restore(JSON.stringify(["restored", "again"]));
flushTimers();
assert.equal(textarea.value, "again", "valid active tab survives external restoration");
assert.equal(buttons(root, "场景2").length, 1);
mounted.restore("not json");
flushTimers();
assert.equal(textarea.value, "");
assert.equal(buttons(root, "场景1").length, 1);

mounted.restore(JSON.stringify(Array.from({ length: 40 }, (_, index) => `s${index}`)));
flushTimers();
assert.equal(buttons(root, "+")[0].disabled, true);
assert.equal(buttons(root, "场景32").length, 1);
assert.equal(buttons(root, "场景33").length, 0);
assert.equal(JSON.parse(mounted.value).length, 40,
  "external restore is normalized in memory without a surprise write");

const staleWrites = mounted.sets.length;
fixture.mountDef.destroy();
assert.equal(container.children.length, 0);
assert.equal(mounted.listeners.size, 0);
assert.equal(tabStrip.listeners.get("wheel").length, 0);
assert.equal(timers.size, 0);
textarea.value = "stale";
textarea.dispatch("input");
assert.equal(mounted.sets.length, staleWrites, "destroyed controls cannot mutate state");
extension.hooks.removed(fixture.node);

const restored = makeNode(JSON.stringify(["one", "two"]));
extension.hooks.created(restored.node);
const restoredValue = new MountedValue(restored.mountDef.defaultValue);
const restoredContainer = new Element("div", ownerDocument);
restored.mountDef.render(restoredContainer, restoredValue);
flushTimers();
assert.deepEqual(JSON.parse(restoredValue.value), ["one", "two"],
  "workflow scene state survives remount");
restored.mountDef.destroy();

console.log("PASS: secure multi-scene mounted editor, serialization, bounds, and teardown");
