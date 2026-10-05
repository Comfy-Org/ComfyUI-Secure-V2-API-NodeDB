import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const sourcePath = new URL("../web/advanced_sequence_seed.js", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8").replace(
  'import { comfy } from "/comfy/api/v2.js";',
  "const comfy = globalThis.__comfy;",
);

const callbacks = {};
const comfy = {
  defs: {
    extend(type, configure) {
      assert.equal(type, "AdvancedSequenceSeedNode");
      configure({
        onCreated(fn) { callbacks.created = fn; },
        onConfigured(fn) { callbacks.configured = fn; },
        onExecuted(fn) { callbacks.executed = fn; },
        onRemoved(fn) { callbacks.removed = fn; },
      });
    },
  },
};

new vm.Script(source, { filename: sourcePath.pathname }).runInContext(
  vm.createContext({ __comfy: comfy, WeakMap, Boolean, Number, Math, Array, Error }),
);

function emitter() {
  const listeners = new Set();
  return {
    on(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    emit(value, oldValue) { for (const listener of [...listeners]) listener(value, oldValue); },
    get size() { return listeners.size; },
  };
}

function makeNode(id, graphId, forced, seed) {
  const changes = emitter();
  let forceValue = forced;
  let seedValue = seed;
  const disabled = [];
  const force = {
    getValue: () => forceValue,
    on(name, listener) { assert.equal(name, "change"); return changes.on(listener); },
    setValue(value) {
      const old = forceValue;
      forceValue = value;
      changes.emit(value, old);
    },
    get listeners() { return changes.size; },
  };
  const current = {
    getValue: () => seedValue,
    setValue(value) { seedValue = value; },
    setDisabled(value) { disabled.push(value); },
  };
  return {
    id, graphId, force, current, disabled,
    widgets: { get(name) { return name === "force_recalculation" ? force : name === "current_seed" ? current : undefined; } },
  };
}

const first = makeNode("1", "graph-a", true, 5);
const second = makeNode("2", "graph-a", false, 6);
const otherGraph = makeNode("1", "graph-b", false, 7);
callbacks.created(first);
callbacks.created(second);
callbacks.created(otherGraph);
assert.deepEqual(first.disabled, [true]);
assert.deepEqual(second.disabled, [false]);
assert.deepEqual(otherGraph.disabled, [false]);
assert.equal(first.force.listeners, 1);

first.force.setValue(false);
assert.equal(first.disabled.at(-1), false);
first.force.setValue(true);
callbacks.configured(first);
assert.equal(first.disabled.at(-1), true);
assert.equal(first.force.listeners, 1, "configure does not duplicate subscriptions");

callbacks.executed(first, { raw: { seed: [89] } });
assert.equal(first.current.getValue(), 89);
assert.equal(second.current.getValue(), 6, "same-graph peer is not overwritten");
assert.equal(otherGraph.current.getValue(), 7, "other graph is not overwritten");
callbacks.executed(otherGraph, { raw: { seed: 144 } });
assert.equal(otherGraph.current.getValue(), 144);
assert.equal(first.current.getValue(), 89);

callbacks.executed(first, { raw: { seed: ["not-a-number"] } });
callbacks.executed(first, { raw: { seed: [Number.POSITIVE_INFINITY] } });
callbacks.executed(first, {});
assert.equal(first.current.getValue(), 89, "malformed execution data is ignored");

callbacks.created(first);
assert.equal(first.force.listeners, 1, "idempotent remount replaces the listener");
callbacks.removed(first);
callbacks.removed(first);
assert.equal(first.force.listeners, 0, "removal is idempotent and unsubscribes");
first.force.setValue(false);
assert.equal(first.disabled.at(-1), true, "removed nodes receive no later updates");

console.log("advanced sequence seed frontend behavior/security tests passed");
