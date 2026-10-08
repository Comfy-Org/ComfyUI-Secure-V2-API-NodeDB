"""Pixel-exact image/mask paste including native quantization and zip quirks."""
import asyncio
import ast
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
PAIR=DB/'patches/comfyui-imgmask2png/xa7ae08c/comfyui-imgmask2png-xa7ae08c'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_imgmask_old',PACK);NEW=load('ned_imgmask_new',V2);CLS=NEW.NODE_CLASS_MAPPINGS['ImageMask2PNG'];CLS.GET_SCHEMA()
SOURCE=OLD.NODE_CLASS_MAPPINGS['ImageMask2PNG']
def fixture(ib=2,mb=2,height=7,columns=13,channels=3,mh=7,mw=13,dtype=torch.float32):
 image=((torch.arange(ib*height*columns*channels,dtype=torch.float64).reshape(ib,height,columns,channels)%311)/255-.1).to(dtype)
 mask=((torch.arange(mb*mh*mw,dtype=torch.float64).reshape(mb,mh,mw)%199)/150-.2).to(dtype)
 return mask,image
def same(actual,expected):
 assert len(actual)==len(expected)==1
 a,b=actual[0],expected[0]
 assert type(a) is torch.Tensor and a.dtype==b.dtype==torch.float32 and a.shape==b.shape and torch.equal(a,b)
def differential(mask,image):
 try:expected=SOURCE().remove_background(mask,image)
 except Exception as native:
  with pytest.raises(type(native)):CLS.execute(mask,image)
 else:same(CLS.execute(mask,image).result,expected)
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{'ImageMask2PNG':{'module':'_secure_nodes','class':'ImageMaskSecure','sdk_refs':False,'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_single_census_schema_proxy_and_byte_exact_source():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==['ImageMask2PNG']
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS=={'ImageMask2PNG':'🌊ImageMask2PNG'}
 assert (PACK/'imgmask2png.py').read_bytes()==(V2/'imgmask2png.py').read_bytes()
 schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id=='ImageMask2PNG' and schema.display_name=='🌊ImageMask2PNG' and schema.category==SOURCE.CATEGORY
 assert [o.io_type for o in schema.outputs]==['IMAGE'] and [o.display_name for o in schema.outputs]==['image']
 assert [(i.id,i.io_type,i.optional) for i in schema.inputs]==[('mask','MASK',False),('image','IMAGE',False)]
 assert SOURCE.INPUT_TYPES()=={'required':{'mask':('MASK',),'image':('IMAGE',)}}
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_imgmask_proxy')
 assert list(loaded.node_mappings)==['ImageMask2PNG'] and not loaded.routes and loaded.web_directory is None
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==('raw',)

@pytest.mark.parametrize('ib,mb',[(1,1),(1,3),(3,1),(2,2)])
@pytest.mark.parametrize('mh,mw',[(7,13),(3,5),(14,26)])
@pytest.mark.parametrize('channels',[1,2,3,4])
def test_exact_lanczos_paste_modes_and_unequal_batch_zip(ib,mb,mh,mw,channels):differential(*fixture(ib=ib,mb=mb,mh=mh,mw=mw,channels=channels))

@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.uint8,torch.int16,torch.bool,torch.bfloat16])
@pytest.mark.parametrize('channels',[1,2,3,4])
def test_source_dtype_quantization_and_bfloat_numpy_native_error(dtype,channels):differential(*fixture(channels=channels,dtype=dtype))

def test_discriminating_rgb_and_alpha_scale_not_alpha_only():
 image=torch.ones((3,2,3,4));image[...,3]=.5
 mask=torch.zeros((2,2,3));mask[0]=.5;mask[1]=1
 actual=CLS.execute(mask,image).result;same(actual,SOURCE().remove_background(mask,image))
 assert actual[0].shape==(2,2,3,4)
 assert torch.all(actual[0][0,:,:,:3]==127/255) and torch.all(actual[0][0,:,:,3]==63/255)
 assert torch.all(actual[0][1,:,:,:3]==1) and torch.all(actual[0][1,:,:,3]==127/255)
 assert torch.equal(CLS.execute(torch.zeros_like(mask),image).result[0],torch.zeros((2,2,3,4)))

def test_seeded_pixels_resize_noncontiguous_state_and_input_identity():
 g=torch.Generator().manual_seed(5182)
 for index in range(80):
  image=torch.rand((1+index%4,7,13,1+index%4),generator=g)*2-.5
  mask=torch.rand((1+(index+2)%4,3+index%5,5+index%7),generator=g)*2-.5
  before=(mask.clone(),image.clone());differential(mask,image)
  assert torch.equal(mask,before[0]) and torch.equal(image,before[1])
 mask,image=fixture(columns=26,mw=26);image=image[:,:,::2,:];mask=mask[:,:,::2]
 assert not image.is_contiguous() and not mask.is_contiguous();differential(mask,image)
 same(CLS.execute(mask,image).result,CLS.execute(mask,image).result)

@pytest.mark.parametrize('shape',[(0,7,13,3),(1,0,13,3),(1,7,0,3),(1,1,13,3),(1,7,1,3),(1,7,13,0),(1,7,13,5)])
def test_native_empty_squeeze_image_channel_controls(shape):differential(torch.zeros((1,7,13)),torch.zeros(shape))

