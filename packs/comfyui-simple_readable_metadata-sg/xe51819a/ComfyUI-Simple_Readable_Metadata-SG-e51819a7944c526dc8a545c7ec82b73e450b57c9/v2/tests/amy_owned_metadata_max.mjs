import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
const v2=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=path.join(process.env.MANY_OVERLAY_ROOT,'frontend/src');
const {chromium}=createRequire(path.resolve(process.env.AUTHOR_BROWSER_DEPS,'package.json'))('@playwright/test');
const permissions=JSON.parse(readFileSync(path.join(v2,'secure-nodes.json'))).frontend_permissions;
const probe=`
import {comfy} from '/comfy/api/v2.js';
const report=row=>comfy.backend.fetch('/report',{method:'POST',body:JSON.stringify(row)});
const wait=phase=>comfy.backend.fetch('/wait',{method:'POST',body:JSON.stringify({phase})});
const refuses=async fn=>{try{await fn();return false;}catch{return true;}};
const first=comfy.element('srm-preview-1-1',{nodeId:'1',widget:'metadata_preview'});
const second=comfy.element('srm-preview-2-1',{nodeId:'2',widget:'metadata_preview'});
const events=[];const off=await first.listen('load',()=>events.push('load'));
const decoy=comfy.ui.panel('2','decoy');await decoy.render('<img data-name="srm-preview-1-1" src="/view?filename=wide.svg">');
await report({phase:'initial',dimensions:[await first.get('naturalWidth'),await first.get('naturalHeight'),await second.get('naturalWidth'),await second.get('naturalHeight')],
 ambiguous:await refuses(()=>comfy.element('srm-preview-1-1').get('naturalWidth')),
 wrongScope:await refuses(()=>comfy.element('srm-preview-1-1',{nodeId:'1',widget:'metadata_readout'}).get('naturalWidth'))});
await wait('event');await first.get('naturalWidth');off();off();await report({phase:'event',events:[...events]});
await wait('off');await first.get('naturalWidth');await report({phase:'off',events:[...events]});
await wait('removed');await report({phase:'removed',denied:await refuses(()=>first.get('naturalWidth')),second:await second.get('naturalWidth')});
await wait('remount');const fresh=comfy.element('srm-preview-1-1',{nodeId:'1',widget:'metadata_preview'});
await report({phase:'remount',stale:await refuses(()=>first.get('naturalWidth')),fresh:await fresh.get('naturalWidth'),events:[...events]});
`;
const foreign=`import {comfy} from '/comfy/api/v2.js';let denied=false;try{await comfy.element('srm-preview-2-1',{nodeId:'2',widget:'metadata_preview'}).get('naturalWidth');}catch{denied=true;}await comfy.backend.fetch('/report',{method:'POST',body:JSON.stringify({phase:'foreign',denied})});`;
const pageSource=`<!doctype html><meta charset="utf-8"><body><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
const nodes=new Map(),registrations=[],reports=[],waits=new Map();
const type='SimpleReadableMetadataMAXSG';
function makeNode(id){
 const records=new Map(),properties={};let image='';const listeners=new Set();
 const widget={name:'image',widgetType:'combo',getValue:()=>image,setValue(value){image=value;for(const fn of listeners)fn(value);},
 getOptions:()=>({}),isSerialized:()=>true,isHidden:()=>false,getHeight:()=>28,on(event,fn){listeners.add(fn);return()=>listeners.delete(fn);}};
 records.set('image',{handle:widget});
 const node={id,type,comfyClass:type,getProperties:()=>properties,getProperty:key=>properties[key],setProperty:(key,value)=>properties[key]=value,
 setSizeConstraints(){},snapshot:()=>({id,type,title:type,position:{x:0,y:0},size:{width:400,height:300}}),inputs:{all:()=>[]},outputs:{all:()=>[]},
 widgets:{get:name=>records.get(name)?.handle,names:()=>[...records.keys()],all:()=>[...records.values()].map(row=>row.handle),
 mount(def){const container=document.createElement('section');document.body.append(container);
 const handle={name:def.name,widgetType:'custom',getValue:()=>undefined,getOptions:()=>({serialize:false}),isSerialized:()=>false,isHidden:()=>false,getHeight:()=>def.height,on:()=>()=>{}};
 records.set(def.name,{handle,def,container});def.render(container);return handle;},
 remove(name){const row=records.get(name);row?.def?.destroy?.();row?.container?.remove();return records.delete(name);}}};
 nodes.set(id,node);return node;
}
makeNode('1');makeNode('2');
const response=value=>({ok:true,status:200,text:async()=>JSON.stringify(value),json:async()=>value});
const comfy={version:'2.0',major:2,backend:{url:value=>new URL(value,location.origin).href,fetch:async(url,init)=>{
 if(url==='/object_info')return response({[type]:{}});if(url==='/report'){reports.push(JSON.parse(init.body));return response({});}
 if(url==='/wait'){const {phase}=JSON.parse(init.body);return new Promise(resolve=>waits.set(phase,()=>resolve(response({}))));}throw Error(url);}},
 graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[]},workflow:{documentId:()=> 'max-two-nodes'},onWorkflowLoaded:()=>()=>{},
 defs:{extend(selector,apply){const row={selector};apply({onCreated(fn){row.created=fn;},onRemoved(fn){row.removed=fn;},onExecuted(fn){row.executed=fn;},onConfigured(fn){row.configured=fn;},onSerialize(fn){row.serialize=fn;}});registrations.push(row);return()=>{};}}};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',match:()=>true,capabilities:${JSON.stringify(permissions)}});
const hooks=id=>registrations.filter(row=>row.selector===nodes.get(id)?.type);
const panel=(id,name)=>[...host._uiByKey].find(([key])=>key.startsWith('readable:'+id+':'+name+':'))?.[1].__shadow;
window.__start=async()=>{await host.load('/extensions/readable/entry.js');for(const node of nodes.values())for(const row of hooks(node.id))row.created?.(node,{});};
window.__image=(id,name)=>nodes.get(id).widgets.get('image').setValue(name);
window.__event=()=>panel('1','metadata_preview').querySelector('img').dispatchEvent(new Event('load'));
window.__release=phase=>{waits.get(phase)();waits.delete(phase);};
window.__probe=()=>void host.load('/extensions/readable/probe.js').catch(error=>reports.push({phase:'error',error:String(error)}));
window.__foreign=()=>host.load('/extensions/foreign/probe.js');
window.__remove=id=>{const node=nodes.get(id);for(const row of hooks(id))row.removed?.(node);for(const name of [...node.widgets.names()])node.widgets.remove(name);nodes.delete(id);};
window.__remount=id=>{const node=makeNode(id);for(const row of hooks(id))row.created?.(node,{});};
window.__state=()=>({reports,panels:host._uiByKey.size,waits:[...waits.keys()],readouts:['1','2'].map(id=>panel(id,'metadata_readout')?.textContent),errors:host.packErrors??[],sandbox:document.querySelector('iframe')?.getAttribute('sandbox')});
window.__finish=()=>{host.destroy();return host._elements.size;};
</script></body>`;
const server=http.createServer((request,response)=>{
 const parsed=new URL(request.url,'http://localhost'),url=parsed.pathname;let body,type='text/javascript';
 if(url==='/'){body=pageSource;type='text/html';}
 else if(url==='/guest.js')body=readFileSync(path.join(runtime,'guest.mjs'));
 else if(url==='/comfy/api/v2.js')body='export const comfy=globalThis.comfy;';
 else if(url==='/extensions/readable/entry.js')body="import './Simple_Readable_Metadata_MAX_SG.js';";
 else if(url==='/extensions/readable/probe.js')body=probe;
 else if(url==='/extensions/foreign/probe.js')body=foreign;
 else if(url.startsWith('/extensions/readable/')){const file=path.resolve(v2,'web',url.slice('/extensions/readable/'.length));if(file.startsWith(path.join(v2,'web')+path.sep)&&existsSync(file))body=readFileSync(file);}
 else if(url.startsWith('/src/')){const file=path.resolve(runtime,url.slice(5));if(file.startsWith(runtime+path.sep)&&existsSync(file))body=readFileSync(file);}
 else if(url==='/view'||url==='/api/view'){const wide=parsed.searchParams.get('filename')==='wide.svg';body='<svg xmlns="http://www.w3.org/2000/svg" width="'+(wide?8:3)+'" height="'+(wide?4:2)+'"></svg>';type='image/svg+xml';}
 if(body===undefined){response.writeHead(404);response.end();return;}response.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});response.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});let page;
