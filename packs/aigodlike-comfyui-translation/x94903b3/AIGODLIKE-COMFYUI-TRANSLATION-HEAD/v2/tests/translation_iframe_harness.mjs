/** Run the actual locale pack through the real allow-scripts host boundary. */
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

const definitions = [
  {
    type: 'KSampler',
    title: 'KSampler',
    category: 'sampling',
    description: 'Uses the model to denoise a latent.',
    inputs: [
      { name: 'model', type: 'MODEL', options: {} },
      {
        name: 'steps',
        type: 'INT',
        options: {
          tooltip: 'The number of steps used in the denoising process.',
        },
      },
    ],
    outputs: [{
      name: 'LATENT',
      type: 'LATENT',
      tooltip: 'The denoised latent.',
    }],
    hidden: {},
    isOutputNode: false,
  },
  {
    type: 'UntranslatedFixture',
    title: 'Untranslated Fixture',
    category: 'tests',
    description: '',
    inputs: [],
    outputs: [],
    hidden: {},
    isOutputNode: false,
  },
];

const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs'

window.__settings = new Map([['Comfy.Locale', 'zh']])
window.__settingListeners = new Map()
window.__storage = new Map()
window.__catalogs = []
window.__buttons = []

const definitions = ${JSON.stringify(definitions)}
const objectInfo = {
  KSampler: {
    display_name: 'KSampler',
    category: 'sampling',
    description: 'Uses the model to denoise a latent.',
    input: {
      required: {
        model: ['MODEL', {}],
        steps: ['INT', {
          tooltip: 'The number of steps used in the denoising process.',
        }],
      },
    },
    output: ['LATENT'],
    output_name: ['LATENT'],
    output_tooltips: ['The denoised latent.'],
    output_node: false,
  },
  UntranslatedFixture: {
    display_name: 'Untranslated Fixture',
    category: 'tests',
    description: '',
    input: { required: {} },
    output: [],
    output_node: false,
  },
}
const comfy = {
  onWorkflowLoaded() { return () => {} },
  graph: { nodes() { return [] }, node() { return undefined } },
  workflow: { documentId() { return 'translation-fixture' } },
  backend: {
    url(value) { return new URL(value, location.origin).href },
    async fetch(route) {
      if (route !== '/object_info') throw new Error('unexpected route ' + route)
      return { ok: true, json: async () => structuredClone(objectInfo) }
    },
  },
  settings: {
    get(id) { return window.__settings.get(id) },
    async set(id, value) {
      const previous = window.__settings.get(id)
      window.__settings.set(id, value)
      for (const listener of window.__settingListeners.get(id) || []) {
        listener(value, previous)
      }
    },
    onChange(id, listener) {
      const listeners = window.__settingListeners.get(id) || []
      listeners.push(listener)
      window.__settingListeners.set(id, listeners)
      return () => {
        const index = listeners.indexOf(listener)
        if (index >= 0) listeners.splice(index, 1)
      }
    },
  },
  storage: {
    async get(name) { return window.__storage.get(name) },
    async set(name, value) { window.__storage.set(name, value) },
    async remove(name) { window.__storage.delete(name) },
    async list() { return [] },
    async usage() { return { usedBytes: 0, entryCount: 0 } },
  },
  defs: {
    all() { return structuredClone(definitions) },
    get(type) { return definitions.find((definition) => definition.type === type) },
    has(type) { return definitions.some((definition) => definition.type === type) },
    extend() { return () => {} },
  },
  localization: {
    registerCatalog(locale, catalog) {
      window.__catalogs.push({ locale, catalog: structuredClone(catalog) })
      return () => {}
    },
  },
  ui: {
    addActionBarButton(definition) {
      window.__buttons.push(definition)
      return { update() {}, remove() {} }
    },
  },
}

const host = new SecureExtensionHost({
  comfy,
  bootstrapUrl: '/guest.js',
  capabilities: ['localization'],
  match: () => true,
  registerLocalizationCatalog(_pack, locale, catalog) {
    return comfy.localization.registerCatalog(locale, catalog)
  },
})
window.__host = host
window.__start = () => host.load(
  '/extensions/AIGODLIKE-COMFYUI-TRANSLATION/main.js')
