import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "../../../../../../../frontend/tests/_deps.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../../../../../../..");
const root = path.resolve(here, "..");
const frontend = path.join(repo, "frontend", "src");

const pageSource = `<!doctype html><meta charset="utf-8"><body>
<canvas id="graph" style="position:fixed;left:40px;top:30px;width:640px;height:360px"></canvas>
<script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

window.__commands = Object.create(null)
window.__buttons = []
window.__extra = Object.create(null)
window.__viewportListeners = []
window.__wheelEvents = 0
window.__globalKeys = 0
window.__transform = { scale: 2, offset: [10, 20] }
const settings = new Map()
const settingListeners = new Map()
const graphCanvas = document.querySelector('#graph')
graphCanvas.addEventListener('wheel', () => { window.__wheelEvents += 1 })
document.addEventListener('keydown', () => { window.__globalKeys += 1 })

const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url === '/object_info') return { ok: true, json: async () => ({}) }
      throw new Error('unexpected backend URL: ' + url)
    },
  },
  commands: {
    register(definition) { window.__commands[definition.id] = definition.run },
  },
  settings: {
    declare(definition) {
      if (!settings.has(definition.id)) settings.set(definition.id, definition.defaultValue)
    },
    get: (id) => settings.get(id),
    set: async (id, value) => { settings.set(id, value) },
    onChange(id, listener) {
      const listeners = settingListeners.get(id) ?? []
      listeners.push(listener)
      settingListeners.set(id, listeners)
      return () => settingListeners.set(
        id, listeners.filter((candidate) => candidate !== listener))
    },
  },
  ui: {
    addActionBarButton(definition) {
      window.__buttons.push(definition)
      return { update() {}, remove() {} }
    },
  },
  graph: { nodes: () => [], node: () => undefined },
  workflow: { documentId: () => 'comfyjot-document' },
  onWorkflowLoaded(listener) {
    window.__workflowLoaded = listener
    return () => { window.__workflowLoaded = null }
  },
  onViewportChanged(listener) {
    window.__viewportListeners.push(listener)
    return () => {
      window.__viewportListeners = window.__viewportListeners
        .filter((candidate) => candidate !== listener)
    }
  },
  defs: { extend: (_selector, apply) => {
    apply({ onCreated() {}, onRemoved() {} })
    return () => {}
  } },
}

const host = new SecureExtensionHost({
  comfy,
  bootstrapUrl: '/guest.js',
  match: () => true,
  capabilities: ['ui.graph-overlay', 'ui.viewport-panel', 'workflow.extra'],
  graphViewport: () => ({
    element: graphCanvas,
    scale: window.__transform.scale,
    offset: window.__transform.offset,
  }),
  workflowExtra: {
    read: (key) => structuredClone(window.__extra[key]),
    write: (key, value) => {
      if (value === undefined) delete window.__extra[key]
      else window.__extra[key] = structuredClone(value)
    },
  },
})
window.__host = host
window.__start = () => host.load('/extensions/jot/comfyjot_extension.js')
window.__run = (id) => window.__commands[id]()
window.__clickTool = (label) => {
  const record = [...host._viewportPanels.values()][0]
  const element = [...record.ui.__shadow.querySelectorAll('button')]
    .find((candidate) => candidate.textContent === label)
  if (!element) throw new Error('missing tool ' + label)
  element.click()
}
window.__state = () => {
  const overlay = [...host._graphOverlays.values()][0]
  const panel = [...host._viewportPanels.values()][0]
  const buttons = panel
    ? [...panel.ui.__shadow.querySelectorAll('button')]
      .map((button) => ({ label: button.textContent, disabled: button.disabled }))
    : []
  return {
    overlays: host._graphOverlays.size,
    panels: host._viewportPanels.size,
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    overlay: overlay ? {
      pointerEvents: overlay.canvas.style.pointerEvents,
      hidden: overlay.canvas.hidden,
      style: {
        left: overlay.canvas.style.left,
        top: overlay.canvas.style.top,
        width: overlay.canvas.style.width,
        height: overlay.canvas.style.height,
      },
      rect: overlay.canvas.getBoundingClientRect().toJSON(),
      pixels: overlay.canvas.getContext('2d')
        .getImageData(0, 0, overlay.canvas.width, overlay.canvas.height).data
        .some((value) => value !== 0),
    } : null,
    buttons,
    extra: structuredClone(window.__extra),
    packErrors: host.packErrors ?? [],
    loadResults: host.loadResults ?? [],
    wheelEvents: window.__wheelEvents,
    globalKeys: window.__globalKeys,
  }
}
window.__changeViewport = () => {
  window.__transform = { scale: 1.5, offset: [-5, 7] }
  for (const listener of window.__viewportListeners) listener()
}
window.__reloadWorkflow = async (value) => {
  window.__extra.comfyjot = structuredClone(value)
  await window.__workflowLoaded()
}
window.__destroy = () => host.destroy()
</script></body>`;