try{
 page=await browser.newPage();page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',error=>errors.push(String(error)));
 await page.goto('http://127.0.0.1:'+server.address().port);await page.evaluate(()=>window.__start());
 await page.waitForFunction(()=>window.__state().panels===4);
 await page.evaluate(()=>{window.__image('1','small.svg');window.__image('2','wide.svg');});
 await page.waitForFunction(()=>window.__state().readouts[0]?.startsWith('3x2')&&window.__state().readouts[1]?.startsWith('8x4'));
 await page.evaluate(()=>window.__probe());await page.waitForFunction(()=>window.__state().waits.includes('event'));
 let state=await page.evaluate(()=>window.__state());const initial=state.reports.find(row=>row.phase==='initial');
 assert.deepEqual(initial.dimensions,[3,2,8,4]);assert.equal(initial.ambiguous,true);assert.equal(initial.wrongScope,true);
 await page.evaluate(()=>{window.__event();window.__release('event');});await page.waitForFunction(()=>window.__state().waits.includes('off'));
 state=await page.evaluate(()=>window.__state());assert.deepEqual(state.reports.find(row=>row.phase==='event').events,['load']);
 await page.evaluate(()=>{window.__event();window.__release('off');});await page.waitForFunction(()=>window.__state().waits.includes('removed'));
 state=await page.evaluate(()=>window.__state());assert.deepEqual(state.reports.find(row=>row.phase==='off').events,['load']);
 await page.evaluate(()=>{window.__remove('1');window.__release('removed');});await page.waitForFunction(()=>window.__state().waits.includes('remount'));
 state=await page.evaluate(()=>window.__state());assert.deepEqual(state.reports.find(row=>row.phase==='removed'),{phase:'removed',denied:true,second:8});
 await page.evaluate(()=>window.__remount('1'));await page.evaluate(()=>window.__image('1','wide.svg'));
 await page.waitForFunction(()=>window.__state().readouts[0]?.startsWith('8x4'));await page.evaluate(()=>window.__release('remount'));
 await page.waitForFunction(()=>window.__state().reports.some(row=>row.phase==='remount'));
 state=await page.evaluate(()=>window.__state());const remount=state.reports.find(row=>row.phase==='remount');assert.equal(remount.stale,true);assert.equal(remount.fresh,8);assert.deepEqual(remount.events,['load']);
 await page.evaluate(()=>window.__foreign());await page.waitForFunction(()=>window.__state().reports.some(row=>row.phase==='foreign'));
 state=await page.evaluate(()=>window.__state());assert.equal(state.reports.find(row=>row.phase==='foreign').denied,true);
 assert.deepEqual(state.errors,[]);assert.deepEqual(errors,[]);assert.equal(state.sandbox,'allow-scripts');assert.equal(await page.evaluate(()=>window.__finish()),0);
 console.log(JSON.stringify({pass:true,actualMaxCallbacks:true,twoInstances:true,dimensions:true,subscribeOff:true,removedRemount:true,foreignWrongScope:true,reports:state.reports}));
}catch(error){console.error(JSON.stringify(await page?.evaluate(()=>window.__state()).catch(()=>null)));throw error;}
finally{await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
