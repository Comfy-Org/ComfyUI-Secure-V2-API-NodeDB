import vm from "node:vm";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";


const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, "../web");


function assert(condition, message) {
  if (!condition) throw new Error(`ASSERT: ${message}`);
}


const definitionRegistrations = [];
const importers = [];
const comfy = {
  defs: {
    extend(selector, configure) {
      const registration = { selector, created: [], menus: [] };
      const builder = {
        onCreated(callback) { registration.created.push(callback); return builder; },
        addMenuItem(item) { registration.menus.push(item); return builder; },
      };
      configure(builder);
      definitionRegistrations.push(registration);
    },
  },
  workflow: {
    registerImporter(importer) { importers.push(importer); return () => {}; },
  },
};


const context = vm.createContext({
  console,
  TextDecoder,
  Uint8Array,
  ArrayBuffer,
  Number,
  String,
  Boolean,
  Math,
  JSON,
  Error,
  SyntaxError,
  Set,
});
for (const name of [
  "window", "parent", "top", "app", "comfyAPI", "LiteGraph",
  "XMLHttpRequest", "WebSocket",
]) {
  assert(context[name] === undefined, `${name} leaked into worker realm`);
}


const api = new vm.SyntheticModule(
  ["comfy"],
  function loadApi() { this.setExport("comfy", comfy); },
  { context, identifier: "/comfy/api/v2.js" },
);


async function load(name) {
  const filename = path.join(WEB, name);
  const source = readFileSync(filename, "utf8");
  for (const forbidden of [
    "/scripts/app.js", "registerExtension", "Object.defineProperty",
    "prototype.", "XMLHttpRequest", "WebSocket", "FileReader",
  ]) {
    assert(!source.includes(forbidden), `${name} contains ${forbidden}`);
  }
  const module = new vm.SourceTextModule(source, {
    context,
    identifier: pathToFileURL(filename).href,
  });
  await module.link(async (specifier) => {
    assert(specifier === "/comfy/api/v2.js", `${name} imports ${specifier}`);
    return api;
  });
  await module.evaluate();
  return module.namespace;
}


class Widget {
  constructor(name, value) {
    this.name = name;
    this.value = value;
    this.hidden = false;
    this.disabled = false;
    this.listeners = new Map();
  }
  getValue() { return this.value; }
  setValue(value) {
    const old = this.value;
    this.value = value;
    for (const listener of this.listeners.get("change") || []) listener(value, old);
  }
  setHidden(value) { this.hidden = Boolean(value); }
  isHidden() { return this.hidden; }
  setDisabled(value) { this.disabled = Boolean(value); }
  on(event, callback) {
    const listeners = this.listeners.get(event) || [];
    listeners.push(callback);
    this.listeners.set(event, listeners);
  }
}


function node(type, entries) {
  const values = entries.map(([name, value]) => new Widget(name, value));
  return {
    type,
    comfyClass: type,
    widgets: {
      get(name) { return values.find((item) => item.name === name); },
      all() { return [...values]; },
    },
  };
}


function put16(bytes, offset, value) {
  bytes[offset] = value & 255;
  bytes[offset + 1] = value >>> 8 & 255;
}


function put32(bytes, offset, value) {
  bytes[offset] = value & 255;
  bytes[offset + 1] = value >>> 8 & 255;
  bytes[offset + 2] = value >>> 16 & 255;
  bytes[offset + 3] = value >>> 24 & 255;
}


function jpeg(comment) {
  const encoded = new TextEncoder().encode(comment);
  const userComment = new Uint8Array(8 + encoded.length);
  userComment.set(new TextEncoder().encode("ASCII\0\0\0"));
  userComment.set(encoded, 8);
  const tiff = new Uint8Array(44 + userComment.length);
  tiff.set([0x49, 0x49]);
  put16(tiff, 2, 42);
  put32(tiff, 4, 8);
  put16(tiff, 8, 1);
  put16(tiff, 10, 0x8769);
  put16(tiff, 12, 4);
  put32(tiff, 14, 1);
  put32(tiff, 18, 26);
  put32(tiff, 22, 0);
  put16(tiff, 26, 1);
  put16(tiff, 28, 0x9286);
  put16(tiff, 30, 7);
  put32(tiff, 32, userComment.length);
  put32(tiff, 36, 44);
  put32(tiff, 40, 0);
  tiff.set(userComment, 44);
  const payload = new Uint8Array(6 + tiff.length);
  payload.set([0x45, 0x78, 0x69, 0x66, 0, 0]);
  payload.set(tiff, 6);
  const out = new Uint8Array(2 + 2 + 2 + payload.length + 2);
  out.set([0xff, 0xd8, 0xff, 0xe1]);
  const segmentLength = payload.length + 2;
  out[4] = segmentLength >>> 8;
  out[5] = segmentLength & 255;
  out.set(payload, 6);
  out.set([0xff, 0xd9], 6 + payload.length);
  return out;
}


