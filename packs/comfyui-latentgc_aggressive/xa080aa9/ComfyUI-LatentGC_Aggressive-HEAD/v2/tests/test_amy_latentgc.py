"""Exact shallow-copy controls and actual managed cleanup/guest boundaries."""
import asyncio,copy,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
from unittest.mock import patch
import pytest
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution,torch,gc
import comfy.model_management as mm
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-latentgc_aggressive/xa080aa9/comfyui-latentgc_aggressive-xa080aa9'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('amy_gc_old',PACK);NEW=load('amy_gc_new',V2)
SOURCE=OLD.NODE_CLASS_MAPPINGS['LatentGC'];CLS=NEW.NODE_CLASS_MAPPINGS['LatentGC'];CLS.GET_SCHEMA()
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{'LatentGC':{'module':'nodes','class':'LatentGC_Aggressive','sdk_refs':False,'permissions':['raw','models.manage'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}
def same(a,b):
 if isinstance(a,torch.Tensor):
  assert a.shape==b.shape and a.dtype==b.dtype
  assert torch.equal(a.contiguous().reshape(-1).view(torch.uint8),b.contiguous().reshape(-1).view(torch.uint8))
 elif type(a) is dict:
  assert type(b) is dict and list(a)==list(b)
  for k in a:same(a[k],b[k])
 elif type(a) in (tuple,list):
  assert type(a) is type(b) and len(a)==len(b)
  for x,y in zip(a,b):same(x,y)
 else:assert type(a) is type(b) and a==b
def value(dtype=torch.float32,empty=False,view=False):
 samples=torch.arange(32,dtype=dtype).reshape(1,4,2,4)
 if empty:samples=samples[:0]
 if view:samples=samples[...,::2]
 return {'samples':samples,'noise_mask':torch.ones(1,2,4,dtype=dtype),'batch_index':[2,0],'spatial_downscale_ratio':8,'temporal_downscale_ratio':4,'extra':{'tuple':('a',1,False,None),'list':[0.25,-0.0,'λ😀']}}
def test_census_exact_schema_displays_proxy_authority():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==['LatentGC']
 assert not hasattr(OLD,'NODE_DISPLAY_NAME_MAPPINGS')
 schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id==schema.display_name=='LatentGC' and schema.category==SOURCE.CATEGORY
 assert [v.id for v in schema.inputs]==['samples'] and [v.io_type for v in schema.inputs]==['LATENT']
 assert [v.io_type for v in schema.outputs]==list(SOURCE.RETURN_TYPES)
 assert SOURCE.INPUT_TYPES()=={'required':{'samples':('LATENT',)}}
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==('raw','models.manage')
 proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_gc_proxy')
 assert list(proxy.node_mappings)==['LatentGC'] and not proxy.routes and proxy.web_directory is None

@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16,torch.uint8,torch.int64,torch.bool])
@pytest.mark.parametrize('empty,view',[(False,False),(True,False),(False,True)])
def test_source_shallow_copy_exact_values_aliases_and_three_ordered_service_calls(dtype,empty,view):
 # bool arange is unsupported natively; use a cast fixture, not a source repair.
 samples=value(torch.int64 if dtype is torch.bool else dtype,empty,view)
 if dtype is torch.bool:
  samples['samples']=samples['samples'].to(dtype);samples['noise_mask']=samples['noise_mask'].to(dtype)
 before=copy.deepcopy(samples);calls=[]
 with patch.object(gc,'collect',lambda:calls.append('gc')),patch.object(mm,'unload_all_models',lambda:calls.append('unload')),patch.object(mm,'soft_empty_cache',lambda:calls.append('cache')):
  native=SOURCE().tunnelLatents(samples)[0]
 assert calls==['gc','unload','cache'] and native is not samples
 for key in samples:assert native[key] is samples[key]
 class Models:
  async def memory_cleanup(self,**kw):
   calls.append(kw);return (100,100)
 calls.clear()
 with patch.object(sys.modules[CLS.__module__].sdk,'ctx',return_value=type('Ctx',(),{'models':Models()})()):
  converted=asyncio.run(CLS.execute(samples)).result[0]
 assert calls==[{'empty_cache':False,'collect_cycles':True,'unload_all_models':False},{'empty_cache':False,'collect_cycles':False,'unload_all_models':True},{'empty_cache':True,'collect_cycles':False,'unload_all_models':False}]
 assert converted is not samples
 for key in samples:assert converted[key] is samples[key]
 same(native,converted);same(samples,before)

@pytest.mark.parametrize('item',[object(),{1:'nonstrkey'},torch.sparse_coo_tensor(torch.tensor([[0],[0]]),torch.ones(1),(1,1))])
def test_unsupported_wire_values_fail_before_cleanup_without_metadata_stripping(item):
 with pytest.raises(TypeError,match='wire|dense'):asyncio.run(CLS.execute({'samples':torch.zeros(1,4,1,1),'opaque':item}))
