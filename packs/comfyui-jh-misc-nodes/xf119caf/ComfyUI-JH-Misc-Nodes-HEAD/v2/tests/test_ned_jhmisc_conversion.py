"""Whole four-node JH pack: exact scalar/ref intent and managed temp PNG bytes."""
import asyncio
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import shutil
import sys
from unittest.mock import patch
import numpy as np
from PIL import Image
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution
import folder_paths
from comfy_api.latest import io,sdk,_sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-jh-misc-nodes/xf119caf/comfyui-jh-misc-nodes-xf119caf'
def load(name,path):
 before=list(sys.path)
 try:
  spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
  mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
 finally:sys.path[:]=before
OLD=load('ned_jhmisc_old',PACK);NEW=load('ned_jhmisc_new',V2)
IDS=list(OLD.NODE_CLASS_MAPPINGS)
for cls in NEW.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{name:{'module':cls.__module__.split('ned_jhmisc_new.')[-1],'class':cls.__name__,'sdk_refs':True,'permissions':list(cls.SDK_PERMISSIONS),'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for name,cls in NEW.NODE_CLASS_MAPPINGS.items()}}
def roots(tmp_path,monkeypatch):
 result={name:tmp_path/name for name in ('temp','output')}
 for name,root in result.items():
  root.mkdir(parents=True);monkeypatch.setattr(folder_paths,'get_'+name+'_directory',lambda root=root:str(root))
 return result
def fixture(batch=2,channels=3,dtype=torch.float32,h=7,w=13):
 return ((torch.arange(batch*h*w*channels,dtype=torch.float64).reshape(batch,h,w,channels)%311)/255-.1).to(dtype)

def test_actual_four_census_exact_schema_and_proxy():
 assert IDS==list(NEW.NODE_CLASS_MAPPINGS)==['JHDaisyChainableStringConstantNode','JHTwoWaySwitchNode','JHThreeWaySwitchNode','JHPreviewImage']
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 for name in IDS:
  old=OLD.NODE_CLASS_MAPPINGS[name];cls=NEW.NODE_CLASS_MAPPINGS[name];schema=cls.GET_SCHEMA();schema.validate()
  assert schema.node_id==name and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[name] and schema.category==old.CATEGORY and schema.is_experimental
  assert schema.is_output_node==getattr(old,'OUTPUT_NODE',False)
  assert [o.io_type for o in schema.outputs]==list(old.RETURN_TYPES)
  if hasattr(old,'RETURN_NAMES'):assert [o.display_name for o in schema.outputs]==list(old.RETURN_NAMES)
  expected=old.INPUT_TYPES()
  assert encode_schema(schema)['hidden']==list(expected.get('hidden',{}))
  assert [(i.id,i.optional,str(i.io_type)) for i in schema.inputs]==[(key,section=='optional',str(spec[0])) for section in ('required','optional') for key,spec in expected.get(section,{}).items()]
  for i in schema.inputs:
   spec=expected['optional' if i.optional else 'required'][i.id]
   for key,value in spec[1].items():assert i.as_dict()[key]==value
  assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS==(('raw','output') if name=='JHPreviewImage' else ())
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_jhmisc_proxy')
 assert list(loaded.node_mappings)==IDS and not loaded.routes and loaded.web_directory is None

@pytest.mark.parametrize('text',['','word','  a\n\n b\t c  ','\u2003a\u00a0b','<script>alert(1)</script>','日本語\n текст','\n\r\t','a'*4096])
@pytest.mark.parametrize('prefix',['','prefix','  preserve\n prefix  ',None])
def test_string_exact_normalization_concatenation(text,prefix):
 old=OLD.NODE_CLASS_MAPPINGS[IDS[0]];cls=NEW.NODE_CLASS_MAPPINGS[IDS[0]]
 assert cls.execute(text,input_text=prefix).result==old().execute(text,input_text=prefix)

def test_string_native_missing_none_and_bounded_work():
 cls=NEW.NODE_CLASS_MAPPINGS[IDS[0]];old=OLD.NODE_CLASS_MAPPINGS[IDS[0]]
 for thunk in (lambda:old().execute(),lambda:cls.execute(),lambda:old().execute(None),lambda:cls.execute(None)):
  with pytest.raises(TypeError):thunk()
 with pytest.raises(ValueError,match='byte budget'):cls.execute('é'*32769)
 with pytest.raises(ValueError,match='output byte'):cls.execute('a'*40000,'b'*40000)
 random_state=random.getstate()
 for i in range(100):
  text=(' \n\t_'*i)+'word';prefix='prefix '*i
  assert cls.execute(text,prefix).result==old().execute(text,prefix)
 assert random.getstate()==random_state

@pytest.mark.parametrize('name',['JHTwoWaySwitchNode','JHThreeWaySwitchNode'])
@pytest.mark.parametrize('kwargs',[{}, {'input_1':None},{'input_1':None,'input_2':False},{'input_1':0,'input_2':1},{'input_1':'','input_2':'x'},{'input_2':'second','input_1':'first'},{'input_1':[1,2],'input_2':None},{'input_1':(1,False),'input_2':None},{'input_1':{'k':[1]},'input_2':'x'}])
def test_switch_exact_first_not_none_keyword_order_false_zero_empty_and_identity(name,kwargs):
 old=OLD.NODE_CLASS_MAPPINGS[name]().do_switch(**kwargs);new=NEW.NODE_CLASS_MAPPINGS[name].execute(**kwargs).result
 assert len(new)==1 and new[0] is old[0]

def test_switch_host_refs_are_opaque_and_do_not_need_raw():
 async def run():
  plan=_sdk.ExecutionPlan(prompt_id='jh-ref',node_id='1',node_type='probe')
  refs=_sdk.InProcessRefResolver();runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
  with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):
   image=await sdk.ImageRef.from_value(fixture())
   for name in IDS[1:3]:
    result=NEW.NODE_CLASS_MAPPINGS[name].execute(input_2=image,input_1=None)
    assert result.result[0] is image
 asyncio.run(run())

@pytest.mark.parametrize('channels',[2,3,4])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.uint8])
def test_preview_actual_source_encoder_bytes_metadata_absence_passthrough(tmp_path,monkeypatch,channels,dtype):
 original_root=tmp_path/'original';original_root.mkdir();monkeypatch.setattr(folder_paths,'get_temp_directory',lambda:str(original_root))
 value=fixture(channels=channels,dtype=dtype);before=value.clone()
 with patch('random.choice',return_value='a'):
  old=OLD.NODE_CLASS_MAPPINGS['JHPreviewImage']()
 source_prefix=old.prefix_append;assert source_prefix=='_temp_aaaaa'
 first=old.preview_images(value,prompt={'fixture':'prompt'},extra_pnginfo={'workflow':{'nodes':[]}})
 second=old.preview_images(value)
 assert first['result'][0] is value and first['ui']['images'][0]['filename']=='ComfyUI_temp_aaaaa_00001_.png'
 assert second['ui']['images'][0]['filename']=='ComfyUI_temp_aaaaa_00003_.png' and old.prefix_append==source_prefix
 expected=[(original_root/row['filename']).read_bytes() for row in first['ui']['images']]
 output=roots(tmp_path/'converted',monkeypatch)
 async def run():
  refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='jh-png',node_id='1',node_type='probe')
  runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
  with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):
   image=await sdk.ImageRef.from_value(value)
   result=await NEW.NODE_CLASS_MAPPINGS['JHPreviewImage'].execute(image,prompt={'fixture':'prompt'},extra_pnginfo={'workflow':{'nodes':[]}})
   assert result.result[0] is image
   for row,wanted in zip(result.ui['images'],expected):
    assert row['type']=='temp' and row['subfolder']=='' and re.fullmatch(r'ComfyUI_temp_[abcdefghijklmnopqrstupvxyz]{5}_\d{5}_\.png',row['filename'])
    target=output['temp']/row['filename'];assert target.read_bytes()==wanted
    with Image.open(target) as pil:assert 'prompt' not in pil.info and 'workflow' not in pil.info
 asyncio.run(run());assert torch.equal(value,before) and not list(output['output'].iterdir())

