import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js|\/scripts\/api\.js/,
  /LiteGraph|app\.graph|app\.canvas/,
  /(?:^|[^A-Za-z])document\s*\./m,
  /(?:^|[^A-Za-z])window\s*\./m,
  /localStorage|indexedDB|fetch\s*\(|comfy\.backend|innerHTML/,
]) assert.doesNotMatch(source, forbidden);


class FakeWidget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.listeners = new Map();
  }
  getValue() { return this.value; }
  setValue(value) { this.value = value; }
  on(event, listener) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(listener);
    return () => this.listeners.get(event)?.delete(listener);
  }
  listenerCount(event) { return this.listeners.get(event)?.size || 0; }
  serialize(context) {
    let serialized = this.value;
    const event = {
      context,
      value: this.value,
      setSerializedValue(value) { serialized = value; },
    };
    for (const listener of [...(this.listeners.get("beforeSerialize") || [])]) {
      listener(event);
    }
    return serialized;
  }
}


class FakeNode {
  constructor(id, start, count = 0) {
    this.id = id;
    this.graphId = undefined;
    this.map = new Map([
      ["start", new FakeWidget("start", start)],
      ["count", new FakeWidget("count", count)],
    ]);
    this.widgets = { get: (name) => this.map.get(name) };
  }
}


const definitions = new Map();
const afterRun = new Set();
const comfy = {
  defs: {
    extend(selector, configure) {
      const hooks = { hidden: [] };
      configure({
        hideWidget(name) { hooks.hidden.push(name); },
        onCreated(callback) { hooks.created = callback; },
        onConfigured(callback) { hooks.configured = callback; },
        onRemoved(callback) { hooks.removed = callback; },
      });
      definitions.set(selector, hooks);
    },
  },
  queue: {
    onAfterRun(listener) {
      afterRun.add(listener);
      return () => afterRun.delete(listener);
    },
  },
};


const context = vm.createContext({ console, Promise, Math, Number, Object, String, Array, Set, WeakMap });
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


assert.equal(module.namespace.integerValue(4), 4);
assert.equal(module.namespace.integerValue("7"), 7);
assert.equal(module.namespace.integerValue(-1, 9), 9);
assert.equal(module.namespace.integerValue("bad", 9), 9);

const hooks = definitions.get("Simple Counter");
assert.ok(hooks, "Simple Counter is extended through the typed definition API");
assert.deepEqual(hooks.hidden, ["count"]);
assert.equal(afterRun.size, 1, "one global accepted-submission listener is registered");

// These instances deliberately share a node id while living in different graphs.
const first = new FakeNode("same-id", 3);
const second = new FakeNode("same-id", 10);
first.graphId = "graph-a";
second.graphId = "graph-b";
hooks.created(first);
hooks.created(second);
const firstCount = first.map.get("count");
const secondCount = second.map.get("count");

assert.equal(firstCount.serialize("workflow"), 0);
assert.equal(firstCount.serialize("embedded"), 0);
assert.equal(firstCount.serialize("prompt"), 3);
assert.equal(firstCount.serialize("prompt"), 4);
assert.equal(secondCount.serialize("prompt"), 10,
  "same node ids in different graphs have independent counters");

for (const listener of afterRun) listener({ promptIds: [], rejected: 1 });
assert.equal(firstCount.serialize("prompt"), 5,
  "a rejected submission does not reset an already serialized count");

// An interruption adds no lifecycle event here, matching the upstream extension.
assert.equal(firstCount.serialize("prompt"), 6);
assert.equal(firstCount.serialize("prompt"), 7,
  "interruption without another accepted submission does not reset");

first.map.get("start").setValue(20);
second.map.get("start").setValue(30);
for (const listener of afterRun) {
  listener({ promptIds: ["p1", "p2"], rejected: 0 });
}
assert.equal(firstCount.serialize("prompt"), 20);
assert.equal(secondCount.serialize("prompt"), 30,
  "accepted batch submission resets every live instance from its own start widget");

hooks.configured(first, {});
assert.equal(firstCount.listenerCount("beforeSerialize"), 1,
  "configuration replaces rather than duplicates serialization handlers");
assert.equal(firstCount.serialize("prompt"), 20);

hooks.removed(first);
assert.equal(firstCount.listenerCount("beforeSerialize"), 0);
assert.equal(firstCount.serialize("prompt"), 0,
  "removed nodes no longer override serialization");
second.map.get("start").setValue(41);
for (const listener of afterRun) listener({ promptIds: ["p3"], rejected: 0 });
assert.equal(secondCount.serialize("prompt"), 41,
  "cleanup of one graph does not affect another graph's counter");
hooks.removed(first);
hooks.removed(second);
assert.equal(secondCount.listenerCount("beforeSerialize"), 0);

console.log("PASS: secure SimpleCounter ordering, rejection, isolation, reset, and cleanup");
