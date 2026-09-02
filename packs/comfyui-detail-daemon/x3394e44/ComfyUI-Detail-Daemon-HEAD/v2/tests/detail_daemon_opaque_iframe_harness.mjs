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

const objectInfo = {
  DetailDaemonSamplerGUINode: {
    display_name: "Detail Daemon Sampler GUI",
    category: "sampling/custom_sampling/samplers",
    input: {
      required: {
        sampler: ["SAMPLER", {}],
        sigmas: ["SIGMAS", { forceInput: true }],
        detail_amount: ["FLOAT", { default: 0.1 }],
        start: ["FLOAT", { default: 0.2 }],
        end: ["FLOAT", { default: 0.8 }],
        bias: ["FLOAT", { default: 0.5 }],
        exponent: ["FLOAT", { default: 1 }],
        start_offset: ["FLOAT", { default: 0 }],
        end_offset: ["FLOAT", { default: 0 }],
        fade: ["FLOAT", { default: 0 }],
        smooth: ["BOOLEAN", { default: true }],
        cfg_scale_override: ["FLOAT", { default: 0 }],
      },
    },
    output: ["SAMPLER", "SIGMAS"],
    output_name: ["sampler", "sigmas"],
    output_node: false,
  },
};

const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

window.__hooks = null
window.__canvasDef = null
window.__constraints = []
window.__hostDraws = 0

function makeWidget(name, initial) {
  let value = initial
  const listeners = new Map()
  return {
    name, widgetType: typeof initial === 'boolean' ? 'toggle' : 'number',
    getValue() { return value },
    setValue(next) {
      const previous = value
      value = next
      for (const callback of listeners.get('change') || []) callback(next, previous)
    },
    getOptions() { return {} },
    setHidden() {}, isHidden() { return false },
    on(event, callback) {
      const values = listeners.get(event) || []
      values.push(callback)
      listeners.set(event, values)
      return () => {}
    },
  }
}

const initial = {
  detail_amount: 0.1, start: 0.2, end: 0.8, bias: 0.5, exponent: 1,
  start_offset: 0, end_offset: 0, fade: 0, smooth: true,
  cfg_scale_override: 0,
}
const widgetList = Object.entries(initial).map(([name, value]) => makeWidget(name, value))
const widgetMap = new Map(widgetList.map((widget) => [widget.name, widget]))
window.__widgetMap = widgetMap
const emptySlots = { all() { return [] }, get() { return undefined } }
let size = { width: 420, height: 300 }
const paint = document.createElement('canvas')
paint.width = 500
paint.height = 250
document.body.append(paint)
const paintContext = paint.getContext('2d')
const node = {
  id: '42', type: 'DetailDaemonSamplerGUINode',
  snapshot() {
    return {
      id: '42', type: this.type, graphId: 'root', title: this.type,
      mode: 0, collapsed: false, pinned: false,
      position: { x: 10, y: 20 }, size: { ...size }, properties: {},
    }
  },
  getProperties() { return {} }, isSerializingWidgets() { return true },
  getSize() { return { ...size } }, setSize(next) { size = { ...next } },
  setSizeConstraints(next) { window.__constraints.push(structuredClone(next)) },
  inputs: emptySlots, outputs: emptySlots,
  widgets: {
    all() { return widgetList }, get(name) { return widgetMap.get(name) },
    canvas(options) {
      window.__canvasDef = options
      const surface = {
        redraw() {
          window.__hostDraws += 1
          options.draw(paintContext, [500, 250])
        },
      }
      surface.redraw()
      return surface
    },
  },
}

const comfy = {
  backend: {
    url(value) { return new URL(value, location.origin).href },
    async fetch(route) {
      if (route === '/object_info') return {
        ok: true, status: 200, json: async () => (${JSON.stringify(objectInfo)}),
      }
      if (route.startsWith('/secure-nodes/extensions/')) return {
        ok: true, status: 200, json: async () => ({ capabilities: [] }),
      }
      throw new Error('unexpected backend route ' + route)
    },
  },
  defs: {
    extend(selector, apply) {
      if (selector !== 'DetailDaemonSamplerGUINode') return () => {}
      const hooks = {}
      apply({
        onCreated(callback) { hooks.created = callback },
        onConfigured(callback) { hooks.configured = callback },
        onRemoved(callback) { hooks.removed = callback },
      })
      window.__hooks = hooks
      return () => {}
    },
  },
  graph: {
    nodes() { return [node] },
    node(id) { return String(id) === '42' ? node : undefined },
    pointerPosition() { return { x: 0, y: 0 } }, selection() { return [] },
  },
  workflow: { documentId() { return 'detail-daemon-iframe' } },
  onWorkflowLoaded() { return () => {} },
}

