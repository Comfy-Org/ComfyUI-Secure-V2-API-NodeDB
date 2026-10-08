import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {fileURLToPath} from 'node:url'
import {build} from '/Users/ben/comfy/ComfyUI_frontend-secure-nodes/node_modules/.pnpm/esbuild@0.28.1/node_modules/esbuild/lib/main.js'
import {chromium} from '/Users/ben/comfy/ComfyUI_frontend-secure-nodes/node_modules/.pnpm/playwright@1.61.1/node_modules/playwright/index.mjs'
const bundle=await build({entryPoints:[fileURLToPath(new URL('./ned_chibi_catalogue_entry.mjs',import.meta.url))],write:false,bundle:true,format:'esm',platform:'browser',alias:{'@':'/Users/ben/comfy/ComfyUI_frontend-secure-nodes/src'},
  plugins:[{name:'local-owner-facades',setup(builder){
    builder.onResolve({filter:/^@\/scripts\/api$|^@\/stores\/authStore$|^@\/platform\/distribution\/types$/},args=>({path:args.path,namespace:'fixture'}))
    builder.onLoad({filter:/.*/,namespace:'fixture'},args=>({contents:args.path.endsWith('/api')?'export const api=new EventTarget()':args.path.endsWith('/authStore')?'export function useAuthStore(){throw new Error("Cloud forbidden")}':'export const isCloud=false',loader:'js'}))
  }}]})
let names=['poses.txt','chibi-wildcards/deleted.txt','chibi-wildcards/current.txt'],reads=0
const server=createServer(async(req,res)=>{
  if(req.url==='/secure-nodes/text-files/input?prefix=chibi-wildcards/&suffix=.txt'){
    reads++;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(names))
  }else if(req.url==='/state'&&req.method==='POST'){
    let body='';for await(const chunk of req)body+=chunk;names=JSON.parse(body);res.end('ok')
  }else if(req.url==='/bundle.mjs'){res.setHeader('Content-Type','text/javascript');res.end(bundle.outputFiles[0].text)}
  else {res.setHeader('Content-Type','text/html');res.end('<!doctype html><script type="module" src="/bundle.mjs"></script>')}
})
await new Promise(done=>server.listen(0,'127.0.0.1',done))
const origin='http://127.0.0.1:'+server.address().port
const browser=await chromium.launch({headless:true})
try{
  const context=await browser.newContext()
  await context.route('**/*',route=>route.request().url().startsWith(origin+'/')?route.continue():route.abort())
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)))
  await page.goto(origin);await page.waitForFunction(()=>window.catalogueProof!==undefined)
  const r=await page.evaluate(()=>window.catalogueProof)
  assert.equal(r.bundled.length,10)
  assert.deepEqual(r.initial,{values:[...r.bundled,'chibi-wildcards/deleted.txt','chibi-wildcards/current.txt'],selected:r.bundled[0]})
  assert.deepEqual(r.isolated,['other.txt','poses.txt','chibi-wildcards/deleted.txt','chibi-wildcards/current.txt'])
  assert.deepEqual(r.raw,['poses.txt','chibi-wildcards/deleted.txt','chibi-wildcards/current.txt'])
  assert.deepEqual(r.refreshed,{values:[...r.bundled,'chibi-wildcards/current.txt'],selected:'chibi-wildcards/current.txt'})
  assert.deepEqual(r.empty,{values:r.bundled,selected:r.bundled.at(-1)})
  assert.equal(reads,3);assert.deepEqual(errors,[])
  console.log(JSON.stringify({status:'PASS',reads,result:r,browser:browser.version(),qualification:'Actual useRemoteWidget/Axios/native selects; local HTTP and graph/API/auth facades, not full app or Cloud.'}))
  await context.close()
}finally{await browser.close();await new Promise(done=>server.close(done))}
