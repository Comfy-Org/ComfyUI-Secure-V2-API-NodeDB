"""Exact source motion pixels, first-batch quirks, bounded actual guest IMAGE."""
import asyncio
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
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
PAIR=DB/'patches/comfyui-hunyuanvideoimagesguider/xec91d76/comfyui-hunyuanvideoimagesguider-xec91d76'
ID='Hunyuan Video Image To Guider'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('amy_imagesguider_old',PACK);NEW=load('amy_imagesguider_new',V2)
SOURCE=OLD.NODE_CLASS_MAPPINGS[ID];CLS=NEW.NODE_CLASS_MAPPINGS[ID];CLS.GET_SCHEMA()
def fixture(dtype=torch.float32,shape=(2,7,11,3)):
 return ((torch.arange(torch.tensor(shape).prod().item(),dtype=torch.float64).reshape(shape)%211+1)/212).to(dtype)
def inputs(image=None,x=.4,y=-.25,zoom=.25,frames=5,mode='disabled',crop=False):
 return dict(image=fixture() if image is None else image,move_range_x=x,move_range_y=y,zoom=zoom,frame_num=frames,resize_mode=mode,target_width=64,target_height=80,center_crop=crop)
def same(actual,expected):
 assert len(actual)==len(expected)==1
 x,y=actual[0],expected[0]
 assert type(x) is type(y) is torch.Tensor and x.shape==y.shape and x.dtype==y.dtype and x.device==y.device and torch.equal(x,y)
def differential(value):
 before=value['image'].clone()
 try:expected=SOURCE().guide_motion(**value)
 except Exception as native:
  with pytest.raises(type(native)):CLS.execute(**value)
 else:same(CLS.execute(**value).result,expected)
 assert torch.equal(value['image'],before)
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':'ImageMotionGuiderSecure','sdk_refs':False,'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_actual_census_full_schema_proxy_and_normalized_ast_exact_source_algorithm():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
 schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id==ID and schema.category==SOURCE.CATEGORY and [o.io_type for o in schema.outputs]==['IMAGE']
 assert not schema.is_output_node and not schema.is_experimental
 assert [inp.id for inp in schema.inputs]==list(SOURCE.INPUT_TYPES()['required'])
 for inp in schema.inputs:
  spec=SOURCE.INPUT_TYPES()['required'][inp.id]
  if isinstance(spec[0],list):assert inp.as_dict()['options']==spec[0]
  else:assert inp.io_type==spec[0]
  for key,value in (spec[1] if len(spec)>1 else {}).items():assert inp.as_dict()[key]==value
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==('raw',)
 old_ast=ast.parse((PACK/'image_motion_guider.py').read_text())
 old_ast.body=[node for node in old_ast.body if not(isinstance(node,ast.Import) and node.names[0].name in ('nodes','folder_paths'))]
 assert ast.dump(old_ast)==ast.dump(ast.parse((V2/'image_motion_guider.py').read_text()))
 pack=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_imagesguider_proxy')
 assert list(pack.node_mappings)==[ID] and not pack.routes and pack.web_directory is None

@pytest.mark.parametrize('xy',[(0,0),(.4,0),(-.4,0),(0,.6),(0,-.6),(.3,-.7),(-1,1)])
@pytest.mark.parametrize('mode',['disabled','custom','keep_ratio'])
@pytest.mark.parametrize('crop',[False,True])
@pytest.mark.parametrize('zoom',[0,.25,.5])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
def test_exact_motion_direction_floor_zoom_resize_crop_dtype_and_frame_order(xy,mode,crop,zoom,dtype):
 differential(inputs(fixture(dtype),x=xy[0],y=xy[1],mode=mode,crop=crop,zoom=zoom))

def test_source_first_batch_only_black_remainder_and_default_float_canvas():
 value=inputs(x=.4,y=0,zoom=0)
 result=CLS.execute(**value).result[0]
 assert result.shape==(5,7,11,3) and result.dtype==torch.float32
 assert torch.equal(result[0],value['image'][0]) and torch.count_nonzero(result[-1,:,7:])==0
 other=value['image'].clone();other[1]=0
 assert torch.equal(CLS.execute(**{**value,'image':other}).result[0],result)
 source=value['image'].to(torch.float64);previous=torch.get_default_dtype()
 try:
  torch.set_default_dtype(torch.float64);differential(inputs(source));assert CLS.execute(**inputs(source)).result[0].dtype==torch.float64
 finally:torch.set_default_dtype(previous)

