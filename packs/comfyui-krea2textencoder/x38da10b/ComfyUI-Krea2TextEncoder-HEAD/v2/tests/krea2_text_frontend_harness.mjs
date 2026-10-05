import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";


const sourcePath = new URL("../web/krea2_dynamic_images.js", import.meta.url);
let source = fs.readFileSync(sourcePath, "utf8")
  .replace('import { comfy } from "/comfy/api/v2.js";', "const comfy = globalThis.__comfy;")
  .replace("export function reconcileReferencePairs", "function reconcileReferencePairs");

let install;
const comfy = {
  defs: {
    extend(name, callback) {
      assert.equal(name, "TextEncodeKrea2");
      const hooks = {};
      callback({
        onCreated(fn) { hooks.created = fn; },
        onConfigured(fn) { hooks.configured = fn; },
        onConnectionsChanged(fn) { hooks.connections = fn; },
      });
      install = hooks;
    },
  },
};
vm.runInNewContext(source, { __comfy: comfy, console, Set, Number, String }, {
  filename: sourcePath.pathname,
});
assert.ok(install?.created && install.configured && install.connections);

function makeNode(id, names = ["clip", "system_prompt", "image1", "mask1"]) {
  const slots = names.map((name, index) => ({
    id: `${id}:${name}`,
    index,
    name,
    type: name.startsWith("mask") ? "MASK" : name.startsWith("image") ? "IMAGE" : "CLIP",
    isConnected: false,
  }));
  const inputs = {
    all: () => [...slots],
    byName: (name) => slots.find((slot) => slot.name === name),
    add(name, type, options) {
      assert.equal(options?.shape, "optional");
      assert.ok(!this.byName(name), `duplicate ${name}`);
      const slot = { id: `${id}:${name}`, index: slots.length, name, type, isConnected: false };
      slots.push(slot);
      return slot;
    },
    remove(ref) {
      const index = slots.findIndex((slot) => slot.id === ref || slot.name === ref);
      if (index < 0) return false;
      slots.splice(index, 1);
      slots.forEach((slot, offset) => { slot.index = offset; });
      return true;
    },
  };
  return { id, inputs };
}

function pairNames(node) {
  return node.inputs.all().map((slot) => slot.name).filter((name) => /^(image|mask)\d+$/.test(name));
}

const node = makeNode("a");
install.created(node);
assert.deepEqual(pairNames(node), ["image1", "mask1"]);

node.inputs.byName("image1").isConnected = true;
install.connections(node);
assert.deepEqual(pairNames(node), ["image1", "mask1", "image2", "mask2"]);

node.inputs.byName("mask2").isConnected = true;
install.connections(node);
assert.deepEqual(pairNames(node).slice(-2), ["image3", "mask3"]);

node.inputs.byName("mask2").isConnected = false;
install.connections(node);
assert.equal(node.inputs.byName("image3"), undefined);
assert.ok(node.inputs.byName("image2"));

const restored = makeNode("restored", ["clip", "image1", "mask1", "image2"]);
restored.inputs.byName("image2").isConnected = true;
install.configured(restored);
assert.ok(restored.inputs.byName("mask2"));
assert.ok(restored.inputs.byName("image3"));
assert.ok(restored.inputs.byName("mask3"));

const capped = makeNode("cap");
install.created(capped);
for (let index = 1; index <= 16; index += 1) {
  capped.inputs.byName(`image${index}`).isConnected = true;
  install.connections(capped);
}
assert.equal(capped.inputs.byName("image17"), undefined);
assert.equal(pairNames(capped).length, 32);

const oversizedRestore = makeNode("oversized", [
  "clip", "image1", "mask1", "image17", "mask17", "image999", "mask999",
]);
install.configured(oversizedRestore);
assert.equal(oversizedRestore.inputs.byName("image17"), undefined);
assert.equal(oversizedRestore.inputs.byName("mask17"), undefined);
assert.equal(oversizedRestore.inputs.byName("image999"), undefined);
assert.equal(oversizedRestore.inputs.byName("mask999"), undefined);
assert.deepEqual(pairNames(oversizedRestore), ["image1", "mask1"]);

const other = makeNode("other");
install.created(other);
assert.deepEqual(pairNames(other), ["image1", "mask1"]);
assert.equal(pairNames(capped).length, 32);

console.log("krea2 text frontend harness: ok");