const host = new SecureExtensionHost({
  comfy, bootstrapUrl: '/guest.js', match: () => true,
})
window.__host = host
window.__start = () => host.load('/extensions/detail-daemon/detailDaemonSamplerGUI.js')
window.__create = () => window.__hooks.created(node, { restored: false, loading: false })
window.__dragPeak = () => {
  const event = (type, detail = 1) => ({
    type, detail, button: 0, buttons: type === 'pointerup' ? 0 : 1,
    preventDefault() {}, stopPropagation() {},
  })
  window.__canvasDef.onPointerDown({ x: 265, y: 114, event: event('pointerdown') })
  window.__canvasDef.onPointerMove({ x: 310, y: 75, event: event('pointermove') })
  window.__canvasDef.onPointerUp({ x: 310, y: 75, event: event('pointerup') })
}
window.__reset = () => {
  widgetMap.get('detail_amount').setValue(2.5)
  window.__canvasDef.onPointerDown({
    x: 265, y: 114,
    event: { type: 'pointerdown', detail: 2, button: 0, buttons: 1,
             preventDefault() {}, stopPropagation() {} },
  })
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
  if (url === "/") return send(pageSource, "text/html");
  if (url === "/guest.js") {
    return send(readFileSync(path.join(frontend, "guest.mjs")), "text/javascript");
  }
  if (url === "/comfy/api/v2.js") {
    return send("export const comfy = globalThis.comfy\n", "text/javascript");
  }
  if (url === "/extensions/detail-daemon/detailDaemonSamplerGUI.js") {
    return send(readFileSync(path.join(root, "web", "detailDaemonSamplerGUI.js")),
      "text/javascript");
  }
  if (url.startsWith("/src/")) {
    const file = path.join(frontend, url.slice("/src/".length));
    if (existsSync(file)) return send(readFileSync(file), "text/javascript");
  }
  response.writeHead(404);
  response.end("not found");
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForFunction(() => typeof window.__start === "function");
  await page.evaluate(() => window.__start());
  await page.waitForFunction(() => typeof window.__hooks?.created === "function",
    null, { timeout: 10_000 });
  await page.evaluate(() => window.__create());
  await page.waitForFunction(() => window.__canvasDef && window.__hostDraws > 1,
    null, { timeout: 10_000 });

  await page.evaluate(() => window.__dragPeak());
  await page.waitForFunction(() =>
    window.__widgetMap.get("bias").getValue() !== 0.5 ||
    window.__widgetMap.get("detail_amount").getValue() !== 0.1,
  null, { timeout: 10_000 });
  await page.evaluate(() => window.__reset());
  await page.waitForFunction(() =>
    window.__widgetMap.get("detail_amount").getValue() === 0.1,
  null, { timeout: 10_000 });

  const observed = await page.evaluate(() => ({
    sandbox: document.querySelector("iframe")?.getAttribute("sandbox"),
    constraints: window.__constraints,
    hostDraws: window.__hostDraws,
    packErrors: window.__host.packErrors || [],
    loadResults: window.__host.loadResults || [],
  }));
  assert.equal(observed.sandbox, "allow-scripts");
  assert.ok(observed.constraints.some((value) =>
    value.minWidth === 420 && value.minHeight === 250));
  assert.ok(observed.hostDraws > 1);
  assert.deepEqual(observed.packErrors, []);
  assert.equal(observed.loadResults.length, 1);
  assert.equal(observed.loadResults[0].ok, true);
  assert.deepEqual(pageErrors, []);
  console.log("Detail-Daemon opaque iframe canvas harness: PASS");
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
