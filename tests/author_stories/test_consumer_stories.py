"""Actual converted pack consumers against the candidate provider, no shared edits."""
import asyncio,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
CORE=Path(os.environ['COMFY_CORE_ROOT']);OVERLAY=Path(os.environ['MANY_OVERLAY_ROOT'])
PROFILE=json.loads(Path(os.environ['AUTHOR_RUNTIME_PROFILE']).read_text())
sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy.cli_args import args
args.cpu=True
import execution,torch
from comfy_api.latest import _sdk
from comfy_secure_nodes import storage,packstorage_routes
from comfy_secure_nodes.transport.host import GuestSession
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
def load(name,root):
 s=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
 m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def bits(a,b):
 assert a.shape==b.shape and a.dtype==b.dtype
 assert torch.equal(a.contiguous().reshape(-1).view(torch.uint8),b.contiguous().reshape(-1).view(torch.uint8))
def test_declared_wheels_actually_execute_without_acquiring_default_network(tmp_path):
 import socket
 async def run():
  root=tmp_path/'authority';shutil.copytree(HERE/'consumer_pack',root);mod=load('many_authority_gate',root)
  module=__import__(mod.__name__+'.runtime_probe',fromlist=['RuntimeAuthorityProbe']);cls=module.RuntimeAuthorityProbe;cls.GET_SCHEMA()
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.setblocking(False)
  session=await GuestSession('many-authority',guest_runtime_root=root).start()
  prior=_sdk.providers.execution_backend
  class Backend:
   async def dispatch(self,plan,local_call,runtime):
    assert not plan.permissions
    return await session.execute(plan,runtime,capabilities=(),tenant='account-a')
  _sdk.providers.register_execution_backend(Backend())
  try:
   assert session.sandbox_kind==PROFILE['sandbox_kind']
   result=await execution._async_map_node_over_list('authority','1',cls,{'port':[listener.getsockname()[1]]},cls.FUNCTION)
   data=json.loads((await execution.resolve_map_node_over_list_results(result))[0].result[0]);assert data['denied']is True
   assert data['numpy']==PROFILE['numpy']and data['opencv']==PROFILE['opencv']and data['torch'].split('+')[0]==PROFILE['torch']
   assert data['denial_errno']in PROFILE['network_denial_errno']
   with pytest.raises(BlockingIOError):listener.accept()
   print('actual wheel/native authority gate',session.last_guest_pid,json.dumps(data,sort_keys=True))
  finally:await session.kill();listener.close();_sdk.providers.register_execution_backend(prior)
 asyncio.run(run())
def test_actual_mask_algorithm_named_data_hit_miss_expiry_fresh_render_account_pack_isolation(tmp_path,monkeypatch):
 now=[1_700_000_000_000];monkeypatch.setattr(storage,'_now_ms',lambda:now[0])
 backing=tmp_path/'backing';monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
 pids=[];root_ids=[]
 async def render(number,value,algorithm,tenant='account-a',owner='mask-pack',caps=('inspect','raw','storage')):
  # Recreated files, refs and process each time; only host-owned DATA survives.
  root=tmp_path/f'root-{number}';shutil.copytree(HERE/'consumer_pack',root);root_ids.append(str(root))
  mod=load(f'many_author_story_{number}',root);cls=mod.CachedMaskAlgorithm;cls.GET_SCHEMA()
  session=await GuestSession(owner,guest_runtime_root=root).start()
  class Backend:
   async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=caps,tenant=tenant)
  previous=_sdk.providers.execution_backend;_sdk.providers.register_execution_backend(Backend())
  try:
   assert session.sandbox_kind==PROFILE['sandbox_kind']
   fields={'mask':[value],'algorithm':[algorithm],'name':['shared-name'],'ttl_seconds':[5]}
   mapped=await execution._async_map_node_over_list('author-story','1',cls,fields,cls.FUNCTION)
   result=(await execution.resolve_map_node_over_list_results(mapped))[0].result
   assert session.last_guest_pid not in (None,os.getpid());pids.append(session.last_guest_pid)
   assert result[2]==pids[-1];return result
  finally:_sdk.providers.register_execution_backend(previous);await session.kill()
 async def run():
  value=torch.zeros((1,9,12),dtype=torch.float64);value[:,1:8,2]=1;value[:,7,2:10]=1;value[:,1:8,9]=1
  for offset,algorithm in enumerate(['MaskToConvexMask','MaskToBottonHalfConvexMask']):
   source=load(f'many_source_{offset}',HERE/'source_original');expected=source.NODE_CLASS_MAPPINGS[algorithm]().generate_convex_mask(value)[0]
   first=await render(offset*10,value,algorithm);assert first[1]is False;bits(first[0],expected)
   # Reopen backing as a new provider object; no process-global cache proof.
   monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
   second=await render(offset*10+1,value,algorithm);assert second[1]is True;bits(second[0],expected);assert first[3]==second[3]
   second[0].zero_();third=await render(offset*10+2,value,algorithm);assert third[1]is True;bits(third[0],expected)
   for n,tenant,owner in [(3,'account-b','mask-pack'),(4,'account-a','other-pack')]:
    foreign=await render(offset*10+n,value,algorithm,tenant,owner);assert foreign[1]is False;bits(foreign[0],expected)
   now[0]+=5000
   expired=await render(offset*10+5,value,algorithm);assert expired[1]is False;bits(expired[0],expected)
   recovered=await render(offset*10+6,value,algorithm);assert recovered[1]is True;bits(recovered[0],expected)
   with pytest.raises(Exception):await render(offset*10+7,value,algorithm,caps=('inspect','raw'))
   recovery=await render(offset*10+8,value,algorithm);assert recovery[1]is True;bits(recovery[0],expected)
  assert len(set(pids))==len(pids)and len(set(root_ids))==len(root_ids)
  assert list(backing.rglob('*.safetensors'))
  print('DATA cache actual fresh guest PIDs',pids)
 asyncio.run(run())

