import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import vm from 'node:vm';
import { TextDecoder, TextEncoder } from 'node:util';
import { webcrypto } from 'node:crypto';


const root = path.resolve(process.argv[2]);
const mainPath = path.join(root, 'js', 'comfyui-workflow-encrypt.js');
const fernetPath = path.join(root, 'js', 'fernet.js');
const commands = new Map();
const buttons = [];
const importers = [];
const notifications = [];
const prompts = [];
const downloads = [];
const opened = [];
const promptAnswers = [];
const pickedFiles = [];
const cryptoCalls = [];
const workflow = {
  id: 'secure-workflow',
  revision: 4,
  nodes: [{ id: 1, type: 'KSampler', widgets_values: ['café', 7] }],
  links: [],
  extra: { note: '🔒 local only' },
};
const plain = (value) => JSON.parse(JSON.stringify(value));
let snapshotValue = workflow;
let pickerCalls = 0;
let snapshotError;
let downloadError;


const comfy = {
  crypto: {
    async aesCbcEncrypt({ key, iv, plaintext }) {
      cryptoCalls.push('aes-encrypt');
      const imported = await webcrypto.subtle.importKey(
        'raw', key, { name: 'AES-CBC' }, false, ['encrypt']);
      return new Uint8Array(await webcrypto.subtle.encrypt(
        { name: 'AES-CBC', iv }, imported, plaintext));
    },
    async aesCbcDecrypt({ key, iv, ciphertext }) {
      cryptoCalls.push('aes-decrypt');
      const imported = await webcrypto.subtle.importKey(
        'raw', key, { name: 'AES-CBC' }, false, ['decrypt']);
      return new Uint8Array(await webcrypto.subtle.decrypt(
        { name: 'AES-CBC', iv }, imported, ciphertext));
    },
    async hmacSha256({ key, data }) {
      cryptoCalls.push('hmac');
      const imported = await webcrypto.subtle.importKey(
        'raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      return new Uint8Array(await webcrypto.subtle.sign('HMAC', imported, data));
    },
    async verifyHmacSha256({ key, data, signature }) {
      cryptoCalls.push('verify-hmac');
      const imported = await webcrypto.subtle.importKey(
        'raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']);
      return await webcrypto.subtle.verify('HMAC', imported, signature, data);
    },
  },
  commands: {
    register(def) {
      assert.equal(typeof def.id, 'string');
      assert.equal(typeof def.run, 'function');
      commands.set(def.id, def);
    },
    async run(id) {
      const command = commands.get(id);
      if (!command) throw new Error(`unknown command ${id}`);
      await command.run();
    },
    notify(def) {
      notifications.push(def);
    },
  },
  ui: {
    addActionBarButton(def) {
      buttons.push(def);
      return { update() {}, remove() {} };
    },
    async prompt(def) {
      prompts.push(def);
      return promptAnswers.shift();
    },
  },
  workflow: {
    async snapshot() {
      if (snapshotError) throw snapshotError;
      return structuredClone(snapshotValue);
    },
    async open(value) {
      opened.push(structuredClone(value));
    },
    registerImporter(def) {
      importers.push(def);
      return () => {};
    },
  },
  files: {
    async download(def) {
      if (downloadError) throw downloadError;
      downloads.push(def);
    },
    async pick() {
      pickerCalls += 1;
      return pickedFiles.shift();
    },
  },
};


const context = vm.createContext({
  console,
  crypto: webcrypto,
  structuredClone,
  TextDecoder,
  TextEncoder,
  Uint8Array,
});
const apiModule = new vm.SyntheticModule(
  ['comfy'],
  function initialise() { this.setExport('comfy', comfy); },
  { context, identifier: '/comfy/api/v2.js' },
);
const fernetModule = new vm.SourceTextModule(
  fs.readFileSync(fernetPath, 'utf8'),
  { context, identifier: fernetPath },
);
const mainModule = new vm.SourceTextModule(
  fs.readFileSync(mainPath, 'utf8'),
  { context, identifier: mainPath },
);


