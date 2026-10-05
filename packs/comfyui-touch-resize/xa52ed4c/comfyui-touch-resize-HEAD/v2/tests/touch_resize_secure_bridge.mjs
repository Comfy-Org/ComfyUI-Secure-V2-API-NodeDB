import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "../web");
const runtimeRoot = process.env.SECURE_RUNTIME_ROOT ??
  "/Users/ben/comfy/ComfyUI_secure_nodes-pack2-workspace-manager";
const sourceRoot = path.join(runtimeRoot, "frontend/src");
const { chromium } = await import(path.join(
  runtimeRoot, "frontend/tests/_deps.mjs",
));

const pageSource = `<!doctype html><meta charset="utf-8"><body>
<canvas id="graph" style="position:fixed;left:20px;top:30px;width:640px;height:440px"></canvas>
<script type="module">
import { SecureExtensionHost } from "/src/host-entry.mjs";
const graphElement = document.querySelector("#graph");
const state = {
  position: { x: 100, y: 100 }, size: { width: 200, height: 100 },
  writes: [], graphPointers: 0,
};
const empty = { all: () => [], get: () => undefined, names: () => [] };
const node = {
  id: "1", type: "TouchResizeProof",
  snapshot: () => ({
    id: "1", type: "TouchResizeProof", title: "Proof", mode: "always",
    collapsed: false, pinned: false,
    position: { ...state.position }, size: { ...state.size },
  }),
  getBounds: () => ({
    x: state.position.x, y: state.position.y - 30,
    width: state.size.width, height: state.size.height + 30,
  }),
  getMinimumSize: () => ({ width: 160, height: 90 }),
  getProperties: () => ({}), isSerializingWidgets: () => false,
  widgets: empty, inputs: empty, outputs: empty,
  setPosition(value) {
    state.position = { ...value };
    state.writes.push(["position", { ...value }]);
  },
  setSize(value) {
    state.size = {
      width: Math.max(160, value.width), height: Math.max(90, value.height),
    };
    state.writes.push(["size", { ...state.size }]);
  },
};
graphElement.addEventListener("pointerdown", () => { state.graphPointers += 1; });
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url === "/object_info") return { ok: true, json: async () => ({}) };
      throw new Error("unexpected backend URL: " + url);
    },
  },
  graph: {
    nodes: () => [node], node: (id) => String(id) === "1" ? node : undefined,
    groups: () => [], selection: () => [node], groupSelection: () => [],
    pointerPosition: () => ({ x: 0, y: 0 }),
  },
  workflow: { documentId: () => "touch-resize-proof" },
  onWorkflowLoaded: () => () => {},
  onViewportChanged: () => () => {},
  onSelectionChanged: () => () => {},
  defs: { extend: (_selector, apply) => {
    apply({ onCreated() {}, onRemoved() {} });
    return () => {};
  } },
};
const host = new SecureExtensionHost({
  comfy, bootstrapUrl: "/guest.js", match: () => true,
  capabilities: ["ui.graph-overlay"],
  graphViewport: () => ({ element: graphElement, scale: 1, offset: [0, 0] }),
});
window.__start = () => host.load("/extensions/touch-resize/index.js");
window.__state = () => ({
  position: { ...state.position }, size: { ...state.size },
  writes: structuredClone(state.writes), graphPointers: state.graphPointers,
  overlays: host._graphOverlays.size, errors: host.packErrors ?? [],
  regions: structuredClone([...host._graphOverlays.values()][0]?.hitRegions),
  sandbox: document.querySelector("iframe")?.getAttribute("sandbox"),
});
window.__destroy = () => host.destroy();
</script></body>`;

const server = http.createServer((request, response) => {
  const url = request.url.split("?")[0];
  const send = (body, type) => {
    response.writeHead(200, {
      "Content-Type": type, "Access-Control-Allow-Origin": "*",
    });
    response.end(body);
  };
  if (url === "/") return send(pageSource, "text/html");
  if (url === "/guest.js") {
    return send(readFileSync(path.join(sourceRoot, "guest.mjs")), "text/javascript");
  }
  if (url === "/comfy/api/v2.js") {
    return send("export const comfy = globalThis.comfy;", "text/javascript");
  }
  if (url.startsWith("/extensions/touch-resize/")) {
    const file = path.join(web, url.slice("/extensions/touch-resize/".length));
    if (existsSync(file)) return send(readFileSync(file), "text/javascript");
  }
  if (url.startsWith("/src/")) {
    const file = path.join(sourceRoot, url.slice("/src/".length));
    if (existsSync(file)) return send(readFileSync(file), "text/javascript");
  }
  if (url === "/object_info") return send("{}", "application/json");
  response.writeHead(404);
  response.end("not found");
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 760, height: 560 } });
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.evaluate(() => window.__start());
  await page.waitForFunction(() => window.__state?.().regions?.length === 4);
  let state = await page.evaluate(() => window.__state());
  assert.equal(state.sandbox, "allow-scripts");
  assert.deepEqual(state.regions[0], {
    kind: "circle", x: 100, y: 70, radius: 18,
  });

  await page.mouse.click(600, 400);
  assert.equal((await page.evaluate(() => window.__state())).graphPointers, 1);

  await page.mouse.move(120, 100);
  await page.mouse.down();
  await page.mouse.move(270, 230);
  await page.mouse.up();
  await page.waitForFunction(() => window.__state().writes.length === 2);
  state = await page.evaluate(() => window.__state());
  assert.deepEqual(state.position, { x: 140, y: 110 });
  assert.deepEqual(state.size, { width: 160, height: 90 });
  assert.equal(state.graphPointers, 1, "owned handle pointer must not reach graph");

  await page.waitForFunction(() => window.__state().regions?.[0]?.x === 140);
  await page.mouse.move(160, 110);
  await page.mouse.down();
  await page.keyboard.press("Escape");
  await page.mouse.move(240, 200);
  await page.mouse.up();
  assert.equal((await page.evaluate(() => window.__state())).writes.length, 2);

  state = await page.evaluate(() => window.__state());
  assert.deepEqual(state.errors, []);
  assert.deepEqual(pageErrors, []);
  await page.evaluate(() => window.__destroy());
  assert.equal(await page.locator("[data-secure-graph-overlay]").count(), 0);
  console.log("touch resize secure bridge: PASS");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
