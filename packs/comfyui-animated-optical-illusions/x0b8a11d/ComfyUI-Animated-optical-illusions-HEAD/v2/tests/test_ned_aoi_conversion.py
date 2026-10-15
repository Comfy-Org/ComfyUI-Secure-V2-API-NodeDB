"""Whole interleaver: source strip quirks, quantization/alpha and actual guest."""
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
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-animated-optical-illusions/x0b8a11d/comfyui-animated-optical-illusions-x0b8a11d'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_aoi_old',PACK);NEW=load('ned_aoi_new',V2);CLS=NEW.NODE_CLASS_MAPPINGS['AOI_Processing_Zho'];CLS.GET_SCHEMA()
SOURCE=OLD.NODE_CLASS_MAPPINGS['AOI_Processing_Zho']
def fixture(batch=3,height=7,columns=13,channels=3,dtype=torch.float32):
 values=torch.arange(batch*height*columns*channels,dtype=torch.float64).reshape(batch,height,columns,channels)
 return ((values%311)/255-.1).to(dtype)
def same(a,b):
 assert len(a)==len(b)==2
 for x,y in zip(a,b):assert type(x) is torch.Tensor and x.dtype==y.dtype and x.shape==y.shape and torch.equal(x,y)
def differential(images,width):
 try:expected=SOURCE().aoi_processing(images,width)
 except Exception as native:
  with pytest.raises(type(native)):CLS.execute(images,width)
 else:same(CLS.execute(images,width).result,expected)
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{'AOI_Processing_Zho':{'module':'_secure_nodes','class':'AOISecure','sdk_refs':False,'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_actual_single_census_schema_and_unchanged_original_algorithm_file():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==['AOI_Processing_Zho']
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS=={'AOI_Processing_Zho':'AOI_Processing_Zho'}
 assert (PACK/'Animated_optical_illusions_Zho.py').read_bytes()==(V2/'Animated_optical_illusions_Zho.py').read_bytes()
 schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id==schema.display_name=='AOI_Processing_Zho' and schema.category==SOURCE.CATEGORY
 assert [o.io_type for o in schema.outputs]==['IMAGE','IMAGE'] and [o.display_name for o in schema.outputs]==['image','mask']
 for inp in schema.inputs:
  spec=SOURCE.INPUT_TYPES()['required'][inp.id];assert inp.io_type==spec[0] and not inp.optional
  if len(spec)>1:
   for key,value in spec[1].items():assert inp.as_dict()[key]==value
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_aoi_proxy')
 assert list(loaded.node_mappings)==['AOI_Processing_Zho'] and not loaded.routes and loaded.web_directory is None
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==('raw',)

@pytest.mark.parametrize('batch',[1,2,3,8])
@pytest.mark.parametrize('columns',[4,13,24,37])
@pytest.mark.parametrize('width',[1,2,3,4,9,100])
def test_exact_frame_order_partial_stripe_truncation_and_native_empty_groups(batch,columns,width):differential(fixture(batch=batch,columns=columns),width)

@pytest.mark.parametrize('channels',[1,2,3,4])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.uint8])
def test_exact_source_squeeze_pil_modes_and_dtype_quantization(channels,dtype):differential(fixture(channels=channels,dtype=dtype),2)

def test_discriminating_zip_truncation_and_transparent_white_alpha():
 images=torch.zeros((3,5,13,3));images[0]=.25;images[1]=.5;images[2]=1
 image,mask=CLS.execute(images,4).result
 same((image,mask),SOURCE().aoi_processing(images,4))
 assert image.shape==(1,5,12,3) and mask.shape==(1,5,12,4)
 assert torch.all(image[:,:,0:4]==63/255) and torch.all(image[:,:,4:8]==127/255) and torch.all(image[:,:,8:12]==1)
 assert torch.all(mask[:,:,:4,:3]==1) and torch.all(mask[:,:,:4,3]==0)
 assert torch.all(mask[:,:,4:,:3]==0) and torch.all(mask[:,:,4:,3]==1)

def test_seeded_quantization_noncontiguous_input_repeated_state_and_no_mutation():
 generator=torch.Generator().manual_seed(5521)
 for index in range(60):
  images=torch.rand((1+index%6,7,19,3),generator=generator)*2-.5
  before=images.clone();differential(images,1+index%10);assert torch.equal(images,before)
 images=fixture(columns=38)[:,:,::2,:];assert not images.is_contiguous();differential(images,2)
 same(CLS.execute(images,2).result,CLS.execute(images,2).result)