def test_preview_source_and_draft_native_modes_empty_errors_and_preallocation(monkeypatch,tmp_path):
 from importlib import import_module
 mod=import_module(NEW.NODE_CLASS_MAPPINGS['JHPreviewImage'].__module__)
 monkeypatch.setattr(folder_paths,'get_temp_directory',lambda:str(tmp_path))
 for value in (torch.zeros((0,7,13,3)),torch.zeros((1,7,13,1)),torch.zeros((1,7,13,5)),fixture(dtype=torch.bfloat16)):
  try:OLD.NODE_CLASS_MAPPINGS['JHPreviewImage']().preview_images(value)
  except Exception as native:
   with pytest.raises(type(native)):mod.preflight(value)
  else:raise AssertionError('native fixture did not discriminate')
 for value,message in [(torch.zeros((7,13,3)),'BHWC'),(torch.empty((65,2,2,3)),'dimensions'),(torch.zeros(1).expand(64,512,512,3),'input byte'),(torch.zeros(1).expand(1,1500,1500,3),'workspace')]:
  with pytest.raises(ValueError,match=message):mod.preflight(value)

def test_preview_default_connected_512_pixels_and_rng_locality(tmp_path,monkeypatch):
 result=roots(tmp_path,monkeypatch);before=random.getstate();value=fixture(batch=1,h=512,w=512)
 async def run():
  refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='jh-default',node_id='1',node_type='probe')
  runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
  with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):
   image=await sdk.ImageRef.from_value(value);saved=await NEW.NODE_CLASS_MAPPINGS['JHPreviewImage'].execute(image)
   with Image.open(result['temp']/saved.ui['images'][0]['filename']) as pil:assert np.array_equal(np.array(pil),np.clip(value[0].numpy()*255,0,255).astype(np.uint8))
 asyncio.run(run());assert random.getstate()==before