await apiModule.link(() => { throw new Error('API module imports nothing'); });
await fernetModule.link(async (specifier) => {
  if (specifier === '/comfy/api/v2.js') return apiModule;
  throw new Error(`unexpected Fernet import: ${specifier}`);
});
await mainModule.link(async (specifier) => {
  if (specifier === '/comfy/api/v2.js') return apiModule;
  if (specifier === './fernet.js') return fernetModule;
  throw new Error(`unexpected guest import: ${specifier}`);
});
await mainModule.evaluate();


// Module evaluation is a real worker-realm check: neither a parent window nor
// a DOM was necessary to register all behavior.
assert.equal('window' in context, false);
assert.equal('document' in context, false);
assert.equal('fetch' in context, false);
assert.deepEqual([...commands.keys()], [
  'ComfyWorkflowEncrypt.saveEncrypted',
  'ComfyWorkflowEncrypt.loadDecrypted',
]);
assert.equal(buttons.length, 2);
assert.equal(importers.length, 1);
assert.deepEqual(Array.from(importers[0].mimeTypes), ['text/plain']);
assert.deepEqual(Array.from(importers[0].extensions), ['txt']);
assert.equal(importers[0].maxBytes, 16 * 1024 * 1024);
assert.equal(importers[0].enabled(), true);


// Save: snapshot -> pack-side Fernet -> bounded host download -> one-time key.
await commands.get('ComfyWorkflowEncrypt.saveEncrypted').run();
assert.equal(downloads.length, 1);
assert.equal(downloads[0].name, 'encrypted_data.txt');
assert.equal(downloads[0].mimeType, 'text/plain');
assert(downloads[0].bytes instanceof Uint8Array);
assert.deepEqual(cryptoCalls, ['aes-encrypt', 'hmac']);
assert.equal(prompts.length, 1);
assert.match(prompts[0].label, /shown once/i);
const generatedKey = prompts[0].value;
assert.match(generatedKey, /^[A-Za-z0-9_-]{43}=$/);
const generatedToken = new TextDecoder().decode(downloads[0].bytes);
assert.equal(fernetModule.namespace.looksLikeFernetToken(downloads[0].bytes), true);
const decrypted = await fernetModule.namespace.decryptFernet(
  generatedToken, generatedKey);
assert.deepEqual(
  JSON.parse(new TextDecoder().decode(decrypted)),
  workflow,
);


// Explicit load uses only the approved prompt, bounded picker, and workflow
// opener. No filename path or backend request is involved.
promptAnswers.push(generatedKey);
pickedFiles.push({
  name: 'encrypted_data.txt',
  type: 'text/plain',
  bytes: downloads[0].bytes,
});
await commands.get('ComfyWorkflowEncrypt.loadDecrypted').run();
assert.equal(pickerCalls, 1);
assert.deepEqual(opened, [workflow]);
assert.deepEqual(
  cryptoCalls,
  [
    'aes-encrypt', 'hmac',
    'verify-hmac', 'aes-decrypt',
    'verify-hmac', 'aes-decrypt',
  ],
);


// Cancel is fail-closed before file selection.
promptAnswers.push(undefined);
await commands.get('ComfyWorkflowEncrypt.loadDecrypted').run();
assert.equal(pickerCalls, 1);
assert.equal(opened.length, 1);


// A mismatched key or unrelated file never opens or mutates a workflow.
const wrongKey = generatedKey.replace(/^[A-Za-z0-9_-]/, (char) =>
  char === 'A' ? 'B' : 'A');
promptAnswers.push(wrongKey);
pickedFiles.push({ name: 'encrypted_data.txt', type: 'text/plain', bytes: downloads[0].bytes });
await commands.get('ComfyWorkflowEncrypt.loadDecrypted').run();
const decryptionsBeforeRefusals = cryptoCalls.filter(
  (name) => name === 'aes-decrypt').length;
