import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import vm from 'node:vm';

const require = createRequire('/deps/package.json');
const { JSDOM } = require('/deps/node_modules/jsdom');
const cases = [], observations = [];
const check = (name, fn) => { fn(); cases.push(name); };
const tick = () => new Promise((done) => setImmediate(done));
const sha = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');
const savedTitle = 'Label acceptance\nSecond line <&"\'>';
const controls = [
  { id: 'title', tag: 'textarea', value: savedTitle },
  { id: 'empty-text', tag: 'textarea', value: '', text: 'old default' },
  { id: 'align', tag: 'select', value: 'center', options: ['left', 'center', 'right'] },
  { id: 'right', tag: 'select', value: 'right', options: ['left', 'center', 'right'] },
  { id: 'empty-select', tag: 'select', value: '', options: ['left', '', 'right'] },
  { id: 'missing-choice', tag: 'select', value: 'missing', options: ['left', 'right'] },
  { id: 'escaped-choice', tag: 'select', value: '<&"\'>', options: ['left', '<&"\'>'] },
  { id: 'font-size', tag: 'input', type: 'number', value: '20' },
  { id: 'plain', tag: 'input', type: 'text', value: '<&"\'>' },
];
const fixtureEntry = `
  import { comfy } from '/comfy/api/v2.js';
  const fields = new Map();
  comfy.ui.showDialog({key: 'fixture.form-values', title: 'Form values', render(container) {
    for (const spec of self.controlSpecs) {
      const input = document.createElement(spec.tag);
      input.id = spec.id;
      if (spec.type) input.type = spec.type;
      if (spec.text !== undefined) input.textContent = spec.text;
      for (const value of spec.options || []) {
        const option = document.createElement('option');
        option.value = value; option.textContent = value; input.appendChild(option);
      }
      input.value = spec.value;
      input.addEventListener('change', () => self.postMessage({t:'observed-control', id:spec.id, value:input.value}));
      fields.set(spec.id,input); container.appendChild(input);
    }
    const update = document.createElement('button'); update.id='update'; update.textContent='Update';
    update.addEventListener('click', () => {
      fields.get('title').value = 'Updated\\nTitle';
      fields.get('align').value = 'right';
      fields.get('empty-text').value = '';
    });
    container.appendChild(update);
  }});
`;

