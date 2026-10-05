import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "../web");
const runtimeRoot = process.env.SECURE_RUNTIME_ROOT ??
  "/Users/ben/comfy/ComfyUI_secure_nodes-pack2-workspace-manager";
const { chromium } = await import(pathToFileURL(
  path.join(runtimeRoot, "frontend/tests/_deps.mjs"),
));

const pageSource = `<!doctype html><meta charset="utf-8"><script type="module">
const assert = {
  equal(actual, expected) {
    if (actual !== expected) throw new Error(
      \`expected \${JSON.stringify(expected)}, got \${JSON.stringify(actual)}\`);
  },
  deepEqual(actual, expected) {
    if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(
      \`expected \${JSON.stringify(expected)}, got \${JSON.stringify(actual)}\`);
  },
};
const records = {
  hitRegions: [], redraws: 0, removed: 0, nodeWrites: [], groupWrites: [],
};
const state = {
  nodePosition: { x: 100, y: 100 },
  nodeSize: { width: 200, height: 100 },
  nodeBounds: { x: 100, y: 70, width: 200, height: 130 },
  minimum: { width: 160, height: 90 },
  pinned: false, collapsed: false,
  groupBounds: { x: 20, y: 30, width: 300, height: 200 },
  selectedNodes: [], selectedGroups: [],
};
const node = {
  id: "n1",
  isPinned: () => state.pinned,
  isCollapsed: () => state.collapsed,
  getBounds: () => ({ ...state.nodeBounds }),
  getPosition: () => ({ ...state.nodePosition }),
  getSize: () => ({ ...state.nodeSize }),
  getMinimumSize: () => ({ ...state.minimum }),
  setPosition(value) {
    records.nodeWrites.push(["position", { ...value }]);
    state.nodePosition = { ...value };
    state.nodeBounds = { ...state.nodeBounds, x: value.x, y: value.y - 30 };
  },
  setSize(value) {
    records.nodeWrites.push(["size", { ...value }]);
    state.nodeSize = { ...value };
    state.nodeBounds = {
      ...state.nodeBounds, width: value.width, height: value.height + 30,
    };
  },
};
const group = {
  id: "g1",
  getBounds: () => ({ ...state.groupBounds }),
  setBounds(value) {
    records.groupWrites.push({ ...value });
    state.groupBounds = { ...value };
  },
};
let overlayDef;
const overlayHandle = {
  redraw: () => { records.redraws += 1; },
  setHitRegions: (value) => { records.hitRegions.push(structuredClone(value)); },
  setInteractive() {}, setVisible() {},
  remove: () => { records.removed += 1; },
};
globalThis.__comfy = {
  graph: {
    selection: () => state.selectedNodes,
    groupSelection: () => state.selectedGroups,
  },
  ui: {
    mountGraphOverlay(definition) {
      overlayDef = definition;
      return overlayHandle;
    },
  },
};

const context = {
  arcs: [],
  save() {}, restore() {}, beginPath() {}, fill() {}, stroke() {},
  arc(x, y, radius) { this.arcs.push({ x, y, radius }); },
};
const viewport = (scale) => ({
  scale,
  graphToViewport: ({ x, y }) => ({ x: x * scale, y: y * scale }),
});
const pointer = (pointerId, x, y) => ({
  pointerId, graph: { x, y }, viewport: { x, y }, key: "",
});

await import("/web/index.js");

globalThis.__run = async () => {
  state.selectedNodes = [node];
  overlayDef.draw(context, [800, 600], viewport(2));
  assert.equal(context.arcs.length, 4);
  assert.deepEqual(context.arcs.map(({ radius }) => radius), [10, 10, 10, 10]);
  assert.deepEqual(records.hitRegions.at(-1), [
    { kind: "circle", x: 200, y: 140, radius: 18 },
    { kind: "circle", x: 600, y: 140, radius: 18 },
    { kind: "circle", x: 200, y: 400, radius: 18 },
    { kind: "circle", x: 600, y: 400, radius: 18 },
  ]);

  overlayDef.onPointerDown(pointer(7, 100, 70));
  context.arcs = [];
  overlayDef.draw(context, [800, 600], viewport(0.5));
  assert.deepEqual(context.arcs.map(({ radius }) => radius), [13.5, 10, 10, 10]);
  overlayDef.onPointerMove(pointer(8, 250, 200));
  assert.deepEqual(records.nodeWrites, []);
  overlayDef.onPointerMove(pointer(7, 250, 200));
  assert.deepEqual(records.nodeWrites, [
    ["position", { x: 140, y: 110 }],
    ["size", { width: 160, height: 90 }],
  ]);
  assert.deepEqual({
    x: state.nodePosition.x + state.nodeSize.width,
    y: state.nodePosition.y + state.nodeSize.height,
  }, { x: 300, y: 200 });
  overlayDef.onPointerUp(pointer(8, 0, 0));
  assert.equal(records.redraws, 2);
  overlayDef.onPointerUp(pointer(7, 0, 0));
  assert.equal(records.redraws, 3);

  state.selectedNodes = [];
  state.selectedGroups = [group];
  overlayDef.draw(context, [800, 600], viewport(1));
  overlayDef.onPointerDown(pointer(11, 320, 230));
  overlayDef.onPointerMove(pointer(11, 40, 40));
  assert.deepEqual(records.groupWrites.at(-1), {
    x: 20, y: 30, width: 140, height: 80,
  });
  overlayDef.onPointerCancel(pointer(11, 0, 0));

  state.selectedNodes = [node];
  assert.equal(state.selectedGroups.length, 1);
  overlayDef.draw(context, [800, 600], viewport(1));
  assert.deepEqual(records.hitRegions.at(-1), []);
  state.selectedGroups = [];
  state.pinned = true;
  overlayDef.draw(context, [800, 600], viewport(1));
  assert.deepEqual(records.hitRegions.at(-1), []);
  state.pinned = false;
  state.collapsed = true;
  overlayDef.draw(context, [800, 600], viewport(1));
  assert.deepEqual(records.hitRegions.at(-1), []);
  state.collapsed = false;

  overlayDef.draw(context, [800, 600], viewport(1));
  overlayDef.onPointerDown(pointer(13, state.nodeBounds.x, state.nodeBounds.y));
  overlayDef.onKeyDown({ key: "Escape" });
  const writes = records.nodeWrites.length;
  overlayDef.onPointerMove(pointer(13, 0, 0));
  assert.equal(records.nodeWrites.length, writes);

  state.nodeBounds = { x: 12, y: 34, width: 56, height: 78 };
  overlayDef.draw(context, [800, 600], viewport(1));
  assert.deepEqual(records.hitRegions.at(-1)[0], {
    kind: "circle", x: 12, y: 34, radius: 18,
  });

  const { touchResize } = await import("/web/index.js");
  touchResize.remove();
  assert.deepEqual(records.hitRegions.at(-1), []);
  assert.equal(records.removed, 1);
  return { records, state };
};
</script>`;

const server = http.createServer((request, response) => {
  const url = request.url.split("?")[0];
  const send = (body, type) => {
    response.writeHead(200, { "Content-Type": type });
    response.end(body);
  };
  if (url === "/") return send(pageSource, "text/html");
  if (url === "/comfy/api/v2.js") {
    return send("export const comfy = globalThis.__comfy;", "text/javascript");
  }
  if (url.startsWith("/web/")) {
    const file = path.join(web, url.slice("/web/".length));
    if (existsSync(file)) return send(readFileSync(file), "text/javascript");
  }
  response.writeHead(404);
  response.end("not found");
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(() => typeof globalThis.__run === "function");
  await page.evaluate(() => globalThis.__run());
  assert.deepEqual(errors, []);
  console.log("touch resize frontend behavior: PASS");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
