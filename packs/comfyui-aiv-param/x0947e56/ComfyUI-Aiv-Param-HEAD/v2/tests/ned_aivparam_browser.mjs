import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { chromium, FE } from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const pack=readFileSync(path.resolve(here,'../js/check.js'),'utf8');
const original=readFileSync(path.resolve(here,'../../js/check.js'),'utf8');
const vectors=['','{}','[ {"title":"中文", "nested":{"values":[1,true]}} ]','\\{already\\}','\\\\{double\\\\}','malformed{ not JSON }','<script>alert(1)</script>{}','😀{é}','\r\n{}\n','{'.repeat(32768),'{'.repeat(65536)];
let legacy;
vm.runInNewContext(original.replace(/^import\s+\{app\}.*$/m,''),{app:{registerExtension(value){legacy=value;}}});
assert.equal(legacy.name,'AivApp');
function old(value){
 const element={value};const widget={name:'text_param',element};
 legacy.nodeCreated({comfyClass:'AivParam',widgets:[widget]},{});
 return {widget,element};
}
for(const text of vectors){
 const x=old('');x.widget.value=text;
 assert.equal(x.element.value,text.replace(/\\([{}])/g,'$1'));
 assert.equal(x.widget.value,x.element.value.replace(/{/g,'\\{').replace(/}/g,'\\}'));
 x.element.value=text;
 assert.equal(x.widget.value,text.replace(/{/g,'\\{').replace(/}/g,'\\}'));
}
const root='/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
const bundle=path.join(FE,'temp/many-oct7-widget-serialization/serialization.mjs');
assert.ok(existsSync(bundle),'tested canonical serialization leaf must already exist; no rebuild/install here');
const pageSource=`<!doctype html><meta charset="utf-8"><body><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
import {registerAsyncWidgetSerializer,preparedWidgetValue,serializeWidgetAsync,serializeWorkflow} from '/serialization.mjs';
const registrations=[];const nodes=new Map();const workflowFeed=[];let generation=0;
function makeNode(id,value,note='untouched {note}') {
 const items=new Map();
 function widget(name,value) {
  const listeners=new Map();const raw={name,value,options:{}};
  raw.serializeWorkflowValue=()=>preparedWidgetValue(raw,()=>raw.value);
  const handle={name,widgetType:'STRING',getValue:()=>raw.value,getOptions:()=>({multiline:true}),isSerialized:()=>true,
   setValue(value){const previous=raw.value;raw.value=value;if(previous!==value)for(const listener of listeners.get('change')||[])listener(value,previous);},
   on(event,listener){let set=listeners.get(event);if(!set)listeners.set(event,set=new Set());set.add(listener);return()=>set.delete(listener);},raw};
  items.set(name,handle);return handle;
 }
 widget('text_param',value);widget('text_note',note);
 const node={id,type:'AivParam',graphId:'aiv-graph-'+generation,widgets:{all:()=>[...items.values()],get:name=>items.get(name)},inputs:{all:()=>[]},outputs:{all:()=>[]},snapshot:()=>({id,type:'AivParam',graphId:'aiv-graph-'+generation,title:'Renamed metadata'})};
 nodes.set(id,node);return node;
}
let a=makeNode('1','\\\\{restored\\\\}'),b=makeNode('2','{"b":2}');
function graph(){return {nodes:[...nodes.values()].map(node=>({widgets:node.widgets.all().map(w=>w.raw),serialize_widgets:true,isSubgraphNode:()=>false})),serialize:()=>({nodes:[...nodes.values()].map(node=>({id:node.id,widgets_values:node.widgets.all().map(w=>w.raw.serializeWorkflowValue())}))})};}
const comfy={backend:{url:v=>new URL(v,location.origin).href,fetch:async()=>new Response('{}')},graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[]},workflow:{documentId:()=> 'aiv-'+generation},onWorkflowLoaded(fn){workflowFeed.push(fn);return()=>{};},defs:{extend(selector,apply){if(selector!=='AivParam'&&typeof selector!=='function')throw Error('foreign type');const record={};apply({onCreated(fn){record.created=fn;},onConfigured(fn){record.configured=fn;},onRemoved(fn){record.removed=fn;}});registrations.push(record);return()=>{};}}};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',capabilities:[],subscribeWidgetSerialization(widget,project){const node=[...nodes.values()].find(n=>n.widgets.all().includes(widget));return registerAsyncWidgetSerializer(widget.raw,project,()=>nodes.get(node.id)===node);}});
const hooks=(type,node)=>registrations.forEach(r=>r[type]?.(node,{}));
window.__start=async()=>{await host.load('/extensions/aiv/pack.js');hooks('created',a);hooks('created',b);};
window.__state=()=>({a:a.widgets.get('text_param').getValue(),b:b.widgets.get('text_param').getValue(),notes:[a,b].map(n=>n.widgets.get('text_note').getValue()),subscriptions:host._subs?.size??0,sandbox:document.querySelector('iframe')?.getAttribute('sandbox'),errors:host.packErrors||[]});
window.__edit=value=>a.widgets.get('text_param').setValue(value);
window.__save=async()=>({saved:await serializeWorkflow(graph()),embedded:await serializeWorkflow(graph(),{context:'embedded'}),prompt:await serializeWidgetAsync(a.widgets.get('text_param').raw,'prompt',a.widgets.get('text_param').getValue()),state:window.__state()});
window.__configure=()=>{hooks('configured',a);hooks('configured',b);};
window.__restore=async()=>{const saved=await serializeWorkflow(graph());generation++;nodes.clear();a=makeNode('1',saved.nodes[0].widgets_values[0],saved.nodes[0].widgets_values[1]);b=makeNode('2',saved.nodes[1].widgets_values[0],saved.nodes[1].widgets_values[1]);workflowFeed.forEach(fn=>fn());hooks('configured',a);hooks('configured',b);};
window.__remove=()=>{hooks('removed',a);nodes.delete('1');};
window.__removeDuringSave=async()=>{const widget=a.widgets.get('text_param');const pending=serializeWidgetAsync(widget.raw,'prompt',widget.getValue());window.__remove();try{await pending;return 'unexpected success';}catch(error){return String(error);}};
window.__remaining=async()=>serializeWidgetAsync(b.widgets.get('text_param').raw,'prompt',b.widgets.get('text_param').getValue());
window.__destroy=()=>{host.destroy();return {subscriptions:host._subs.size,iframe:!!document.querySelector('iframe')};};
</script></body>`;
const server=http.createServer((request,response)=>{
 const url=new URL(request.url,'http://localhost').pathname;let body,type='text/javascript';
 if(url==='/'){body=pageSource;type='text/html';}
 else if(url==='/guest.js')body=readFileSync(path.join(root,'guest.mjs'));
 else if(url==='/serialization.mjs')body=readFileSync(bundle);
 else if(url==='/comfy/api/v2.js')body='export const comfy = globalThis.comfy';
 else if(url==='/extensions/aiv/pack.js')body=pack;
 else if(url.startsWith('/src/')){const file=path.resolve(root,url.slice(5));if(file.startsWith(root+path.sep)&&existsSync(file))body=readFileSync(file);}
 if(body===undefined){response.writeHead(404);response.end();return;}
 response.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});response.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>{errors.push(String(e));console.error('browser page error:',String(e));});
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.waitForFunction(()=>typeof window.__start==='function');await page.evaluate(()=>window.__start());
 // Two widget projections plus the pack's workflow-lifecycle subscription.
 try{await page.waitForFunction(()=>window.__state().subscriptions===3&&window.__state().a==='{restored}');}
 catch(error){console.error('live bridge state:',JSON.stringify(await page.evaluate(()=>window.__state())));throw error;}
 assert.equal((await page.evaluate(()=>window.__state())).sandbox,'allow-scripts');
 for(const text of vectors){
  await page.evaluate(value=>window.__edit(value),text);
  const result=await page.evaluate(()=>window.__save());const expected=old(text).widget.value;
  assert.equal(result.prompt,expected);assert.equal(result.saved.nodes[0].widgets_values[0],expected);assert.equal(result.embedded.nodes[0].widgets_values[0],expected);
  assert.equal(result.state.a,text);assert.equal(result.state.b,'{"b":2}');assert.deepEqual(result.state.notes,['untouched {note}','untouched {note}']);
  assert.equal((await page.evaluate(()=>window.__save())).prompt,expected);
 }
 // Max admitted all-brace raw value projects to128KiB and reloads without reset.
 await page.evaluate(()=>window.__restore());
 try{await page.waitForFunction(()=>window.__state().subscriptions===3&&window.__state().a.length===65536&&!window.__state().a.includes('\\'));}
 catch(error){console.error('reload bridge state:',JSON.stringify(await page.evaluate(()=>{const s=window.__state();return {...s,a:s.a?.slice(0,12),aLength:s.a?.length};})));throw error;}
 assert.equal((await page.evaluate(()=>window.__save())).prompt,'\\{'.repeat(65536));
 await page.evaluate(()=>window.__configure());await page.waitForFunction(()=>window.__state().subscriptions===3);
 for(const bad of ['x'.repeat(65537),'😀'.repeat(16385),null]){
  await page.evaluate(value=>window.__edit(value),bad);
  const result=await page.evaluate(async()=>{try{await window.__save();return 'unexpected success';}catch(e){return String(e);}});
  assert.match(result,/AivParam text/);
 }
 await page.evaluate(()=>window.__edit('{recovery}'));assert.equal((await page.evaluate(()=>window.__save())).prompt,'\\{recovery\\}');
 assert.match(await page.evaluate(()=>window.__removeDuringSave()),/changed during serialization|subscription was removed/);
 await page.waitForFunction(()=>window.__state().subscriptions===2);
 assert.equal(await page.evaluate(()=>window.__remaining()),'\\{"b":2\\}');
 assert.deepEqual((await page.evaluate(()=>window.__state())).errors,[]);assert.deepEqual(errors,[]);
 assert.deepEqual(await page.evaluate(()=>window.__destroy()),{subscriptions:0,iframe:false});
 console.log('PASS exact pinned AivApp setter/getter controls; actual opaque iframe/worker serialization in workflow/prompt/embedded; Unicode/invalidJSON/adversarial/braces,64KiB raw→128KiB restore, no compounding/no widget mutation, two-node isolation, rebind/removal during pending save/destroy and error recovery');
 console.log('QUALIFIED production bridge + tested canonical serialization leaf and host widget/graph fixtures; not full application/API export/Cloud or arbitrary cross-pack programmatic setter certification');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
