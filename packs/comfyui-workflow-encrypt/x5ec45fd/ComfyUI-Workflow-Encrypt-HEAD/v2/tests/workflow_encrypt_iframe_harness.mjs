/** End-to-end iframe/worker run of the converted pack through the real host. */
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '../../../../../../../frontend/tests/_deps.mjs';


const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../../../../../..');
const root = path.resolve(here, '..');
const frontend = path.join(repo, 'frontend', 'src');
const workflow = {
  id: 'iframe-workflow',
  revision: 2,
  nodes: [{ id: 1, type: 'KSampler', widgets_values: ['iframe 🔒'] }],
  links: [],
  extra: { marker: 'real-secure-host' },
};


const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

window.__commands = Object.create(null)
window.__buttons = []
window.__prompts = []
window.__promptAnswers = []
window.__downloads = []
window.__pickedBytes = []
window.__opened = []
window.__notifications = []

const emptyBuilder = { onCreated() {}, onRemoved() {} }
const comfy = {
  backend: {
    url: (value) => new URL(value, location.origin).href,
    fetch: async (url) => {
      if (url !== '/object_info') throw new Error('unexpected backend URL: ' + url)
      return { ok: true, json: async () => ({}) }
    },
  },
  commands: {
    register(definition) { window.__commands[definition.id] = definition.run },
    async run(id) {
      const run = window.__commands[id]
      if (!run) throw new Error('unknown command ' + id)
      await run()
    },
    notify(definition) { window.__notifications.push(definition) },
  },
  ui: {
    addActionBarButton(definition) {
      window.__buttons.push(definition)
      return { update() {}, remove() {} }
    },
    async prompt(definition) {
      window.__prompts.push(definition)
      return window.__promptAnswers.shift()
    },
  },
  graph: { nodes: () => [], node: () => undefined },
  workflow: {
    documentId: () => 'iframe-document',
    async open(value) { window.__opened.push(structuredClone(value)) },
  },
  onWorkflowLoaded: () => () => {},
  defs: { extend: (_selector, apply) => { apply(emptyBuilder); return () => {} } },
}

const host = new SecureExtensionHost({
  comfy,
  bootstrapUrl: '/guest.js',
  match: () => true,
  workflowSnapshot: () => (${JSON.stringify(workflow)}),
  filePicker: async () => {
    const bytes = window.__pickedBytes.shift()
    if (bytes === undefined) return undefined
    return new File([new Uint8Array(bytes)], 'encrypted_data.txt', {
      type: 'text/plain',
    })
  },
  fileDownloader: async (data) => {
    window.__downloads.push({
      name: data.name,
      mimeType: data.mimeType,
      bytes: Array.from(data.bytes),
    })
  },
})
window.__host = host
window.__start = () => host.load(
  '/extensions/workflow-encrypt/comfyui-workflow-encrypt.js')
window.__run = (id) => window.__commands[id]()
window.__import = (bytes) => host.importFile(new File(
  [new Uint8Array(bytes)], 'encrypted_data.txt', { type: 'text/plain' }))
window.__importOrdinary = () => host.importFile(new File(
  ['ordinary text'], 'ordinary.txt', { type: 'text/plain' }))
