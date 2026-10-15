import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';

const v2 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runtime = '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
const entry = "import './TKAudioSpeakerTalkTime..js'; import './TKLocateSpeakersUsingSilenceBreaks.js';";
const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs';
const nodes = new Map(), registrations = [], commits = [];
function makeNode(id, type, count) {
  const records = new Map(), properties = {};
  function number(name, value) {
    const listeners = new Map();
    const handle = { name, widgetType: typeof value === 'string' ? 'text' : 'number',
      getValue: () => value, getOptions: () => ({}), isSerialized: () => true,
      isHidden: () => !!handle.hidden, setHidden: hidden => { handle.hidden = hidden; },
      getHeight: () => 28,
      setValue(next) {
        if (Object.is(next, value)) return;
        const before = value; value = next; commits.push({ id, name, value });
        for (const fn of listeners.get('change') || []) fn(next, before);
      },
      on(event, fn) {
        if (!listeners.has(event)) listeners.set(event, new Set());
        listeners.get(event).add(fn); return () => listeners.get(event).delete(fn);
      }, listeners,
    };
    records.set(name, { handle });
  }
  for (let i = 1; i <= count; i++) { number('track_start_' + i, 0); number('track_end_' + i, 0); }
  if (count === 14) { number('track_state', 'DataUnchanged'); number('speaker_times', ''); number('silence_threshold', 1); }
  const node = { id, type, comfyClass: type,
    getProperties: () => properties, getProperty: key => properties[key],
    setProperty: (key, value) => { properties[key] = value; },
    setSerializeWidgets: value => { node.serialize = value; }, isSerializingWidgets: () => true,
    snapshot: () => ({ id, type, title: type, position: { x: 0, y: 0 }, size: { width: 500, height: 480 } }),
    inputs: { all: () => [] }, outputs: { all: () => [] },
    setSizeConstraints() {},
    widgets: {
      all: () => [...records.values()].map(rec => rec.handle), get: name => records.get(name)?.handle,
      names: () => [...records.keys()],
      mount(def) {
        const container = document.createElement('div'); document.body.append(container);
        const handle = { name: def.name, widgetType: 'custom', getValue: () => undefined,
          getOptions: () => ({ serialize: false }), isSerialized: () => false,
          isHidden: () => false, getHeight: () => def.height,
          on() { return () => {}; },
        };
        records.set(def.name, { def, container, handle });
        def.render(container, { get: () => undefined, onChange: () => () => {} }); return handle;
      },
      canvas(def) {
        const canvas = document.createElement('canvas'); canvas.width = 500; canvas.height = def.height || 65;
        document.body.append(canvas);
        const handle = { name: def.name, widgetType: 'custom', getValue: () => undefined,
          getOptions: () => ({ serialize: false }), isSerialized: () => false, isHidden: () => false,
          on() { return () => {}; },
        };
        records.set(def.name, { def, canvas, handle });
        const surface = { widget: handle, redraw() { def.draw(canvas.getContext('2d'), [500, canvas.height], {}); } };
        surface.redraw(); return surface;
      },
      remove(name) {
        const rec = records.get(name); if (!rec) return false;
        rec.def?.destroy?.(); rec.container?.remove(); rec.canvas?.remove(); records.delete(name); return true;
      },
    }, records,
  };
  nodes.set(id, node); return node;
}
makeNode('1', 'TKAudioSpeakerTalkTime', 10); makeNode('2', 'TKLocateSpeakersUsingSilenceBreaks', 14);
const response = body => ({ ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) });
const comfy = {
  backend: { url: value => new URL(value, location.origin).href, fetch: async url => {
    if (url === '/object_info') return response(JSON.stringify({ TKAudioSpeakerTalkTime: {}, TKLocateSpeakersUsingSilenceBreaks: {} }));
    throw Error('unexpected backend URL ' + url);
  } },
  graph: { nodes: () => [...nodes.values()], node: id => nodes.get(String(id)), groups: () => [] },
  workflow: { documentId: () => 'handy-workflow-proof' }, onWorkflowLoaded: () => () => {},
  defs: { extend(selector, apply) {
    const rec = { selector }; apply({ onCreated(fn) { rec.created = fn; }, onRemoved(fn) { rec.removed = fn; },
      onExecuted(fn) { rec.executed = fn; }, onConfigured(fn) { rec.configured = fn; } });
    registrations.push(rec); return () => {};
  } },
};
const host = new SecureExtensionHost({ comfy, bootstrapUrl: '/guest.js', match: () => true, capabilities: [] });
window.__start = async () => {
  await host.load('/extensions/handy-proof/entry.js');
  for (const rec of registrations) for (const node of nodes.values())
    if (rec.selector === node.type) rec.created?.(node, {});
};
window.__state = () => ({
  errors: host.packErrors ?? [], sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
  panels: host._uiByKey.size, commits: structuredClone(commits),
  values: [...nodes].map(([id, node]) => ({ id, values: Object.fromEntries([...node.records]
    .filter(([, rec]) => !rec.def).map(([name, rec]) => [name, rec.handle.getValue()])) })),
});
window.__edit = (id, row, index, value) => {
  const ui = [...host._uiByKey].find(([key]) => key.includes(':' + id + ':' + row + ':'))?.[1];
  if (!ui) throw Error('no mounted row');
  const input = ui.__shadow.querySelectorAll('input')[index];
  input.value = value; input.dispatchEvent(new Event('input', { bubbles: true }));
};
window.__external = (id, name, value) => nodes.get(id).widgets.get(name).setValue(value);
window.__input = (id, row, index) => [...host._uiByKey].find(([key]) => key.includes(':' + id + ':' + row + ':'))
  ?.[1].__shadow.querySelectorAll('input')[index].value;