const dynamic = await load("smZdynamicWidgets.js");
const metadata = await load("metadata.js");

assert(definitionRegistrations.length === 1, "dynamic extension registration count changed");
assert(importers.length === 1, "workflow importer registration count changed");
assert(importers[0].id === "Comfy.smZ.WorkflowImage", "workflow importer ID changed");
assert(importers[0].maxBytes === 16 * 1024 * 1024, "workflow importer is unbounded");

const encode = node("smZ CLIPTextEncode", [
  ["text", "cat"], ["parser", "comfy"], ["mean_normalization", true],
  ["multi_conditioning", true], ["use_old_emphasis_implementation", false],
  ["with_SDXL", false], ["ascore", 6], ["width", 1024], ["height", 1024],
  ["crop_w", 0], ["crop_h", 0], ["target_width", 1024],
  ["target_height", 1024], ["text_g", ""], ["text_l", ""], ["smZ_steps", 1],
]);
definitionRegistrations[0].created[0](encode);
assert(encode.widgets.get("mean_normalization").hidden, "comfy parser left mean normalization visible");
assert(encode.widgets.get("ascore").hidden, "disabled SDXL left SDXL controls visible");
encode.widgets.get("with_SDXL").setValue(true);
assert(!encode.widgets.get("ascore").hidden, "enabled SDXL left controls hidden");
assert(encode.widgets.get("text").hidden, "enabled SDXL left the single prompt visible");

const settings = node("smZ Settings", [
  ["extra", '{"show_headings":true,"show_descriptions":false}'],
  ["ㅤ", "Stable Diffusion"], ["info_RNG", "Random source"], ["RNG", "cpu"],
]);
definitionRegistrations[0].created[0](settings);
assert(settings.widgets.get("extra").hidden, "settings transport widget is visible");
assert(settings.widgets.get("info_RNG").hidden, "descriptions ignored settings visibility");
assert(settings.widgets.get("info_RNG").disabled, "description remained editable");

const apiPrompt = { "1": { class_type: "SaveImage", inputs: {} } };
const jsonJpeg = jpeg(JSON.stringify(apiPrompt));
const jsonComment = metadata.parseJpegUserComment(jsonJpeg);
assert(jsonComment === JSON.stringify(apiPrompt), `EXIF comment changed: ${jsonComment}`);
const importedJson = metadata.parseWorkflowImage(jsonJpeg);
assert(importedJson.prompt["1"].class_type === "SaveImage", "JSON API prompt was not imported");

const a1111 = [
  "a cat <lora:detail.safetensors:0.7>", "Negative prompt: blur",
  "Steps: 28, Sampler: Euler a, Schedule type: DDIM, CFG scale: 6.5, Seed: 42, Size: 640x832, Model: demo.safetensors",
].join("\n");
const importedA1111 = metadata.parseWorkflowImage(jpeg(a1111));
assert(importedA1111.prompt["7"].inputs.steps === 28, "A1111 steps changed");
assert(importedA1111.prompt["7"].inputs.sampler_name === "euler_ancestral", "A1111 sampler changed");
assert(importedA1111.prompt["7"].inputs.scheduler === "ddim_uniform", "A1111 schedule type changed");
assert(importedA1111.prompt["6"].inputs.width === 640, "A1111 size changed");
assert(importedA1111.prompt["3"].inputs.text.trim() === "a cat", "A1111 positive prompt changed");
assert(importedA1111.prompt["10"].inputs.lora_name === "detail.safetensors", "A1111 LoRA was not imported");
assert(metadata.parseWorkflowImage(new Uint8Array([1, 2, 3])) === null, "non-JPEG was claimed");

console.log("smZNodes frontend harness: PASS");