for (const variant of ['baseline', 'candidate']) {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'https://fixture.invalid/' });
  for (const name of ['document', 'DOMParser', 'Node', 'HTMLElement', 'Element']) globalThis[name] = dom.window[name];
  globalThis.requestAnimationFrame = (fn) => { queueMicrotask(() => fn(performance.now())); return 1; };
  const { SecureExtensionHost } = await import(pathToFileURL(`/src/${variant}/host-entry.mjs`));
  const { sanitizeMarkup } = await import(pathToFileURL(`/src/${variant}/ui-renderer.mjs`));
  const host = Object.create(SecureExtensionHost.prototype);
  const outgoing = [], incoming = [], observed = [], errors = [], intervals = new Set();
  const transport = [];
  let receive;
  host._dialogs = new Map(); host._dialogByKey = new Map(); host._uiByKey = new Map();
  host._host = { send(_pack, data) { incoming.push(structuredClone(data)); } };
  host.comfy = { ui: { showDialog(definition) {
    const container = document.createElement('div'); document.body.appendChild(container);
    definition.render(container);
    return { close() { definition.destroy?.(); container.remove(); } };
  } } };
  const context = vm.createContext({
    URL, Blob, TextEncoder, TextDecoder, structuredClone, performance,
    console: { error: (...args) => errors.push(args.join(' ')), warn: (...args) => errors.push(args.join(' ')), log() {} },
    setTimeout, clearTimeout, queueMicrotask,
    setInterval(...args) { const timer = setInterval(...args); intervals.add(timer); return timer; },
    clearInterval(timer) { clearInterval(timer); intervals.delete(timer); },
    location: { href: 'https://fixture.invalid/guest' }, navigator: {}, controlSpecs: structuredClone(controls),
    postMessage(data) { outgoing.push(structuredClone(data)); },
    addEventListener(type, listener) { assert.equal(type, 'message'); receive = listener; },
  });
  context.self = context;
  const guest = readFileSync(`/src/${variant}/guest.mjs`, 'utf8');
  vm.runInContext(guest, context, { filename: 'actual-guest.mjs', importModuleDynamically: async (specifier) => {
    assert.equal(specifier, 'fixture-entry');
    const module = new vm.SourceTextModule(fixtureEntry, { context });
    await module.link(async (name) => {
      assert.equal(name, '/comfy/api/v2.js');
      const api = new vm.SyntheticModule(['comfy'], function () { this.setExport('comfy', context.comfy); }, { context });
      await api.link(() => assert.fail('API module has no imports')); return api;
    });
    await module.evaluate(); return module;
  } });
  async function pump() {
    for (let count = 0; count < 100; count++) {
      while (outgoing.length) {
        const message = outgoing.shift();
        if (message.t === 'observed-control') { observed.push(message); continue; }
        if (message.t === 'dialogupdate') transport.push(message.markup);
        if (message.t === 'packerror' || message.t === 'loaderror') errors.push(message.error);
        await host._onPackMessage('fixture', message);
      }
      while (incoming.length) {
        const message = incoming.shift();
        if (message.t === 'ret' && !message.ok) errors.push(message.error);
        await receive({ data: message });
      }
      await tick();
      if (!incoming.length && !outgoing.length) return;
    }
    throw new Error('DOM bridge did not settle in100 finite steps');
  }
  try {
    let ready = false;
    const initial = receive({ data: { t: 'init', name: 'fixture', packUrl: 'fixture-entry', boot: { defs: [] } } }).then(() => { ready = true; });
    for (let i = 0; !ready && i < 100; i++) await pump();
    assert.equal(ready, true); await initial; await pump();
    const dialog = [...host._dialogs.values()][0];
    const find = (id) => dialog.ui.__shadow.querySelector('#' + id);
    check(`${variant}: real host mounts nine serialized controls in a closed shadow`, () => {
      assert.equal(dialog.ui.__shadow.mode, 'closed');
      assert.equal(dialog.ui.__shadow.querySelectorAll('textarea,select,input').length, 9);
      assert.deepEqual(errors, []);
    });
    check(`${variant}: actual guest transports title and selected value`, () => {
      const parsed = new dom.window.DOMParser().parseFromString(transport.at(-1), 'text/html');
      assert.equal(parsed.getElementById('title').getAttribute('value'), savedTitle);
      assert.equal(parsed.getElementById('align').getAttribute('value'), 'center');
    });
    observations.push({ variant, title: find('title').value, alignment: find('align').value, markup: transport.at(-1) });
    if (variant === 'baseline') {
      check('baseline: title preservation assertion fails on actual DOM', () => {
        assert.throws(() => assert.equal(find('title').value, savedTitle), assert.AssertionError);
        assert.equal(find('title').value, '');
      });
      check('baseline: alignment preservation assertion fails on actual DOM', () => {
        assert.throws(() => assert.equal(find('align').value, 'center'), assert.AssertionError);
        assert.equal(find('align').value, 'left');
      });
    } else {
      for (const spec of controls) check(`candidate: ${spec.id} has native assigned value`, () => {
        const expected = spec.id === 'missing-choice' ? '' : spec.value;
        assert.equal(find(spec.id).value, expected);
        if (spec.id === 'missing-choice') assert.equal(find(spec.id).selectedIndex, -1);
        if (spec.id === 'align') assert.equal(find(spec.id).selectedIndex, 1);
        if (spec.id === 'right') assert.equal(find(spec.id).selectedIndex, 2);
        if (spec.id === 'empty-select') assert.equal(find(spec.id).selectedIndex, 1);
      });
      for (const [id, value] of [['title', 'Edited\nTitle <&>'], ['align', 'right'], ['title', ''], ['align', '']]) {
        const field = find(id); field.value = value;
        field.dispatchEvent(new dom.window.Event('change', { bubbles: true })); await pump();
        check(`candidate: ${id} change ${JSON.stringify(value)} crosses host-to-guest and back`, () => {
          assert.equal(observed.at(-1).id, id); assert.equal(observed.at(-1).value, value);
          assert.equal(find(id).value, value);
        });
      }
      find('update').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })); await pump();
      check('candidate: worker refresh applies textarea and select values after child reconstruction', () => {
        assert.equal(find('title').value, 'Updated\nTitle');
        assert.equal(find('align').value, 'right');
        assert.equal(find('empty-text').value, '');
      });
    }
    const direct = sanitizeMarkup('<textarea id="native">Native\ntext</textarea><select id="native-select"><option value="a">A</option><option value="b" selected>B</option></select>');
    check(`${variant}: ordinary markup without value attribute keeps native defaults`, () => {
      assert.equal(direct.querySelector('#native').value, 'Native\ntext');
      assert.equal(direct.querySelector('#native-select').value, 'b');
    });
    const unsafe = sanitizeMarkup('<script>globalThis.pwned=1</script><iframe src="https://bad.invalid"></iframe><textarea id="safe" onfocus="bad()" value="&lt;script&gt;bad()&lt;/script&gt;"></textarea><select id="safe-select" value="b" onchange="bad()"><option value="a">A</option><option value="b" onclick="bad()">B</option></select><img src="javascript:bad()" onerror="bad()">');
    check(`${variant}: scripts, disallowed subtree, inline handlers and unsafe URLs remain rejected`, () => {
      assert.equal(unsafe.querySelector('script,iframe'), null);
      assert.equal(unsafe.querySelector('[onfocus],[onchange],[onclick],[onerror]'), null);
      assert.equal(unsafe.querySelector('img').hasAttribute('src'), false);
      assert.equal(dom.window.pwned, undefined);
      if (variant === 'candidate') assert.equal(unsafe.querySelector('#safe').value, '<script>bad()</script>');
    });
    check(`${variant}: no actual host/guest bridge errors`, () => assert.deepEqual(errors, []));
  } finally {
    for (const record of [...host._dialogs.values()]) record.handle?.close();
    for (const timer of intervals) clearInterval(timer);
    dom.window.close();
  }
}
const sourceHashes = {};
for (const v of ['baseline', 'candidate']) for (const file of ['host-entry.mjs', 'guest.mjs', 'ui-renderer.mjs', 'sandbox-host.mjs']) sourceHashes[`${v}/${file}`] = sha(`/src/${v}/${file}`);
sourceHashes['dom-regression.mjs'] = sha('/src/dom-regression.mjs');
const receipt = { status: 'PASS', checks: cases.length, cases, expected_old_source_failures: 2, source_sha256: sourceHashes, jsdom_version: require('/deps/node_modules/jsdom/package.json').version, evidence: observations, scope: 'Unmodified production guest bootstrap/serialization, host dialog/dispatch, mountPackUI and sanitizeMarkup execute against real jsdom DOMParser/elements/events/closed shadow roots. Only the generic textarea/select value restoration differs.', not_proven: ['Real Chromium keyboard/mouse editing, raster and graph save/reload remain DANNY browser acceptance gates.'] };
writeFileSync('/out/DOM_REGRESSION.json', JSON.stringify(receipt, null, 2) + '\n');
console.log(JSON.stringify({ status: receipt.status, checks: receipt.checks, expected_old_source_failures: 2, jsdom_version: receipt.jsdom_version }));
