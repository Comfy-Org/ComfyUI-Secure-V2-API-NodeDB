import { existsSync, readFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";


const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../../../../../../");
const SRC = path.join(REPO, "frontend/src");
const WEB = path.resolve(HERE, "../web");
const { chromium } = await import(pathToFileURL(
  path.join(REPO, "frontend/tests/_deps.mjs"),
));


function assert(condition, message) {
  if (!condition) throw new Error(`ASSERT: ${message}`);
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
  put16(tiff, 26, 1);
  put16(tiff, 28, 0x9286);
  put16(tiff, 30, 7);
  put32(tiff, 32, userComment.length);
  put32(tiff, 36, 44);
  tiff.set(userComment, 44);
  const payload = new Uint8Array(6 + tiff.length);
  payload.set([0x45, 0x78, 0x69, 0x66, 0, 0]);
  payload.set(tiff, 6);
  const out = new Uint8Array(8 + payload.length);
  out.set([0xff, 0xd8, 0xff, 0xe1]);
  const length = payload.length + 2;
  out[4] = length >>> 8;
  out[5] = length & 255;
  out.set(payload, 6);
  out.set([0xff, 0xd9], 6 + payload.length);
  return out;
}


const PAGE = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from "/src/host-entry.mjs"

const registrations = []
const builder = {
  onCreated() {}, onExecuted() {}, onConfigured() {}, onConnectionsChanged() {},
  onRemoved() {}, onResized() {}, onHover() {}, onDoubleClick() {},
  onDragOver() {}, onDrop() {}, onUnplacedLink() {}, addMenuItem() {},
}
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url !== "/object_info") throw new Error("unexpected URL: " + url)
      return { ok: true, json: async () => ({}) }
    },
  },
  graph: { nodes: () => [], node: () => undefined },
  workflow: { documentId: () => "smz-iframe-document" },
  onWorkflowLoaded: () => () => {},
  defs: {
    extend: (selector, apply) => {
      registrations.push(selector)
      apply(builder)
      return () => {}
    },
  },
}
const host = new SecureExtensionHost({
  comfy,
  bootstrapUrl: "/guest.js",
  match: () => true,
})
window.__host = host
window.__registrations = registrations
window.__start = () => host.load("/extensions/smz/all.js")
window.__run = async (bytes) => {
  const file = new File([new Uint8Array(bytes)], "embedded.JPG", {
    type: "image/jpeg",
  })
  const imported = await host.importFile(file)
  return {
    imported,
    importerCount: host._importers.size,
    registrationCount: registrations.length,
    sandbox: document.querySelector("iframe")?.getAttribute("sandbox"),
  }
}
<\/script></body>`;


const server = http.createServer((request, response) => {
  const url = request.url.split("?")[0];
  const send = (body, type) => {
    response.writeHead(200, {
      "Content-Type": type,
      "Access-Control-Allow-Origin": "*",
    });
    response.end(body);
  };
  if (url === "/guest.js") {
    return send(readFileSync(path.join(SRC, "guest.mjs"), "utf8"), "text/javascript");
  }
  if (url === "/comfy/api/v2.js") {
    return send("export const comfy = globalThis.comfy\n", "text/javascript");
  }
  if (url === "/extensions/smz/all.js") {
    return send(
      'import "./smZdynamicWidgets.js"; import "./metadata.js";\n',
      "text/javascript",
    );
  }
  if (url.startsWith("/extensions/smz/")) {
    const filename = path.join(WEB, path.basename(url));
    if (existsSync(filename)) return send(readFileSync(filename, "utf8"), "text/javascript");
  }
  if (url.startsWith("/src/")) {
    const filename = path.join(SRC, url.slice("/src/".length));
    if (existsSync(filename)) return send(readFileSync(filename, "utf8"), "text/javascript");
  }
  return send(PAGE, "text/html");
});


await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const { port } = server.address();
const browser = await chromium.launch();
const page = await browser.newPage();

try {
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.evaluate(() => window.__start());
  await page.waitForFunction(() => window.__host._importers.size === 1);
  const sourcePrompt = { "1": { class_type: "SaveImage", inputs: {} } };
  const result = await page.evaluate(
    (bytes) => window.__run(bytes),
    Array.from(jpeg(JSON.stringify(sourcePrompt))),
  );
  assert(result.sandbox === "allow-scripts", "iframe gained same-origin authority");
  assert(result.importerCount === 1, "workflow importer did not cross the bridge");
  assert(
    result.registrationCount === 2,
    "both dynamic definition selectors did not cross the bridge",
  );
  assert(
    result.imported.prompt["1"].class_type === "SaveImage",
    "bounded JPEG bytes did not round-trip as an API prompt",
  );
  console.log("smZNodes real iframe harness: PASS");
} finally {
  await browser.close();
  server.close();
}
