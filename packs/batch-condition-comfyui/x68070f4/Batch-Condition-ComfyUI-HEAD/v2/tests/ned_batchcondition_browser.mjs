import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {chromium} from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const pack=readFileSync(path.resolve(here,'../js/app.js'),'utf8');
const original=readFileSync(path.resolve(here,'../../js/app.js'),'utf8');
let legacy;
vm.runInNewContext(original.replace(/^import.*$/m,''),{app:{registerExtension(value){legacy=value;}}});
assert.equal(legacy.name,'Comfy.conditioning_batch.Batch String');
const type={prototype:{}};await legacy.beforeRegisterNodeDef(type,{name:'Batch String'});
function oldNode(){const node={inputs:[],addInput(name,type,options){this.inputs.push({name,type,options});},removeInput(i){this.inputs.splice(i,1);}};type.prototype.onNodeCreated.call(node);const menu=[];node.getExtraMenuOptions(null,menu);return{node,menu};}
const old=oldNode();assert.deepEqual(old.menu.map(x=>x.content),['add input','remove input']);
old.menu[1].callback();assert.equal(old.node.inputs.length,0);
for(let i=0;i<64;i++)old.menu[0].callback();assert.equal(old.node.inputs[63].name,'text64');
for(let i=0;i<64;i++)old.menu[1].callback();assert.equal(old.node.inputs.length,0);
const root='/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
const pageSource=`<!doctype html><meta charset="utf-8"><body><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
const menus=[],nodes=new Map(),operations=[];let nextSlot=0;
function make(id,saved=[]) {
 const list=saved.map(s=>({...s}));
 const inputs={all:()=>list.map((s,index)=>({...s,index,link:()=>s.link?{id:s.link}:undefined,snapshot:()=>({...s,index})})),add(name,type){operations.push(['add',id,name]);list.push({id:'slot-'+(++nextSlot),name,type,link:null});},remove(ref){operations.push(['remove',id,ref]);const i=list.findIndex(s=>s.id===ref);if(i>=0)list.splice(i,1);},get:ref=>list.find(s=>s.id===ref)};
 const node={id,type:'Batch String',graphId:'batch-condition-graph',inputs,outputs:{all:()=>[]},widgets:{all:()=>[]},snapshot:()=>({id,type:'Batch String',graphId:'batch-condition-graph'}),data:list};nodes.set(id,node);return node;
}
let a=make('1'),b=make('2');
const comfy={backend:{url:v=>new URL(v,location.origin).href,fetch:async()=>new Response('{}')},workflow:{documentId:()=> 'batch-condition-document'},onWorkflowLoaded(){return()=>{};},graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[],selection:()=>[]},defs:{extend(selector,apply){if(selector!=='Batch String'&&typeof selector!=='function')throw Error('foreign type');apply({onCreated(){},onRemoved(){},addMenuItem(item){menus.push(item);}});return()=>{};}}};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',capabilities:[]});
window.__start=async()=>host.load('/extensions/batch/pack.js');
window.__state=()=>({a:a.data,b:b.data,menus:menus.map(m=>m.label),sandbox:document.querySelector('iframe')?.getAttribute('sandbox'),errors:host.packErrors||[],operations});
window.__menu=(index,node='1')=>menus[index].run(nodes.get(node));
window.__link=()=>{a.data[0].link='kept-link-101';a.data[1].link='dropped-link-102';};
window.__restore=()=>{const saved=JSON.parse(JSON.stringify(a.data));a=make('1',saved);};
window.__remove=()=>nodes.delete('1');
window.__destroy=()=>{host.destroy();return {subs:host._subs?.size??0,iframe:!!document.querySelector('iframe')};};
</script></body>`;
const server=http.createServer((request,response)=>{
 const url=new URL(request.url,'http://localhost').pathname;let body,type='text/javascript';
 if(url==='/'){body=pageSource;type='text/html';}
 else if(url==='/guest.js')body=readFileSync(path.join(root,'guest.mjs'));
 else if(url==='/comfy/api/v2.js')body='export const comfy = globalThis.comfy';
 else if(url==='/extensions/batch/pack.js')body=pack;
 else if(url.startsWith('/src/')){const file=path.resolve(root,url.slice(5));if(file.startsWith(root+path.sep)&&existsSync(file))body=readFileSync(file);}
 if(body===undefined){response.writeHead(404);response.end();return;}
 response.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});response.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true});let page;
