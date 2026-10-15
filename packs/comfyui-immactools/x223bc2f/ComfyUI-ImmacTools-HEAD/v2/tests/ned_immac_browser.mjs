import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
import {chromium} from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const code=fs.readFileSync(path.join(dir,'../web/js/switch_node.js'),'utf8');
const old=fs.readFileSync(path.join(dir,'../../web/js/switch_node.js'),'utf8');
let legacy;vm.runInNewContext(old.replace(/^import.*$/m,''),{app:{registerExtension:e=>legacy=e}});
assert.equal(legacy.name,'immac.switch_node');
function source(count,start=20){
  function Type() {}
  legacy.beforeRegisterNodeDef(Type,{name:'SwitchImmacTools'});
  const node=new Type();
  node.inputs=Array.from({length:start},(_,i)=>({name:'input_'+i,link:'link-'+i}));
  node.widgets=[{name:'num_inputs',value:count}];
  node.addInput=(name,type,options)=>node.inputs.push({name,type,options,link:null});
  node.removeInput=i=>node.inputs.splice(i,1);
  node.computeSize=()=>[200,80+node.inputs.length*20];
  node.setSize=size=>node.size=size;
  node.onNodeCreated();
  return {names:node.inputs.map(i=>i.name),links:node.inputs.map(i=>i.link)};
}
const root='/Users/ben/comfy/ComfyUI_secure_nodes-many-oct8-owner-provider/frontend/src';
const html=`<!doctype html><body><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
const hooks={},nodes=new Map(),ops=[];
function make(id,count=5,start=20,saved=null){
 let value=count,removed=false,size={width:200,height:480},listeners=new Set();
 let slots=saved?saved.map(s=>({...s})):Array.from({length:start},(_,i)=>({id:'s-'+id+'-'+i,name:'input_'+i,type:'*',shape:'optional',linkId:'link-'+i}));
 const minimum=()=>({width:200,height:80+slots.length*20});
 const widget={name:'num_inputs',widgetType:'number',getValue:()=>value,setValue:v=>value=v,getOptions:()=>({min:1,max:20}),on(event,fn){if(event==='change')listeners.add(fn);return()=>listeners.delete(fn);}};
 const handle=s=>({...s,index:slots.indexOf(s),snapshot:()=>({...s}),source:()=>s.linkId?{nodeId:'upstream',outputIndex:0}:undefined,link:()=>s.linkId?{id:s.linkId,sourceNodeId:'upstream',sourceIndex:0,targetNodeId:id,targetIndex:slots.indexOf(s)}:null});
 const node={id,type:'SwitchImmacTools',comfyClass:'SwitchImmacTools',graphId:'g',widgets:{all:()=>[widget],get:()=>widget},outputs:{all:()=>[]},
 inputs:{all:()=>slots.map(handle),add(name,type,options){const s={id:'s-'+id+'-'+name,name,type,...options,linkId:null};slots.push(s);ops.push(['add',id,name]);return handle(s);},remove(ref){let i=slots.findIndex(s=>s.id===ref||s.name===ref);if(typeof ref==='number')i=ref;if(i>=0){ops.push(['remove',id,slots[i].name]);slots.splice(i,1);return true;}return false;}},
 getMinimumSize:minimum,getSize:()=>size,setSize:s=>{const m=minimum();size={width:Math.max(s.width,m.width),height:Math.max(s.height,m.height)};ops.push(['resize',id]);},
 snapshot:()=>({id,type:'SwitchImmacTools',size,position:{x:0,y:0}}),
 state:()=>({id,value,size,slots:slots.map(s=>({...s})),listeners:listeners.size,removed}),
 change(v){const prior=value;value=v;for(const fn of [...listeners])fn(v,prior);},
 remove(){removed=true;hooks.onRemoved?.(node);nodes.delete(id);}
 };nodes.set(id,node);return node;
}
const comfy={backend:{url:p=>new URL(p,location.origin).href,fetch:async()=>new Response('{}')},workflow:{documentId:()=> 'immac-document'},onWorkflowLoaded(){return()=>{};},
graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[],selection:()=>[]},
defs:{extend(selector,apply){if(typeof selector==='function'){apply({onCreated(){},onRemoved(){},onConnectionsChanged(){},onConfigured(){}});return()=>{};}
if(selector!=='SwitchImmacTools')throw Error('unexpected target');apply(Object.fromEntries(['onCreated','onConfigured','onRemoved'].map(k=>[k,fn=>hooks[k]=fn])));return()=>{};}}};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',capabilities:[]});
window.start=()=>host.load('/extensions/immac/pack.js');
window.ready=()=>Object.keys(hooks).length===3;
window.create=(id,count,start=20)=>{const n=make(id,count,start);hooks.onCreated(n,{reconstructing:false});};
window.change=(id,value)=>nodes.get(id).change(value);
window.configure=(id,count)=>{const n=nodes.get(id);n.widgets.get().setValue(count);hooks.onConfigured(n,{widgets_values:[count,0,false]});};
window.reopen=id=>{const saved=nodes.get(id).state();nodes.get(id).remove();const n=make(id,saved.value,0,saved.slots);hooks.onCreated(n,{reconstructing:true});hooks.onConfigured(n,{widgets_values:[saved.value,0,false],inputs:saved.slots});};
window.remove=id=>nodes.get(id).remove();
window.state=id=>({node:nodes.get(id)?.state(),ops,sandbox:document.querySelector('iframe')?.getAttribute('sandbox'),errors:host.packErrors||[]});
window.destroy=()=>{host.destroy();return {subs:host._subs?.size??0,iframe:!!document.querySelector('iframe')};};
</script>`;
const server=http.createServer((req,res)=>{const u=new URL(req.url,'http://localhost').pathname;let body,type='text/javascript';
if(u==='/'){body=html;type='text/html';}else if(u==='/guest.js')body=fs.readFileSync(path.join(root,'guest.mjs'));
else if(u==='/comfy/api/v2.js')body='export const comfy=globalThis.comfy';
else if(u==='/extensions/immac/pack.js')body=code;
else if(u.startsWith('/src/')){const p=path.resolve(root,u.slice(5));if(p.startsWith(root+path.sep)&&fs.existsSync(p))body=fs.readFileSync(p);}
if(body===undefined){res.writeHead(404);res.end();return;}res.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});res.end(body);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage();page.setDefaultTimeout(5000);const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>!!window.start);await page.evaluate(()=>window.start());await page.waitForFunction(()=>window.ready());
 for(const count of [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,-1,0,50]){
  const id='node-'+count;await page.evaluate(([id,n])=>window.create(id,n),[id,count]);
  const expected=source(count);
  await page.waitForFunction(([id,n])=>window.state(id).node.slots.length===n,[id,expected.names.length]);
  let state=(await page.evaluate(id=>window.state(id),id)).node;
  assert.deepEqual(state.slots.map(s=>s.name),expected.names);assert.deepEqual(state.slots.map(s=>s.linkId),expected.links);
  await page.evaluate(id=>window.reopen(id),id);
  await page.waitForFunction(id=>window.state(id).node.listeners===1,id);
  state=(await page.evaluate(id=>window.state(id),id)).node;assert.deepEqual(state.slots.map(s=>s.linkId),expected.links);
  await page.evaluate(id=>window.remove(id),id);
 }
 await page.evaluate(()=>window.create('live',5,0));await page.waitForFunction(()=>window.state('live').node.slots.length===5);
 await page.evaluate(()=>window.change('live',20));await page.waitForFunction(()=>window.state('live').node.slots.length===20);
 await page.evaluate(()=>window.change('live',1));await page.waitForFunction(()=>window.state('live').node.slots.length===1);
 await page.evaluate(()=>window.configure('live',7));await page.waitForFunction(()=>window.state('live').node.slots.length===7);
 await page.evaluate(()=>window.create('isolated',3,0));await page.waitForFunction(()=>window.state('isolated').node.slots.length===3);
 assert.equal((await page.evaluate(()=>window.state('live'))).node.slots.length,7);
 assert.equal((await page.evaluate(()=>window.state('live'))).sandbox,'allow-scripts');
 await page.evaluate(()=>window.remove('live'));await page.waitForFunction(()=>!window.state('live').node);
 assert.deepEqual(await page.evaluate(()=>window.destroy()),{subs:0,iframe:false});assert.deepEqual(errors,[]);
 console.log('PASS actual opaque worker/iframe public switch hooks; all20 source counts, lower/upper clamp, source slot/link order, fresh reconstruction/configure, live growth/shrink, instance isolation/removal/disposal.');
 console.log('QUALIFIED host graph/widget/slot facades implement public semantics; no full-app/cloud renderer attestation.');
}finally{await browser.close();await new Promise(r=>server.close(r));}
