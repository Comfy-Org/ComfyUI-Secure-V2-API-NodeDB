import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const sharedAlias=process.env.AUTHOR_SHARED_ALIAS==='1';
const v2=path.join(here,sharedAlias?'metadata-v2-shared':'metadata-v2');
const firstName=sharedAlias?'srm-shared-viewer':'srm-viewer-1';
const secondName=sharedAlias?'srm-shared-viewer':'srm-viewer-2';
const runtime=path.join(process.env.MANY_OVERLAY_ROOT,'frontend/src');
const {chromium}=createRequire(path.resolve(process.env.AUTHOR_BROWSER_DEPS,'package.json'))('@playwright/test');
const permissions=JSON.parse(readFileSync(path.join(v2,'secure-nodes.json'),'utf8')).frontend_permissions;
const probe=`
import {comfy} from '/comfy/api/v2.js';
const report=value=>comfy.backend.fetch('/report',{method:'POST',body:JSON.stringify(value)});
const wait=phase=>comfy.backend.fetch('/wait',{method:'POST',body:JSON.stringify({phase})});
const refused=async fn=>{try{await fn();return false;}catch{return true;}};
const first=comfy.element('${firstName}',{nodeId:'1',widget:'textDisplay'});
const second=comfy.element('${secondName}',{nodeId:'2',widget:'textDisplay'});
const initial=[await first.get('value'),await second.get('value')];
const events1=[],events2=[];
const off1=await first.listen('input',detail=>events1.push(detail.value));
await second.listen('input',detail=>events2.push(detail.value));
const decoy=comfy.ui.panel('2','decoy');
await decoy.render('<textarea data-name="${firstName}">decoy</textarea>');
const ambiguous=await refused(()=>comfy.element('${firstName}').get('value'));
const wrongScope=await refused(()=>comfy.element('${firstName}',{nodeId:'1',widget:'missing-widget'}).get('value'));
await report({phase:'captured',initial,ambiguous,wrongScope,firstAfterDecoy:await first.get('value')});
await wait('events');await first.get('value');
off1();await report({phase:'subscribed',events1:[...events1],events2:[...events2]});
await wait('unsubscribed');await first.get('value');
await report({phase:'unsubscribed',events1:[...events1],events2:[...events2]});
await wait('removed');
const removed=await refused(()=>first.get('value'));
await report({phase:'removed',removed,second:await second.get('value')});
await wait('replaced');
const stale=await refused(()=>first.get('value'));
const fresh=comfy.element('${firstName}',{nodeId:'1',widget:'textDisplay'});
await report({phase:'replaced',stale,fresh:await fresh.get('value'),events1:[...events1],events2:[...events2]});
`;
const foreign=`import {comfy} from '/comfy/api/v2.js';let denied=false;try{await comfy.element('${secondName}',{nodeId:'2',widget:'textDisplay'}).get('value');}catch{denied=true;}await comfy.backend.fetch('/report',{method:'POST',body:JSON.stringify({phase:'foreign',denied})});`;
const pageSource=`<!doctype html><meta charset="utf-8"><body><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
const nodes=new Map(),registrations=[],reports=[],writes=[],waits=new Map();
const type='Simple Readable Metadata Text Viewer-SG';
function makeNode(id){
 const records=new Map(),properties={};let text='';
 const textWidget={name:'text',widgetType:'text',getValue:()=>text,setValue:value=>{text=value;},getOptions:()=>({}),
  isSerialized:()=>true,isHidden:()=>false,getHeight:()=>28,on:()=>()=>{}};
 records.set('text',{handle:textWidget});
 const node={id,type,comfyClass:type,getProperties:()=>properties,getProperty:key=>properties[key],setProperty:(key,value)=>{properties[key]=value;},
  setSizeConstraints(){},snapshot:()=>({id,type,title:type,position:{x:0,y:0},size:{width:400,height:700}}),
  inputs:{all:()=>[]},outputs:{all:()=>[]},
  widgets:{all:()=>[...records.values()].map(row=>row.handle),get:name=>records.get(name)?.handle,names:()=>[...records.keys()],
   mount(def){const container=document.createElement('section');container.dataset.nodeId=id;document.body.append(container);
    const handle={name:def.name,widgetType:'custom',getValue:()=>undefined,getOptions:()=>({serialize:false}),isSerialized:()=>false,isHidden:()=>false,getHeight:()=>def.height,on:()=>()=>{}};
    records.set(def.name,{def,container,handle});def.render(container);return handle;},
   remove(name){const row=records.get(name);if(!row)return false;row.def?.destroy?.();row.container?.remove();records.delete(name);return true;}}
 };nodes.set(id,node);return node;
}
makeNode('1');makeNode('2');
const response=value=>({ok:true,status:200,text:async()=>JSON.stringify(value),json:async()=>value});
const comfy={version:'2.0',major:2,
 backend:{url:value=>new URL(value,location.origin).href,fetch:async(url,init)=>{
  if(url==='/object_info')return response({[type]:{}});
  if(url==='/report'){reports.push(JSON.parse(init.body));return response({});}
  if(url==='/wait'){const {phase}=JSON.parse(init.body);return await new Promise(resolve=>waits.set(phase,()=>resolve(response({}))));}
  throw Error('Unexpected fixture backend '+url);}},
 graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[]},workflow:{documentId:()=> 'two-metadata-nodes'},onWorkflowLoaded:()=>()=>{},
 defs:{extend(selector,register){const row={selector};register({onCreated(fn){row.created=fn;},onRemoved(fn){row.removed=fn;},onExecuted(fn){row.executed=fn;},onConfigured(fn){row.configured=fn;},onSerialize(fn){row.serialize=fn;}});registrations.push(row);return()=>{};}}
};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',match:()=>true,capabilities:${JSON.stringify(permissions)},
 clipboard:{async readText(){return window.__paste??'paste';},async writeText(value){writes.push(value);}}});
const panel=id=>[...host._uiByKey].find(([key])=>key.startsWith('readable:'+id+':textDisplay:'))?.[1].__shadow;
const hooks=id=>registrations.filter(row=>row.selector===nodes.get(id)?.type);
window.__start=async()=>{await host.load('/extensions/readable/entry.js');for(const node of nodes.values())for(const row of hooks(node.id))row.created?.(node,{});};
window.__executed=(id,value)=>{for(const row of hooks(id))row.executed?.(nodes.get(id),{raw:{text:[value]}});};
window.__select=(id,start,end)=>{const element=panel(id).querySelector('textarea');element.focus();element.setSelectionRange(start,end);};
window.__rect=(id,action)=>{const rect=panel(id).querySelector('[data-testid="viewer-'+action+'"]').getBoundingClientRect();return{x:rect.x+rect.width/2,y:rect.y+rect.height/2};};
window.__input=(id,value)=>{const element=panel(id).querySelector('textarea');element.value=value;element.dispatchEvent(new Event('input'));};
window.__release=phase=>{if(!waits.has(phase))throw Error('Missing phase boundary '+phase);waits.get(phase)();waits.delete(phase);};
window.__remove=id=>{const node=nodes.get(id);for(const row of hooks(id))row.removed?.(node);for(const name of [...node.widgets.names()])node.widgets.remove(name);nodes.delete(id);};
window.__replace=id=>{const node=makeNode(id);for(const row of hooks(id))row.created?.(node,{});};
window.__probe=()=>{void host.load('/extensions/readable/probe.js').catch(error=>reports.push({phase:'probe-failure',error:String(error)}));};
window.__foreign=()=>host.load('/extensions/foreign/probe.js');
window.__state=()=>({reports,writes,texts:['1','2'].map(id=>panel(id)?.querySelector('textarea')?.value),
 selections:['1','2'].map(id=>{const element=panel(id)?.querySelector('textarea');return element?[element.selectionStart,element.selectionEnd]:null;}),mountKeys:[...host._uiByKey.keys()],
 sandbox:document.querySelector('iframe')?.getAttribute('sandbox'),waits:[...waits.keys()],errors:host.packErrors??[]});
window.__finish=()=>{host.destroy();return host._elements.size;};
</script></body>`;

