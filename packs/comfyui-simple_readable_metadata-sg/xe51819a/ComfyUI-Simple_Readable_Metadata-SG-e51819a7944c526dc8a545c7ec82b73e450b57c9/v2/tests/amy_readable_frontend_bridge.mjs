import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/tests/_deps.mjs';
const v2 = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runtime = '/Users/ben/comfy/ComfyUI_secure_nodes/frontend/src';
const frontendPermissions=JSON.parse(readFileSync(path.join(v2,'secure-nodes.json'),'utf8')).frontend_permissions;
const entries = ['Simple_Readable_Metadata_SG.js','Simple_Readable_Metadata_MAX_SG.js','Simple_Readable_Metadata_VIDEO_SG.js','Simple_Readable_Metadata_Save_Text_SG.js','Simple_Readable_Metadata_Text_Viewer_SG.js'];
const pageSource = `<!doctype html><meta charset="utf-8"><body><script type="module">
import { SecureExtensionHost } from '/src/host-entry.mjs';
const nodes=new Map(),registrations=[],commits=[],writes=[],downloads=[],uiEvents=[];
function makeNode(id,type,props={}) {
 const records=new Map(),properties={...props};let constraints=null,size=null;
 function widget(name,value) {
  const listeners=new Map(),options={},handle={name,widgetType:typeof value==='string'?'text':'number',
   getValue:()=>value,getOptions:()=>options,setOption(key,value){options[key]=value;},isSerialized:()=>true,isHidden:()=>false,getHeight:()=>28,
   setValue(next){const before=value;value=next;commits.push({id,name,value});for(const fn of listeners.get('change')||[])fn(next,before);},
   on(event,fn){if(!listeners.has(event))listeners.set(event,new Set());listeners.get(event).add(fn);return()=>listeners.get(event).delete(fn);},
  };records.set(name,{handle});
 }
 widget('text','');widget('image','');widget('video','');widget('show_info','both');widget('filename_prefix','ComfyUI');
 const node={id,type,comfyClass:type,getProperties:()=>properties,getProperty:key=>properties[key],
  setProperty:(key,value)=>{properties[key]=value;},setSizeConstraints(value){constraints=value;},setSize(value){size=value;},
  actualSizes:()=>({constraints,size}),
  snapshot:()=>({id,type,title:type,position:{x:0,y:0},size:{width:400,height:700}}),
  inputs:{all:()=>[]},outputs:{all:()=>[]},
  widgets:{all:()=>[...records.values()].map(r=>r.handle),get:name=>records.get(name)?.handle,names:()=>[...records.keys()],
   mount(def){const container=document.createElement('section');document.body.append(container);
    const handle={name:def.name,widgetType:'custom',getValue:()=>undefined,getOptions:()=>({serialize:false}),
     isSerialized:()=>false,isHidden:()=>false,getHeight:()=>def.height,on(){return()=>{};}};
    records.set(def.name,{def,container,handle});def.render(container);return handle;},
   remove(name){const r=records.get(name);if(!r)return false;r.def?.destroy?.();r.container?.remove();records.delete(name);return true;},
  },records};
 nodes.set(id,node);return node;
}
const types=['SimpleReadableMetadataSG','SimpleReadableMetadataMAXSG','SimpleReadableMetadataVideoSG','SimpleReadableMetadataSaveTextSG','Simple Readable Metadata Text Viewer-SG'];
types.forEach((type,i)=>makeNode(String(i+1),type));
const response=body=>({ok:true,status:200,text:async()=>body,json:async()=>JSON.parse(body)});
const comfy={
 backend:{url:value=>new URL(value,location.origin).href,fetch:async url=>{
  if(url==='/object_info')return response(JSON.stringify(Object.fromEntries(types.map(t=>[t,{}]))));
  throw Error('unexpected backend '+url);}},
 graph:{nodes:()=>[...nodes.values()],node:id=>nodes.get(String(id)),groups:()=>[]},
 workflow:{documentId:()=> 'readable-proof'},onWorkflowLoaded:()=>()=>{},
 defs:{extend(selector,apply){const record={selector};apply({
  onCreated(fn){record.created=fn;},onRemoved(fn){record.removed=fn;},onExecuted(fn){record.executed=fn;},
  onConfigured(fn){record.configured=fn;},onSerialize(fn){record.serialize=fn;},
 });registrations.push(record);return()=>{};}},
};
const host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',match:()=>true,
 capabilities:${JSON.stringify(frontendPermissions)},
 clipboard:{async readText(){if(window.__clipboardFail)throw Error('fixture clipboard refusal');if(window.__holdClipboard)await new Promise(resolve=>{window.__releaseClipboard=resolve;});return window.__pasteText??'paste';},async writeText(text){writes.push(text);}},
 fileDownloader:async request=>{downloads.push({...request,bytes:Array.from(request.bytes)});}});
const send=host._host.send.bind(host._host);host._host.send=(pack,message)=>{if(message.t==='uiEvent')uiEvents.push(message);return send(pack,message);};
window.__start=async()=>{await host.load('/extensions/readable/entry.js');
 for(const r of registrations)for(const node of nodes.values())if(r.selector===node.type)r.created?.(node,{});};
const panel=(id,name)=>[...host._uiByKey].find(([key])=>key.includes(':'+id+':'+name+':'))?.[1].__shadow;
window.__state=()=>({registrations:registrations.filter(r=>typeof r.selector==='string').map(r=>r.selector),
 panels:host._uiByKey.size,sandbox:document.querySelector('iframe')?.getAttribute('sandbox'),writes,commits,downloads,
 text:panel('5','textDisplay')?.querySelector('textarea')?.value,
 status:panel('5','textDisplay')?.querySelector('[data-testid="viewer-status"]')?.textContent,
 matchCounter:panel('5','textDisplay')?.querySelector('[data-testid="viewer-search-input"]')?.nextElementSibling?.textContent,
 lineCounter:panel('5','textDisplay')?.querySelector('[data-testid="viewer-line-filter"]')?.nextElementSibling?.textContent,
 scrollTop:panel('5','textDisplay')?.querySelector('textarea')?.scrollTop,
 saveText:{...nodes.get('4')?.actualSizes(),options:nodes.get('4')?.widgets.get('filename_prefix')?.getOptions()},
 marks:panel('5','textDisplay')?.querySelector('pre')?.textContent,
 html:panel('5','textDisplay')?.querySelector('pre')?.innerHTML,
 confirmVisible:!!panel('5','textDisplay')?.querySelector('[data-testid="viewer-confirm-delete"]')?.getClientRects().length,
 properties:nodes.get('5')?.getProperties(),elements:host._elements.size,
 uiEvents,inputMarkup:panel('5','textDisplay')?.querySelector('[data-testid="viewer-search-input"]')?.outerHTML,
 image:panel('2','metadata_preview')?.innerHTML,
 errors:host.packErrors??[],readouts:['1','2','3'].map(id=>panel(id,'metadata_readout')?.textContent)});
window.__executed=(id,text)=>{const node=nodes.get(id);for(const r of registrations)if(r.selector===node.type)r.executed?.(node,{raw:{text},text:[]});};
window.__configured=(id,info)=>{const node=nodes.get(id);for(const r of registrations)if(r.selector===node.type)r.configured?.(node,info);};
window.__serialize=id=>{const node=nodes.get(id);return registrations.find(r=>r.selector===node.type)?.serialize?.(node);};
window.__newViewer=properties=>{const node=makeNode('6',types[4],properties);
 for(const r of registrations)if(r.selector===node.type)r.created?.(node,{});};
window.__otherText=()=>panel('6','textDisplay')?.querySelector('textarea')?.value;
window.__edit=(testid,value)=>{const el=panel('5','textDisplay').querySelector('[data-testid="'+testid+'"]');el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));};
window.__changeFont=value=>{const el=panel('5','textDisplay').querySelector('[data-testid="viewer-font"]');el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));};
window.__rect=testid=>{const r=panel('5','textDisplay').querySelector('[data-testid="'+testid+'"]').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};};
window.__select=(start,end)=>{const box=panel('5','textDisplay').querySelector('textarea');box.focus();box.setSelectionRange(start,end);};
window.__selection=()=>{const box=panel('5','textDisplay').querySelector('textarea');return[box.selectionStart,box.selectionEnd];};
window.__widget=(id,name,value)=>nodes.get(id).widgets.get(name).setValue(value);
window.__remove=id=>{const node=nodes.get(id);for(const r of registrations)if(r.selector===node.type)r.removed?.(node);
 nodes.delete(id);for(const name of [...node.widgets.names()])if(node.records.get(name)?.def)node.widgets.remove(name);};
window.__finish=()=>{host.destroy();return host._elements.size;};
</script></body>`;
const server=http.createServer((req,res)=>{
 const requestUrl=new URL(req.url,'http://localhost'),url=requestUrl.pathname;
 let body,type='text/javascript';
 if(url==='/'){body=pageSource;type='text/html';}
 else if(url==='/guest.js')body=readFileSync(path.join(runtime,'guest.mjs'));
 else if(url==='/comfy/api/v2.js')body='export const comfy=globalThis.comfy;';
 else if(url==='/extensions/readable/entry.js')body=entries.map(name=>`import './${name}';`).join('\n');
 else if(url.startsWith('/extensions/readable/')){
  const file=path.resolve(v2,'web',url.slice('/extensions/readable/'.length));
  if(file.startsWith(path.join(v2,'web')+path.sep)&&existsSync(file))body=readFileSync(file);
 }else if(url.startsWith('/src/')){
  const file=path.resolve(runtime,url.slice(5));if(file.startsWith(runtime+path.sep)&&existsSync(file))body=readFileSync(file);
 }else if(url==='/view'||url==='/api/view'){
  if(requestUrl.searchParams.get('filename')==='video.mp4'){
   body=Buffer.from(readFileSync(path.join(v2,'tests','browser-preview.base64'),'utf8'),'base64');type='video/webm';
  }else{body='<svg xmlns="http://www.w3.org/2000/svg" width="3" height="2"></svg>';type='image/svg+xml';}
 }
 if(body===undefined){res.writeHead(404);res.end();return;}
 res.writeHead(200,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});res.end(body);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true});let checks=0;
