import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const sourcePath = new URL("../web/button.js", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8")
  .replace(
    'import { comfy } from "/comfy/api/v2.js";',
    "const comfy = globalThis.__comfy;",
  )
  .replace(/\bexport /gu, "");

const callbacks = new Map();
const comfy = {
  defs: {
    extend(type, configure) {
      const handlers = {};
      configure({
        onCreated(fn) { handlers.created = fn; },
        onRemoved(fn) { handlers.removed = fn; },
      });
      callbacks.set(type, handlers);
    },
  },
};
const context = vm.createContext({
  __comfy: comfy,
  Array,
  Boolean,
  Error,
  Map,
  Math,
  Number,
  Object,
  RegExp,
  Set,
  String,
  WeakMap,
});
new vm.Script(source, { filename: sourcePath.pathname }).runInContext(context);

assert.deepEqual(
  [...callbacks.keys()],
  ["CLIPTextEncodeFormatter", "TextOnlyFormatter"],
);

const formatInputs = [
  "  cat   ,  dog  , cat ",
  "（cat） [dog] {bird",
  "cat, cat, BREAK, dog, <lora:x:1>, dog",
  "((cat)), [[dog]], (((bird)))",
  "cat  AND   dog, [red|blue], (sharp:1.2)",
  String.raw`\(literal\), (plain:1.0), <lora:test:0.8>`,
  "cat,\n\n dog , BREAK\n bird",
  "(cat)(dog), [red][blue]",
];
const formatExpected = [
  "cat, dog",
  "(cat:1.1) (dog:0.91) bird",
  "cat BREAK dog <lora:x:1>",
  "(cat:1.21), (dog:0.83), (bird:1.33)",
  "cat AND dog, [red|blue], (sharp:1.2)",
  String.raw`\(literal\), plain <lora:test:0.8>`,
  "cat, dog BREAK\nbird",
  "(cat:1.1) (dog:1.1), (red:0.91) (blue:0.91)",
];
assert.deepEqual(formatInputs.map(context.formatPrompt), formatExpected);

const convertInputs = [
  "blue_hair green_eyes tagme watermark 2024",
  "speech_bubble hello_world onomatopoeia",
  String.raw`character_\(solo\) detailed_artwork signature`,
  "already, comma, text",
  "(ordinary phrase)",
  "first_tag second_tag\nBREAK\nthird_tag\n",
  "",
];
const convertExpected = [
  "blue hair, green eyes,",
  "hello world,",
  String.raw`character \(solo\),`,
  "already, comma, text",
  "(ordinary phrase)",
  "first tag, second tag,\nBREAK\nthird tag,\n",
  "",
];
assert.deepEqual(convertInputs.map(context.convertTags), convertExpected);

function emitter() {
  const listeners = new Set();
  return {
    on(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    emit() { for (const listener of [...listeners]) listener(); },
    get size() { return listeners.size; },
  };
}

function makeNode(id, initialText) {
  const values = { text: initialText };
  const text = {
    getValue: () => values.text,
    setValue(value) { values.text = value; },
  };
  const entries = new Map([["text", text]]);
  return {
    id,
    values,
    entries,
    widgets: {
      get(name) { return entries.get(name); },
      remove(name) { entries.delete(name); },
      add(spec) {
        assert.equal(spec.type, "button");
        assert.equal(spec.serialize, false);
        const activated = emitter();
        const button = {
          on(name, listener) {
            assert.equal(name, "activate");
            return activated.on(listener);
          },
          activate() { activated.emit(); },
          get listeners() { return activated.size; },
        };
        entries.set(spec.name, button);
        return button;
      },
    },
  };
}

const first = makeNode("one", " cat,  dog, cat ");
const second = makeNode("two", "blue_hair tagme");
callbacks.get("CLIPTextEncodeFormatter").created(first);
callbacks.get("TextOnlyFormatter").created(second);
first.entries.get("💫 Format Prompt").activate();
assert.equal(first.values.text, "cat, dog");
assert.equal(second.values.text, "blue_hair tagme", "nodes remain isolated");

first.values.text = "red_hair watermark";
first.entries.get("✒️ Convert Tags").activate();
assert.equal(first.values.text, "red hair,");
first.entries.get("⏪ Undo Last Change").activate();
assert.equal(first.values.text, "red_hair watermark", "undo restores one local change");
first.entries.get("⏪ Undo Last Change").activate();
assert.equal(first.values.text, "red_hair watermark", "undo remains one-step and local");

const oldButton = first.entries.get("💫 Format Prompt");
callbacks.get("CLIPTextEncodeFormatter").created(first);
assert.equal(first.entries.size, 4, "remount has text plus exactly three buttons");
assert.equal(oldButton.listeners, 0, "remount unsubscribes old buttons");
assert.equal(first.entries.get("💫 Format Prompt").listeners, 1);
oldButton.activate();
assert.equal(first.values.text, "red_hair watermark", "disposed listeners cannot mutate text");

callbacks.get("CLIPTextEncodeFormatter").removed(first);
callbacks.get("CLIPTextEncodeFormatter").removed(first);
assert.equal(first.entries.size, 1, "removal is idempotent and removes pack widgets");
assert.equal(second.entries.size, 4, "removing one node does not affect another");

callbacks.get("TextOnlyFormatter").removed(second);
assert.equal(second.entries.size, 1);

console.log("prompt formatter frontend behavior/security tests passed");