window.__setLocale = (locale) => comfy.settings.set('Comfy.Locale', locale)
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
  if (url.startsWith('/extensions/AIGODLIKE-COMFYUI-TRANSLATION/')) {
    const relative = url.slice('/extensions/AIGODLIKE-COMFYUI-TRANSLATION/'.length);
    const file = path.resolve(root, relative);
    if (file.startsWith(root + path.sep) && existsSync(file)) {
      return send(readFileSync(file), 'text/javascript');
    }
  }
  if (url.startsWith('/src/')) {
    const file = path.join(frontend, url.slice('/src/'.length));
    if (existsSync(file)) return send(readFileSync(file), 'text/javascript');
  }
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
  try {
    await page.waitForFunction(
      () => typeof window.__start === 'function',
      null,
      { timeout: 10_000 },
    );
  } catch (error) {
    console.error(`PAGE_ERRORS:${JSON.stringify(pageErrors)}`);
    error.message += `\npage errors: ${JSON.stringify(pageErrors)}`;
    throw error;
  }
  await page.evaluate(() => window.__start());
  try {
    await page.waitForFunction(() =>
      window.__catalogs.length === 5 && window.__buttons.length === 1,
    null, { timeout: 15_000 });
  } catch (error) {
    const diagnostics = await page.evaluate(() => ({
      catalogs: window.__catalogs.length,
      buttons: window.__buttons.length,
      loadResults: window.__host.loadResults || [],
      packErrors: window.__host.packErrors || [],
    }));
    console.error(`LOAD_DIAGNOSTICS:${JSON.stringify(diagnostics)}`);
    error.message += `\n${JSON.stringify(diagnostics)}`;
    throw error;
  }

  const chinese = await page.evaluate(() =>
    window.__catalogs.find(({ locale }) => locale === 'zh'));
  assert.equal(chinese.locale, 'zh');
  assert.equal(chinese.catalog.messages.actionbar.share, '分享');
  assert.equal(chinese.catalog.phrases['Switch Locale'], '切换语言');
  assert.equal(chinese.catalog.phrases['Convert '], '转换 ');
  assert.equal(chinese.catalog.phrases[' to input'], ' 为输入');
  assert.equal(chinese.catalog.phrases['Queue size:'], '队列大小:');
  assert.equal(chinese.catalog.messages.nodeCategories.sampling, '采样');
  assert.equal(
    chinese.catalog.messages.nodeDefs.KSampler.display_name,
    'K采样器',
  );
  assert.equal(
    chinese.catalog.messages.nodeDefs.KSampler.description,
    '使用输入的模型、正面条件、负面条件去除Latent的噪波。',
  );
  assert.equal(
    chinese.catalog.messages.nodeDefs.KSampler.inputs.model.name,
    '模型',
  );
  assert.equal(
    chinese.catalog.messages.nodeDefs.KSampler.inputs.steps.tooltip,
    '降噪的步数。',
  );
  assert.equal(
    chinese.catalog.messages.nodeDefs.KSampler.outputs['0'].name,
    'Latent',
  );
  assert.equal(
    chinese.catalog.messages.nodeDefs.KSampler.outputs['0'].tooltip,
    '降噪后的Latent。',
  );
  assert.equal(
    chinese.catalog.messages.nodeDefs.UntranslatedFixture,
    undefined,
  );

  // This callback crosses from the host button into the sandbox.  The first
  // click selects English; the second returns to the persisted translated id.
  await page.evaluate(() => window.__buttons[0].run());
  await page.waitForFunction(() => window.__settings.get('Comfy.Locale') === 'en');
  await page.evaluate(() => window.__buttons[0].run());
  await page.waitForFunction(() => window.__settings.get('Comfy.Locale') === 'zh');
  assert.equal(await page.evaluate(() => window.__catalogs.length), 5);

  await page.evaluate(() => window.__setLocale('ru'));
  await page.waitForFunction(() =>
    window.__storage.get('AIGODLIKE.Translation/last-locale') === 'ru');
  const russian = await page.evaluate(() =>
    window.__catalogs.find(({ locale }) => locale === 'ru'));
  assert.equal(russian.locale, 'ru');
  assert.equal(russian.catalog.messages.actionbar.share, 'Поделиться');
  assert.equal(russian.catalog.phrases['Switch Locale'], 'Смена языка');

  const observed = await page.evaluate(() => ({
    sandbox: document.querySelector('iframe')?.getAttribute('sandbox'),
    packErrors: window.__host.packErrors || [],
    loadResults: window.__host.loadResults || [],
    stored: window.__storage.get('AIGODLIKE.Translation/last-locale'),
  }));
  assert.equal(observed.sandbox, 'allow-scripts');
  assert.deepEqual(observed.packErrors, []);
  assert.equal(observed.loadResults.length, 1);
  assert.equal(observed.loadResults[0].ok, true);
  assert.equal(observed.stored, 'ru');
  assert.deepEqual(pageErrors, []);

  console.log('PASS: 0 backend nodes, 1 sandboxed AIGODLIKE locale extension');
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
