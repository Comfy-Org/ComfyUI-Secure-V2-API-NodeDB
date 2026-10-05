import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const webRoot = process.argv[2];
if (!webRoot) throw new Error("web root is required");

const extensions = new Map();
const assetUrls = [];
const comfy = {
  defs: {
    extend(type, callback) {
      const hooks = {};
      callback({
        onCreated(fn) { hooks.created = fn; },
        onConfigured(fn) { hooks.configured = fn; },
        onExecuted(fn) { hooks.executed = fn; },
        onRemoved(fn) { hooks.removed = fn; },
      });
      extensions.set(type, hooks);
    },
  },
  backend: {
    assetUrl(route) { assetUrls.push(route); return `secure:${route}`; },
  },
};

class Element {
  constructor(tag, ownerDocument) {
    this.tag = tag;
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.naturalWidth = 640;
    this.naturalHeight = 360;
    this._src = "";
  }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; }
  set src(value) {
    this._src = value;
    if (this.tag === "img" && value) queueMicrotask(() => this.onload?.());
  }
  get src() { return this._src; }
}

const ownerDocument = {
  createElement(tag) { return new Element(tag, ownerDocument); },
};

const context = vm.createContext({ console, URL, URLSearchParams, queueMicrotask });
const moduleCache = new Map();
async function loadModule(filename) {
  const absolute = path.resolve(filename);
  if (moduleCache.has(absolute)) return moduleCache.get(absolute);
  const module = new vm.SourceTextModule(fs.readFileSync(absolute, "utf8"), {
    context, identifier: absolute,
  });
  moduleCache.set(absolute, module);
  await module.link(async (specifier, referencingModule) => {
    if (specifier === "/comfy/api/v2.js") {
      const key = "comfy-api";
      if (moduleCache.has(key)) return moduleCache.get(key);
      const api = new vm.SyntheticModule(["comfy"], function initialize() {
        this.setExport("comfy", comfy);
      }, { context, identifier: key });
      moduleCache.set(key, api);
      await api.link(() => {});
      return api;
    }
    return loadModule(path.resolve(path.dirname(referencingModule.identifier), specifier));
  });
  await module.evaluate();
  return module;
}

for (const name of ["view.js", "load.js", "preview.js", "save.js"]) {
  await loadModule(path.join(webRoot, name));
}
assert.deepEqual([...extensions.keys()].sort(), [
  "LoadImageandviewPropertiesSG", "PreviewImageandviewPropertiesSG",
  "SaveImageFormatQualityPropertiesSG", "ViewImagePropertiesSG",
]);

function makeWidget(name, initial) {
  const listeners = new Set();
  return {
    name, value: initial, hidden: undefined,
    getValue() { return this.value; },
    setValue(value) { this.value = value; for (const listener of [...listeners]) listener(value); },
    setHidden(value) { this.hidden = Boolean(value); },
    on(event, listener) {
      assert.equal(event, "change");
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    listenerCount() { return listeners.size; },
  };
}

function makeNode(type, id, values = {}) {
  const widgets = new Map(Object.entries(values).map(([name, value]) => [name, makeWidget(name, value)]));
  const node = {
    id: String(id), properties: {}, constraints: undefined, mountDef: undefined, mountHandle: undefined,
    setProperty(name, value) { this.properties[name] = structuredClone(value); },
    getProperty(name) { return this.properties[name]; },
    setSizeConstraints(value) { this.constraints = value; },
  };
  node.widgets = {
    get(name) { return widgets.get(name); },
    mount(definition) {
      node.mountDef = definition;
      node.mountHandle = { heights: [], setHeight(value) { this.heights.push(value); } };
      return node.mountHandle;
    },
  };
  extensions.get(type).created(node);
  const container = new Element("section", ownerDocument);
  node.mountDef.render(container);
  node.container = container;
  node.widgetMap = widgets;
  return node;
}

function renderedLines(node) {
  const readout = node.container.children[1];
  return readout.children.map((child) => child.textContent);
}

const first = makeNode("ViewImagePropertiesSG", "one");
const second = makeNode("ViewImagePropertiesSG", "two");
extensions.get("ViewImagePropertiesSG").executed(first, { text: ["first", "<b>not markup</b>"] });
assert.deepEqual(renderedLines(first), ["first", "<b>not markup</b>"]);
assert.deepEqual(renderedLines(second), []);
assert.deepEqual(first.properties.imageParamsText, ["first", "<b>not markup</b>"]);

second.properties.imageParamsText = ["restored"];
extensions.get("ViewImagePropertiesSG").configured(second);
assert.deepEqual(renderedLines(second), ["restored"]);

const load = makeNode("LoadImageandviewPropertiesSG", "load", { image: "folder/sample.png" });
await Promise.resolve();
await Promise.resolve();
assert.equal(assetUrls.length, 1);
assert.match(assetUrls[0], /filename=sample.png/);
assert.match(assetUrls[0], /subfolder=folder/);
assert.deepEqual(renderedLines(load), [
  "640x360 | 0.23MP", "Ratio: 16:9 or 1.78:1", "Tensor Size: 2.64MB",
]);
load.widgetMap.get("image").setValue("../escape.png");
await Promise.resolve();
assert.equal(assetUrls.length, 1);

const saveValues = {
  format: "PNG (lossless, larger files)", png_compress_level: 9,
  jpeg_quality: 95, jpeg_optimize: true,
  jpeg_subsampling: "Auto (based on quality)", webp_quality: 90,
  webp_method: 4, webp_lossless: false,
  tiff_compression: "tiff_deflate (lossless, better compression)", tiff_jpeg_quality: 90,
};
const save = makeNode("SaveImageFormatQualityPropertiesSG", "save", saveValues);
assert.equal(save.widgetMap.get("png_compress_level").hidden, false);
assert.equal(save.widgetMap.get("jpeg_quality").hidden, true);
save.widgetMap.get("format").setValue("JPEG (lossy, smaller files)");
assert.equal(save.widgetMap.get("png_compress_level").hidden, true);
assert.equal(save.widgetMap.get("jpeg_quality").hidden, false);
assert.equal(save.widgetMap.get("jpeg_subsampling").hidden, false);
save.widgetMap.get("format").setValue("TIFF (flexible, lossless, limited support)");
assert.equal(save.widgetMap.get("tiff_compression").hidden, false);
assert.equal(save.widgetMap.get("tiff_jpeg_quality").hidden, false);

// Configuration/remount updates state without installing a duplicate listener.
extensions.get("SaveImageFormatQualityPropertiesSG").configured(save);
extensions.get("SaveImageFormatQualityPropertiesSG").configured(save);
assert.equal(save.widgetMap.get("format").listenerCount(), 1);
assert.equal(load.widgetMap.get("image").listenerCount(), 1);

extensions.get("LoadImageandviewPropertiesSG").removed(load);
extensions.get("LoadImageandviewPropertiesSG").removed(load);
assert.equal(load.widgetMap.get("image").listenerCount(), 0);
const before = assetUrls.length;
load.widgetMap.get("image").setValue("folder/after.png");
await Promise.resolve();
assert.equal(assetUrls.length, before);

save.mountDef.destroy();
extensions.get("SaveImageFormatQualityPropertiesSG").removed(save);
assert.equal(save.widgetMap.get("format").listenerCount(), 0);

console.log("PASS: Image Properties SG frontend isolation and teardown");