@pytest.mark.parametrize('shape',[(0,7,11,3),(1,0,11,3),(1,7,0,3),(1,1,1,3),(1,7,11,1),(1,7,11,4)])
def test_native_empty_small_channels_and_noncontiguous_controls(shape):
 differential(inputs(fixture(shape=shape)))
 value=fixture(shape=(1,7,22,3))[...,::2,:]
 assert not value.is_contiguous();differential(inputs(value))

def test_default_declared_controls_connected512_actual_pixels():
 value=inputs(fixture(shape=(1,512,512,3)),x=0,y=0,zoom=0,frames=10)
 value['target_width']=value['target_height']=512
 differential(value)
 result=CLS.execute(**value).result[0]
 assert result.shape==(10,512,512,3) and all(torch.equal(row,value['image'][0]) for row in result)

@pytest.mark.parametrize('key,bad',[('move_range_x',float('nan')),('move_range_x',True),('move_range_y',1.1),('zoom',float('inf')),('zoom',.6),('frame_num',True),('frame_num',151),('frame_num',1),('resize_mode','other'),('target_width',2049),('target_height',False),('center_crop',1)])
def test_closed_admission_controls(key,bad):
 value=inputs();value[key]=bad
 with pytest.raises(ValueError):CLS.execute(**value)

def test_whole_input_projected_frames_and_keep_ratio_bounds_before_algorithm(monkeypatch):
 module=sys.modules[CLS.__module__]
 def forbidden(**kwargs):raise AssertionError('algorithm entered before bounds')
 monkeypatch.setattr(module.Source,'guide_motion',lambda self,**kwargs:forbidden(**kwargs))
 for value,message in [
  (inputs(torch.zeros(1).expand(64,512,512,3)),'input byte'),
  (inputs(fixture(shape=(1,512,512,3)),frames=150),'workspace'),
  (inputs(torch.zeros(1).expand(1,2048,1,3),mode='keep_ratio'),'projected resized'),
  (inputs(torch.zeros((7,11,3))),'BHWC'),
  (inputs(torch.zeros(1).expand(1,4097,2,3)),'dimensions')]:
  with pytest.raises(ValueError,match=message):CLS.execute(**value)

def test_two_fresh_required_guests_real_outer_IMAGE_native_refusal_recovery_and_raw_denial(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[];allowed=('raw',)
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    cls=load('amy_imagesguider_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
    session=await GuestSession('amy-imagesguider-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=allowed,tenant='amy-guider-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(value):
     result=await execution._async_map_node_over_list(prompt_id='amy-guider-outer',unique_id=str(render),obj=cls,input_data_all={k:[v] for k,v in value.items()},func=cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     assert session.sandbox_kind=='seatbelt'
     for value in [inputs(),inputs(fixture(torch.bfloat16),mode='custom',crop=True),inputs(fixture(torch.float16),x=-.4,y=.3,mode='keep_ratio'),inputs(fixture(torch.float64),zoom=0),inputs(fixture(shape=(1,512,512,3)),x=0,y=0,zoom=0,frames=10)]:
      same(await outer(value),SOURCE().guide_motion(**value))
     with pytest.raises(Exception,match='workspace'):await outer(inputs(fixture(shape=(1,512,512,3)),frames=150))
     with pytest.raises(Exception,match='IndexError'):await outer(inputs(fixture(shape=(0,7,11,3))))
     allowed=()
     with pytest.raises(Exception,match='raw|permission|capability|dense BHWC'):await outer(inputs())
     allowed=('raw',);same(await outer(inputs()),SOURCE().guide_motion(**inputs()))
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_resources_manifest_complete_source_stubs_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 p=json.loads((V2/'source-provenance.json').read_text())
 pristine={path.relative_to(PACK).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in PACK.rglob('*') if path.is_file() and not path.is_relative_to(V2)}
 assert pristine==p['source_hashes'] and len(pristine)==11 and p['exact_git_blob_path_mode_match']
 for name in pristine:
  if name not in ('__init__.py','image_motion_guider.py','pyproject.toml'):assert (PACK/name).read_bytes()==(V2/name).read_bytes()
 assert 'MIT License' in (V2/'LICENSE').read_text()
 for name,expected in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==expected
 text=(V2/'_secure_nodes.py').read_text()+(V2/'image_motion_guider.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','import nodes','PromptServer','subprocess','requests','comfy.model_management','eval(', 'exec(', 'open('):assert forbidden not in text
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_patch_zip_two_exact_roundtrips_and_wrong_source_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes().decode('utf-8'))==expected and PAIR.with_suffix('.diff').read_bytes().decode('utf-8')==diff
 for index in range(2):
  fresh=tmp_path/str(index)/'comfyui-hunyuanvideoimagesguider/xec91d76';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-hunyuanvideoimagesguider/xec91d76';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as file:file.write(b'\n#wrong pristine')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
