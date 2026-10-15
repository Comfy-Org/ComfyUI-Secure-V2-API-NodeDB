import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const v2=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=process.env.QR_FRONTEND_SRC;
const deps=process.env.QR_BROWSER_DEPS;
if(!runtime||!deps)throw Error('QR_FRONTEND_SRC and QR_BROWSER_DEPS are required');
const {chromium}=createRequire(path.join(deps,'package.json'))('@playwright/test');
const pageSource=`<!doctype html><meta charset="utf-8"><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
const records=[],nodes=new Map(),commits=[];
function create(id,type='🎭 ShowData',text='original'){
 const widget={name:'data',widgetType:'text',getValue:()=>text,getOptions:()=>({}),
  isSerialized:()=>true,isHidden:()=>false,getHeight:()=>28,
  setValue(value){text=value;commits.push({id,value});},on(){return()=>{};}};
 const node={id,type,comfyClass:type,getProperties:()=>({}),getProperty:()=>undefined,
  snapshot:()=>({id,type,title:type,position:{x:0,y:0},size:{width:320,height:200}}),
  inputs:{all:()=>[]},outputs:{all:()=>[]},
  widgets:{all:()=>[widget],get:name=>name==='data'?widget:undefined,names:()=>['data']}};
 nodes.set(id,node);return node;
}
create('one');create('two');create('other','foreign');
const comfy={backend:{url:value=>new URL(value,location.origin).href},
 graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[]},
 workflow:{documentId:()=> 'qr-owned-widget'},
 onWorkflowLoaded:()=>()=>{},
 defs:{extend(selector,apply){const r={selector};apply({
  onExecuted(fn){r.executed=fn;},onCreated(fn){r.created=fn;},onRemoved(fn){r.removed=fn;},
  onConfigured(fn){r.configured=fn;},onSerialize(fn){r.serialize=fn;},
 });records.push(r);return()=>{};}}};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',match:()=>true,capabilities:[]});
window.start=()=>host.load('/extensions/qr/show_data.js');
window.executed=(id,value)=>{const node=nodes.get(id);for(const r of records)if(r.selector===node.type)r.executed(node,{raw:{data:value},text:[],images:[]});};
window.edit=(id,value)=>nodes.get(id).widgets.get('data').setValue(value);
window.state=()=>({one:nodes.get('one')?.widgets.get('data').getValue(),
 two:nodes.get('two')?.widgets.get('data').getValue(),other:nodes.get('other')?.widgets.get('data').getValue(),
 commits,registrations:records.filter(r=>r.selector==='🎭 ShowData').map(r=>r.selector),errors:host.packErrors??[],
 sandbox:document.querySelector('iframe')?.getAttribute('sandbox')});
window.remove=id=>nodes.delete(id);
window.remount=id=>create(id,'🎭 ShowData','restored workflow text');
window.finish=()=>host.destroy();
</script>`;
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://fixture').pathname;let body,type='text/javascript';
 if(url==='/'){body=pageSource;type='text/html';}
 else if(url==='/guest.js')body=readFileSync(path.join(runtime,'guest.mjs'));
 else if(url==='/comfy/api/v2.js')body='export const comfy=globalThis.comfy;';
 else if(url==='/extensions/qr/show_data.js')body=readFileSync(path.join(v2,'web','show_data.js'));
 else if(url.startsWith('/src/')){
  const file=path.resolve(runtime,url.slice(5));
  if(file.startsWith(path.resolve(runtime)+path.sep)&&existsSync(file))body=readFileSync(file);
 }
 if(body===undefined){res.writeHead(404);res.end();return;}
 res.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});res.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});let checks=0;
const check=fn=>{fn();checks++;};
try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 page.on('console',m=>{if(m.type()==='error')console.error('BROWSER',m.text());});
 page.setDefaultTimeout(5000);
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.waitForFunction(()=>typeof window.start==='function').catch(error=>{console.error('PAGE_ERRORS',JSON.stringify(errors));throw error;});
 await page.evaluate(()=>window.start());await page.waitForFunction(()=>window.state().registrations.length===1);
 let state=await page.evaluate(()=>window.state());
 check(()=>assert.deepEqual(state.registrations,['🎭 ShowData']));
 check(()=>assert.equal(state.sandbox,'allow-scripts'));
 for(const text of ['','one\ntwo','😀é中文','<img src=x onerror=alert(1)> & plain']){
  await page.evaluate(text=>window.executed('one',text),text);
  await page.waitForFunction(text=>window.state().one===text,text);
  state=await page.evaluate(()=>window.state());
  check(()=>assert.equal(state.one,text));check(()=>assert.equal(state.two,'original'));
  check(()=>assert.equal(state.other,'original'));
 }
 await page.evaluate(()=>window.edit('two','authored'));
 await page.evaluate(()=>window.executed('two','new result'));
 await page.waitForFunction(()=>window.state().two==='new result');
 state=await page.evaluate(()=>window.state());check(()=>assert.equal(state.two,'new result'));
 await page.evaluate(()=>{window.remove('one');window.remount('one');});
 state=await page.evaluate(()=>window.state());check(()=>assert.equal(state.one,'restored workflow text'));
 await page.evaluate(()=>window.executed('one','after remount'));
 await page.waitForFunction(()=>window.state().one==='after remount');
 state=await page.evaluate(()=>window.state());check(()=>assert.equal(state.one,'after remount'));
 check(()=>assert.deepEqual(errors,[]));
 state=await page.evaluate(()=>window.state());check(()=>assert.deepEqual(state.errors,[]));
 const preserved=state.one;
 for(const bad of [null,['wrong'], 'x'.repeat(65537)]){
  const before=(await page.evaluate(()=>window.state())).errors.length;
  await page.evaluate(value=>window.executed('one',value),bad);
  await page.waitForFunction(n=>window.state().errors.length>n,before);
  state=await page.evaluate(()=>window.state());
  check(()=>assert.equal(state.one,preserved));
  check(()=>assert.match(state.errors.at(-1).error.message??String(state.errors.at(-1).error),/invalid bounded text/));
 }
 await page.evaluate(()=>window.executed('one','recovered'));
 await page.waitForFunction(()=>window.state().one==='recovered');
 state=await page.evaluate(()=>window.state());check(()=>assert.equal(state.one,'recovered'));
 await page.evaluate(()=>window.finish());
 console.log(JSON.stringify({checks,proof:'production opaque-worker own hook/widget commit; graph handles are fixture-owned',runtime}));
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