const check=fn=>{fn();checks++;};
try{
 const page=await browser.newPage({viewport:{width:1200,height:1600}}),errors=[];page.on('pageerror',error=>errors.push(String(error)));
 page.on('console',message=>{if(message.type()==='error')console.error('BROWSER',message.text());});
 page.setDefaultTimeout(5000);
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.waitForFunction(()=>typeof window.__start==='function');await page.evaluate(()=>window.__start());
 await page.waitForFunction(()=>window.__state().panels===6);
 let state=await page.evaluate(()=>window.__state());
 check(()=>assert.deepEqual(state.registrations.sort(),['SimpleReadableMetadataSG','SimpleReadableMetadataMAXSG','SimpleReadableMetadataVideoSG','SimpleReadableMetadataSaveTextSG','Simple Readable Metadata Text Viewer-SG'].sort()));
 check(()=>assert.equal(state.sandbox,'allow-scripts'));
 const click=async name=>{const point=await page.evaluate(name=>window.__rect('viewer-'+name),name);await page.mouse.click(point.x,point.y);};
 await page.evaluate(()=>window.__executed('5',['A😀BCDEF']));
 await page.waitForFunction(()=>window.__state().text==='A😀BCDEF').catch(async error=>{console.error(JSON.stringify(await page.evaluate(()=>window.__state())));throw error;});
 await page.evaluate(()=>window.__select(1,3));await click('copy');
 await page.waitForFunction(()=>window.__state().writes.length===1);
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.writes[0],'😀'));
 await page.evaluate(()=>{window.__select(1,3);window.__pasteText='paste';});await click('paste');
 await page.waitForFunction(()=>window.__state().text==='ApasteBCDEF');
 const selected=await page.evaluate(()=>window.__selection());check(()=>assert.deepEqual(selected,[6,6]));
 await click('select-all');await page.waitForFunction(()=>window.__selection()[1]===11);
 const selectAll=await page.evaluate(()=>window.__selection());check(()=>assert.deepEqual(selectAll,[0,11]));
 await click('export');await page.waitForFunction(()=>window.__state().downloads.length===1);
 state=await page.evaluate(()=>window.__state());
 check(()=>assert.equal(new TextDecoder().decode(new Uint8Array(state.downloads[0].bytes)),'ApasteBCDEF'));
 check(()=>assert.match(state.downloads[0].name,/^comfy_\d\d-\d\d-\d{4}_\d\d_\d\d_\d\d\.txt$/));
 await page.evaluate(()=>{window.__clipboardFail=true;});await click('paste');
 await page.waitForFunction(()=>window.__state().status.includes('clipboard'));
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.text,'ApasteBCDEF'));
 await page.evaluate(()=>{window.__clipboardFail=false;});
 await click('theme');await page.waitForFunction(()=>window.__state().properties.theme==='Light');
 await click('wrap');await page.waitForFunction(()=>window.__state().properties.word_wrap===false);
 await click('search');await page.waitForFunction(()=>window.__state().properties.text_filter===true);
 await page.evaluate(()=>window.__edit('viewer-search-input','BC'));
 await page.waitForFunction(()=>window.__state().html.includes('current-match')).catch(async error=>{console.error(JSON.stringify(await page.evaluate(()=>window.__state())));throw error;});
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.marks,'ApasteBCDEF'));check(()=>assert(state.html.includes('<span')));
 await page.evaluate(()=>window.__edit('viewer-search-input','(?=x)'));
 await page.waitForFunction(()=>!!window.__state().status);
 state=await page.evaluate(()=>window.__state());check(()=>assert.match(state.status,/unsupported|lookaround/i));
 await click('search');
 await page.evaluate(()=>window.__executed('5',['<script>unsafe</script> & plain']));
 await page.waitForFunction(()=>window.__state().text.startsWith('<script>'));
 await click('search');await page.waitForFunction(()=>window.__state().properties.text_filter===true);await page.evaluate(()=>window.__edit('viewer-search-input','unsafe'));
 await page.waitForFunction(()=>window.__state().html.includes('current-match'));
 state=await page.evaluate(()=>window.__state());check(()=>assert(!state.html.includes('<script>')));check(()=>assert.equal(state.marks,'<script>unsafe</script> & plain'));
 await click('search');
 await page.evaluate(()=>window.__executed('5',["{a:1,b:'two',}"]));await page.waitForFunction(()=>window.__state().text==="{a:1,b:'two',}");
 await click('pretty');await page.waitForFunction(()=>window.__state().text.includes('"a": 1'));
 const saved=await page.evaluate(()=>window.__serialize('5'));check(()=>assert.equal(saved.properties.pretty_json_mode,true));
 await page.evaluate(saved=>window.__newViewer(saved.properties),saved);
 await page.waitForFunction(()=>window.__otherText()?.includes('"a": 1'));
 const restored=await page.evaluate(()=>window.__otherText());check(()=>assert.equal(restored,JSON.stringify({a:1,b:'two'},null,2)));
 await page.evaluate(()=>window.__executed('6',['independent instance']));
 await page.waitForFunction(()=>window.__otherText()==='independent instance');
 state=await page.evaluate(()=>window.__state());check(()=>assert(state.text.includes('"a": 1')));
 await page.evaluate(()=>window.__changeFont('18'));await page.waitForFunction(()=>window.__state().properties.font_size===18);
 await page.evaluate(()=>window.__changeFont('73'));await page.waitForFunction(()=>window.__state().status.includes('6..72'));
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.properties.font_size,18));
 await page.evaluate(saved=>window.__configured('5',saved),saved);
 await page.waitForFunction(()=>window.__state().text.includes('"b": "two"'));
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.properties.theme,'Light'));
 await click('delete');await page.waitForFunction(()=>window.__state().confirmVisible);await click('cancel');
 await page.waitForFunction(()=>!window.__state().confirmVisible);state=await page.evaluate(()=>window.__state());check(()=>assert(state.text.includes('"a": 1')));
 await click('delete');await page.waitForFunction(()=>window.__state().confirmVisible);await click('confirm-delete');await page.waitForFunction(()=>window.__state().text==='');
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.commits.at(-1).value,''));
 await page.evaluate(()=>window.__widget('2','image','example.png'));
 await page.waitForFunction(()=>window.__state().readouts[1]?.includes('3x2')).catch(async error=>{console.error(JSON.stringify(await page.evaluate(()=>window.__state())));throw error;});
 state=await page.evaluate(()=>window.__state());check(()=>assert.match(state.readouts[1],/Ratio: 3:2 or 1.50:1/));
 for(const id of ['1','2','3']){await page.evaluate(id=>window.__executed(id,['dimensions','metadata']),id);
  await page.waitForFunction(id=>window.__state().readouts[Number(id)-1]?.includes('dimensions'),id);
  check(()=>assert(true));}
 await page.evaluate(()=>window.__widget('3','video','video.mp4'));
 await page.waitForFunction(()=>window.__state().readouts[2]?.includes('(Run node to see full metadata)'));
 state=await page.evaluate(()=>window.__state());check(()=>assert.match(state.readouts[2],/Ratio: Calculating/));
 for(const id of ['1','2','3']){
  const serialized=await page.evaluate(id=>window.__serialize(id),id);check(()=>assert(serialized&&Object.keys(serialized).length));
  await page.evaluate(({id,serialized})=>window.__configured(id,serialized),{id,serialized});
 }
 state=await page.evaluate(()=>window.__state());
 check(()=>assert.deepEqual(state.saveText.constraints,{minWidth:280,minHeight:100}));
 check(()=>assert.deepEqual(state.saveText.size,{width:320,height:120}));
 check(()=>assert.equal(state.saveText.options.placeholder,'Enter filename prefix (e.g., output/myfile)'));
 await click('filter');await page.waitForFunction(()=>window.__state().properties.line_filter===true);
 await page.evaluate(()=>window.__executed('5',['\nmatch\n']));
 await page.evaluate(()=>window.__edit('viewer-line-filter','^$'));
 await page.waitForFunction(()=>window.__state().text==='\n'&&window.__state().lineCounter==='2 lines')
  .catch(async error=>{console.error(JSON.stringify(await page.evaluate(()=>window.__state())));throw error;});
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.text,'\n'));
 await page.evaluate(()=>window.__edit('viewer-line-filter','absent'));
 await page.waitForFunction(()=>window.__state().lineCounter==='0 lines');
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.text,''));
 await click('filter');await page.waitForFunction(()=>window.__state().properties.line_filter===false);
 for(const value of ['', '\n', '\n\nstart', '\r\nstart']){
  await page.evaluate(value=>window.__executed('5',[value]),value);
  const normalized=value.replaceAll('\r\n','\n').replaceAll('\r','\n');
  await page.waitForFunction(value=>window.__state().text===value,normalized);
  state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.text,normalized));
 }
 await page.evaluate(()=>{window.__executed('5',['\n😀tail']);});
 await page.waitForFunction(()=>window.__state().text==='\n😀tail');
 await page.evaluate(()=>window.__select(1,3));
 const leadingCopyCount=(await page.evaluate(()=>window.__state())).writes.length;
 await click('copy');await page.waitForFunction(count=>window.__state().writes.length===count+1,leadingCopyCount);
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.writes.at(-1),'😀'));
 await page.evaluate(()=>{window.__select(1,3);window.__pasteText='X';});await click('paste');
 await page.waitForFunction(()=>window.__state().text==='\nXtail');
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.text,'\nXtail'));
 await page.evaluate(()=>window.__executed('5',['Positive: cat\nsecond line\n\nNegative: dog']));
 await page.waitForFunction(()=>window.__state().text.startsWith('Positive:'));
 const writesBeforePositive=(await page.evaluate(()=>window.__state())).writes.length;
 await click('copy-positive');await page.waitForFunction(count=>window.__state().writes.length===count+1,writesBeforePositive);
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.writes.at(-1),'cat\nsecond line'));
 await page.evaluate(()=>window.__executed('5',[Array.from({length:31},(_,i)=>i%10===0?'hit':'row '+i).join('\n')]));
 await page.waitForFunction(()=>window.__state().text.includes('row 30')||window.__state().text.endsWith('hit'));
 await click('search');await page.waitForFunction(()=>window.__state().properties.text_filter===true);
 await page.evaluate(()=>window.__edit('viewer-search-input','hit'));
 await page.waitForFunction(()=>window.__state().matchCounter==='1 / 4');
 await click('next');await page.waitForFunction(()=>window.__state().matchCounter==='2 / 4');
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.scrollTop,90));
 await click('previous');await page.waitForFunction(()=>window.__state().matchCounter==='1 / 4');
 state=await page.evaluate(()=>window.__state());check(()=>assert.equal(state.scrollTop,0));
 await click('search');await page.waitForFunction(()=>window.__state().properties.text_filter===false);
 await page.evaluate(()=>{window.__holdClipboard=true;});await click('paste');
 await page.waitForFunction(()=>typeof window.__releaseClipboard==='function');
 const beforeRemove=await page.evaluate(()=>window.__state().commits.length);
 await page.evaluate(()=>window.__remove('5'));await page.waitForFunction(()=>window.__state().panels===6);
 await page.evaluate(()=>window.__releaseClipboard());
 await page.waitForTimeout(150);check(()=>assert.deepEqual(errors,[]));
 state=await page.evaluate(()=>window.__state());check(()=>assert.deepEqual(state.errors,[]));
 const afterRemove=await page.evaluate(()=>window.__state().commits.length);check(()=>assert.equal(afterRemove,beforeRemove));
 const unaffected=await page.evaluate(()=>window.__otherText());check(()=>assert.equal(unaffected,'independent instance'));
 const finalElements=await page.evaluate(()=>window.__finish());check(()=>assert.equal(finalElements,0));
 console.log(JSON.stringify({passed:checks,failed:0,tier:'actual-opaque-worker/production-renderer/broker',
  qualification:'Actual five pack entries with trusted host graph/widgets/clipboard fixtures; not backend/fullpack/Cloud proof'}));
}catch(error){console.error(error);throw error;}finally{await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
