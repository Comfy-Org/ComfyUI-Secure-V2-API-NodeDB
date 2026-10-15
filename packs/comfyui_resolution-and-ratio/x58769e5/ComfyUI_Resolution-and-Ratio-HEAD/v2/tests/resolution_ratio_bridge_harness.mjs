// Production SecureExtensionHost/guest/opaque iframe/Remote-DOM renderer.
// The host node/widget collection is a contract double, not ComfyUI LiteGraph.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { chromium } from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const V2 = path.dirname(HERE);
const SRC = '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
// Differential oracle runs the pinned original extension, not a hand-written
// copy of its math. The production bridge below remains the system under test.
let legacyExtension;
vm.runInNewContext(fs.readFileSync(path.join(V2,'../web/resolution_and_ratio.js'),'utf8').replace(/^import[^\n]*\n/,''),{
 app:{registerExtension:e=>legacyExtension=e},setTimeout,Math,Number,String,Set,
});
const originalDefaults={width:1152,height:1536,W_ratio:3,H_ratio:4,scale_percent:100,reset:false,swap:false,preset:'Custom',custom_presets:'512x512\n512x768\n1152x1536'};
function legacy(values={}) {
 class Original {constructor(){this.widgets=Object.entries({...originalDefaults,...values}).map(([name,value])=>({name,value,options:{}}));}}
 legacyExtension.beforeRegisterNodeDef(Original,{name:'ResolutionAndRatio'},{});
 const n=new Original();n.onNodeCreated();n.__resolutionAndRatioSync();
 return {state:()=>Object.fromEntries(n.widgets.map(w=>[w.name,w.value])),
  act(name,value,type='change'){const w=n.widgets.find(w=>w.name===name);w.value=value;w.callback?.(value,null,n,null,{type});},
  options:()=>Array.from(n.widgets.find(w=>w.name==='preset').options.values)};
}
const PAGE = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs';
const hooks = [], nodes = new Map();
const defaults = {width:1152,height:1536,W_ratio:3,H_ratio:4,scale_percent:100,reset:false,swap:false,preset:'Custom',custom_presets:'512x512\\n512x768\\n1152x1536'};
class Widget {
 constructor(name,value) {this.name=name;this.value=value;this.options={};this.listeners=new Map();this.widgetType=typeof value==='string'?'text':'number';this.serialized=true;}
 getValue(){return this.value;} getOptions(){return this.options;}
 setOption(k,v){this.options[k]=v;} setHidden(v){this.hidden=v;} isHidden(){return !!this.hidden;}
 isSerialized(){return this.serialized;} on(e,f){let s=this.listeners.get(e);if(!s)this.listeners.set(e,s=new Set());s.add(f);return()=>s.delete(f);}
 setValue(v){if(Object.is(v,this.value))return;const old=this.value;this.value=v;for(const f of this.listeners.get('change')||[])f(v,old);}
 user(v){this.setValue(v);for(const f of this.listeners.get('activate')||[])f(v);}
}
function node(id, values={}) {
 const widgets=new Map(Object.entries({...defaults,...values}).map(([k,v])=>[k,new Widget(k,v)]));
 const n={id,type:'ResolutionAndRatio',graphId:'test',snapshot:()=>({id,type:'ResolutionAndRatio',graphId:'test',title:'Ratio',size:{width:300,height:300},position:{x:0,y:0},properties:{}}),setSizeConstraints(){},widgets:{
  get:k=>widgets.get(k),all:()=>[...widgets.values()],names:()=>[...widgets.keys()],
  remove(k){const w=widgets.get(k);w?.container?.remove();return widgets.delete(k);},
  mount(def){const old=widgets.get(def.name);old?.container?.remove();const w=new Widget(def.name,undefined);w.serialized=false;w.container=document.createElement('section');w.container.dataset.node=id;w.container.style.cssText='width:300px;min-height:90px;margin:20px';document.body.append(w.container);widgets.set(def.name,w);def.render(w.container);return w;},
 }};nodes.set(id,n);return n;
}
const comfy={
 backend:{url:p=>new URL(p,location.origin).href,assetUrl:p=>new URL(p,location.origin).href,fetch:async()=>({ok:true,json:async()=>({}),text:async()=>'{}'})},
 graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(id)},workflow:{documentId:()=> 'ratio-workflow'},
 onWorkflowLoaded:()=>()=>{},defs:{extend(filter,setup){const h={filter};const b={};for(const k of ['onCreated','onConfigured','onRemoved'])b[k]=fn=>h[k]=fn;setup(b);hooks.push(h);}},
};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/src/guest.mjs',capabilities:[]});
window.__host=host;
window.__ready=()=>hooks.some(h=>h.filter==='ResolutionAndRatio');
window.__start=()=>host.load('/extensions/ratio/resolution_and_ratio.js');
window.__create=(id,values,graphId='test')=>{const n=node(id,values);n.graphId=graphId;for(const h of hooks)if(typeof h.filter==='function'||h.filter===n.type)h.onCreated?.(n);};
window.__configure=(id,values)=>{const n=nodes.get(id);for(const[k,v]of Object.entries(values))n.widgets.get(k).setValue(v);for(const h of hooks)if(h.filter===n.type)h.onConfigured?.(n);};
window.__native=(id,name,value)=>nodes.get(id).widgets.get(name).user(value);
window.__state=id=>Object.fromEntries(nodes.get(id).widgets.all().filter(w=>w.serialized).map(w=>[w.name,w.value]));
window.__options=id=>nodes.get(id).widgets.get('preset').options.values;
window.__remove=id=>{const n=nodes.get(id);for(const h of hooks)if(h.filter===n.type)h.onRemoved?.(n);setTimeout(()=>{nodes.delete(id);n.widgets.get('resolution_dimensions')?.container?.remove();},50);};
window.__element=(id,label)=>{const ui=[...host._uiByKey.entries()].find(([key])=>key.includes(':'+id+':'))?.[1];if(!ui)return;const tag=label.startsWith('Drag ')?'button':'input';const index=label.endsWith('height')?1:0;return ui.__shadow.querySelectorAll(tag)[index];};
window.__rect=(id,label)=>{const el=window.__element(id,label);const r=el?.getBoundingClientRect();return r?{x:r.x+r.width/2,y:r.y+r.height/2}:null;};
window.__value=(id,label)=>window.__element(id,label)?.value;
window.__listeners=id=>Object.fromEntries(nodes.get(id).widgets.all().map(w=>[w.name,[...w.listeners.values()].reduce((sum,s)=>sum+s.size,0)]));
window.__retiredState=id=>{const n=nodes.get(id);window.__retired=()=>Object.fromEntries(n.widgets.all().filter(w=>w.serialized).map(w=>[w.name,w.value]));window.__retiredListeners=()=>n.widgets.all().reduce((sum,w)=>sum+[...w.listeners.values()].reduce((a,s)=>a+s.size,0),0);};
</script>`;

const server = http.createServer((req,res) => {
  const url = new URL(req.url, 'http://localhost');
  let body, type='text/javascript';
  if(url.pathname === '/') {body=PAGE;type='text/html';}
  else if(url.pathname === '/extensions/ratio/resolution_and_ratio.js') body=fs.readFileSync(path.join(V2,'web/resolution_and_ratio.js'));
  else if(url.pathname === '/comfy/api/v2.js') body='export const comfy=globalThis.comfy;';
  else if(url.pathname.startsWith('/src/') && !url.pathname.includes('..')) {
    const target=path.join(SRC,url.pathname.slice(5));
    if(fs.existsSync(target))body=fs.readFileSync(target);
  }
  if(body===undefined){res.writeHead(404);res.end();return;}
  res.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});res.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
const errors=[];
page.on('pageerror',error=>errors.push(String(error)));
page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
const state=id=>page.evaluate(id=>window.__state(id),id);
const act=async(name,value,id='a')=>{
 await page.evaluate(({id,name,value})=>window.__native(id,name,value),{id,name,value});
 await page.waitForTimeout(150);
};
try {
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.evaluate(()=>window.__start());
 await page.waitForFunction(()=>window.__ready(),null,{timeout:10000});
 await page.evaluate(()=>window.__create('a'));
 await page.waitForFunction(()=>window.__rect('a','Drag width'),null,{timeout:10000});
 assert.equal(await page.evaluate(()=>document.querySelector('iframe').getAttribute('sandbox')),'allow-scripts');
 await act('custom_presets','512 * 768\n0512×0768\n256x768\ninvalid\n1024x1024');
 assert.deepEqual(await page.evaluate(()=>window.__options('a')),['Custom','512x768','1024x1024']);
 await act('preset','512x768');assert.equal((await state('a')).width,512);
 await act('scale_percent',150);assert.equal((await state('a')).width,768);
 await act('scale_percent',200);assert.equal((await state('a')).width,1024);
 await act('reset',true);await page.waitForTimeout(150);assert.equal((await state('a')).reset,false);
 assert.equal((await state('a')).width,512);
 // A REAL mouse gesture held across renderer settling intervals. Dispatching
 // synthetic pointerup to a freshly replaced button would hide capture loss.
 const p=await page.evaluate(()=>window.__rect('a','Drag width'));
 await page.evaluate(()=>window.__captured=window.__element('a','Drag width'));
 await page.mouse.move(p.x,p.y);await page.mouse.down();
 await page.mouse.move(p.x+13,p.y);await page.waitForTimeout(350);
 assert.equal((await state('a')).width,525,'live drag must remain unsnapped');
 await page.mouse.move(p.x+21,p.y);await page.waitForTimeout(350);
 assert.equal((await state('a')).width,533,'continuous drag must retain captured element');
 console.log('MEASURED capture lifecycle:', await page.evaluate(()=>({originalConnected:window.__captured.isConnected,sameElement:window.__captured===window.__element('a','Drag width'),captured:window.__captured.hasPointerCapture(1),width:window.__state('a').width})));
 await page.mouse.move(p.x+350,p.y+100);await page.waitForTimeout(150);
 await page.mouse.up();await page.waitForTimeout(250);
 assert.equal((await state('a')).width,864,'release outside widget must snap');
 assert.equal((await state('a')).scale_percent,100);
 assert.equal((await state('a')).preset,'Custom');
 // Cancellation travels through the actual renderer/worker event channel. It
 // is an explicit PointerEvent (not used to substitute for the real release
 // test above), and must finalize bounded/snap state and end the gesture.
 const cancelPoint=await page.evaluate(()=>window.__rect('a','Drag height'));
 await page.mouse.move(cancelPoint.x,cancelPoint.y);await page.mouse.down();
 await page.mouse.move(cancelPoint.x+13,cancelPoint.y);await page.waitForTimeout(350);
 assert.equal((await state('a')).height,525);
 await page.evaluate(()=>window.__element('a','Drag height').dispatchEvent(new PointerEvent('pointercancel',{pointerId:1,bubbles:true,clientX:0,clientY:0})));
 await page.waitForTimeout(180);assert.equal((await state('a')).height,512);
 await page.mouse.move(cancelPoint.x+70,cancelPoint.y);await page.mouse.up();await page.waitForTimeout(200);
 assert.equal((await state('a')).height,512,'cancelled gesture cannot resume');

 const reference=legacy();
 await page.evaluate(()=>window.__create('d'));
 await page.waitForFunction(()=>window.__rect('d','width'));
 const compare=async()=>assert.deepEqual(await state('d'),reference.state());
 await compare();
 for(const [name,value] of [
  ['custom_presets',' 0512 * 0768\n512×768\n511x900\n0x512\ninvalid\n8192x1024\n1024x1024'],
  ['preset','512x768'],['scale_percent',150],['scale_percent',200],['swap',true],
  ['scale_percent',100],['W_ratio',3],['H_ratio',4],['preset','8192x1024'],['reset',true],
 ]) {
  reference.act(name,value);await act(name,value,'d');await page.waitForTimeout(100);
  await compare();
  assert.deepEqual(await page.evaluate(()=>window.__options('d')),reference.options());
 }
 // Input editing preserves live values then commits on change, with no
 // feedback-loop callback; compare against original move/release callbacks.
 await page.evaluate(()=>{const el=window.__element('d','width');el.focus();el.value='533';el.dispatchEvent(new Event('input',{bubbles:true}));});
 reference.act('width',533,'pointermove');await page.waitForTimeout(350);await compare();
 assert.equal(await page.evaluate(()=>window.__element('d','width').getRootNode().activeElement===window.__element('d','width')),true);
 await page.evaluate(()=>window.__element('d','width').dispatchEvent(new Event('change',{bubbles:true})));
 reference.act('width',533,'pointerup');await page.waitForTimeout(250);await compare();
 for(const value of ['8','32','48','4097','-10']) {
  await page.evaluate(value=>{const el=window.__element('d','height');el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));},value);
  reference.act('height',Number(value));await page.waitForTimeout(160);await compare();
 }
 // Invalid content is data, never markup. Oversized/corrupt authored text is
 // retained for workflow serialization but excluded from bounded parsing.
 await act('custom_presets','<img src=x onerror="throw 1">\n1024x1024','d');
 assert.deepEqual(await page.evaluate(()=>window.__options('d')),['Custom','1024x1024']);
 for(const text of ['x'.repeat(65537),'🙂'.repeat(16385),'\n'.repeat(1024),null]) {
  await act('custom_presets',text,'d');
  assert.equal((await state('d')).custom_presets,text);
  assert.deepEqual(await page.evaluate(()=>window.__options('d')),['Custom']);
  assert.ok(await page.evaluate(()=>[...window.__host._uiByKey.values()].some(ui=>ui.__shadow.textContent.includes('64 KiB'))));
 }
 await act('custom_presets','1024x2048\n768x1024','d');await act('preset','1024x2048','d');
 await act('scale_percent',150,'d');const saved=await state('d');
 assert.equal(saved.width,1536);assert.equal(saved.custom_presets,'1024x2048\n768x1024');
 assert.equal(Object.hasOwn(saved,'resolution_dimensions'),false,'mounted controls are not prompt/workflow state');
 const unaffected=await state('a');
 await page.evaluate(saved=>window.__create('e',saved,'other-graph'),saved);
 await page.waitForFunction(()=>window.__rect('e','width'));
 const restored=legacy(saved);assert.deepEqual(await state('e'),restored.state());
 await act('scale_percent',200,'e');restored.act('scale_percent',200);
 assert.deepEqual(await state('e'),restored.state());assert.deepEqual(await state('a'),unaffected);
 // Reconfiguration must retire subscriptions/timers; it must not accumulate
 // multiple listeners or serialize mounted nodes.
 await page.evaluate(saved=>window.__configure('e',saved),saved);await page.waitForTimeout(200);
 assert.deepEqual(await page.evaluate(()=>window.__listeners('e')),await page.evaluate(()=>window.__listeners('d')));
 // Remove while reset's 200ms timer and initial preset timer are pending.
 await page.evaluate(()=>{window.__create('gone');window.__native('gone','reset',true);window.__retiredState('gone');window.__remove('gone');});
 await page.waitForTimeout(500);
 assert.equal(await page.evaluate(()=>window.__retired().reset),true,'removed node timer must not write');
 assert.equal(await page.evaluate(()=>window.__retiredListeners()),0,'removed node has no widget subscriptions');
 assert.equal(await page.evaluate(()=>[...window.__host._uiByKey.entries()].find(([key])=>key.includes(':gone:'))?.[1].__shadow.querySelectorAll('input,button,[data-on]').length),0,'removed guest UI is empty and has no controls/listeners');
 // A new page/new opaque guest reconstructs all state exclusively from saved
 // original schema values, without reusing pack module globals/DOM/files.
 await page.reload();await page.evaluate(()=>window.__start());await page.waitForFunction(()=>window.__ready());
 await page.evaluate(saved=>window.__create('fresh',saved),saved);await page.waitForFunction(()=>window.__rect('fresh','width'));
 assert.deepEqual(await state('fresh'),legacy(saved).state());
 assert.deepEqual(await page.evaluate(()=>window.__options('fresh')),['Custom','1024x2048','768x1024']);
 await act('preset','768x1024','fresh');assert.equal((await state('fresh')).width,768);
 assert.deepEqual(errors,[]);
 console.log('PASS: production opaque-worker bridge; pinned-JS differential callbacks/parsing/ratio/noncompounding scale/swap/reset; real captured outside drag/release; cancellation; bounded/adversarial text; focus; workflow serialization/fresh guest reload/instance isolation; remount and pending-removal cleanup');
} catch(error) { console.error('Observed bridge errors:',errors);console.error(await page.evaluate(()=>({errors:window.__host.packErrors,ui:[...window.__host._uiByKey.entries()].map(([key,ui])=>[key,ui.__shadow.innerHTML]),body:document.body.innerHTML.slice(-1000)})));throw error; }
finally {await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