@pytest.mark.parametrize('shape',[(0,7,13,3),(3,0,13,3),(3,7,0,3),(3,1,13,3),(3,7,1,3),(3,7,13,0),(3,7,13,5)])
def test_native_empty_squeeze_and_pil_channel_error_controls(shape):differential(torch.zeros(shape),1)

@pytest.mark.parametrize('width',[True,0,101,1.5,None,'1'])
def test_declared_integer_width_admission(width):
 with pytest.raises(ValueError,match='width'):CLS.execute(fixture(),width)

def test_allocation_and_work_bounds_before_original_conversion(monkeypatch):
 mod=sys.modules[CLS.__module__]
 def forbidden(*a,**k):raise AssertionError('original source ran before admission')
 monkeypatch.setattr(mod.AOI_Processing_Zho,'aoi_processing',forbidden)
 for images,message in [(torch.empty((65,2,2,3)),'batch'),(torch.empty((1,2,4097,3)),'dimensions'),(torch.zeros(1).expand(64,512,512,3),'input byte'),(torch.zeros(1,dtype=torch.uint8).expand(1,2048,2048,3),'pixel'),(torch.zeros(1).expand(1,1024,1024,3),'workspace')]:
  with pytest.raises(ValueError,match=message):CLS.execute(images,1)
 with pytest.raises(ValueError,match='BHWC'):CLS.execute(torch.zeros((7,13,3)),1)

def test_default_width_real_512_batch_not_just_small_fixture():
 images=fixture(batch=3,height=512,columns=512)
 differential(images,1)
 assert CLS.execute(images,1).result[0].shape==(1,512,510,3)

def test_two_fresh_required_raw_guests_real_outer_images_pixels_errors_denial_recovery(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    with (fresh/'_secure_nodes.py').open('a') as probe:
     probe.write('\nclass NedRawDenialProbe(io.ComfyNode):\n    @classmethod\n    async def execute(cls):\n        from comfy_api.latest import sdk\n        return io.NodeOutput(await sdk.TensorRef.from_value(torch.zeros(1)))\n')
    cls=load('ned_aoi_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS['AOI_Processing_Zho'];cls.GET_SCHEMA()
    session=await GuestSession('ned-aoi-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=('raw',),tenant='aoi-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(images,width):
     result=await execution._async_map_node_over_list(prompt_id='aoi-outer',unique_id=str(render),obj=cls,input_data_all={'images':[images],'width':[width]},func=cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     for images,width in [(fixture(),4),(fixture(batch=2,channels=4),2),(fixture(batch=1,dtype=torch.float16),100),(fixture(batch=3,height=512,columns=512),1)]:same(await outer(images,width),SOURCE().aoi_processing(images,width))
     for images,width in [(fixture(batch=8,columns=4),100),(torch.zeros((0,7,13,3)),1)]:
      try:SOURCE().aoi_processing(images,width)
      except Exception as native:
       with pytest.raises(Exception,match=re.escape(type(native).__name__)):await outer(images,width)
      else:raise AssertionError('native fixture did not discriminate')
     with pytest.raises(Exception,match='width'):await outer(fixture(),True)
     with pytest.raises(Exception,match='workspace'):await outer(torch.zeros((1,1024,1024,3)),1)
     refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='aoi-denial',node_id='1',node_type=cls.__name__,node_module=cls.__module__,inputs={'images':fixture(),'width':1},permissions=('raw',),method='execute',input_types={'images':'IMAGE'})
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps());plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
     with pytest.raises(Exception,match='dense image tensor'):await session.execute(plan,runtime,capabilities=(),tenant='aoi-user-'+str(render))
     plan=_sdk.ExecutionPlan(prompt_id='aoi-probe',node_id='probe',node_type='NedRawDenialProbe',node_module=cls.__module__,inputs={},permissions=('raw',),method='execute')
     with pytest.raises(Exception,match='raw|permission|capabil'):await session.execute(plan,runtime,capabilities=(),tenant='aoi-user-'+str(render))
     same(await outer(fixture(),1),SOURCE().aoi_processing(fixture(),1));pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_provenance_gpl_resources_stubs_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes']
 assert (V2/'LICENSE').read_bytes()==(PACK/'LICENSE').read_bytes()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 text=(V2/'_secure_nodes.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in text
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_patch_bundle_two_exact_roundtrips_wrong_pristine_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-animated-optical-illusions/x0b8a11d';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-animated-optical-illusions/x0b8a11d';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as f:f.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