<\/script></body>`;


const server = http.createServer((request, response) => {
  const url = request.url.split('?')[0];
  const send = (body, type) => {
    response.writeHead(200, {
      'Content-Type': type,
      'Access-Control-Allow-Origin': '*',
    });
    response.end(body);
  };
  if (url === '/') return send(pageSource, 'text/html');
  if (url === '/guest.js') {
    return send(readFileSync(path.join(frontend, 'guest.mjs')), 'text/javascript');
  }
  if (url === '/comfy/api/v2.js') {
    return send('export const comfy = globalThis.comfy\n', 'text/javascript');
  }
  if (url === '/extensions/workflow-encrypt/comfyui-workflow-encrypt.js') {
    return send(readFileSync(path.join(root, 'js', 'comfyui-workflow-encrypt.js')),
      'text/javascript');
  }
  if (url === '/extensions/workflow-encrypt/fernet.js') {
    return send(readFileSync(path.join(root, 'js', 'fernet.js')),
      'text/javascript');
  }
  if (url.startsWith('/src/')) {
    const file = path.join(frontend, url.slice('/src/'.length));
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript');
  }
  if (url === '/object_info') return send('{}', 'application/json');
  response.writeHead(404);
  response.end('not found');
});


await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error)));
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.waitForFunction(() => typeof window.__start === 'function');
  await page.evaluate(() => window.__start());
  try {
    await page.waitForFunction(() =>
      Object.keys(window.__commands).length === 2 && window.__buttons.length === 2,
    null, { timeout: 10_000 });
  } catch (error) {
    error.message += `\n${JSON.stringify(await page.evaluate(() => ({
      commands: Object.keys(window.__commands),
      buttons: window.__buttons.length,
      loadResults: window.__host.loadResults || [],
      packErrors: window.__host.packErrors || [],
    })))}`;
    throw error;
  }

  await page.evaluate(() =>
    window.__run('ComfyWorkflowEncrypt.saveEncrypted'));
  try {
    await page.waitForFunction(() =>
      window.__downloads.length === 1 && window.__prompts.length === 1,
    null, { timeout: 10_000 });
  } catch (error) {
    const diagnostics = await page.evaluate(() => ({
      downloads: window.__downloads,
      prompts: window.__prompts,
      notifications: window.__notifications,
      packErrors: window.__host.packErrors || [],
    }));
    throw new Error(`${error.message}\n${JSON.stringify(diagnostics)}`);
  }
  const first = await page.evaluate(() => ({
    download: window.__downloads[0],
    key: window.__prompts[0].value,
  }));
  assert.equal(first.download.name, 'encrypted_data.txt');
  assert.equal(first.download.mimeType, 'text/plain');
  assert.match(first.key, /^[A-Za-z0-9_-]{43}=$/);

  await page.evaluate(({ key, bytes }) => {
    window.__promptAnswers.push(key);
    window.__pickedBytes.push(bytes);
    window.__run('ComfyWorkflowEncrypt.loadDecrypted');
  }, { key: first.key, bytes: first.download.bytes });
  await page.waitForFunction(() => window.__opened.length === 1);

  // This click crosses the dedicated worker-owned action callback bridge and
  // then reuses the command, proving the visible action is not a dead clone.
  await page.evaluate(() => window.__buttons[0].run());
  await page.waitForFunction(() =>
    window.__downloads.length === 2 && window.__prompts.length === 3);

  const imported = await page.evaluate(async ({ key, bytes }) => {
    window.__promptAnswers.push(key);
    return await window.__import(bytes);
  }, { key: first.key, bytes: first.download.bytes });
  assert.deepEqual(imported, { workflow });

  const promptsBeforeOrdinary = await page.evaluate(() => window.__prompts.length);
  assert.equal(await page.evaluate(() => window.__importOrdinary()), undefined);
  assert.equal(
    await page.evaluate(() => window.__prompts.length),
    promptsBeforeOrdinary,
  );

  const wrongKey = first.key.replace(/^[A-Za-z0-9_-]/, (character) =>
    character === 'A' ? 'B' : 'A');
  const refused = await page.evaluate(async ({ key, bytes }) => {
    window.__promptAnswers.push(key);
    return await window.__import(bytes);
  }, { key: wrongKey, bytes: first.download.bytes });
  assert.equal(refused, undefined);

  const observed = await page.evaluate(() => ({
    buttons: window.__buttons.map(({ id, label }) => ({ id, label })),
    opened: window.__opened,
    notifications: window.__notifications,
    packErrors: window.__host.packErrors || [],
    loadResults: window.__host.loadResults || [],
    importerCount: window.__host._importers.size,
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
  }));
  assert.deepEqual(observed.opened, [workflow]);
  assert.equal(observed.importerCount, 1);
  assert.equal(observed.notifications.at(-1).severity, 'error');
  assert.deepEqual(observed.packErrors, []);
  assert.equal(observed.loadResults.length, 1);
  assert.equal(observed.loadResults[0].ok, true);
  assert.equal(observed.sandbox, 'allow-scripts');
  assert.deepEqual(pageErrors, []);

  console.log(`IFRAME_FERNET_VECTOR:${JSON.stringify({
    key: first.key,
    token: new TextDecoder().decode(new Uint8Array(first.download.bytes)),
    plaintext: JSON.stringify(workflow),
  })}`);
  console.log('PASS: actual pack ran in allow-scripts-only iframe and worker');
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
