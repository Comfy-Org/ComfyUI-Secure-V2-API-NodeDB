"""Complete two-node zero latent math, all42choices, bounded5D guest transport."""
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution
import nodes
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-emptyhunyuanlatent/x3930b0f/comfyui-emptyhunyuanlatent-x3930b0f'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_hunyuanempty_old',PACK);NEW=load('ned_hunyuanempty_new',V2);IDS=list(OLD.NODE_CLASS_MAPPINGS)
for cls in NEW.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
CHOICES=OLD.NODE_CLASS_MAPPINGS[IDS[0]].INPUT_TYPES()['required']['resolution'][0]
def old(name,inputs):return OLD.NODE_CLASS_MAPPINGS[name]().generate(**inputs)
def new(name,inputs):return NEW.NODE_CLASS_MAPPINGS[name].execute(**inputs).result
def same(a,b):
 assert len(a)==len(b)==1 and type(a[0]) is type(b[0]) is dict and set(a[0])==set(b[0])=={'samples'}
 x,y=a[0]['samples'],b[0]['samples'];assert type(x) is torch.Tensor and x.shape==y.shape and x.dtype==y.dtype and x.device==y.device and torch.equal(x,y)
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{name:{'module':'_secure_nodes','class':cls.__name__,'sdk_refs':False,'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for name,cls in NEW.NODE_CLASS_MAPPINGS.items()}}

def test_actual_full_schema_choices_category_and_public_proxy_census():
 assert IDS==list(NEW.NODE_CLASS_MAPPINGS)==['EmptyHunyuanLatentForImage','EmptyHunyuanLatentForVideo']
 assert not hasattr(OLD,'NODE_DISPLAY_NAME_MAPPINGS') and not hasattr(NEW,'NODE_DISPLAY_NAME_MAPPINGS')
 assert len(CHOICES)==42 and nodes.MAX_RESOLUTION==16384
 for name in IDS:
  cls=NEW.NODE_CLASS_MAPPINGS[name];schema=cls.GET_SCHEMA();schema.validate();source=OLD.NODE_CLASS_MAPPINGS[name]
  assert schema.node_id==name and schema.category==source.CATEGORY and [o.io_type for o in schema.outputs]==['LATENT']
  assert [i.id for i in schema.inputs]==list(source.INPUT_TYPES()['required'])
  for inp in schema.inputs:
   spec=source.INPUT_TYPES()['required'][inp.id];assert not inp.optional
   if isinstance(spec[0],list):assert inp.options==spec[0]
   else:
    assert inp.io_type==spec[0]
    for key,value in spec[1].items():assert inp.as_dict()[key]==value
  assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==('raw',)
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_hunyuanempty_proxy')
 assert list(loaded.node_mappings)==IDS and not loaded.routes and loaded.web_directory is None

@pytest.mark.parametrize('name',IDS)
@pytest.mark.parametrize('resolution',CHOICES)
def test_all42ordered_resolution_choices_exact_shapes_zeros_and_float32(name,resolution):
 inputs={'resolution':resolution,'batch_size':1}
 if name==IDS[1]:inputs['length']=25
 same(new(name,inputs),old(name,inputs))

@pytest.mark.parametrize('length',[0,1,2,3,4,5,8,9,24,25,26,29,33,65])
@pytest.mark.parametrize('batch',[0,1,3])
def test_video_temporal_integer_floor_boundaries_batch_and_zero_axes(length,batch):
 inputs={'resolution':'256x384 (2:3)','length':length,'batch_size':batch}
 same(new(IDS[1],inputs),old(IDS[1],inputs))
 assert new(IDS[1],inputs)[0]['samples'].shape==(batch,16,((length-1)//4)+1,48,32)

@pytest.mark.parametrize('name',IDS)
@pytest.mark.parametrize('resolution',['15x15 custom','17x31 custom','33x47 ignored trailing text','0x256','256x0','nonsense','256X256','256xabc','256x256x256'])
def test_offmenu_floor16_zero_dimension_and_native_parse_failure_controls(name,resolution):
 inputs={'resolution':resolution,'batch_size':1}
 if name==IDS[1]:inputs['length']=25
 try:expected=old(name,inputs)
 except Exception as native:
  with pytest.raises(type(native)):new(name,inputs)
 else:same(new(name,inputs),expected)

def test_source_ast_math_unchanged_except_explicit_local_cpu_and_closed_max():
 def tree(path):
  value=ast.parse(path.read_text())
  # Remove only host imports/closed equivalent MAX declaration and normalize
  # the two explicit allocation-device expressions for algorithm comparison.
  value.body=[n for n in value.body if not (isinstance(n,ast.Import) and any(a.name in ('nodes','comfy.model_management') for a in n.names)) and not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAX_RESOLUTION' for t in n.targets))]
  class Normalize(ast.NodeTransformer):
   def visit_keyword(self,n):
    if n.arg=='device':n.value=ast.Constant(value='closed-device')
    return self.generic_visit(n)
   def visit_Attribute(self,n):
    if isinstance(n.value,ast.Name) and n.value.id=='nodes' and n.attr=='MAX_RESOLUTION':return ast.Name(id='MAX_RESOLUTION',ctx=ast.Load())
    return self.generic_visit(n)
  return ast.dump(Normalize().visit(value),include_attributes=False)
 assert tree(PACK/'nodes_hunyuan.py')==tree(V2/'nodes_hunyuan.py')

def test_trusted_local_float64_default_policy_preserved_and_source_global_not_changed():
 previous=torch.get_default_dtype()
 try:
  torch.set_default_dtype(torch.float64)
  for name in IDS:
   inputs={'resolution':CHOICES[0],'batch_size':2}
   if name==IDS[1]:inputs['length']=9
   same(new(name,inputs),old(name,inputs));assert new(name,inputs)[0]['samples'].dtype==torch.float64
 finally:torch.set_default_dtype(previous)

@pytest.mark.parametrize('name',IDS)
@pytest.mark.parametrize('bad',[True,-1,4097,1.5,None,'1'])
def test_batch_admission_no_implicit_casts(name,bad):
 inputs={'resolution':CHOICES[0],'batch_size':bad}
 if name==IDS[1]:inputs['length']=25
 with pytest.raises(ValueError):new(name,inputs)

@pytest.mark.parametrize('bad',[True,-1,16385,1.5,'25'])
def test_length_closed_integer_admission(bad):
 with pytest.raises(ValueError):new(IDS[1],{'resolution':CHOICES[0],'length':bad})

def test_whole_5d_budget_before_tensor_allocation(monkeypatch):
 mod=sys.modules[NEW.NODE_CLASS_MAPPINGS[IDS[0]].__module__]
 def forbidden(*args,**kwargs):raise AssertionError('allocation preceded preflight')
 monkeypatch.setattr(mod.source.torch,'zeros',forbidden)
 for name,values in [(IDS[0],{'resolution':'16384x16384','batch_size':1}),(IDS[1],{'resolution':'1728x576','batch_size':4096,'length':16384}),(IDS[1],{'resolution':'256x256','batch_size':64,'length':129})]:
  with pytest.raises(ValueError,match='budget'):new(name,values)
 with pytest.raises(ValueError,match='dimension'):new(IDS[0],{'resolution':'16400x256'})
 with pytest.raises(ValueError,match='bounded resolution'):new(IDS[0],{'resolution':'1x1 '+'x'*1025})

def test_required_video_length_not_invented_default():
 with pytest.raises(TypeError):old(IDS[1],{'resolution':CHOICES[0]})
 with pytest.raises(TypeError):new(IDS[1],{'resolution':CHOICES[0]})

def test_two_fresh_raw_guests_real_outer_latent_5d_allchoices_limits_and_denial(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    with (fresh/'_secure_nodes.py').open('a') as probe:
     probe.write('\nclass NedRawDenialProbe(io.ComfyNode):\n    @classmethod\n    async def execute(cls):\n        import torch\n        from comfy_api.latest import sdk\n        return io.NodeOutput(await sdk.TensorRef.from_value(torch.zeros(1)))\n')
    module=load('ned_hunyuanempty_fresh_'+str(render),fresh)
    for cls in module.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
    session=await GuestSession('ned-hunyuanempty-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=('raw',),tenant='hunyuan-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(name,inputs):
     cls=module.NODE_CLASS_MAPPINGS[name]
     result=await execution._async_map_node_over_list(prompt_id='hunyuan-outer',unique_id=name,obj=cls,input_data_all={key:[value] for key,value in inputs.items()},func=cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     for name in IDS:
      for resolution in CHOICES:
       inputs={'resolution':resolution,'batch_size':1}
       if name==IDS[1]:inputs['length']=25
       same(await outer(name,inputs),old(name,inputs))
      inputs={'resolution':'17x31','batch_size':3}
      if name==IDS[1]:inputs['length']=0
      same(await outer(name,inputs),old(name,inputs))
      inputs={'resolution':'nonsense','batch_size':1}
      if name==IDS[1]:inputs['length']=25
      with pytest.raises(Exception,match='ValueError'):await outer(name,inputs)
     with pytest.raises(Exception,match='budget'):await outer(IDS[1],{'resolution':CHOICES[-1],'batch_size':4096,'length':16384})
     refs=_sdk.InProcessRefResolver();cls=module.NODE_CLASS_MAPPINGS[IDS[0]]
     plan=_sdk.ExecutionPlan(prompt_id='hunyuan-denial',node_id='1',node_type=cls.__name__,node_module=cls.__module__,inputs={'resolution':CHOICES[0],'batch_size':1},permissions=('raw',),method='execute')
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
     # With no raw, value-mode output stays an unmarshalable tensor, never a
     # published handle; explicit public raw denial is checked separately.
     with pytest.raises(Exception,match='Tensor cannot cross the guest wire'):await session.execute(plan,runtime,capabilities=(),tenant='hunyuan-user-'+str(render))
     probe_plan=_sdk.ExecutionPlan(prompt_id='hunyuan-probe',node_id='probe',node_type='NedRawDenialProbe',node_module=cls.__module__,inputs={},permissions=('raw',),method='execute')
     with pytest.raises(Exception,match='raw|permission|capabil'):await session.execute(probe_plan,runtime,capabilities=(),tenant='hunyuan-user-'+str(render))
     same(await outer(IDS[0],{'resolution':CHOICES[0]}),old(IDS[0],{'resolution':CHOICES[0]}));pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_all_resources_workflows_missing_license_stubs_pristine_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes'] and len(pristine)==8
 for name in pristine:
  if name not in ('__init__.py','nodes_hunyuan.py','pyproject.toml'):assert (PACK/name).read_bytes()==(V2/name).read_bytes()
 assert not list(PACK.rglob('LICENSE*')) and 'MIT' in (PACK/'README.md').read_text()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 text=(V2/'_secure_nodes.py').read_text()+(V2/'nodes_hunyuan.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','comfy.model_management','eval(', 'exec(', 'open('):assert forbidden not in text
 for name in ('_secure_nodes.py','nodes_hunyuan.py'):
  for item in ast.walk(ast.parse((V2/name).read_text())):
   if isinstance(item,ast.Import):assert all(alias.name!='nodes' for alias in item.names)
   if isinstance(item,ast.ImportFrom):assert item.level or item.module!='nodes'
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_patch_bundle_two_exact_roundtrips_and_wrong_pristine_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-emptyhunyuanlatent/x3930b0f';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-emptyhunyuanlatent/x3930b0f';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'nodes_hunyuan.py').open('ab') as f:f.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
