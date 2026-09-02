import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";


function check(condition, message) {
  if (!condition) throw new Error(message);
}


const expectedTargets = [
  "OllamaGenerate",
  "OllamaGenerateAdvance",
  "OllamaVision",
  "OllamaConnectivityV2",
];
const registrations = new Map();
let selector;
const calls = [];
const notifications = [];
let failNext = false;

const comfy = {
  defs: {
    extend(value, apply) {
      selector = value;
      for (const type of expectedTargets) {
        const hooks = {};
        const builder = {
          def: { type },
          onCreated(callback) { hooks.created = callback; },
          onRemoved(callback) { hooks.removed = callback; },
        };
        apply(builder);
        registrations.set(type, hooks);
      }
    },
  },
  integrations: {
    ollama: {
      async listModels({ endpoint }) {
        calls.push(endpoint);
        if (failNext) {
          failNext = false;
          throw new Error("offline");
        }
        return endpoint.includes("second")
          ? ["second-model", "stable-model"]
          : ["first-model", "stable-model"];
      },
    },
  },
  commands: {
    notify(definition) { notifications.push(definition); },
  },
};

const context = vm.createContext({ console });
const facade = new vm.SyntheticModule(
  ["comfy"],
  function initialize() { this.setExport("comfy", comfy); },
  { context, identifier: "/comfy/api/v2.js" },
);
const source = fs.readFileSync(process.env.TARGET_JS, "utf8");
const module = new vm.SourceTextModule(source, {
  context,
  identifier: path.resolve(process.env.TARGET_JS),
});
await module.link(async (specifier) => {
  if (specifier === "/comfy/api/v2.js") return facade;
  throw new Error(`unexpected import: ${specifier}`);
});
await module.evaluate();

check(
  JSON.stringify(selector) === JSON.stringify(expectedTargets),
  "wrong definition selector",
);
for (const type of expectedTargets) {
  check(typeof registrations.get(type)?.created === "function", `${type} missing created hook`);
  check(typeof registrations.get(type)?.removed === "function", `${type} missing removed hook`);
}
for (const name of [
  "window",
  "document",
  "parent",
  "app",
  "fetch",
  "XMLHttpRequest",
  "WebSocket",
  "localStorage",
]) {
  check(vm.runInContext(`typeof ${name}`, context) === "undefined", `${name} leaked into guest`);
}

function makeWidget(name, initial) {
  let value = initial;
  let label = name;
  let disabled = false;
  const options = {};
  const listeners = new Map();
  return {
    name,
    getValue() { return value; },
    setValue(next) { value = next; },
    getLabel() { return label; },
    setLabel(next) { label = String(next); },
    isDisabled() { return disabled; },
    setDisabled(next) { disabled = Boolean(next); },
    setOption(key, next) { options[key] = next; },
    getOption(key) { return options[key]; },
    on(event, callback) {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event).add(callback);
      return () => listeners.get(event)?.delete(callback);
    },
    async emit(event) {
      for (const callback of listeners.get(event) || []) await callback(value);
    },
    listenerCount(event) { return listeners.get(event)?.size || 0; },
  };
}

function makeNode(id, type, endpoint, model = "stable-model") {
  const url = makeWidget("url", endpoint);
  const modelWidget = makeWidget("model", model);
  const widgets = new Map([["url", url], ["model", modelWidget]]);
  let added = null;
  const node = {
    id,
    graphId: "root",
    widgets: {
      get(name) { return widgets.get(name); },
      add(definition) {
        added = makeWidget(definition.name, definition.value);
        added.definition = definition;
        widgets.set(definition.name, added);
        return added;
      },
    },
  };
  return { node, url, modelWidget, get added() { return added; }, type };
}

const connectivity = makeNode(
  "1",
  "OllamaConnectivityV2",
  "http://127.0.0.1:11434",
);
await registrations.get(connectivity.type).created(connectivity.node);
check(calls[0] === "http://127.0.0.1:11434", "initial endpoint was not brokered");
check(connectivity.added !== null, "connectivity refresh button missing");
check(connectivity.added.definition.serialize === false, "refresh button must not serialize");
check(connectivity.added.getLabel() === "🔄 Reconnect", "refresh label was not restored");
check(connectivity.added.isDisabled() === false, "refresh button stayed disabled");
check(
  JSON.stringify(connectivity.modelWidget.getOption("values"))
    === JSON.stringify(["first-model", "stable-model"]),
  "model options were not updated",
);
check(connectivity.modelWidget.getValue() === "stable-model", "existing model was not preserved");

connectivity.url.setValue("http://localhost:11434");
await connectivity.url.emit("change");
check(calls.at(-1) === "http://localhost:11434", "URL change did not refresh");

connectivity.url.setValue("ollama://second");
connectivity.modelWidget.setValue("missing-model");
await connectivity.added.emit("activate");
check(calls.at(-1) === "ollama://second", "button did not use the current endpoint");
check(connectivity.modelWidget.getValue() === "second-model", "first model was not selected");

failNext = true;
await connectivity.added.emit("activate");
check(notifications.length === 1, "connection failure did not notify");
check(notifications[0].severity === "error", "failure notification severity is wrong");
check(connectivity.added.isDisabled() === false, "failed refresh left the button disabled");
check(connectivity.added.getLabel() === "🔄 Reconnect", "failed refresh left a busy label");

const legacy = makeNode(
  "2",
  "OllamaGenerate",
  "http://127.0.0.1:11434",
  "",
);
await registrations.get(legacy.type).created(legacy.node);
check(legacy.added === null, "deprecated node unexpectedly gained a button");
check(legacy.modelWidget.getValue() === "first-model", "legacy node did not load models");

check(connectivity.url.listenerCount("change") === 1, "URL listener was not installed");
check(connectivity.added.listenerCount("activate") === 1, "button listener was not installed");
registrations.get(connectivity.type).removed(connectivity.node);
check(connectivity.url.listenerCount("change") === 0, "URL listener leaked after removal");
check(connectivity.added.listenerCount("activate") === 0, "button listener leaked after removal");

console.log("ollama frontend harness: ok");