def test_preflight_work_depth_cycles_and_backing_storage_bounds(monkeypatch):
 mod=sys.modules[CLS.__module__]
 with pytest.raises(ValueError,match='byte budget'):asyncio.run(CLS.execute({'samples':torch.empty(1,device='meta').as_strided((20000000,),(0,))}))
 with pytest.raises(ValueError,match='work'):asyncio.run(CLS.execute({'samples':torch.zeros(1,4,1,1),'rows':[0]*4097}))
 item={};item['self']=item
 with pytest.raises(ValueError,match='cyclic'):asyncio.run(CLS.execute(item))
 nested=0
 for _ in range(18):nested=[nested]
 with pytest.raises(ValueError,match='work'):asyncio.run(CLS.execute({'deep':nested}))
 with pytest.raises(TypeError,match='plain'):asyncio.run(CLS.execute(None))
 monkeypatch.setattr(mod,'MAX_BYTES',16)
 with pytest.raises(ValueError,match='byte budget'):asyncio.run(CLS.execute({'samples':torch.empty(100)[:1]}))

def test_two_fresh_required_guests_real_cleanup_outer_LATENT_alias_normalization_and_denials(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    cls=load('amy_gc_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS['LatentGC'];cls.GET_SCHEMA()
    session=await GuestSession('amy-gc-'+str(render),guest_runtime_root=fresh).start()
    caps=('raw','models.manage');calls=[];armed=[False]
    originals=(gc.collect,mm.unload_all_models,mm.soft_empty_cache)
    def spy(index,name):
     def call(*a,**kw):
      if armed[0]:calls.append(name)
      return originals[index](*a,**kw)
     return call
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=caps,tenant='amy-gc-user')
    _sdk.providers.register_execution_backend(Backend())
    async def outer(samples):
     r=await execution._async_map_node_over_list(prompt_id='amy-gc-outer',unique_id=str(render),obj=cls,input_data_all={'samples':[samples]},func=cls.FUNCTION,v3_data=None)
     return r[0].result[0]
    try:
     assert session.sandbox_kind=='seatbelt'
     for dtype in (torch.float32,torch.float16,torch.bfloat16):
      samples=value(dtype,view=True);before=copy.deepcopy(samples)
      with patch.object(gc,'collect',spy(0,'gc')),patch.object(mm,'unload_all_models',spy(1,'unload')),patch.object(mm,'soft_empty_cache',spy(2,'cache')):
       calls.clear();armed[0]=True
       try:actual=await outer(samples)
       finally:armed[0]=False
      assert calls[:3]==['gc','unload','cache']
      assert type(actual) is dict and actual is not samples
      same(actual,samples);same(samples,before)
     pids.append(session.last_guest_pid)
     calls.clear()
     armed[0]=True
     try:
      with pytest.raises(Exception,match='work budget'):
       await outer({'samples':torch.zeros(1,4,1,1),'extra':[0]*4097})
     finally:armed[0]=False
     assert not calls
     class Opaque:
      pass
     with pytest.raises(Exception,match='wire|opaque|unsupported|cannot|serializ'):
      await outer({'samples':torch.zeros(1,4,1,1),'unknown':Opaque()})
     same(await outer(value()),value())
     for denied in (('models.manage',),('raw',),()):
      caps=denied
      with pytest.raises(Exception,match='raw|models.manage|permission|capability'):await outer(value())
     caps=('raw','models.manage');same(await outer(value()),value())
     for denied in (('models.manage',),()):
      refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,{'samples':value()},{'samples':'LATENT'})
      plan=_sdk.ExecutionPlan(prompt_id='amy-gc-denial',node_id='deny',node_type='Probe',tier='sandbox',node_module='tests.amy_gc_permissions',inputs=wrapped,permissions=())
      with pytest.raises(Exception,match='raw|permission|capability'):
       await session.execute(plan,_sdk.Runtime(refs=refs,ctx=object(),ops=_sdk.InProcessOps()),capabilities=denied,tenant='amy-gc-user')
     assert not list(fresh.rglob('*.pyc'))
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_resources_stubs_imports_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text())
 hashes={f.relative_to(PACK).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in PACK.rglob('*') if f.is_file() and not f.is_relative_to(V2)}
 assert hashes==provenance['source_hashes'] and len(hashes)==4 and provenance['archive_all_paths_bytes_verified']
 assert (V2/'README.md').read_bytes()==(PACK/'README.md').read_bytes()
 assert not (PACK/'LICENSE').exists()
 for file,expected in [('comfy-api.pyi','4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:
  assert hashlib.sha256((V2/file).read_bytes()).hexdigest()==expected
 text=(V2/'nodes.py').read_text()
 for name in ('_from_raw','folder_paths','import nodes','comfy.model_management','PromptServer','subprocess','requests','eval(','exec(','open('):assert name not in text
 assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.js'))
def test_exact_patch_zip_twice_and_wrong_source_atomic_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes())==expected
 assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-latentgc_aggressive/xa080aa9';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  else:packpatch.apply(fresh,expected,diff)
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-latentgc_aggressive/xa080aa9';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'nodes.py').open('ab') as output:output.write(b'\n#badsource')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