const server=http.createServer((request,response)=>{
 const url=new URL(request.url,'http://localhost').pathname;let body,type='text/javascript';
 if(url==='/'){body=pageSource;type='text/html';}
 else if(url==='/guest.js')body=readFileSync(path.join(runtime,'guest.mjs'));
 else if(url==='/comfy/api/v2.js')body='export const comfy=globalThis.comfy;';
 else if(url==='/extensions/readable/entry.js')body="import './Simple_Readable_Metadata_Text_Viewer_SG.js';";
 else if(url==='/extensions/readable/probe.js')body=probe;
 else if(url==='/extensions/foreign/probe.js')body=foreign;
 else if(url.startsWith('/extensions/readable/')){const file=path.resolve(v2,'web',url.slice('/extensions/readable/'.length));if(file.startsWith(path.join(v2,'web')+path.sep)&&existsSync(file))body=readFileSync(file);}
 else if(url.startsWith('/src/')){const file=path.resolve(runtime,url.slice(5));if(file.startsWith(runtime+path.sep)&&existsSync(file))body=readFileSync(file);}
 if(body===undefined){response.writeHead(404);response.end();return;}
 response.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});response.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});
let activePage;
try{
 const page=await browser.newPage({viewport:{width:1200,height:1600}}),errors=[];page.setDefaultTimeout(12000);page.on('pageerror',error=>errors.push(String(error)));
 activePage=page;
 await page.goto('http://127.0.0.1:'+server.address().port);await page.evaluate(()=>window.__start());
 await page.waitForFunction(()=>window.__state().texts.every(value=>value===''));
 await page.evaluate(()=>{window.__executed('1','A😀BCDEF');window.__executed('2','second value');});
 await page.waitForFunction(()=>window.__state().texts[0]==='A😀BCDEF'&&window.__state().texts[1]==='second value');
 const click=async(id,action)=>{const point=await page.evaluate(({id,action})=>window.__rect(id,action),{id,action});await page.mouse.click(point.x,point.y);};
 await page.evaluate(()=>window.__select('1',1,3));await click('1','copy');await page.waitForFunction(()=>window.__state().writes.length===1);
 assert.equal((await page.evaluate(()=>window.__state())).writes[0],'😀');
 await page.evaluate(()=>{window.__select('2',0,6);window.__paste='changed';});await click('2','paste');
 await page.waitForFunction(()=>window.__state().texts[1]==='changed value');
 assert.equal((await page.evaluate(()=>window.__state())).texts[0],'A😀BCDEF');
 await page.evaluate(()=>window.__probe());
 await page.waitForFunction(()=>window.__state().reports.some(row=>row.phase==='captured')&&window.__state().waits.includes('events'));
 let state=await page.evaluate(()=>window.__state());const captured=state.reports.find(row=>row.phase==='captured');
 assert.deepEqual(captured.initial,['A😀BCDEF','changed value']);assert.equal(captured.ambiguous,true);assert.equal(captured.wrongScope,true);assert.equal(captured.firstAfterDecoy,'A😀BCDEF');
 await page.evaluate(()=>{window.__input('1','first event');window.__input('2','second event');window.__release('events');});
 await page.waitForFunction(()=>window.__state().waits.includes('unsubscribed'));
 state=await page.evaluate(()=>window.__state());const subscribed=state.reports.find(row=>row.phase==='subscribed');
 assert.deepEqual(subscribed.events1,['first event']);assert.deepEqual(subscribed.events2,['second event']);
 await page.evaluate(()=>{window.__input('1','ignored after unsubscribe');window.__input('2','second event two');window.__release('unsubscribed');});
 await page.waitForFunction(()=>window.__state().waits.includes('removed'));
 state=await page.evaluate(()=>window.__state());const unsubscribed=state.reports.find(row=>row.phase==='unsubscribed');
 assert.deepEqual(unsubscribed.events1,['first event']);assert.deepEqual(unsubscribed.events2,['second event','second event two']);
 await page.evaluate(()=>{window.__remove('1');window.__release('removed');});
 await page.waitForFunction(()=>window.__state().waits.includes('replaced'));
 state=await page.evaluate(()=>window.__state());const removed=state.reports.find(row=>row.phase==='removed');assert.equal(removed.removed,true);assert.equal(removed.second,'second event two');
 await page.evaluate(()=>window.__replace('1'));await page.waitForFunction(()=>window.__state().texts[0]==='');
 await page.evaluate(()=>window.__executed('1','fresh instance'));await page.waitForFunction(()=>window.__state().texts[0]==='fresh instance');
 await page.evaluate(()=>{window.__input('1','replacement event');window.__release('replaced');});
 await page.waitForFunction(()=>window.__state().reports.some(row=>row.phase==='replaced'));
 state=await page.evaluate(()=>window.__state());const replaced=state.reports.find(row=>row.phase==='replaced');
 assert.equal(replaced.stale,true);assert.equal(replaced.fresh,'replacement event');assert.deepEqual(replaced.events1,['first event']);
 await page.evaluate(()=>window.__foreign());await page.waitForFunction(()=>window.__state().reports.some(row=>row.phase==='foreign'));
 state=await page.evaluate(()=>window.__state());assert.equal(state.reports.find(row=>row.phase==='foreign').denied,true);
 assert.deepEqual(errors,[]);assert.deepEqual(state.errors,[]);assert.equal(state.sandbox,'allow-scripts');assert.equal(await page.evaluate(()=>window.__finish()),0);
 console.log(JSON.stringify({pass:true,actual_metadata_viewer:true,test_only_shared_alias:sharedAlias,explicit_scoped_successor:true,two_instances:true,selection_copy_paste:true,subscription_unsubscribe:true,removal_replacement_no_retarget:true,wrong_scope_denied:true,foreign_denied:true,definition_registration_fixture:true,reports:state.reports}));
}catch(error){console.error(JSON.stringify(await activePage?.evaluate(()=>window.__state()).catch(()=>null)));throw error;}
finally{await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
