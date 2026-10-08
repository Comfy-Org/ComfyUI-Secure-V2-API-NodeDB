import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
const {chromium}=createRequire(resolve(process.env.AUTHOR_BROWSER_DEPS,'package.json'))('@playwright/test');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();const errors=[];
page.on('pageerror',error=>errors.push(String(error)));
try {
 await page.goto(process.argv[2]);
 await page.waitForFunction(()=>typeof window.__start==='function');
 await page.evaluate(()=>window.__start());
 await page.waitForFunction(()=>window.__state().reports.some(x=>x.phase==='written'));
 let state=await page.evaluate(()=>window.__state());
 assert.equal(state.sandbox,'allow-scripts');assert.equal(state.reports.at(-1).same,true);
 await page.evaluate(()=>window.__rebuild());
 await page.waitForFunction(()=>window.__state().reports.some(x=>x.phase==='fresh-read'));
 state=await page.evaluate(()=>window.__state());assert.equal(state.reports.at(-1).same,true);
 assert.deepEqual(errors,[]);
 await page.evaluate(()=>window.__finish());
 console.log(JSON.stringify({opaque_worker:true,production_host_storage_call:true,fresh_worker_read:true,errors,reports:state.reports}));
} finally {await browser.close();}
