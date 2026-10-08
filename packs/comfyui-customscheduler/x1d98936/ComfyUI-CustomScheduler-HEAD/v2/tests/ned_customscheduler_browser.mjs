import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import http from 'node:http';
import vm from 'node:vm';
import { chromium } from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const pack = readFileSync(path.resolve(here, '../js/extension.js'), 'utf8');
const source = readFileSync(path.resolve(here, '../../js/extension.js'), 'utf8');
let legacy;
vm.runInNewContext(source.replace(/^import[^\n]+\n/, ''), { app: { registerExtension(value) { legacy = value; } } });
const oldNode = {
  size: [200, 100], getTitle: () => 'CustomScheduler', setSize(size) { this.size = size; },
  computeSize() { return [200, 100 + this.widgets.filter(w => w.type === 'number').length * 22]; },
  widgets: [{ name: 'steps', value: 4, type: 'number' }, ...Array.from({ length: 26 }, (_, i) => ({ name: `sigma_${i}`, value: i / 100, type: 'number', computeSize: () => [200, 22] }))],
};
legacy.nodeCreated(oldNode);
for (const steps of [1, 25, 7, 4]) {
  oldNode.widgets[0].value = steps;
  assert.equal(oldNode.widgets.slice(1).filter(w => w.type === 'number').length, steps + 1);
  assert.deepEqual(oldNode.widgets.slice(1).map(w => w.value), Array.from({ length: 26 }, (_, i) => i / 100));
}

const root = '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs';
const nodes = new Map();
const registrations = [];
function makeNode(id, steps, sigmas) {
  const items = new Map();
  function widget(name, value) {
    const listeners = new Map();
    const w = { name, widgetType: name === 'steps' ? 'INT' : 'FLOAT', value, hidden: false,
      getValue() { return this.value; }, getOptions() { return {}; }, isHidden() { return this.hidden; },
      isSerialized() { return true; }, setHidden(v) { this.hidden = v; },
      setValue(v) { const old = this.value; if (old === v) return; this.value = v;
        for (const fn of listeners.get('change') || []) fn(v, old); },
      on(event, fn) { let set = listeners.get(event); if (!set) listeners.set(event, set = new Set());
        set.add(fn); return () => set.delete(fn); },
      count() { return [...listeners.values()].reduce((n, set) => n + set.size, 0); },
    }; items.set(name, w); return w;
  }
  widget('steps', steps);
  for (let i = 0; i <= 25; i++) widget('sigma_' + i, sigmas?.[i] ?? i / 100);
  const node = { id, type: 'CustomScheduler', widgets: { all: () => [...items.values()], get: name => items.get(name) },
    inputs: { all: () => [] }, outputs: { all: () => [] }, layouts: 0,
    snapshot: () => ({ id, type: 'CustomScheduler', title: 'Renamed user title' }),
    setSizeConstraints(c) { if (JSON.stringify(c) !== JSON.stringify({ autoHeight: true })) throw Error('wrong layout'); this.layouts++; },
  }; nodes.set(id, node); return node;
}
let a = makeNode('1', 4), b = makeNode('2', 1);
const workflowFeed = [];
let oldNodes = [];
const comfy = { backend: { url: v => new URL(v, location.origin).href, fetch: async () => new Response('{}') },
  graph: { nodes: () => [...nodes.values()], node: id => nodes.get(String(id)), groups: () => [] },
  workflow: { documentId: () => 'customscheduler-proof' }, onWorkflowLoaded: fn => { workflowFeed.push(fn); return () => {}; },
  defs: { extend(selector, apply) { if (selector !== 'CustomScheduler' && typeof selector !== 'function') throw Error('foreign selector');
    const record = {}; apply({ onCreated(fn) { record.created = fn; }, onConfigured(fn) { record.configured = fn; }, onRemoved(fn) { record.removed = fn; } });
    registrations.push(record); return () => {}; } },
};
const host = new SecureExtensionHost({ comfy, bootstrapUrl: '/guest.js', capabilities: [] });
const hooks = (key, node) => registrations.forEach(r => r[key]?.(node, {}));
window.__start = async () => { await host.load('/extensions/customscheduler/pack.js'); hooks('created', a); hooks('created', b); };
window.__state = () => ({ a: a.widgets.all().slice(1).map(w => ({ value: w.value, hidden: w.hidden })),
 b: b.widgets.all().slice(1).map(w => ({ value: w.value, hidden: w.hidden })),
 subscriptions: host._subs?.size ?? 0, layouts: [a.layouts, b.layouts], errors: host.packErrors || [],
 sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
 oldListeners: oldNodes.map(n => n.widgets.get('steps').count()) });
