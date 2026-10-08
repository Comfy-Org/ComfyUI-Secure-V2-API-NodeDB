"""Exact time-block duplication, logistic masks and full actual LATENT wire."""
import asyncio
import copy
import hashlib
import importlib.util
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-hunyuanimagelatenttovideolatent/x08e542b/comfyui-hunyuanimagelatenttovideolatent-x08e542b'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_hvconvert_old',PACK);NEW=load('ned_hvconvert_new',V2);ID='HunyuanImageLatentToVideoLatent';CLS=NEW.NODE_CLASS_MAPPINGS[ID];CLS.GET_SCHEMA();SOURCE=OLD.NODE_CLASS_MAPPINGS[ID]
def fixture(dtype=torch.float32,shape=(2,16,1,3,5)):
 values=torch.arange(torch.tensor(shape).prod().item(),dtype=torch.float64).reshape(shape)%97/16-.5
 return {'samples':values.to(dtype),'ignored_metadata':{'source':'discarded'},'noise_mask':torch.ones(shape)}
def inputs(length=49,mask=True,latent=None,s=20,o=.25,w=.05):return {'length':length,'latent':fixture() if latent is None else latent,'use_noise_mask':mask,'noise_s':s,'noise_o':o,'noise_w':w}
def same(actual,expected):
 assert len(actual)==len(expected)==1 and type(actual[0]) is type(expected[0]) is dict and set(actual[0])==set(expected[0])
 for key,x in actual[0].items():
  y=expected[0][key];assert type(x) is torch.Tensor and x.shape==y.shape and x.dtype==y.dtype and x.device==y.device and torch.equal(x,y)
def differential(values):
 try:expected=SOURCE().run_node(**values)
 except Exception as native:
  with pytest.raises(type(native)):CLS.execute(**values)
 else:same(CLS.execute(**values).result,expected)
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':'HunyuanConvertSecure','sdk_refs':False,'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_actual_single_census_full_schema_description_proxy_and_byte_exact_math():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 assert (PACK/'__init__.py').read_bytes()==(V2/'source_algorithm.py').read_bytes()
 schema=CLS.GET_SCHEMA();schema.validate();assert schema.node_id==ID and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[ID] and schema.description==SOURCE.DESCRIPTION and schema.category==SOURCE.CATEGORY
 assert [o.io_type for o in schema.outputs]==['LATENT'] and not schema.is_output_node
 assert [i.id for i in schema.inputs]==list(SOURCE.INPUT_TYPES()['required'])
 for inp in schema.inputs:
  spec=SOURCE.INPUT_TYPES()['required'][inp.id];assert inp.io_type==spec[0] and not inp.optional
  for key,value in spec[1].items():assert inp.as_dict()[key]==value
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==('raw',)
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_hvconvert_proxy');assert list(loaded.node_mappings)==[ID] and not loaded.routes and loaded.web_directory is None

@pytest.mark.parametrize('length',[0,1,2,3,4,5,8,9,24,25,26,29,48,49,50,65,129])
@pytest.mark.parametrize('mask',[False,True])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16,torch.int16])
def test_exact_temporal_floor_dtype_blocks_mask_policy_and_native_length_zero(length,mask,dtype):differential(inputs(length,mask,fixture(dtype)))

@pytest.mark.parametrize('shape',[(0,16,1,3,5),(1,16,0,3,5),(1,16,1,0,5),(1,16,1,3,0),(1,4,2,3,5),(3,1,3,2,2)])
@pytest.mark.parametrize('mask',[False,True])
def test_source_empty_axes_and_multiple_input_time_blocks_not_firstframe_substitution(shape,mask):differential(inputs(9,mask,fixture(shape=shape)))

@pytest.mark.parametrize('s,o,w',[(0,0,0),(20,.25,.05),(100,-2,2),(100,2,0),(1,.5,1),(20,0,0)])
def test_exact_logistic_noise_curve_extremes_no_math_substitution(s,o,w):
 value=inputs(49,True,s=s,o=o,w=w);differential(value)
 result=CLS.execute(**value).result[0]
 assert set(result)=={'samples','noise_mask'} and result['noise_mask'].dtype==torch.get_default_dtype()
 count=13
 for index in range(count):assert torch.equal(result['noise_mask'][:,:,index],torch.ones_like(result['noise_mask'][:,:,index])*SOURCE().get_noise_intensity(index/count,s,o,w))

def test_discriminating_block_repeat_not_frame_repeat_and_drop_metadata_no_mutation():
 values=inputs(9,True,fixture(shape=(1,2,2,3,5)));before=values['latent']['samples'].clone()
 actual=CLS.execute(**values).result;same(actual,SOURCE().run_node(**values))
 assert torch.equal(actual[0]['samples'],torch.cat([before,before,before],dim=2))
 assert set(actual[0])=={'samples','noise_mask'} and torch.equal(values['latent']['samples'],before)
 assert actual[0]['samples'] is not values['latent']['samples']
 values['latent']['samples']=fixture(shape=(1,2,2,3,10))['samples'][...,::2]
 assert not values['latent']['samples'].is_contiguous();differential(values)
 same(CLS.execute(**values).result,CLS.execute(**values).result)

