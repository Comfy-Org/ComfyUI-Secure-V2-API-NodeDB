import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error("frontend source path is required");

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.style = {};
    this.children = [];
    this.parent = undefined;
    this.listeners = new Map();
    this.attributes = new Map();
    this.textContent = "";
    this.type = "";
  }
  append(...children) {
    for (const child of children) {
      child.parent = this;
      this.children.push(child);
    }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parent = undefined;
    this.children = [];
    this.append(...children);
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }
  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  dispatch(type) {
    const event = {
      type,
      defaultPrevented: false,
      propagationStopped: false,
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.propagationStopped = true; },
    };
    for (const listener of [...(this.listeners.get(type) ?? [])]) listener(event);
    return event;
  }
}

class FakeDocument {
  constructor() { this.created = []; }
  createElement(tagName) {
    const element = new FakeElement(tagName, this);
    this.created.push(element);
    return element;
  }
}

const extensions = new Map();
const comfy = {
  defs: {
    extend(type, callback) {
      const hooks = {};
      callback({
        onCreated(listener) { hooks.created = listener; },
        onRemoved(listener) { hooks.removed = listener; },
      });
      extensions.set(type, hooks);
    },
  },
};

const context = vm.createContext({ console });
const module = new vm.SourceTextModule(fs.readFileSync(sourcePath, "utf8"), {
  context,
  identifier: sourcePath,
});
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  const api = new vm.SyntheticModule(["comfy"], function initialize() {
    this.setExport("comfy", comfy);
  }, { context });
  await api.link(() => {});
  await api.evaluate();
  return api;
});
await module.evaluate();

assert.deepEqual([...extensions.keys()], ["Calculator"]);
const hooks = extensions.get("Calculator");

function makeNode(id, graphId = "root") {
  const document = new FakeDocument();
  const mounts = new Map();
  const node = {
    id: String(id),
    type: "Calculator",
    comfyClass: "Calculator",
    graphId,
    constraints: undefined,
    setSizeConstraints(constraints) { this.constraints = constraints; },
    widgets: {
      mount(definition) {
        const container = document.createElement("div");
        const handle = {
          definition,
          container,
          destroy() { definition.destroy?.(); },
        };
        mounts.set(definition.name, handle);
        definition.render(container, {
          get() { return undefined; },
          set() { throw new Error("decorative mount must not store state"); },
          onChange() { throw new Error("decorative mount must not subscribe"); },
        });
        return handle;
      },
    },
    mounts,
    document,
  };
  hooks.created(node);
  return node;
}

function display(node) {
  return node.document.created.find(
    (element) => element.attributes.get("aria-label") === "Calculator display",
  );
}

function button(node, label) {
  const aria = label === "=" ? "Calculate" : label === "C" ? "Clear" : label;
  return node.document.created.find(
    (element) => element.tagName === "BUTTON" && element.attributes.get("aria-label") === aria,
  );
}

function press(node, labels) {
  let last;
  for (const label of labels) {
    last = button(node, label).dispatch("click");
    assert.equal(last.defaultPrevented, true);
    assert.equal(last.propagationStopped, true);
  }
  return last;
}

const first = makeNode("same", "root");
const second = makeNode("same", "subgraph");
const firstMount = first.mounts.get("calc_ui");
assert.equal(firstMount.definition.height, 330);
assert.equal(firstMount.definition.serialize, false);
assert.equal(firstMount.definition.sendToPrompt, false);
assert.equal(first.constraints.minWidth, 240);
assert.equal(first.constraints.minHeight, 360);
assert.equal(display(first).textContent, "0");
assert.equal(display(second).textContent, "0");

// Normal precedence, result continuation, and digit-after-result behavior.
press(first, ["1", "+", "2", "*", "3", "="]);
assert.equal(display(first).textContent, "7");
assert.equal(display(second).textContent, "0");
press(first, ["+", "2", "="]);
assert.equal(display(first).textContent, "9");
press(first, ["4"]);
assert.equal(display(first).textContent, "4");

// Unary signs, decimals, division, and JavaScript-number result spelling.
press(first, ["C", "-", "3", "*", "2", "="]);
assert.equal(display(first).textContent, "-6");
press(first, ["C", ".", "5", "+", "1", ".", "2", "5", "="]);
assert.equal(display(first).textContent, "1.75");
press(first, ["C", "1", "/", "0", "="]);
assert.equal(display(first).textContent, "Infinity");
press(first, ["C", "0", "/", "0", "="]);
assert.equal(display(first).textContent, "NaN");

// Malformed decimal/operator input fails closed and the next digit recovers.
press(first, ["C", "1", ".", ".", "2", "="]);
assert.equal(display(first).textContent, "Error");
press(first, ["3"]);
assert.equal(display(first).textContent, "3");
press(first, ["C", "1", "+", "+", "2", "="]);
assert.equal(display(first).textContent, "Error");

// The display truncates at 15 characters without truncating the expression.
press(first, ["C", ..."1234567890123456"]);
assert.equal(display(first).textContent, "123456789012345");
press(first, ["-", ..."1234567890123450", "="]);
assert.equal(display(first).textContent, "6");

// Removal and widget teardown are idempotent and release every DOM listener.
const oldButtons = [...first.document.created].filter((element) => element.tagName === "BUTTON");
assert.equal(oldButtons.length, 17);
assert.ok(oldButtons.every((element) => element.listeners.get("click")?.size === 1));
hooks.removed(first);
assert.ok(oldButtons.every((element) => element.listeners.get("click")?.size === 0));
firstMount.destroy();
assert.ok(oldButtons.every((element) => element.listeners.get("click")?.size === 0));
const remounted = makeNode("same", "root");
assert.equal(display(remounted).textContent, "0");
assert.equal(button(remounted, "1").listeners.get("click").size, 1);
press(remounted, ["2", "+", "2", "="]);
assert.equal(display(remounted).textContent, "4");
assert.equal(display(second).textContent, "0");

console.log("PASS: Calculator behavior, isolation, and lifecycle");