const server = http.createServer((request, response) => {
  const url = request.url.split("?")[0];
  const send = (body, type) => {
    response.writeHead(200, {
      "Content-Type": type,
      "Access-Control-Allow-Origin": "*",
    });
    response.end(body);
  };
  if (url === "/") return send(pageSource, "text/html");
  if (url === "/guest.js") {
    return send(readFileSync(path.join(frontend, "guest.mjs")), "text/javascript");
  }
  if (url === "/comfy/api/v2.js") {
    return send("export const comfy = globalThis.comfy\n", "text/javascript");
  }
  if (url === "/extensions/jot/comfyjot_extension.js") {
    return send(readFileSync(path.join(root, "web", "comfyjot_extension.js")),
      "text/javascript");
  }
  if (url === "/extensions/jot/jot/secure-overlay.js") {
    return send(readFileSync(path.join(root, "web", "jot", "secure-overlay.js")),
      "text/javascript");
  }
  if (url.startsWith("/src/")) {
    const file = path.join(frontend, url.slice("/src/".length));
    if (existsSync(file)) return send(readFileSync(file), "text/javascript");
  }
  if (url === "/object_info") return send("{}", "application/json");
  response.writeHead(404);
  response.end("not found");
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.evaluate(() => window.__start());
  await page.waitForFunction(() => {
    const state = window.__state?.();
    return state?.overlays === 1 && state?.panels === 1 &&
      Object.keys(window.__commands).length === 5 && window.__buttons.length === 1;
  });

  let state = await page.evaluate(() => window.__state());
  assert.equal(state.sandbox, "allow-scripts");
  assert.deepEqual(state.overlay.style,
    { left: "40px", top: "30px", width: "640px", height: "360px" });
  assert.equal(state.overlay.hidden, true);
  assert.equal(state.overlay.pointerEvents, "none");

  await page.evaluate(() => window.__run("ComfyJot.ToggleOverlay"));
  await page.waitForFunction(() => window.__state().overlay.hidden === false);
  assert.deepEqual((await page.evaluate(() => window.__state())).overlay.rect, {
    x: 40, y: 30, width: 640, height: 360,
    top: 30, right: 680, bottom: 390, left: 40,
  });
  await page.evaluate(() => window.__clickTool("Ink Off"));
  await page.waitForFunction(() => window.__state().overlay.pointerEvents === "auto");

  await page.mouse.move(140, 110);
  await page.mouse.down();
  await page.mouse.move(180, 130, { steps: 4 });
  await page.mouse.up();
  await page.waitForFunction(() =>
    window.__state().extra.comfyjot?.strokes?.length === 1);

  state = await page.evaluate(() => window.__state());
  assert.deepEqual(state.extra.comfyjot.strokes[0].points.at(0), [40, 20]);
  assert.deepEqual(state.extra.comfyjot.strokes[0].points.at(-1), [60, 30]);
  assert.match(state.extra.comfyjot.snapshot.image, /^data:image\/png;base64,/);
  assert.equal(state.overlay.pixels, true);
  const saved = state.extra.comfyjot;

  await page.keyboard.press("Control+z");
  await page.waitForFunction(() => window.__state().extra.comfyjot === undefined);
  assert.equal(await page.evaluate(() => window.__state().globalKeys), 0,
    "overlay-owned undo leaked to the global canvas");
  await page.keyboard.press("Control+y");
  await page.waitForFunction(() =>
    window.__state().extra.comfyjot?.strokes?.length === 1);

  await page.evaluate(() => window.__changeViewport());
  await page.waitForTimeout(50);
  state = await page.evaluate(() => window.__state());
  assert.equal(state.overlay.pixels, true);

  const rect = state.overlay.rect;
  await page.mouse.move(rect.x + 120, rect.y + 80);
  await page.mouse.wheel(0, 100);
  await page.waitForFunction(() => window.__state().wheelEvents === 1);

  await page.evaluate(() => window.__clickTool("Ink On"));
  await page.waitForFunction(() => window.__state().overlay.pointerEvents === "none");
  await page.evaluate((documentData) => window.__reloadWorkflow(documentData), saved);
  await page.waitForFunction(() =>
    window.__state().extra.comfyjot?.strokes?.length === 1);

  state = await page.evaluate(() => window.__state());
  assert.deepEqual(state.packErrors, []);
  assert.equal(state.loadResults.length, 1);
  assert.equal(state.loadResults[0].ok, true);
  assert.deepEqual(pageErrors, []);

  await page.evaluate(() => window.__destroy());
  assert.deepEqual(await page.evaluate(() => ({
    overlays: document.querySelectorAll("[data-secure-graph-overlay]").length,
    panels: document.querySelectorAll("[data-secure-viewport-panel]").length,
  })), { overlays: 0, panels: 0 });
  console.log("PASS: ComfyJot graph notes, local undo/redo, and workflow persistence");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
