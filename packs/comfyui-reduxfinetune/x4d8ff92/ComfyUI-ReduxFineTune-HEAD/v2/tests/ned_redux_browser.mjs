import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {chromium} from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const pack=readFileSync(path.resolve(here,'../web/js/appearance.js'),'utf8');
const original=readFileSync(path.resolve(here,'../../web/js/appearance.js'),'utf8');
let legacy;vm.runInNewContext(original.replace(/^import.*$/m,''),{app:{registerExtension(v){legacy=v;}}});
assert.equal(legacy.name,'reduxfinetune.appearance');
const targets=['ReduxFineTune','ReduxFineTuneAdvanced','ClipVision','ClipVisionStyleLoader'];
for(const type of [...targets,'Other'])for(const size of [undefined,[140,80],[511,201]]){
  const node={comfyClass:type,size:size?.slice(),color:'old',bgcolor:'old-bg'};
  legacy.nodeCreated(node);
  if(targets.includes(type)){assert.equal(node.color,'#222e40');assert.equal(node.bgcolor,'#364254');assert.equal(node.size[0],340);assert.equal(node.size[1],size?.[1]??80);}
  else assert.equal(node.color,'old');
}
const root='/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
const html=`<!doctype html><body><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
const callbacks=[],nodes=new Map(),ops=[];
function make(id,type,height=201){let state={id,type,graphId:'redux-graph',size:{width:511,height},color:'old',bgColor:'old-bg'};
const node={id,type,graphId:'redux-graph',comfyClass:type,widgets:{all:()=>[]},inputs:{all:()=>[]},outputs:{all:()=>[]},snapshot:()=>({...state}),getSize:()=>state.size,setSize:size=>{state.size=size;ops.push(['size',id,size]);},getColor:()=>state.color,setColor:c=>{state.color=c;ops.push(['color',id,c]);},getBgColor:()=>state.bgColor,setBgColor:c=>{state.bgColor=c;ops.push(['bgColor',id,c]);},state:()=>state};nodes.set(id,node);return node;}
for(const [i,type] of ${JSON.stringify(targets)}.entries())make(String(i),type,201+i);make('other','Other');
const comfy={backend:{url:v=>new URL(v,location.origin).href,fetch:async()=>new Response('{}')},workflow:{documentId:()=> 'redux-document'},onWorkflowLoaded(){return()=>{};},graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[],selection:()=>[]},defs:{extend(selector,apply){if(typeof selector==='function'){apply({onCreated(){},onRemoved(){},onConnectionsChanged(){},onConfigured(){}});return()=>{};}if(JSON.stringify(selector)!==${JSON.stringify(JSON.stringify(targets))})throw Error('changed targets');apply({onCreated(callback){callbacks.push(callback);}});return()=>{};}}};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',capabilities:[]});
window.start=()=>host.load('/extensions/redux/pack.js');
window.create=id=>callbacks.forEach(fn=>fn(nodes.get(id),{}));
window.reload=id=>{const old=nodes.get(id).state();const node=make(id,old.type,old.size.height);callbacks.forEach(fn=>fn(node,{reconstructing:true}));};
window.state=()=>({callbacks:callbacks.length,nodes:[...nodes.values()].map(n=>n.state()),ops,sandbox:document.querySelector('iframe')?.getAttribute('sandbox'),errors:host.packErrors||[]});
window.remove=id=>nodes.delete(id);
window.destroy=()=>{host.destroy();return {subs:host._subs?.size??0,iframe:!!document.querySelector('iframe')};};
</script>`;
const server=http.createServer((req,res)=>{
const url=new URL(req.url,'http://localhost').pathname;let body,type='text/javascript';
if(url==='/'){body=html;type='text/html';}else if(url==='/guest.js')body=readFileSync(path.join(root,'guest.mjs'));
else if(url==='/comfy/api/v2.js')body='export const comfy=globalThis.comfy';
else if(url==='/extensions/redux/pack.js')body=pack;
else if(url.startsWith('/src/')){const p=path.resolve(root,url.slice(5));if(p.startsWith(root+path.sep)&&existsSync(p))body=readFileSync(p);}
if(body===undefined){res.writeHead(404);res.end();return;}res.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});res.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true});
try{
const page=await browser.newPage();page.setDefaultTimeout(5000);const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>typeof window.start==='function');await page.evaluate(()=>window.start());try{await page.waitForFunction(()=>window.state().callbacks===1);}catch(error){console.error('registration state',JSON.stringify(await page.evaluate(()=>window.state())),'errors',errors);throw error;}
for(let i=0;i<4;i++)await page.evaluate(id=>window.create(id),String(i));
try{await page.waitForFunction(()=>window.state().ops.length===12);}catch(error){console.error('measured state',JSON.stringify(await page.evaluate(()=>window.state())),'errors',errors);throw error;}
let state=await page.evaluate(()=>window.state());assert.equal(state.sandbox,'allow-scripts');
for(let i=0;i<4;i++){assert.equal(state.nodes[i].color,'#222e40');assert.equal(state.nodes[i].bgColor,'#364254');assert.deepEqual(state.nodes[i].size,{width:340,height:201+i});}
assert.equal(state.nodes[4].color,'old');
await page.evaluate(()=>window.reload('0'));await page.waitForFunction(()=>window.state().ops.length===15);
assert.deepEqual((await page.evaluate(()=>window.state())).nodes.find(n=>n.id==='0').size,{width:340,height:201});
await page.evaluate(()=>window.remove('1'));assert.equal((await page.evaluate(()=>window.state())).nodes.length,4);
assert.deepEqual(await page.evaluate(()=>window.destroy()),{subs:0,iframe:false});assert.deepEqual(errors,[]);
console.log('PASS pinned theme/width/height/default/foreign controls + actual opaque iframe-worker V2 setColor/setBgColor/setSize all4 targets, reconstruction/removal/cleanup');
console.log('QUALIFIED production bridge with host graph handle fixtures; no whole-app/cloud rendering assertion.');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
