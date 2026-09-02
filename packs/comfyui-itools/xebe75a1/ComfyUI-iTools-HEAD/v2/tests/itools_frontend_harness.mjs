import fs from "node:fs";
import vm from "node:vm";


const target = process.env.TARGET_JS;
if (!target) throw new Error("TARGET_JS is required");
const stylesTarget = process.env.STYLE_JS;
if (!stylesTarget) throw new Error("STYLE_JS is required");

const styleSource = fs.readFileSync(stylesTarget, "utf8")
  .replace("export const STYLE_NAMES", "globalThis.__STYLE_NAMES");
const source = fs.readFileSync(target, "utf8")
  .replace('import { comfy } from "/comfy/api/v2.js";', "const comfy = globalThis.__comfy;")
  .replace('import { STYLE_NAMES } from "./style_names.js";', "const STYLE_NAMES = globalThis.__STYLE_NAMES;")
  .replace("export const FRONTEND_INTENTS", "const FRONTEND_INTENTS")
  + "\nglobalThis.__intents = FRONTEND_INTENTS;";


function apiDouble() {
  const settings = new Map();
  const settingListeners = new Map();
  const extensions = [];
  const sidebars = [];
  const commands = [];
  const comfy = {
    settings: {
      declare(def) { if (!settings.has(def.id)) settings.set(def.id, def.defaultValue); },
      get(id) { return settings.get(id); },
      async set(id, value) {
        const previous = settings.get(id);
        settings.set(id, value);
        for (const listener of settingListeners.get(id) || []) listener(value, previous);
      },
      onChange(id, listener) {
        const values = settingListeners.get(id) || [];
        values.push(listener);
        settingListeners.set(id, values);
        return () => values.splice(values.indexOf(listener), 1);
      },
    },
    defs: {
      extend(selector, apply) {
        const hooks = { selector };
        const builder = {
          def: { type: Array.isArray(selector) ? selector[0] : selector },
          onCreated(callback) { hooks.created = callback; },
          onExecuted(callback) { hooks.executed = callback; },
          onRemoved(callback) { hooks.removed = callback; },
        };
        apply(builder);
        extensions.push(hooks);
        return () => {};
      },
    },
    commands: {
      register(def) { commands.push(def); },
      notify() {},
    },
    ui: {
      addSidebarTab(def) { sidebars.push(def); return () => {}; },
      addActionBarButton() { return { remove() {}, update() {} }; },
      showDialog() { return { close() {} }; },
      async prompt() { return undefined; },
    },
    backend: {
      url(route) { return `http://host.invalid/api${route}`; },
    },
    files: {
      async pick() { return undefined; },
      async download() {},
    },
    storage: {
      async get() { return undefined; },
      async set() {},
      async list() { return []; },
      async remove() {},
    },
  };
  return { comfy, extensions, sidebars, commands, settings };
}


// Worker-shaped module evaluation: there is deliberately no document/window.
{
  const api = apiDouble();
  const context = vm.createContext({
    __comfy: api.comfy,
    console,
    TextDecoder,
    TextEncoder,
    URLSearchParams,
    Uint8Array,
    DataView,
    JSON,
    Object,
    String,
    Number,
    Boolean,
    Array,
    Map,
    Set,
    Error,
  });
  vm.runInContext(styleSource, context, { filename: stylesTarget });
  vm.runInContext(source, context, { filename: target });
  if (context.__intents.length !== 21) throw new Error("frontend intent census drifted");
  if (api.commands.length !== 1) throw new Error("prompt command was not registered");
  if (api.sidebars.length !== 1) throw new Error("prompt sidebar was not registered");
}


class FakeElement {
  constructor(tag = "div") {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.style = {};
    this.listeners = new Map();
    this.classList = { add() {}, remove() {} };
    this.value = "";
    this.textContent = "";
    this.checked = false;
    this.width = 512;
    this.height = 512;
  }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, listener) {
    const values = this.listeners.get(name) || [];
    values.push(listener);
    this.listeners.set(name, values);
  }
  dispatch(name, event = {}) {
    for (const listener of this.listeners.get(name) || []) listener(event);
  }
  focus() {}
  select() {}
  setPointerCapture() {}
  getBoundingClientRect() { return { left: 0, top: 0, width: 512, height: 512 }; }
  getContext() {
    return {
      save() {}, restore() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {},
      fillRect() {}, clearRect() {}, drawImage() {}, strokeRect() {}, setLineDash() {},
      fillText() {},
    };
  }
  toDataURL() { return "data:image/png;base64,AA=="; }
  set src(value) { this._src = value; queueMicrotask(() => this.dispatch("load")); }
  get src() { return this._src || ""; }
}