window.__change = (id, steps) => nodes.get(id).widgets.get('steps').setValue(steps);
window.__edit = () => a.widgets.get('sigma_20').setValue(77.1234);
window.__reload = () => { hooks('configured', a); hooks('configured', b); };
window.__reconstruct = () => {
  const saved = JSON.parse(JSON.stringify([a, b].map(node => node.widgets.all().map(w => w.getValue()))));
  oldNodes = [a, b];
  a = makeNode('1', saved[0][0], saved[0].slice(1));
  b = makeNode('2', saved[1][0], saved[1].slice(1));
  workflowFeed.forEach(fn => fn()); hooks('configured', a); hooks('configured', b);
};
window.__remove = () => hooks('removed', a);
window.__destroy = () => { host.destroy(); return { subscriptions: host._subs?.size ?? 0,
 listeners: [a.widgets.get('steps').count(), b.widgets.get('steps').count()], iframe: !!document.querySelector('iframe') }; };
</script></body>`;
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost').pathname;
  let body, type = 'text/javascript';
  if (url === '/') { body = pageSource; type = 'text/html'; }
  else if (url === '/guest.js') body = readFileSync(path.join(root, 'guest.mjs'));
  else if (url === '/comfy/api/v2.js') body = 'export const comfy = globalThis.comfy';
  else if (url === '/extensions/customscheduler/pack.js') body = pack;
  else if (url.startsWith('/src/')) {
    const file = path.resolve(root, url.slice(5));
    if (file.startsWith(root + path.sep) && existsSync(file)) body = readFileSync(file);
  }
  if (body === undefined) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' }); response.end(body);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({ headless: true });
function check(rows, steps) { rows.forEach((w, i) => assert.equal(w.hidden, i > steps)); }
try {
  const page = await browser.newPage();
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  page.on('console', message => { if (message.type() === 'error') console.error('browser:', message.text()); });
  await page.goto('http://127.0.0.1:' + server.address().port);
  await page.waitForFunction(() => typeof window.__start === 'function');
  await page.evaluate(() => window.__start());
  try { await page.waitForFunction(() => window.__state().subscriptions === 2 && window.__state().layouts.every(v => v > 0)); }
  catch (error) { console.error('readiness state', JSON.stringify(await page.evaluate(() => window.__state())), errors); throw error; }
  let state = await page.evaluate(() => window.__state()); check(state.a, 4); check(state.b, 1);
  assert.equal(state.sandbox, 'allow-scripts');
  await page.evaluate(() => window.__edit());
  for (const steps of [25, 1, 7, 4]) {
    await page.evaluate(v => window.__change('1', v), steps);
    await page.waitForFunction(v => window.__state().a.every((w, i) => w.hidden === (i > v)), steps);
    state = await page.evaluate(() => window.__state()); check(state.a, steps); check(state.b, 1);
    assert.equal(state.a[20].value, 77.1234);
  }
  await page.evaluate(() => window.__reload());
  await page.waitForFunction(() => window.__state().subscriptions === 2);
  state = await page.evaluate(() => window.__state()); check(state.a, 4); assert.equal(state.a[20].value, 77.1234);
  await page.evaluate(() => window.__reconstruct());
  await page.waitForFunction(() => window.__state().subscriptions === 2 && window.__state().oldListeners.every(v => v === 0) && window.__state().layouts.every(v => v > 0));
  state = await page.evaluate(() => window.__state()); check(state.a, 4); check(state.b, 1); assert.equal(state.a[20].value, 77.1234);
  await page.evaluate(() => window.__remove());
  await page.waitForFunction(() => window.__state().subscriptions === 1);
  const before = await page.evaluate(() => window.__state());
  await page.evaluate(() => window.__change('1', 25));
  // An independent live B update serves as the message barrier after removal.
  await page.evaluate(() => window.__change('2', 3));
  await page.waitForFunction(() => window.__state().b.every((w, i) => w.hidden === (i > 3)));
  state = await page.evaluate(() => window.__state()); assert.deepEqual(state.a, before.a); check(state.b, 3);
  assert.deepEqual(state.errors, []); assert.deepEqual(errors, []);
  assert.deepEqual(await page.evaluate(() => window.__destroy()), { subscriptions: 0, listeners: [0, 0], iframe: false });
  console.log('PASS pinned legacy visibility controls and actual production opaque iframe/worker facade: steps+1, all26 values retained, renamed title, independent nodes, configured rebind, teardown and removal isolation');
  console.log('QUALIFIED host widget/node fixtures; real production SecureExtensionHost/guest/sandbox messaging, not complete ComfyUI application renderer or Cloud');
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
