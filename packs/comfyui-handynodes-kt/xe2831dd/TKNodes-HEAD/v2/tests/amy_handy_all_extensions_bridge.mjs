import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';

const v2 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runtime = '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
const entry = "import './TKAudioSpeakerTalkTime..js'; import './TKLocateSpeakersUsingSilenceBreaks.js'; import './TKVideoUserInputs.js'; import './TKPhotoUserInputs.js'; import './TKVideoUserInputsBasic.js'; import './extTKMultiImagePrompt.js'; import './extTKMultiImageSelect.js';";
const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs';
const nodes = new Map(), registrations = [], commits = [];
function makeNode(id, type, count) {
  const records = new Map(), properties = {};
  function number(name, value) {
    const listeners = new Map(), options = name.startsWith('image_') ? { values: ['', 'existing.png'] } : {};
    const handle = { name, widgetType: name.startsWith('image_') ? 'combo' : typeof value === 'string' ? 'text' : 'number',
      getValue: () => value, getOptions: () => options, setOption: (key, value) => { options[key] = value; }, isSerialized: () => true,
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
    inputs: { all: () => [] }, outputs: { all: () => [] }, getSize: () => ({ width: 500, height: 480 }),
    add: number,
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
// Actual pinned backend supplies5 tracks; both native and converted frontend
// loops inspect10 but skip absent widget pairs. No invented extra schema.
makeNode('1', 'TKAudioSpeakerTalkTime', 5); makeNode('2', 'TKLocateSpeakersUsingSilenceBreaks', 14);
for (const [id, kind] of [['3','TKVideoUserInputs'],['4','TKPhotoUserInputs'],['5','TKVideoUserInputsBasic']]) {
  const node = makeNode(id, kind, 0);
  for (const [key, value] of Object.entries({width:512,height:512,fps:24,num_seconds:2,total_frames:48,length_selector:'Use # Frames'})) node.add(key,value);
}
for (const [id, kind, count] of [['6','TKMultiImagePrompt',4],['7','TKMultiImageSelect',12]]) {
  const node = makeNode(id, kind, 0);
  for (let i=1;i<=count;i++) { node.add('image_'+i,''); if(id==='6') node.add('prompt_'+i,'initial '+i); }
}
const response = body => ({ ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) });
const comfy = {
  backend: { url: value => new URL(value, location.origin).href, fetch: async (url, init) => {
    if (url === '/object_info') return response(JSON.stringify(Object.fromEntries([...nodes.values()].map(node => [node.type,{}]))));
    if (url === '/secure-nodes/uploads') { window.__uploadStarts=(window.__uploadStarts||0)+1;window.__uploadDeclaration = JSON.parse(init.body); return response(JSON.stringify({upload_id:'handy-fixture',chunk_bytes:1024})); }
    if (url === '/secure-nodes/uploads/handy-fixture/0') { window.__uploadBytes = [...new Uint8Array(await init.body.arrayBuffer())]; return response('{}'); }
    if (url === '/secure-nodes/uploads/handy-fixture/complete') return response(JSON.stringify({path:'managed/upload.png',name:'upload.png',subfolder:'managed'}));
    throw Error('unexpected backend URL ' + url);
  } },
  graph: { nodes: () => [...nodes.values()], node: id => nodes.get(String(id)), groups: () => [] },
  workflow: { documentId: () => 'handy-workflow-proof' }, onWorkflowLoaded: () => () => {},
  ui: { showDialog(def) { const container = document.createElement('div'); document.body.append(container); def.render(container); return {close(){container.remove();}}; } },
  defs: { extend(selector, apply) {
    const rec = { selector }; apply({ onCreated(fn) { rec.created = fn; }, onRemoved(fn) { rec.removed = fn; },
      onExecuted(fn) { rec.executed = fn; }, onConfigured(fn) { rec.configured = fn; }, onDragDrop(fn) {rec.drop=fn;}, onPropertyChanged(fn){rec.property=fn;} });
    registrations.push(rec); return () => {};
  } },
};
const host = new SecureExtensionHost({ comfy, bootstrapUrl: '/guest.js', match: () => true, capabilities: ['files.upload'],
  filePicker: async options => {window.__pickOptions=options;if(window.__pickerFail)throw Error('picker refused fixture');if(window.__pickerPending)await new Promise(resolve=>{window.__releasePicker=resolve;});return new File([new Uint8Array([1,2,3])],'upload.png',{type:'image/png'});} });
window.__start = async () => {
  await host.load('/extensions/handy-proof/entry.js');
  for (const rec of registrations) for (const node of nodes.values())
    if (rec.selector === node.type) rec.created?.(node, {});
};
window.__state = () => ({
  errors: host.packErrors ?? [], sandbox: document.querySelector('iframe')?.getAttribute('sandbox'), registrations:registrations.map(rec=>rec.selector),
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
window.__pointer = (id, handler, x, y, modifiers={}) => nodes.get(id).records.get('tk_dimension_canvas').def[handler]({x,y,event:{button:0,buttons:1,...modifiers}});
window.__button = (id, name, index=0) => [...host._uiByKey].find(([key]) => key.includes(':'+id+':'+name+':'))?.[1].__shadow.querySelectorAll('button')[index].dispatchEvent(new MouseEvent('click',{bubbles:true}));
window.__textarea = (id, value) => {const el=[...host._uiByKey].find(([key]) => key.includes(':'+id+':row_1:'))[1].__shadow.querySelector('textarea');el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));};
window.__images = id => [...host._uiByKey].filter(([key]) => key.includes(':'+id+':row_')).flatMap(([,ui])=>[...ui.__shadow.querySelectorAll('img')].map(el=>({src:el.getAttribute('src'),display:el.style.display})));
window.__panels = () => [...host._uiByKey].map(([key,ui])=>({key,text:ui.__shadow.textContent}));
window.__buttonInfo = () => [...host._uiByKey].find(([key])=>key.includes(':6:row_1:'))?.[1].__shadow.querySelector('button')?.outerHTML;
window.__save = id => {const node=nodes.get(id);return {type:node.type,values:Object.fromEntries([...node.records].filter(([,r])=>!r.def).map(([name,r])=>[name,r.handle.getValue()])),properties:structuredClone(node.getProperties())};};
window.__restore = async (id, saved) => {const node=makeNode(id,saved.type,0);for(const[key,value]of Object.entries(saved.values))node.add(key,value);for(const[key,value]of Object.entries(saved.properties))node.setProperty(key,value);for(const rec of registrations)if(rec.selector===node.type){rec.created?.(node,{});rec.configured?.(node,{});}};
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
    await page.waitForFunction(() => window.__state().panels === 23);
    let state = await page.evaluate(() => window.__state());
    check(() => assert.equal(state.sandbox, 'allow-scripts'));
    for (let i = 1; i <= 5; i++) {
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
    check(() => assert.deepEqual(state.registrations.filter(selector=>typeof selector==='string'&&selector.startsWith('TK')).sort(),['TKAudioSpeakerTalkTime','TKLocateSpeakersUsingSilenceBreaks','TKVideoUserInputs','TKPhotoUserInputs','TKVideoUserInputsBasic','TKMultiImagePrompt','TKMultiImageSelect'].sort()));
    for (const id of ['3','4','5']) {
        await page.evaluate(id=>window.__pointer(id,'onPointerDown',260,160),id);
        await page.evaluate(id=>window.__pointer(id,'onPointerMove',320,120,{ctrlKey:true}),id);
        await page.waitForFunction(id=>window.__state().values.find(n=>n.id===id).values.width!==512,id);
        await page.evaluate(id=>window.__pointer(id,'onPointerUp',320,120),id);
        const saved=await page.evaluate(id=>window.__save(id),id);
        check(()=>assert.ok(Number.isFinite(saved.values.width)&&Number.isFinite(saved.values.height)));
        check(()=>assert.equal(saved.properties.valueX,saved.values.width));
        await page.evaluate(([id,saved])=>window.__restore(id+'r',saved),[id,saved]);
        await page.waitForTimeout(50);
        const restored=await page.evaluate(id=>window.__save(id+'r'),id);
        check(()=>assert.deepEqual(restored,saved));
        await page.evaluate(id=>window.__remove(id+'r'),id);
    }
    for (const id of ['6','7']) {
        await page.evaluate(()=>{window.__pickerFail=true;});
        await page.evaluate(id=>window.__button(id,id==='6'?'row_1':'row_0'),id);
        await page.waitForFunction(id=>window.__panels().find(p=>p.key.includes(':'+id+':'+(id==='6'?'row_1':'row_0')+':')).text.includes('picker refused fixture'),id);
        const refused=await page.evaluate(id=>window.__save(id),id);
        check(()=>assert.equal(refused.values.image_1,''));
        await page.evaluate(()=>{window.__pickerFail=false;});
        await page.evaluate(id=>window.__button(id,id==='6'?'row_1':'row_0'),id);
        await page.waitForFunction(id=>window.__state().values.find(n=>n.id===id).values.image_1==='managed/upload.png',id);
        // Widget commit and queued UI render are distinct observable events.
        // Retain the exact preview assertion; wait for its renderer result.
        await page.waitForFunction(id=>window.__images(id)[0]?.src?.includes('filename=upload.png&type=input&subfolder=managed'),id);
        const previews=await page.evaluate(id=>window.__images(id),id);
        check(()=>assert.ok(previews[0].src.includes('filename=upload.png&type=input&subfolder=managed')));
        check(()=>assert.equal(previews.length,id==='6'?4:12));
        if(id==='6') {
            await page.evaluate(()=>window.__textarea('6','edited\nworkflow'));
            await page.waitForFunction(()=>window.__state().values.find(n=>n.id==='6').values.prompt_1==='edited\nworkflow');
        }
        const saved=await page.evaluate(id=>window.__save(id),id);
        await page.evaluate(([id,saved])=>window.__restore(id+'r',saved),[id,saved]);
        await page.waitForFunction(id=>window.__images(id+'r')[0]?.display==='block',id);
        const restored=await page.evaluate(id=>window.__save(id+'r'),id);
        check(()=>assert.deepEqual(restored,saved));
        await page.evaluate(id=>window.__button(id,'clear_button'),id);
        await page.waitForFunction(id=>window.__state().values.find(n=>n.id===id).values.image_1==='',id);
        check(()=>assert.equal(saved.values.image_1,'managed/upload.png'));
        const beforePending=await page.evaluate(()=>window.__uploadStarts);
        await page.evaluate(()=>{window.__pickerPending=true;});
        await page.evaluate(id=>window.__button(id+'r',id==='6'?'row_1':'row_0'),id);
        await page.waitForFunction(()=>typeof window.__releasePicker==='function');
        await page.evaluate(id=>window.__remove(id+'r'),id);
        await page.evaluate(()=>{window.__pickerPending=false;window.__releasePicker();delete window.__releasePicker;});
        await page.waitForTimeout(150);
        const afterPending=await page.evaluate(()=>window.__uploadStarts);
        check(()=>assert.equal(afterPending,beforePending));
    }
    const uploads=await page.evaluate(()=>({declaration:window.__uploadDeclaration,bytes:window.__uploadBytes,pick:window.__pickOptions}));
    check(()=>assert.deepEqual(uploads.bytes,[1,2,3]));
    check(()=>assert.equal(uploads.declaration.name,'upload.png'));
    check(()=>assert.equal(uploads.pick.maxBytes,16*1024*1024));
    check(()=>assert.deepEqual(uploads.pick.mimeTypes,['image/png','image/jpeg','image/webp','image/gif','image/bmp','image/tiff']));
    for(const id of ['1','2','3','4','5','6','7'])await page.evaluate(id=>window.__remove(id),id);
    await page.waitForFunction(() => window.__state().panels === 0);
    // Removal is asynchronous across the worker boundary: observe queued replies
    // rather than scoring absence of errors in the first host task only.
    await page.waitForTimeout(150);
    check(() => assert.deepEqual(pageErrors, []));
    await page.evaluate(() => window.__destroy());
    console.log(JSON.stringify({ passed: checks, failed: 0, tier: 'actual-opaque-iframe-worker-production-renderer',
        qualification: 'All7 actual entrypoints/production guest+host+sanitizer, public host widget/canvas fixture and managed upload service response fixture; no actual backend upload storage/private-route/cloud proof.' }));
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