class FakeWidget {
  constructor(name, value = "") {
    this.name = name;
    this.value = value;
    this.listeners = new Map();
    this.options = {};
  }
  getValue() { return this.value; }
  setValue(value) {
    const old = this.value;
    this.value = value;
    if (old !== value) for (const callback of this.listeners.get("change") || []) callback(value, old);
  }
  setOption(name, value) { this.options[name] = value; }
  setHidden() {}
  setLabel() {}
  setDisabled() {}
  setHeight() {}
  on(name, callback) {
    const values = this.listeners.get(name) || [];
    values.push(callback);
    this.listeners.set(name, values);
    return () => values.splice(values.indexOf(callback), 1);
  }
}


function fakeNode(type, mountedNames) {
  const widgets = new Map();
  const defaults = {
    output_mode: "list", style_file: "basic.yaml", template_name: "none",
    base_file: "basic.yaml", base_style: "none", second_file: "camera.yaml",
    second_style: "none", third_file: "artist.yaml", third_style: "none",
    fourth_file: "mood.yaml", fourth_style: "none", pattern_picker: "custom",
    regex_pattern: "", replace_match: "", replace_non_match: "", timeline_data: "[]",
    text: "", widget_state: "{}", resize_rule: "grid", grid_step: 64, image: "",
  };
  const collection = {
    get(name) {
      if (!widgets.has(name)) widgets.set(name, new FakeWidget(name, defaults[name] ?? ""));
      return widgets.get(name);
    },
    add(def) {
      const widget = new FakeWidget(def.name, def.value);
      widgets.set(def.name, widget);
      return widget;
    },
    mount(def) {
      mountedNames.add(def.name);
      const widget = new FakeWidget(def.name, def.defaultValue);
      widgets.set(def.name, widget);
      let value = def.defaultValue ?? null;
      const listeners = [];
      const mounted = {
        get() { return value; },
        set(next) { value = next; for (const listener of listeners) listener(next); },
        onChange(listener) { listeners.push(listener); return () => {}; },
      };
      def.render(new FakeElement("div"), mounted);
      return widget;
    },
  };
  return {
    id: `${type}-1`, graphId: "root", type, comfyClass: type, widgets: collection,
    outputs: { at() { return { modify() {} }; } },
    setSize() {}, setColor() {}, setBgColor() {},
  };
}


// allow-scripts opaque-frame-shaped evaluation and mounted-control exercise.
{
  const api = apiDouble();
  const document = {
    createElement(tag) { return new FakeElement(tag); },
    createTextNode(text) { const value = new FakeElement("#text"); value.textContent = text; return value; },
  };
  const context = vm.createContext({
    __comfy: api.comfy,
    document,
    Node: FakeElement,
    FileReader: class {},
    console,
    TextDecoder,
    TextEncoder,
    URLSearchParams,
    Uint8Array,
    DataView,
    JSON,
    Object,
    String,
    Number,
    Boolean,
    Array,
    Map,
    Set,
    Error,
    btoa(value) { return Buffer.from(value, "binary").toString("base64"); },
    queueMicrotask,
  });
  vm.runInContext(styleSource, context, { filename: stylesTarget });
  vm.runInContext(source, context, { filename: target });

  const byType = new Map();
  for (const extension of api.extensions) {
    const selectors = Array.isArray(extension.selector) ? extension.selector : [extension.selector];
    for (const type of selectors) {
      const hooks = byType.get(type) || [];
      hooks.push(extension);
      byType.set(type, hooks);
    }
  }
  const mountedNames = new Set();
  for (const [type, hooks] of byType) {
    const node = fakeNode(type, mountedNames);
    for (const hook of hooks) hook.created?.(node, { restored: false });
    for (const hook of hooks) hook.executed?.(node, {
      images: [
        { filename: "a.png", subfolder: "", type: "temp" },
        { filename: "b.png", subfolder: "", type: "temp" },
      ],
      text: ["frontend harness text"],
      raw: {},
    });
    for (const hook of hooks) hook.removed?.(node);
  }
  const requiredMounts = [
    "CounterWidget", "Click", "InstructorWidget", "PromptBuilderWidget",
    "itools_adjust_panel", "PaintWidget", "crop", "itools_compare_viewer",
    "itools_preview_viewer", "itools_prompt_history",
  ];
  for (const name of requiredMounts) {
    if (!mountedNames.has(name)) throw new Error(`mounted control missing: ${name}`);
  }
  const sidebarContainer = new FakeElement("aside");
  api.sidebars[0].render(sidebarContainer);
  if (!sidebarContainer.children.length) throw new Error("sidebar rendered no controls");
}

console.log("iTools frontend worker/iframe harness: PASS");
