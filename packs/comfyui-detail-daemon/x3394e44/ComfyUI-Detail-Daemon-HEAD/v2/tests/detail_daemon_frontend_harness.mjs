import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";


function check(condition, message) {
  if (!condition) throw new Error(message);
}

const hooks = {};
const redraws = [];
const mounted = [];
const comfy = {
  defs: {
    extend(selector, apply) {
      check(selector === "DetailDaemonSamplerGUINode", "node selector changed");
      apply({
        onCreated(callback) { hooks.created = callback; },
        onConfigured(callback) { hooks.configured = callback; },
        onRemoved(callback) { hooks.removed = callback; },
      });
    },
  },
};

const context = vm.createContext({ console });
const facade = new vm.SyntheticModule(
  ["comfy"],
  function initialize() { this.setExport("comfy", comfy); },
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

for (const name of [
  "window", "document", "parent", "top", "fetch", "XMLHttpRequest",
  "WebSocket", "localStorage", "sessionStorage", "setTimeout", "setInterval",
]) {
  check(vm.runInContext(`typeof ${name}`, context) === "undefined",
    `${name} leaked into the isolated frontend realm`);
}

const widgetValues = {
  detail_amount: 0.1,
  start: 0.2,
  end: 0.8,
  bias: 0.5,
  exponent: 1,
  start_offset: 0,
  end_offset: 0,
  fade: 0,
  smooth: true,
};
const listeners = new Map();
const widgets = new Map(Object.entries(widgetValues).map(([name, initial]) => {
  let value = initial;
  return [name, {
    getValue() { return value; },
    setValue(next) {
      const previous = value;
      value = next;
      for (const callback of listeners.get(name) || []) callback(next, previous);
    },
    on(event, callback) {
      check(event === "change", `unexpected widget event ${event}`);
      const values = listeners.get(name) || [];
      values.push(callback);
      listeners.set(name, values);
      return () => {};
    },
  }];
}));

const calls = [];
const drawingContext = new Proxy({}, {
  get(target, property) {
    if (!(property in target)) {
      target[property] = (...args) => {
        calls.push([String(property), ...args]);
        if (property === "measureText") return { width: 72 };
        if (property === "createLinearGradient") {
          return { addColorStop() {} };
        }
        return undefined;
      };
    }
    return target[property];
  },
  set(target, property, value) {
    target[property] = value;
    return true;
  },
});

let constraints = null;
const node = {
  id: "detail-1",
  widgets: {
    get(name) { return widgets.get(name); },
    canvas(options) {
      const surface = {
        options,
        redraw() {
          redraws.push(redraws.length + 1);
          options.draw(drawingContext, [500, 250]);
        },
      };
      mounted.push(surface);
      return surface;
    },
  },
  setSizeConstraints(value) { constraints = value; },
};

hooks.created(node);
check(mounted.length === 1, "schedule canvas was not mounted");
check(calls.some(([name]) => name === "stroke"), "schedule curve was not drawn");
check(constraints.minWidth === 420 && constraints.minHeight === 250,
  "node size constraints changed");

const surface = mounted[0];
let prevented = 0;
const gesture = (detail = 1) => ({
  x: 265,
  y: 114,
  event: { detail, preventDefault() { prevented += 1; } },
});
surface.options.onPointerDown(gesture());
surface.options.onPointerMove({
  x: 310,
  y: 75,
  event: { detail: 1, preventDefault() { prevented += 1; } },
});
surface.options.onPointerUp();
check(widgets.get("bias").getValue() !== 0.5 ||
      widgets.get("detail_amount").getValue() !== 0.1,
  "dragging the peak did not update widgets");
check(prevented >= 1, "handled pointer gestures were not consumed");

widgets.get("detail_amount").setValue(2.25);
surface.options.onPointerDown(gesture(2));
check(widgets.get("detail_amount").getValue() === 0.1,
  "double-click did not restore the default curve");
hooks.configured(node);
hooks.removed(node);
check(redraws.length >= 4, "lifecycle and widget changes did not redraw");

console.log("Detail-Daemon frontend worker/allow-scripts harness: PASS");
