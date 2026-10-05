import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|\/scripts\/widgets\.js/,
  /LiteGraph|app\.graph|app\.canvas/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|innerHTML/,
]) assert.doesNotMatch(source, forbidden);


class FakeWidget {
  constructor(name, value = "") {
    this.name = name;
    this.value = value;
    this.options = {};
    this.height = undefined;
    this.listeners = new Map();
  }
  getValue() { return this.value; }
  setValue(value) {
    const oldValue = this.value;
    if (Object.is(value, oldValue)) return;
    this.value = value;
    this.emit("change", value, oldValue);
  }
  setOption(name, value) { this.options[name] = value; }
  setHeight(value) { this.height = value; }
  on(event, listener) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(listener);
    return () => this.listeners.get(event)?.delete(listener);
  }
  emit(event, ...args) {
    for (const listener of [...(this.listeners.get(event) || [])]) listener(...args);
  }
  listenerCount(event) { return this.listeners.get(event)?.size || 0; }
}


class FakeNode {
  constructor(entries) {
    this.map = new Map(entries.map(([name, value]) => [name, new FakeWidget(name, value)]));
    this.widgets = { get: (name) => this.map.get(name) };
  }
}


const definitions = new Map();
const comfy = {
  defs: {
    extend(selector, configure) {
      const hooks = {};
      configure({
        onCreated(callback) { hooks.created = callback; },
        onConfigured(callback) { hooks.configured = callback; },
        onExecuted(callback) { hooks.executed = callback; },
        onConnectionsChanged(callback) { hooks.connections = callback; },
        onRemoved(callback) { hooks.removed = callback; },
      });
      definitions.set(selector, hooks);
    },
  },
};


const context = vm.createContext({ console, Promise, Math, Number, Object, String, Array });
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


assert.deepEqual(
  JSON.parse(JSON.stringify(module.namespace.checkDelimiters("[(ok)]"))),
  {
    unmatchedOpeningBrackets: [], unmatchedClosingBrackets: [],
    unmatchedOpeningParentheses: [], unmatchedClosingParentheses: [],
  },
);
assert.equal(
  module.namespace.formatValidation("]["),
  "Unmatched opening bracket at: 2. Unmatched closing bracket at: 1. ",
);
assert.equal(
  module.namespace.formatValidation("(()"),
  "Unmatched opening parenthesis at: 1. ",
);


const validation = definitions.get("RandomizeTextWithCheck");
assert.ok(validation, "validation node uses the typed definition extension");
const first = new FakeNode([["text", "[red|blue]"], ["info_text", "saved"]]);
const second = new FakeNode([["text", "(second"], ["info_text", ""]]);
validation.created(first);
validation.created(second);
assert.equal(first.map.get("info_text").options.read_only, true);
assert.equal(first.map.get("info_text").height, 60);
assert.equal(first.map.get("info_text").value,
  "All brackets and parentheses are properly matched!");
assert.equal(second.map.get("info_text").value,
  "Unmatched opening parenthesis at: 1. ");

first.map.get("text").emit("textInteraction", {
  kind: "input", value: "bad ] and (", selection: { start: 0, end: 0 },
});
assert.equal(first.map.get("info_text").value,
  "Unmatched closing bracket at: 5. Unmatched opening parenthesis at: 11. ");
assert.equal(second.map.get("info_text").value,
  "Unmatched opening parenthesis at: 1. ", "instances do not share validation state");

first.map.get("text").setValue("[fixed]");
assert.equal(first.map.get("info_text").value,
  "All brackets and parentheses are properly matched!");
validation.configured(first, {});
assert.equal(first.map.get("text").listenerCount("change"), 1,
  "configure replaces rather than duplicates listeners");
assert.equal(first.map.get("text").listenerCount("textInteraction"), 1);

const oldInfo = first.map.get("info_text").value;
validation.removed(first);
assert.equal(first.map.get("text").listenerCount("change"), 0);
assert.equal(first.map.get("text").listenerCount("textInteraction"), 0);
first.map.get("text").setValue("(");
assert.equal(first.map.get("info_text").value, oldInfo,
  "removed instances no longer receive widget events");
validation.removed(first);


const show = definitions.get("ShowText");
assert.ok(show, "ShowText uses the typed definition extension");
const display = new FakeNode([["text", ""], ["preview", "restored preview"]]);
show.created(display);
assert.equal(display.map.get("preview").options.read_only, true);
assert.equal(display.map.get("preview").value, "restored preview");
show.executed(display, { raw: { text: ["safe <b>", " & literal"] } });
assert.equal(display.map.get("preview").value, "safe <b> & literal",
  "adversarial-looking text remains a plain widget value");
show.executed(display, { raw: { text: ["replacement"] } });
assert.equal(display.map.get("preview").value, "replacement");
show.executed(display, { raw: { text: [] } });
assert.equal(display.map.get("preview").value, "replacement",
  "empty execution payload preserves the legacy display");
show.connections(display, { side: "output", index: 0, connected: false });
assert.equal(display.map.get("preview").value, "replacement");
show.connections(display, { side: "input", index: 0, connected: true });
assert.equal(display.map.get("preview").value, "");
display.map.get("preview").setValue("again");
show.connections(display, { side: "input", index: 0, connected: false });
assert.equal(display.map.get("preview").value, "");

validation.removed(second);
console.log("PASS: secure Text Randomizer validation, results, isolation, and teardown");
