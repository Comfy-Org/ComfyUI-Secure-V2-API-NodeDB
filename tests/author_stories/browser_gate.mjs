import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
const {chromium}=createRequire(resolve(process.env.AUTHOR_BROWSER_DEPS,'package.json'))('@playwright/test');
const base=process.env.AUTHOR_BROWSER_BASE;
const root=process.env.AUTHOR_FRONTEND_FIXTURE;
const browser=await chromium.launch({headless:true});const page=await browser.newPage();const errors=[];page.setDefaultTimeout(15000);
page.on('pageerror',error=>errors.push(error.stack||String(error)));
page.on('console',message=>{if(message.type()==='error')console.error(message.text())});
try {
 await page.route('**/*', async route=>{const request=route.request();if(request.resourceType()==='fetch' && !new URL(request.url()).pathname.startsWith('/extensions/') && !new URL(request.url()).pathname.includes('/provider/') && !new URL(request.url()).pathname.endsWith('.json')){console.log('FIXTURE_HTTP',request.url());await route.fulfill({body:'{}',contentType:'application/json'});}else await route.fallback();});
 await page.route('**/extensions/MetadataStory/**',async route=>{
  const name=new URL(route.request().url()).pathname.split('/').at(-1);
  const body=name==='entry.js'?`import './SaveText_SG.js';import {comfy} from '/comfy/api/v2.js';
comfy.defs.extend('SimpleReadableMetadataSaveTextSG',builder=>builder.onCreated(node=>{
 node.widgets.get('filename_prefix').on('beforeSerialize',async event=>{
  await Promise.resolve();if(event.value==='refuse')throw Error('author projection refused');
  event.setSerializedValue(event.context+'_'+event.value);
 });
}));`:readFileSync(root+'/SaveText_SG.js','utf8');
  await route.fulfill({body,contentType:'text/javascript',headers:{'Access-Control-Allow-Origin':'*'}});
 });
 await page.route('**/comfy/api/v2.js',route=>route.fulfill({body:'export const comfy=globalThis.comfy',contentType:'text/javascript',headers:{'Access-Control-Allow-Origin':'*'}}));
 await page.route('**/provider/guest.mjs',route=>route.fulfill({body:readFileSync(root+'/provider/guest.mjs','utf8'),contentType:'text/javascript',headers:{'Access-Control-Allow-Origin':'*'}}));
 await page.goto(base+'/temp/author-stories/index.html');
 await page.waitForFunction(()=>typeof window.__start==='function');
 await page.evaluate(()=>window.__start());
 await page.waitForFunction(()=>window.__subscriptions()===1);
 const result=await page.evaluate(()=>window.__run());
 assert.deepEqual(result.saved,['workflow_author_Ω','txt',true]);
 assert.equal(result.live,'author_Ω');assert.equal(result.reopened,'workflow_author_Ω');
 assert.deepEqual(result.embedded,['embedded_author_Ω','txt',true]);assert.equal(result.prompt,'prompt_author_Ω');
 assert.match(result.refusal,/author projection refused/);assert.equal(result.recovered,'prompt_recovered');
 assert.equal(result.sandbox,'allow-scripts');assert.deepEqual(errors,[]);
 await page.evaluate(()=>window.__finish());
 console.log(JSON.stringify({pass:true,canonical_graph:true,opaque_worker:true,actual_metadata_save_text_frontend:true,definition_registration_fixture:true,...result}));
}catch(error){console.error(JSON.stringify({errors,state:await page.evaluate(()=>({start:typeof window.__start,body:document.body?.innerText})).catch(()=>null)}));throw error;}finally{await browser.close();}