window.__executed = (id, raw) => {
  const node = nodes.get(id); for (const rec of registrations) if (rec.selector === node.type) rec.executed?.(node, { raw, images: [], text: [] });
};
window.__remove = async id => {
  const node = nodes.get(id); for (const rec of registrations) if (rec.selector === node.type) rec.removed?.(node);
  nodes.delete(id);
  for (const name of [...node.widgets.names()]) if (node.records.get(name)?.def) node.widgets.remove(name);
};
window.__destroy = () => host.destroy();
</script></body>`;
const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost').pathname;
    let body, type = 'text/javascript';
    if (url === '/') { body = pageSource; type = 'text/html'; }
    else if (url === '/guest.js') body = readFileSync(path.join(runtime, 'guest.mjs'));
    else if (url === '/comfy/api/v2.js') body = 'export const comfy = globalThis.comfy;';
    else if (url === '/extensions/handy-proof/entry.js') body = entry;
    else if (url.startsWith('/extensions/handy-proof/')) {
        const file = path.resolve(v2, 'web', url.slice('/extensions/handy-proof/'.length));
        if (file.startsWith(path.join(v2, 'web') + path.sep) && existsSync(file)) body = readFileSync(file);
    } else if (url.startsWith('/src/')) {
        const file = path.resolve(runtime, url.slice(5));
        if (file.startsWith(runtime + path.sep) && existsSync(file)) body = readFileSync(file);
    }
    if (body === undefined) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' }); res.end(body);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({ headless: true });
let checks = 0;
function check(fn) { fn(); checks++; }
try {
    const page = await browser.newPage(), pageErrors = [];
    page.on('pageerror', error => pageErrors.push(String(error)));
    await page.goto('http://127.0.0.1:' + server.address().port);
    await page.waitForFunction(() => typeof window.__start === 'function');
    await page.evaluate(() => window.__start());
    await page.waitForFunction(() => window.__state().panels === 18);
    let state = await page.evaluate(() => window.__state());
    check(() => assert.equal(state.sandbox, 'allow-scripts'));
    for (let i = 1; i <= 10; i++) {
        await page.evaluate(i => window.__edit('1', 'track_row_' + i, 0, String(i + .25)), i);
        await page.waitForFunction(i => window.__state().values[0].values['track_start_' + i] === i + .25, i);
        state = await page.evaluate(() => window.__state());
        check(() => assert.equal(state.values[0].values['track_start_' + i], i + .25));
    }
    await page.evaluate(() => window.__external('1', 'track_end_3', 25.5));
    await page.waitForFunction(() => window.__input('1', 'track_row_3', 1) === '25.5');
    const externalValue = await page.evaluate(() => window.__input('1', 'track_row_3', 1));
    check(() => assert.equal(externalValue, '25.5'));
    const segments = Array.from({ length: 20 }, (_, i) => ({ start: i / 3, end: i / 3 + .25, speaker: i % 2 }));
    await page.evaluate(segments => window.__executed('2', { duration: [10], speaker_times: [segments] }), segments);
    await page.waitForFunction(() => window.__state().values[1].values.track_state === 'DataChange');
    await page.waitForFunction(() => Object.entries(window.__state().values[1].values)
        .filter(([name, value]) => name.startsWith('track_end_') && value > 0).length === 14);
    state = await page.evaluate(() => window.__state());
    check(() => assert.equal(JSON.parse(state.values[1].values.speaker_times).length, 20));
    check(() => assert.equal(Object.entries(state.values[1].values).filter(([name, value]) => name.startsWith('track_end_') && value > 0).length, 14));
    check(() => assert.deepEqual(state.errors, []));
    await page.evaluate(() => window.__remove('1'));
    await page.waitForFunction(() => window.__state().panels === 8);
    // Removal is asynchronous across the worker boundary: observe queued replies
    // rather than scoring absence of errors in the first host task only.
    await page.waitForTimeout(150);
    check(() => assert.deepEqual(pageErrors, []));
    await page.evaluate(() => window.__destroy());
    console.log(JSON.stringify({ passed: checks, failed: 0, tier: 'actual-opaque-iframe-worker-production-renderer',
        qualification: 'Actual pack files/production guest+host+sanitizer with public host widget fixture; no complete29/backend/PCM/route/cloud proof.' }));
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