promptAnswers.push(generatedKey);
pickedFiles.push({
  name: 'notes.txt',
  type: 'text/plain',
  bytes: new TextEncoder().encode('{"not":"encrypted"}'),
});
await commands.get('ComfyWorkflowEncrypt.loadDecrypted').run();

const tamperedBytes = downloads[0].bytes.slice();
tamperedBytes[50] = tamperedBytes[50] === 65 ? 66 : 65;
assert.equal(fernetModule.namespace.looksLikeFernetToken(tamperedBytes), true);
promptAnswers.push(generatedKey);
pickedFiles.push({
  name: 'encrypted_data.txt', type: 'text/plain', bytes: tamperedBytes,
});
await commands.get('ComfyWorkflowEncrypt.loadDecrypted').run();
assert.equal(opened.length, 1);
assert.equal(notifications.filter((item) => item.severity === 'error').length, 3);
assert.equal(
  cryptoCalls.filter((name) => name === 'aes-decrypt').length,
  decryptionsBeforeRefusals,
  'authentication failures must not reach AES decryption',
);


// Snapshot/download refusal is reported and emits neither a file nor a key.
snapshotError = new Error('snapshot denied');
await commands.get('ComfyWorkflowEncrypt.saveEncrypted').run();
snapshotError = undefined;
assert.equal(downloads.length, 1);
assert.equal(prompts.length, 6);
assert.equal(notifications.at(-1).summary, 'Workflow encryption failed');

snapshotValue = { nodes: [], padding: 'x'.repeat(8 * 1024 * 1024) };
await commands.get('ComfyWorkflowEncrypt.saveEncrypted').run();
snapshotValue = workflow;
assert.equal(downloads.length, 1);
assert.equal(prompts.length, 6);
assert.equal(notifications.at(-1).summary, 'Workflow encryption failed');

downloadError = new Error('download denied');
await commands.get('ComfyWorkflowEncrypt.saveEncrypted').run();
downloadError = undefined;
assert.equal(downloads.length, 1);
assert.equal(prompts.length, 7, 'upstream shows the key before starting download');
assert.equal(notifications.at(-1).summary, 'Workflow encryption failed');


// Native file importing leaves unrelated text to ComfyUI, and opens valid
// legacy-compatible tokens only after local authentication succeeds.
const importer = importers[0];
assert.equal(
  await importer.parse(new TextEncoder().encode('ordinary text'), {
    name: 'ordinary.txt', type: 'text/plain',
  }),
  null,
);
promptAnswers.push(generatedKey);
assert.deepEqual(
  plain(await importer.parse(downloads[0].bytes, {
    name: 'encrypted_data.txt', type: 'text/plain',
  })),
  { workflow },
);
promptAnswers.push(wrongKey);
assert.equal(
  await importer.parse(downloads[0].bytes, {
    name: 'encrypted_data.txt', type: 'text/plain',
  }),
  null,
);
assert.equal(opened.length, 1, 'importer returns data; host owns workflow opening');


// Independent OpenSSL/HMAC reference -> worker Web Crypto compatibility.
if (process.env.WORKFLOW_ENCRYPT_REFERENCE_KEY) {
  const referencePlaintext = await fernetModule.namespace.decryptFernet(
    process.env.WORKFLOW_ENCRYPT_REFERENCE_TOKEN,
    process.env.WORKFLOW_ENCRYPT_REFERENCE_KEY,
  );
  assert.equal(
    new TextDecoder().decode(referencePlaintext),
    process.env.WORKFLOW_ENCRYPT_REFERENCE_PLAINTEXT,
  );
}


// The caller verifies this worker-generated vector with that reference.
console.log(`FERNET_VECTOR:${JSON.stringify({
  key: generatedKey,
  token: generatedToken,
  plaintext: JSON.stringify(workflow),
})}`);
console.log('PASS: 0 backend nodes, 1 sandboxed workflow-encrypt extension');