def test_frontend_http_authored_text_read_by_actual_comfyroll_node_in_recreated_render(tmp_path,monkeypatch):
 # Real opaque worker, authoritative HTTP relay, then fresh Python guest.
 backing=tmp_path/'documents';monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
 monkeypatch.setattr(packstorage_routes,'_OWNERS',{})
 monkeypatch.delenv('COMFY_TENANT_ID',raising=False);monkeypatch.delenv('COMFY_SECURE_REALM_ROOT',raising=False)
 owner='ComfyrollAuthorStory';pack_id='development/'+owner
 registered=SimpleNamespace(name=owner,web_directory=tmp_path,runtime=SimpleNamespace(pack_id=pack_id))
 packstorage_routes.register(registered);uid=packstorage_routes.base_for(owner)
 @web.middleware
 async def authenticated_fixture(request,handler):
  request['comfy_secure_tenant_id']='account-a'
  return await handler(request)
 async def render(generation,tenant='account-a',session_owner=owner):
  root=tmp_path/f'comfyroll-{generation}';shutil.copytree(HERE/'templates/comfyroll',root)
  mod=load(f'many_story_comfyroll_{generation}',root);cls=mod.NODE_CLASS_MAPPINGS['CR Load Text List'];cls.GET_SCHEMA()
  session=await GuestSession(session_owner,guest_runtime_root=root).start()
  class Backend:
   async def dispatch(self,plan,local_call,runtime):
    return await session.execute(plan,runtime,capabilities=('storage','assets'),tenant=tenant)
  prior=_sdk.providers.execution_backend;_sdk.providers.register_execution_backend(Backend())
  try:
   assert session.sandbox_kind==PROFILE['sandbox_kind']
   fields={'input_file_path':['author-story'],'file_name':['notes'],'file_extension':['txt']}
   mapped=await execution._async_map_node_over_list('story-document','1',cls,fields,cls.FUNCTION)
   return (await execution.resolve_map_node_over_list_results(mapped))[0],session.last_guest_pid
  finally:_sdk.providers.register_execution_backend(prior);await session.kill()
 async def run():
  sample=load('many_story_comfyroll_document_schema',HERE/'templates/comfyroll')
  text=__import__(sample.__name__+'.secure_text_artifacts',fromlist=['_identity'])
  identity=text._identity('author-story','notes','txt');key=text._key(identity)
  payload='frontend line one\r\nsecond line Ω';record=text._encode(identity,payload)
  server=SimpleNamespace(routes=web.RouteTableDef());packstorage_routes.register_routes(server)
  app=web.Application(middlewares=[authenticated_fixture]);app.add_routes(server.routes)
  # Serve the actual candidate host/guest, with only graph APIs left as a
  # trusted fixture. The untrusted writer runs in the real opaque worker.
  async def frontend(request):
   path=request.path
   if path=='/':
    page="""<!doctype html><meta charset="utf-8"><script type="module">
import {SecureExtensionHost} from '/src/host-entry.mjs';
const reports=[];
const response=x=>({ok:true,status:200,text:async()=>JSON.stringify(x),json:async()=>x});
const comfy={backend:{url:x=>new URL(x,location.origin).href,fetch:async (url,init)=>{
 if(url==='/object_info')return response({});
 if(url.startsWith('/secure-nodes/extensions/'))return response({capabilities:[],storage_base:STORAGE_UID});
 if(url==='/report'){reports.push(JSON.parse(init.body));return response({});}
 return fetch(url,init);
}},graph:{nodes:()=>[],node:()=>undefined,groups:()=>[]},workflow:{documentId:()=> 'author-story'},onWorkflowLoaded:()=>()=>{},defs:{extend:()=>()=>{}}};
let host;const start=()=>host=new SecureExtensionHost({comfy,bootstrapUrl:'/guest.js',match:()=>true,capabilities:[]});start();
window.__start=()=>host.load('/extensions/ComfyrollAuthorStory/write.js');
window.__rebuild=()=>{host.destroy();start();return host.load('/extensions/ComfyrollAuthorStory/read.js');};
window.__state=()=>({reports,sandbox:document.querySelector('iframe')?.getAttribute('sandbox')});
window.__finish=()=>host.destroy();
</script>""".replace('STORAGE_UID',json.dumps(uid))
    return web.Response(text=page,content_type='text/html')
   if path.startswith('/extensions/ComfyrollAuthorStory/'):
    write=path.endswith('/write.js')
    action='await comfy.storage.set(key,record);'if write else''
    body="import {comfy} from '/comfy/api/v2.js';const key="+json.dumps(key)+",record="+json.dumps(record)+";"+action+"const same=(await comfy.storage.get(key))===record;await comfy.backend.fetch('/report',{method:'POST',body:JSON.stringify({phase:"+json.dumps('written'if write else'fresh-read')+",same})});"
    return web.Response(text=body,content_type='text/javascript',headers={'Access-Control-Allow-Origin':'*'})
   if path=='/comfy/api/v2.js':return web.Response(text='export const comfy=globalThis.comfy',content_type='text/javascript',headers={'Access-Control-Allow-Origin':'*'})
   name='guest.mjs'if path=='/guest.js'else path.removeprefix('/src/')
   if not(path=='/guest.js'or path.startswith('/src/')):raise web.HTTPNotFound()
   if '..'in name or name.startswith('/'):raise web.HTTPNotFound()
   file=OVERLAY/'frontend/src'/name
   if not file.is_file():raise web.HTTPNotFound()
   return web.Response(body=file.read_bytes(),content_type='text/javascript',headers={'Access-Control-Allow-Origin':'*'})
  app.router.add_get('/{tail:.*}',frontend)
  async with TestClient(TestServer(app))as client:
   prefix=f'/secure-nodes/storage/{uid}'
   process=await asyncio.create_subprocess_exec(os.environ['AUTHOR_NODE'],str(HERE/'worker_storage_gate.mjs'),str(client.make_url('/')),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
   stdout,_=await asyncio.wait_for(process.communicate(),timeout=40)
   print('OPAQUE_WORKER_SHARED_DOCUMENT',stdout.decode())
   assert process.returncode==0,stdout.decode()
   first,pid1=await render(1);assert first.result[0]==['frontend line one\n','second line Ω']
   # Recreated backing and pack filesystem: persisted authored document remains.
   monkeypatch.setattr(storage,'_STORAGE',storage.PackStorage(backing))
   second,pid2=await render(2);assert second.result==first.result and pid1!=pid2
   assert storage.host_storage().get('account-b',pack_id,key)is None
   assert storage.host_storage().get('account-a','development/ForeignAuthorStory',key)is None
   # Corruption is visible; the actual node never silently imports/replaces KV.
   response=await client.post(prefix+'/set',json={'name':key,'value':'corrupt'});assert response.status==200
   with pytest.raises(Exception,match='Corrupt'):await render(3)
   response=await client.post(prefix+'/set',json={'name':key,'value':record});assert response.status==200
   recovered,pid4=await render(4);assert recovered.result==first.result
   response=await client.post(prefix+'/get',json={'name':key});assert await response.json()=={'value':record}
   packstorage_routes.unregister(owner)
   response=await client.post(prefix+'/get',json={'name':key});assert response.status==404
   print('actual Comfyroll persisted reader guest PIDs',pid1,pid2,pid4)
 asyncio.run(run())