try {
 page=await browser.newPage();page.setDefaultTimeout(5000);const errors=[];page.on('pageerror',e=>{errors.push(String(e));console.error('page error',String(e));});
 await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>typeof window.__start==='function');await page.evaluate(()=>window.__start());
 try{await page.waitForFunction(()=>window.__state().menus.length===2);}catch(error){console.error('bridge registration state',JSON.stringify(await page.evaluate(()=>window.__state())));throw error;}
 assert.deepEqual((await page.evaluate(()=>window.__state())).menus,['add input','remove input']);
 assert.equal((await page.evaluate(()=>window.__state())).sandbox,'allow-scripts');
 await page.evaluate(()=>window.__menu(1));
 for(let i=1;i<=3;i++){await page.evaluate(()=>window.__menu(0));await page.waitForFunction(n=>window.__state().a.length===n,i);}
 assert.deepEqual((await page.evaluate(()=>window.__state())).a.map(s=>s.name),['text1','text2','text3']);
 await page.evaluate(()=>window.__menu(0,'2'));await page.waitForFunction(()=>window.__state().b.length===1);
 await page.evaluate(()=>window.__link());await page.evaluate(()=>window.__restore());
 await page.evaluate(()=>window.__menu(1));await page.waitForFunction(()=>window.__state().a.length===2);
 assert.deepEqual((await page.evaluate(()=>window.__state())).a.map(s=>[s.name,s.link]),[['text1','kept-link-101'],['text2','dropped-link-102']]);
 await page.evaluate(()=>window.__menu(1));await page.waitForFunction(()=>window.__state().a.length===1);
 assert.deepEqual((await page.evaluate(()=>window.__state())).a.map(s=>[s.name,s.link]),[['text1','kept-link-101']]);
 await page.evaluate(()=>window.__menu(0));await page.waitForFunction(()=>window.__state().a.length===2);
 assert.equal((await page.evaluate(()=>window.__state())).a[1].name,'text2');
 for(let i=3;i<=64;i++){await page.evaluate(()=>window.__menu(0));await page.waitForFunction(n=>window.__state().a.length===n,i);}
 assert.equal((await page.evaluate(()=>window.__state())).a[63].name,'text64');
 await page.evaluate(()=>window.__menu(0));await page.waitForTimeout(100);assert.equal((await page.evaluate(()=>window.__state())).a.length,64);
 // Expected bounded pack error is diagnosed, not a lost successful addition.
 assert.equal((await page.evaluate(()=>window.__state())).b.length,1);
 const diagnosed=(await page.evaluate(()=>window.__state())).errors;
 assert.equal(diagnosed.length,1);assert.match(diagnosed[0].error,/RangeError: Batch String supports at most64/);
 await page.evaluate(()=>window.__remove());await page.evaluate(()=>window.__menu(1,'2'));await page.waitForFunction(()=>window.__state().b.length===0);
 assert.deepEqual(await page.evaluate(()=>window.__destroy()),{subs:0,iframe:false});assert.deepEqual(errors,[]);
 console.log('PASS pinned add/remove menu controls; actual opaque iframe/worker source module with sequential add64 limit, last-slot removal, restored slot/link identity and numbering, two-node isolation, removal and host destroy');
 console.log('QUALIFIED real production guest/host bridge with typed graph-slot fixtures, not canonical application serialization owner/full browser or cloud deployment');
} catch(error) {console.error('measured bridge state',JSON.stringify(await page.evaluate(()=>window.__state?.())));throw error;}
finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
