import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { pathToFileURL } from "node:url";


const entry = path.resolve(process.argv[2]);
const source = fs.readFileSync(entry, "utf8");
for (const forbidden of [
  /\/scripts\/app\.js/, /app\.registerExtension|app\.handleFile|loadGraphData|loadApiJson/,
  /(?:^|[^A-Za-z])document\s*\./m, /(?:^|[^A-Za-z])window\s*\./m,
  /FileReader|fetch\s*\(|innerHTML|localStorage|indexedDB/,
]) assert.doesNotMatch(source, forbidden);


let importer;
const comfy = {
  workflow: {
    registerImporter(value) { importer = value; return () => { importer = undefined; }; },
  },
};
const context = vm.createContext({ console, Uint8Array, DataView, ArrayBuffer, JSON, String });
const module = new vm.SourceTextModule(source, {
  context,
  identifier: pathToFileURL(entry).href,
});
await module.link(async (specifier) => {
  assert.equal(specifier, "/comfy/api/v2.js");
  const stub = new vm.SyntheticModule(["comfy"], function () {
    this.setExport("comfy", comfy);
  }, { context });
  await stub.link(() => {});
  return stub;
});
await module.evaluate();


function tiff(metadata) {
  const text = new TextEncoder().encode(`${JSON.stringify(metadata)}\0`);
  const bytes = new Uint8Array(26 + text.length);
  const data = new DataView(bytes.buffer);
  bytes.set([0x49, 0x49]);
  data.setUint16(2, 42, true);
  data.setUint32(4, 8, true);
  data.setUint16(8, 1, true);
  data.setUint16(10, 0x9286, true);
  data.setUint16(12, 2, true);
  data.setUint32(14, text.length, true);
  data.setUint32(18, 26, true);
  data.setUint32(22, 0, true);
  bytes.set(text, 26);
  return bytes;
}


function canonicalTiff(metadata) {
  const entries = Object.entries(metadata).map(([key, value], index) => ({
    tag: key === "prompt" ? 0x0110 : 0x010f - index,
    text: new TextEncoder().encode(`${key}:${JSON.stringify(value)}\0`),
  }));
  const dataOffset = 8 + 2 + entries.length * 12 + 4;
  const total = dataOffset + entries.reduce((sum, entry) => sum + entry.text.length, 0);
  const bytes = new Uint8Array(total);
  const data = new DataView(bytes.buffer);
  bytes.set([0x49, 0x49]);
  data.setUint16(2, 42, true);
  data.setUint32(4, 8, true);
  data.setUint16(8, entries.length, true);
  let payloadOffset = dataOffset;
  entries.forEach((item, index) => {
    const entry = 10 + index * 12;
    data.setUint16(entry, item.tag, true);
    data.setUint16(entry + 2, 2, true);
    data.setUint32(entry + 4, item.text.length, true);
    data.setUint32(entry + 8, payloadOffset, true);
    bytes.set(item.text, payloadOffset);
    payloadOffset += item.text.length;
  });
  return bytes;
}


function jpeg(metadata) {
  const payload = metadata instanceof Uint8Array ? metadata : tiff(metadata);
  const length = 2 + 6 + payload.length;
  const bytes = new Uint8Array(2 + 2 + length + 2);
  const data = new DataView(bytes.buffer);
  bytes.set([0xff, 0xd8, 0xff, 0xe1], 0);
  data.setUint16(4, length, false);
  bytes.set(new TextEncoder().encode("Exif\0\0"), 6);
  bytes.set(payload, 12);
  bytes.set([0xff, 0xd9], 4 + length);
  return bytes;
}


function webp(metadata) {
  const payload = metadata instanceof Uint8Array ? metadata : tiff(metadata);
  const padded = payload.length + (payload.length & 1);
  const bytes = new Uint8Array(12 + 8 + padded);
  const data = new DataView(bytes.buffer);
  bytes.set(new TextEncoder().encode("RIFF"), 0);
  data.setUint32(4, bytes.length - 8, true);
  bytes.set(new TextEncoder().encode("WEBP"), 8);
  bytes.set(new TextEncoder().encode("EXIF"), 12);
  data.setUint32(16, payload.length, true);
  bytes.set(payload, 20);
  return bytes;
}


assert.ok(importer);
assert.equal(importer.id, "SaveImagePlus.Metadata");
assert.equal(importer.maxBytes, 16 * 1024 * 1024);
assert.equal(JSON.stringify(importer.mimeTypes), JSON.stringify(["image/jpeg", "image/webp"]));
assert.equal(
  JSON.stringify(importer.parse(jpeg({ workflow: { nodes: [{ id: 1 }] } }), { name: "a.jpg", type: "image/jpeg" })),
  JSON.stringify({ workflow: { nodes: [{ id: 1 }] } }),
);
assert.equal(
  JSON.stringify(importer.parse(webp({ prompt: { "1": { class_type: "KSampler" } } }), { name: "b.webp", type: "" })),
  JSON.stringify({ prompt: { "1": { class_type: "KSampler" } } }),
);
assert.equal(
  JSON.stringify(importer.parse(
    webp(canonicalTiff({ prompt: { "1": { class_type: "KSampler" } }, workflow: { nodes: [{ id: 7 }] } })),
    { name: "canonical.webp", type: "image/webp" },
  )),
  JSON.stringify({ workflow: { nodes: [{ id: 7 }] } }),
);
assert.equal(importer.parse(jpeg({ other: true }), { name: "c.jpeg", type: "image/jpeg" }), null);
assert.equal(importer.parse(new Uint8Array([1, 2, 3]), { name: "bad.jpg", type: "image/jpeg" }), null);

const truncated = jpeg({ workflow: { nodes: [] } }).subarray(0, 15);
assert.equal(importer.parse(truncated, { name: "bad.jpg", type: "image/jpeg" }), null);
console.log("PASS: Save Image Plus bounded JPEG/WebP workflow importer");