@pytest.mark.parametrize('shape',[(0,7,13),(1,0,13),(1,7,0),(1,1,13),(1,7,1)])
def test_native_mask_empty_squeeze_controls(shape):differential(torch.zeros(shape),torch.zeros((1,7,13,3)))

def test_native_nonfinite_quantization_values():
 mask,image=fixture();mask[0,0,:3]=torch.tensor([float('nan'),float('inf'),-float('inf')]);image[0,0,0,:]=float('nan')
 differential(mask,image)

def test_preallocation_bounds_do_not_run_original_pillow(monkeypatch):
 mod=sys.modules[CLS.__module__]
 def forbidden(*a,**k):raise AssertionError('source ran before admission')
 monkeypatch.setattr(mod.ImageMask2PNG,'remove_background',forbidden)
 cases=[(torch.zeros((1,2,2)),torch.empty((65,2,2,3)),'dimensions'),
        (torch.empty((1,2,4097)),torch.zeros((1,2,2,3)),'dimensions'),
        (torch.zeros(1).expand(64,512,512),torch.zeros(1).expand(64,512,512,3),'input byte'),
        (torch.zeros(1,dtype=torch.uint8).expand(16,600,600),torch.zeros(1,dtype=torch.uint8).expand(16,600,600,3),'output byte'),
        (torch.zeros(1).expand(1,1400,1400),torch.zeros(1).expand(1,1400,1400,3),'workspace')]
 for mask,image,message in cases:
  with pytest.raises(ValueError,match=message):CLS.execute(mask,image)
 for mask,image in [(torch.zeros((7,13)),torch.zeros((1,7,13,3))),(torch.zeros((1,7,13)),torch.zeros((7,13,3)))]:
  with pytest.raises(ValueError,match='BHWC'):CLS.execute(mask,image)

def test_representative_512_batch_connected_inputs_usable():
 mask,image=fixture(ib=3,mb=3,height=512,columns=512,mh=256,mw=256)
 differential(mask,image);assert CLS.execute(mask,image).result[0].shape==(3,512,512,4)

def test_two_fresh_required_raw_guests_outer_image_mask_hint_native_denial_recovery(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    with (fresh/'_secure_nodes.py').open('a') as probe:
     probe.write('\nclass NedRawDenialProbe(io.ComfyNode):\n    @classmethod\n    async def execute(cls):\n        from comfy_api.latest import sdk\n        return io.NodeOutput(await sdk.TensorRef.from_value(torch.zeros(1)))\n')
    cls=load('ned_imgmask_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS['ImageMask2PNG'];cls.GET_SCHEMA()
    session=await GuestSession('ned-imgmask-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=('raw',),tenant='imgmask-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(mask,image):
     result=await execution._async_map_node_over_list(prompt_id='imgmask-outer',unique_id=str(render),obj=cls,input_data_all={'mask':[mask],'image':[image]},func=cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     for mask,image in [fixture(),fixture(ib=3,mb=1,mh=3,mw=5,channels=4),fixture(dtype=torch.float16),fixture(ib=3,mb=3,height=512,columns=512,mh=256,mw=256)]:same(await outer(mask,image),SOURCE().remove_background(mask,image))
     for mask,image in [(torch.zeros((0,7,13)),torch.zeros((1,7,13,3))),(torch.zeros((1,7,13)),torch.zeros((1,7,13,5)))]:
      try:SOURCE().remove_background(mask,image)
      except Exception as native:
       with pytest.raises(Exception,match=re.escape(type(native).__name__)):await outer(mask,image)
      else:raise AssertionError('native fixture did not discriminate')
     with pytest.raises(Exception,match='workspace'):await outer(torch.zeros((1,1400,1400)),torch.zeros((1,1400,1400,3)))
     mask,image=fixture();refs=_sdk.InProcessRefResolver()
     plan=_sdk.ExecutionPlan(prompt_id='imgmask-denial',node_id='1',node_type=cls.__name__,node_module=cls.__module__,inputs={'mask':mask,'image':image},permissions=('raw',),method='execute',input_types={'mask':'MASK','image':'IMAGE'})
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps());plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
     with pytest.raises(Exception,match='dense .* tensor'):await session.execute(plan,runtime,capabilities=(),tenant='imgmask-user-'+str(render))
     plan=_sdk.ExecutionPlan(prompt_id='imgmask-probe',node_id='probe',node_type='NedRawDenialProbe',node_module=cls.__module__,inputs={},permissions=('raw',),method='execute')
     with pytest.raises(Exception,match='raw|permission|capabil'):await session.execute(plan,runtime,capabilities=(),tenant='imgmask-user-'+str(render))
     mask,image=fixture();same(await outer(mask,image),SOURCE().remove_background(mask,image));pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_pristine_no_license_resources_stubs_imports_and_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes'] and len(pristine)==3
 assert not list(PACK.glob('*LICENSE*')) and (V2/'README.md').read_bytes()==(PACK/'README.md').read_bytes()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 text=(V2/'_secure_nodes.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in text
 for p in V2.glob('*.py'):
  for node in ast.walk(ast.parse(p.read_text())):
   if isinstance(node,ast.Import):assert all(a.name not in ('nodes','folder_paths','server','comfy.model_management') for a in node.names)
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_patch_bundle_two_exact_roundtrips_wrong_pristine_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-imgmask2png/xa7ae08c';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-imgmask2png/xa7ae08c';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as f:f.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