def test_two_fresh_required_guests_all_registered_outer_scalar_ref_png_and_caps(tmp_path,monkeypatch):
 outputs=roots(tmp_path/'outputs',monkeypatch)
 async def run():
  prior=_sdk.providers.execution_backend;pids=[];allowed=()
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    classes=load('ned_jhmisc_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS
    for cls in classes.values():cls.GET_SCHEMA()
    session=await GuestSession('ned-jhmisc-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=allowed,tenant='jh-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(name,values):
     cls=classes[name]
     result=await execution._async_map_node_over_list(prompt_id='jh-outer',unique_id=str(render),obj=cls,input_data_all={k:[v] for k,v in values.items()},func=cls.FUNCTION,v3_data=None)
     return result[0]
    try:
     assert session.sandbox_kind=='seatbelt'
     assert (await outer(IDS[0],{'text':'  hi\n there ','input_text':'keep\n prefix'})).result==('keep\n prefix hi there',)
     for name in IDS[1:3]:
      for values in ({},{'input_1':False,'input_2':'other'},{'input_2':(1,False),'input_1':None},{'input_1':{'k':[1]},'input_2':'other'}):
       assert (await outer(name,values)).result==OLD.NODE_CLASS_MAPPINGS[name]().do_switch(**values)
      value=fixture();r=await outer(name,{'input_1':value,'input_2':None});assert r.result[0] is value
     value=fixture();allowed=('raw','output');before=value.clone()
     saved=await outer('JHPreviewImage',{'images':value})
     assert saved.result[0] is value and torch.equal(value,before)
     for row,pixels in zip(saved.ui['images'],value):
      assert row['type']=='temp'
      with Image.open(outputs['temp']/row['filename']) as pil:assert np.array_equal(np.array(pil),np.clip(pixels.numpy()*255,0,255).astype(np.uint8))
     for dtype in (torch.float16,torch.float32,torch.float64,torch.uint8):
      la=fixture(channels=2,dtype=dtype);la_before=la.clone()
      saved_la=await outer('JHPreviewImage',{'images':la})
      assert saved_la.result[0] is la and torch.equal(la,la_before)
      for row,pixels in zip(saved_la.ui['images'],la):
       import io as bytes_io
       expected=bytes_io.BytesIO()
       Image.fromarray(np.clip(pixels.numpy()*255,0,255).astype(np.uint8)).save(expected,format='PNG',compress_level=1)
       assert (outputs['temp']/row['filename']).read_bytes()==expected.getvalue()
       with Image.open(outputs['temp']/row['filename']) as pil:
        assert pil.mode=='LA' and np.array_equal(np.array(pil),np.clip(pixels.numpy()*255,0,255).astype(np.uint8))
     files=set(outputs['temp'].iterdir());allowed=('raw',)
     with pytest.raises(Exception,match="capability 'output'"):await outer('JHPreviewImage',{'images':value})
     assert set(outputs['temp'].iterdir())==files
     allowed=('output',)
     with pytest.raises(Exception,match="raw|permission|capability"):await outer('JHPreviewImage',{'images':value})
     assert set(outputs['temp'].iterdir())==files
     allowed=('raw','output')
     with pytest.raises(Exception,match='IndexError'):await outer('JHPreviewImage',{'images':torch.zeros((0,7,13,3))})
     with pytest.raises(Exception,match='workspace'):await outer('JHPreviewImage',{'images':torch.zeros((1,1500,1500,3))})
     r=await outer('JHPreviewImage',{'images':value});assert r.result[0] is value
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids and not list(outputs['output'].iterdir())
 asyncio.run(run())

def test_manifest_resources_license_conflict_source_stubs_and_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes'] and len(pristine)==20
 assert (V2/'LICENSE').read_bytes()==(PACK/'LICENSE').read_bytes() and 'GNU GENERAL PUBLIC LICENSE' in (V2/'LICENSE').read_text()
 assert 'license = "MIT"' in (V2/'pyproject.toml').read_text()
 for name in ('README.md','requirements.txt','requirements-dev.txt','poetry.lock','comfyui_jh_misc_nodes/jh_daisy_chainable_string_constant_node.py'):
  assert (V2/name).read_bytes()==(PACK/name).read_bytes()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 for p in [V2/'__init__.py',V2/'_secure_nodes.py',*list((V2/'comfyui_jh_misc_nodes').glob('*.py'))]:
  text=p.read_text()
  for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','sys.path','os.path','open('):assert forbidden not in text
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_pair_zip_two_exact_roundtrips_wrong_source(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-jh-misc-nodes/xf119caf';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-jh-misc-nodes/xf119caf';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as f:f.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
