/** Hermetic differential checks for every generated locale catalog. */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import {
  buildNativeCatalog,
  buildNodeDefinitions,
  escapeI18nMessage,
  normalizeI18nKey,
} from '../MenuTranslate.js';


const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const localeMap = new Map([
  ['zh', 'zh-CN'],
  ['zh-TW', 'zh-TW'],
  ['ja', 'ja-JP'],
  ['ko', 'ko-KR'],
  ['ru', 'ru-RU'],
]);
const metadata = JSON.parse(readFileSync(
  path.join(root, 'catalogs', 'catalog-meta.json'), 'utf8'));

function mergeDirectory(directory) {
  const result = {};
  for (const filename of readdirSync(directory).filter((name) =>
    name.endsWith('.json')).sort()) {
    Object.assign(
      result,
      JSON.parse(readFileSync(path.join(directory, filename), 'utf8')),
    );
  }
  return result;
}

function legacyMenu(locale) {
  const directory = path.join(root, locale);
  const result = {};
  try {
    Object.assign(result, mergeDirectory(path.join(directory, 'Menus')));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  for (const filename of ['Menu.json', 'menu.json']) {
    try {
      Object.assign(
        result,
        JSON.parse(readFileSync(path.join(directory, filename), 'utf8')),
      );
      break;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  return result;
}

const definitions = [
  {
    type: 'KSampler',
    title: 'KSampler',
    category: 'sampling',
    description: '',
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
];

for (const [hostLocale, legacyLocale] of localeMap) {
  const moduleUrl = pathToFileURL(
    path.join(root, 'catalogs', `${hostLocale}.js`),
  );
  const generated = (await import(moduleUrl)).default;
  const expectedNodes = mergeDirectory(path.join(root, legacyLocale, 'Nodes'));
  assert.deepEqual(generated.nodes, expectedNodes);

  const expectedPhrases = Object.fromEntries(
    Object.entries(legacyMenu(legacyLocale)).filter(([key, value]) =>
      typeof value === 'string' && key && key !== value),
  );
  assert.deepEqual(generated.phrases, expectedPhrases);
  assert.equal(
    Object.keys(generated.nodes).length,
    metadata.locales[hostLocale].node_definitions,
  );
  assert.equal(
    Object.keys(legacyMenu(legacyLocale)).length,
    metadata.locales[hostLocale].menu_source_phrases,
  );

  const catalog = buildNativeCatalog(generated, definitions);
  assert.equal(typeof catalog.messages, 'object');
  assert.equal(catalog.phrases, generated.phrases);
  if (generated.nodes.KSampler) {
    assert.equal(
      catalog.messages.nodeDefs.KSampler.display_name,
      escapeI18nMessage(generated.nodes.KSampler.title),
    );
  }
}

const maliciousDefinition = [{
  type: 'Pack.Node',
  title: 'Pack.Node',
  category: 'test',
  description: '',
  inputs: [{
    name: 'value.with.dot',
    localizedName: 'value',
    type: 'STRING',
    options: { tooltip: 'raw tooltip' },
  }],
  outputs: [{ name: 'OUT', type: 'STRING', tooltip: 'raw output tooltip' }],
  hidden: {},
  isOutputNode: false,
}];
const escaped = buildNodeDefinitions({
  'Pack.Node': {
    title: `@{'unsafe'}|$%\\`,
    inputs: {
      'value.with.dot': 'translated $ value',
      'raw tooltip': `raw @{'tooltip'}`,
    },
    outputs: {
      OUT: 'translated output',
      'raw output tooltip': 'translated output tooltip',
    },
  },
}, maliciousDefinition);
assert.equal(normalizeI18nKey('Pack.Node'), 'Pack_Node');
assert.equal(
  escaped.Pack_Node.inputs.value_with_dot.name,
  "translated {'$'} value",
);
assert.equal(
  escaped.Pack_Node.inputs.value_with_dot.tooltip,
  `raw @{'tooltip'}`,
);
assert.equal(
  escaped.Pack_Node.outputs['0'].tooltip,
  'translated output tooltip',
);
assert.match(escaped.Pack_Node.display_name, /\{'@'\}/);

console.log('PASS: all 5 AIGODLIKE catalogs match pristine dictionaries');
