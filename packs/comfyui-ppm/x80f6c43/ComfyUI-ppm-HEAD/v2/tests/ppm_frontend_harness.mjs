import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";


function check(condition, message) {
  if (!condition) throw new Error(message);
}

const hooks = new Map();
const selectors = [];
const comfy = {
  defs: {
    extend(selector, apply) {
      selectors.push(selector);
      const target = {};
      apply({
        onConnectionsChanged(callback) {
          target.connections = callback;
        },
      });
      hooks.set(selector, target);
    },
  },
};

const context = vm.createContext({ console });
const facade = new vm.SyntheticModule(
  ["comfy"],
  function initialize() {
    this.setExport("comfy", comfy);
  },
  { context, identifier: "/comfy/api/v2.js" },
);
const source = fs.readFileSync(process.env.TARGET_JS, "utf8");
const guest = new vm.SourceTextModule(source, {
  context,
  identifier: path.resolve(process.env.TARGET_JS),
});
await guest.link(async (specifier) => {
  if (specifier === "/comfy/api/v2.js") return facade;
  throw new Error(`unexpected import: ${specifier}`);
});
await guest.evaluate();

check(
  JSON.stringify(selectors) ===
    JSON.stringify(["AttentionCouplePPM", "MaskCompositePPM"]),
  "definition selectors changed",
);
check(
  guest.namespace.FRONTEND_INTENTS.length === 4,
  "frontend intent census changed",
);
for (const name of [
  "window",
  "document",
  "parent",
  "top",
  "fetch",
  "XMLHttpRequest",
  "WebSocket",
  "localStorage",
  "sessionStorage",
  "setTimeout",
  "setInterval",
]) {
  check(
    vm.runInContext(`typeof ${name}`, context) === "undefined",
    `${name} leaked into the worker/allow-scripts context`,
  );
}

let nextSlot = 1;
function slot(name, type, connected = false) {
  return {
    id: `slot-${nextSlot++}`,
    name,
    type,
    isConnected: connected,
  };
}

function nodeWith(inputs) {
  const values = [...inputs];
  return {
    id: `node-${nextSlot++}`,
    inputs: {
      all() {
        return [...values];
      },
      byName(name) {
        return values.find((item) => item.name === name);
      },
      add(name, type, options = {}) {
        check(options.shape === "optional", `${name} lost optional shape`);
        const value = slot(name, type);
        values.push(value);
        return value;
      },
      remove(ref) {
        const index = values.findIndex(
          (item) => item.id === ref || item.name === ref,
        );
        if (index < 0) return false;
        values.splice(index, 1);
        return true;
      },
    },
  };
}

const attention = nodeWith([
  slot("model", "MODEL"),
  slot("base_cond", "CONDITIONING"),
  slot("base_mask", "MASK"),
]);
const attentionHook = hooks.get("AttentionCouplePPM").connections;
attention.inputs.byName("base_cond").isConnected = true;
attention.inputs.byName("base_mask").isConnected = true;
attentionHook(attention, { side: "input", index: 1, connected: true });
check(attention.inputs.byName("cond_1"), "first conditioning was not added");
check(attention.inputs.byName("mask_1"), "first mask was not added");

attention.inputs.byName("cond_1").isConnected = true;
attentionHook(attention, { side: "input", index: 3, connected: true });
check(!attention.inputs.byName("cond_2"), "half-filled pair grew early");
attention.inputs.byName("mask_1").isConnected = true;
attentionHook(attention, { side: "input", index: 4, connected: true });
check(attention.inputs.byName("cond_2"), "full pair did not grow conditioning");
check(attention.inputs.byName("mask_2"), "full pair did not grow mask");

attention.inputs.byName("mask_1").isConnected = false;
attentionHook(attention, { side: "input", index: 4, connected: false });
check(!attention.inputs.byName("cond_2"), "unused conditioning tail remained");
check(!attention.inputs.byName("mask_2"), "unused mask tail remained");
attention.inputs.byName("cond_1").isConnected = false;
attention.inputs.byName("base_cond").isConnected = false;
attention.inputs.byName("base_mask").isConnected = false;
attentionHook(attention, { side: "input", index: 3, connected: false });
check(!attention.inputs.byName("cond_1"), "empty conditioning pair remained");
check(!attention.inputs.byName("mask_1"), "empty mask pair remained");

const composite = nodeWith([
  slot("mask_1", "MASK"),
  slot("operation", "COMBO"),
]);
const compositeHook = hooks.get("MaskCompositePPM").connections;
composite.inputs.byName("mask_1").isConnected = true;
compositeHook(composite, { side: "input", index: 0, connected: true });
check(composite.inputs.byName("mask_2"), "mask composite did not grow");
composite.inputs.byName("mask_2").isConnected = true;
compositeHook(composite, { side: "input", index: 2, connected: true });
check(composite.inputs.byName("mask_3"), "second mask did not grow tail");
composite.inputs.byName("mask_2").isConnected = false;
compositeHook(composite, { side: "input", index: 2, connected: false });
check(composite.inputs.byName("mask_2"), "empty tail was not retained");
check(!composite.inputs.byName("mask_3"), "extra empty mask tail remained");
composite.inputs.byName("mask_1").isConnected = false;
compositeHook(composite, { side: "input", index: 0, connected: false });
check(!composite.inputs.byName("mask_2"), "unused composite tail remained");
check(composite.inputs.byName("mask_1"), "required mask_1 was removed");

console.log("ComfyUI-ppm frontend worker/allow-scripts harness: PASS");