def test_trusted_local_default_float64_noise_mask_exact_then_restore_global():
 previous=torch.get_default_dtype()
 try:
  torch.set_default_dtype(torch.float64);value=inputs(9,True,fixture(torch.float16));differential(value)
  assert CLS.execute(**value).result[0]['noise_mask'].dtype==torch.float64
 finally:torch.set_default_dtype(previous)

def test_declared_default49_connected_512_spatial_latent_real_values():
 value=inputs(49,True,fixture(shape=(1,16,1,64,64)));differential(value)
 assert CLS.execute(**value).result[0]['samples'].shape==(1,16,13,64,64)

@pytest.mark.parametrize('field,bad',[('length',True),('length',-1),('length',40001),('length',1.5),('use_noise_mask',1),('noise_s',float('nan')),('noise_s',101),('noise_o',float('inf')),('noise_o',-2.1),('noise_w',2.1),('noise_w',True)])
def test_closed_scalar_admission_before_algorithm(field,bad):
 value=inputs();value[field]=bad
 with pytest.raises(ValueError):CLS.execute(**value)

def test_projection_bounds_before_concat_mask_or_print_and_native_missing_samples(monkeypatch):
 with pytest.raises(KeyError):CLS.execute(**inputs(latent={}))
 with pytest.raises(KeyError):SOURCE().run_node(**inputs(latent={}))
 module=sys.modules[CLS.__module__]
 def forbidden(*a,**k):raise AssertionError('algorithm started before admission')
 monkeypatch.setattr(module.Source,'run_node',forbidden)
 for latent,length,error in [({'samples':torch.zeros(1).expand(1,16,1,512,512)},49,'temporal'),({'samples':torch.zeros(1).expand(64,16,1,512,512)},1,'input byte'),({'samples':torch.zeros(1).expand(1,16,1,4,4097)},1,'dimension'),({'samples':torch.zeros((1,16,3,5))},1,'five-dimensional')]:
  with pytest.raises(ValueError,match=error):CLS.execute(**inputs(length,True,latent))
 value=fixture();value['ignored_metadata']['large']=torch.zeros(1).expand(10_000_000)
 with pytest.raises(ValueError,match='input byte'):CLS.execute(**inputs(latent=value))
 value=fixture();value['ignored_metadata']['deep']=[];leaf=value['ignored_metadata']['deep']
 for index in range(10):leaf.append([]);leaf=leaf[0]
 with pytest.raises(ValueError,match='tree bound'):CLS.execute(**inputs(latent=value))

def test_two_fresh_required_raw_guests_outer_complete_latent_dict_curves_native_caps(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[];allowed=('raw',)
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    cls=load('ned_hvconvert_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
    shutil.copyfile(V2/'tests/native_error_oracle.py',fresh/'native_error_oracle.py')
    oracle=importlib.import_module(cls.__module__.rsplit('.',1)[0]+'.native_error_oracle').NedPristineErrorOracle
    oracle.GET_SCHEMA()
    session=await GuestSession('ned-hvconvert-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=allowed,tenant='hvconvert-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(values,target=cls):
     result=await execution._async_map_node_over_list(prompt_id='hvconvert-outer',unique_id=str(render),obj=target,input_data_all={k:[v] for k,v in values.items()},func=target.FUNCTION,v3_data=None)
     return result[0].result
    try:
     assert session.sandbox_kind=='seatbelt'
     for value in [inputs(),inputs(9,False,fixture(torch.float16)),inputs(9,True,fixture(torch.bfloat16)),inputs(9,True,fixture(torch.int16)),inputs(9,True,fixture(shape=(1,4,2,3,5))),inputs(49,True,fixture(shape=(1,16,1,64,64))),inputs(9,True,fixture(shape=(0,16,1,3,5)))]:same(await outer(value),SOURCE().run_node(**value))
     # Compare the byte-exact pristine algorithm in the SAME confined runtime.
     # The trusted host's Torch RuntimeError is retained in differential controls;
     # the guest may classify its identical empty-cat native error differently.
     kind,message,version=await outer(inputs(0),oracle)
     print('PRISTINE_GUEST_EMPTY_CONCAT',kind,repr(message),'torch',version)
     assert kind=='ValueError' and message=='torch.cat(): expected a non-empty list of Tensors'
     with pytest.raises(Exception,match=re.escape(kind+': '+message)):await outer(inputs(0))
     with pytest.raises(Exception,match='budget'):await outer(inputs(49,True,{'samples':torch.zeros((1,16,1,512,512))}))
     allowed=()
     with pytest.raises(Exception,match='raw|permission|capability'):await outer(inputs())
     allowed=('raw',);same(await outer(inputs()),SOURCE().run_node(**inputs()));pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_source_mit_resources_stubs_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes'] and len(pristine)==4
 assert (V2/'LICENSE').read_bytes()==(PACK/'LICENSE').read_bytes() and (V2/'README.md').read_bytes()==(PACK/'README.md').read_bytes()
 assert 'MIT License' in (V2/'LICENSE').read_text()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 text=(V2/'_secure_nodes.py').read_text()+(V2/'source_algorithm.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','comfy.model_management','eval(', 'exec(', 'open('):assert forbidden not in text
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_patch_zip_two_exact_roundtrips_and_wrong_pristine_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-hunyuanimagelatenttovideolatent/x08e542b';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-hunyuanimagelatenttovideolatent/x08e542b';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as f:f.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
