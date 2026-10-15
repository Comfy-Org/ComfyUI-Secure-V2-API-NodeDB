"""Exact OpenCV pixels, optional IMAGE/MASK, allocation admission and real guests."""
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
import cv2
import numpy as np
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
PAIR=DB/'patches/comfyui-cs-customnodes/x87cea44/comfyui-cs-customnodes-x87cea44'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('ned_cs_old',PACK);NEW=load('ned_cs_new',V2);CLS=NEW.NODE_CLASS_MAPPINGS['CS Transform'];CLS.GET_SCHEMA()
def defaults():return {name:value[1]['default'] for name,value in OLD.CSTransform.INPUT_TYPES()['required'].items()}
def fixture(dtype=torch.float32,channels=3):
 image=torch.arange(7*9*channels,dtype=dtype).reshape(1,7,9,channels)
 if dtype.is_floating_point:image=image/(7*9*channels)
 mask=torch.arange(7*9,dtype=dtype).reshape(1,7,9)
 return image,mask
def same(actual,expected):
 assert len(actual)==len(expected)==2
 for a,b in zip(actual,expected):
  if b is None:assert a is None
  else:assert type(a) is torch.Tensor and a.shape==b.shape and a.dtype==b.dtype and torch.equal(a,b)
def differential(values):
 try:expected=OLD.CSTransform().execute(**values)
 except Exception as native:
  with pytest.raises(type(native)):CLS.execute(**values)
 else:same(CLS.execute(**values).result,expected)
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{'CS Transform':{'module':'_secure_nodes','class':'CSTransformSecure','sdk_refs':False,'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_exact_actual_census_schema_display_quirk_source_and_proxy():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==['CS Transform']
 assert NEW.NODE_DISPLAY_NAME_MAPPINGS==OLD.NODE_DISPLAY_NAME_MAPPINGS=={'CSTransform':'CS Transform'}
 assert (PACK/'nodes/transform.py').read_bytes()==(V2/'nodes/transform.py').read_bytes()
 schema=CLS.GET_SCHEMA();schema.validate();source=OLD.CSTransform
 assert schema.node_id=='CS Transform' and schema.category==source.CATEGORY
 assert [o.io_type for o in schema.outputs]==list(source.RETURN_TYPES)
 assert [o.display_name for o in schema.outputs]==list(source.RETURN_NAMES)
 for inp in schema.inputs:
  group='optional' if inp.optional else 'required';spec=source.INPUT_TYPES()[group][inp.id]
  assert inp.io_type==spec[0]
  if len(spec)>1:
   for key,value in spec[1].items():assert inp.as_dict()[key]==value
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_cs_proxy')
 assert list(loaded.node_mappings)==['CS Transform'] and not loaded.routes and loaded.web_directory is None
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==('raw',)

@pytest.mark.parametrize('rotation',[-360,-37.5,0,25.25,360])
@pytest.mark.parametrize('scale',[0,.5,1,1.75])
@pytest.mark.parametrize('expand',[False,True])
@pytest.mark.parametrize('show',[False,True])
def test_exact_three_warps_expand_snapping_pivot_mask_pixels(rotation,scale,expand,show):
 image,mask=fixture();values=defaults();values.update(image=image,mask=mask,canvas_width=29,canvas_height=31,position_x=-2,position_y=3,pivot_x=2,pivot_y=-1,rotation=rotation,scale=scale,expand_canvas=expand,show_pivot=show)
 differential(values)

@pytest.mark.parametrize('dtype',[torch.float32,torch.float64,torch.uint8])
@pytest.mark.parametrize('channels',[1,3,4])
def test_native_channels_dtype_squeeze_and_canvas_dimension_precedence(dtype,channels):
 image,mask=fixture(dtype,channels);values=defaults();values.update(image=image,mask=mask,canvas=torch.zeros((1,17,19,3)),canvas_width=5,canvas_height=5,rotation=18.0,scale=.7,show_pivot=True)
 differential(values)

@pytest.mark.parametrize('which',['image','mask','both','none'])
def test_optional_presence_output_order_and_none_identity(which):
 image,mask=fixture();values=defaults();values.update(canvas_width=13,canvas_height=15)
 if which in ('image','both'):values['image']=image
 if which in ('mask','both'):values['mask']=mask
 differential(values)

def test_120_seeded_image_mask_pixel_exact_and_no_input_mutation():
 rng=np.random.default_rng(2571);image,mask=fixture();before=image.clone(),mask.clone()
 for _ in range(120):
  values=defaults();values.update(image=image,mask=mask,canvas_width=31,canvas_height=33,position_x=int(rng.integers(-10,11)),position_y=int(rng.integers(-10,11)),pivot_x=int(rng.integers(-5,6)),pivot_y=int(rng.integers(-5,6)),rotation=float(rng.uniform(-360,360)),scale=float(rng.uniform(.1,3)),expand_canvas=bool(rng.integers(2)),show_pivot=bool(rng.integers(2)))
  differential(values)
 assert torch.equal(image,before[0]) and torch.equal(mask,before[1])

def test_usable_default_1024_rgba_plus_mask_and_repeat_stateless():
 image,mask=fixture(channels=4);values=defaults();values.update(image=image,mask=mask)
 differential(values);same(CLS.execute(**values).result,CLS.execute(**values).result)
 assert CLS.execute(**values).result[0].shape==(1,1024,1024,4)

@pytest.mark.parametrize('image',[torch.zeros((2,7,9,3)),torch.zeros((1,1,9,3)),torch.zeros((1,7,1,3)),torch.zeros((0,7,9,3)),torch.zeros((1,7,9,3),dtype=torch.int64)])
def test_native_malformed_shape_dtype_boundaries_not_silently_repaired(image):
 values=defaults();values.update(image=image,canvas_width=17,canvas_height=19)
 differential(values)

@pytest.mark.parametrize('name,bad',[('position_x',True),('position_y',.1),('pivot_x',5001),('rotation',float('nan')),('rotation',361),('scale',float('inf')),('scale',-1),('canvas_width',10001),('canvas_height',0),('expand_canvas',1),('show_pivot',None)])
def test_closed_scalar_admission(name,bad):
 values=defaults();values[name]=bad
 with pytest.raises(ValueError):CLS.execute(**values)

def test_projected_dimensions_and_combined_workspace_refuse_before_original_allocation(monkeypatch):
 mod=sys.modules[CLS.__module__];image,mask=fixture()
 def forbidden(*a,**k):raise AssertionError('original allocation ran before admission')
 monkeypatch.setattr(mod.CSTransform,'execute',forbidden)
 values=defaults();values.update(image=image,mask=mask,canvas_width=10000,canvas_height=10000)
 with pytest.raises(ValueError,match='aggregate'):CLS.execute(**values)
 huge=np.lib.stride_tricks.as_strided(np.zeros(1,dtype=np.float32),shape=(1,1024,4096,4),strides=(0,0,0,0))
 with pytest.raises(ValueError,match='input byte'):CLS.execute(**(defaults()|{'image':huge}))
 huge_dimension=np.zeros((1,2,120,3),dtype=np.float32)
 values=defaults();values.update(image=huge_dimension,expand_canvas=True,scale=100)
 with pytest.raises(ValueError,match='dimension'):CLS.execute(**values)

def test_missing_control_original_and_converted_fail_without_invented_defaults():
 values=defaults();values.pop('scale')
 with pytest.raises(TypeError):OLD.CSTransform().execute(**values)
 with pytest.raises(KeyError):CLS.execute(**values)

def test_actual_two_fresh_guests_outer_image_mask_denial_native_errors_budget_and_recovery(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    # Test-only public raw publisher, not part of the released census or source.
    with (fresh/'_secure_nodes.py').open('a') as probe:
     probe.write('\nclass NedRawDenialProbe(io.ComfyNode):\n    @classmethod\n    async def execute(cls):\n        from comfy_api.latest import sdk\n        return io.NodeOutput(await sdk.TensorRef.from_value(torch.zeros(1)))\n')
    cls=load('ned_cs_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS['CS Transform'];cls.GET_SCHEMA()
    session=await GuestSession('ned-cs-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=('raw',),tenant='cs-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(values):
     result=await execution._async_map_node_over_list(prompt_id='cs-outer',unique_id=str(render),obj=cls,input_data_all={key:[value] for key,value in values.items()},func=cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     image,mask=fixture()
     for changes in ({},{'mask':mask},{'image':image},{'image':image,'mask':mask,'expand_canvas':True,'show_pivot':True,'rotation':-37.5,'scale':1.25,'position_x':-3},{'image':image,'canvas':torch.zeros((1,13,15,3))}):
      values=defaults()|{'canvas_width':29,'canvas_height':31}|changes
      same(await outer(values),OLD.CSTransform().execute(**values))
     values=defaults()|{'image':image,'mask':mask}
     same(await outer(values),OLD.CSTransform().execute(**values))
     values=defaults()|{'image':image,'canvas_width':10000,'canvas_height':10000}
     with pytest.raises(Exception,match='aggregate'):await outer(values)
     malformed=defaults()|{'image':torch.zeros((2,7,9,3)),'canvas_width':17,'canvas_height':19}
     try:OLD.CSTransform().execute(**malformed)
     except Exception as native:
      with pytest.raises(Exception,match=re.escape(type(native).__name__)):await outer(malformed)
     else:raise AssertionError('native fixture no longer fails')
     refs=_sdk.InProcessRefResolver();values=defaults()|{'image':image}
     plan=_sdk.ExecutionPlan(prompt_id='cs-denial',node_id='1',node_type=cls.__name__,node_module=cls.__module__,inputs=values,permissions=('raw',),method='execute',input_types={'image':'IMAGE','mask':'MASK','canvas':'IMAGE'})
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
     plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
     # Value mode without raw leaves typed handles unresolved; the node cannot
     # run its tensor algorithm. Separately exercise explicit public raw denial.
     with pytest.raises(Exception,match='dense tensor input required'):await session.execute(plan,runtime,capabilities=(),tenant='cs-user-'+str(render))
     probe_plan=_sdk.ExecutionPlan(prompt_id='cs-raw-probe',node_id='probe',node_type='NedRawDenialProbe',node_module=cls.__module__,inputs={},permissions=('raw',),method='execute')
     with pytest.raises(Exception,match='raw|permission|capabil'):await session.execute(probe_plan,runtime,capabilities=(),tenant='cs-user-'+str(render))
     values=defaults()|{'mask':mask,'canvas_width':29,'canvas_height':31}
     same(await outer(values),OLD.CSTransform().execute(**values));pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_pristine_resources_stubs_no_license_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes']
 assert not list(PACK.rglob('LICENSE*')) and 'No license' in provenance['licensing']
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 text=(V2/'_secure_nodes.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in text
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_patch_bundle_two_exact_roundtrips_and_wrong_source_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-cs-customnodes/x87cea44';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-cs-customnodes/x87cea44';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'nodes/transform.py').open('ab') as f:f.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
