"""Exact palette oracle, public publisher, genuine guest/outer and owned artifacts."""
import ast
import asyncio
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
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb, packpatch

V2=Path(__file__).resolve().parents[1]
PACK=V2.parent
SNAPSHOT=PACK.parent
DB=SNAPSHOT.parents[2]
NODE='ColorPalette|AIPOQUE'
PAIR=DB/'patches/comfyui-apqnodes/x25a7aea/comfyui-apqnodes-x25a7aea'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_apq_pristine',PACK)
NEW=load('ned_apq_v2',V2)
CLS=NEW.NODE_CLASS_MAPPINGS[NODE]
CLS.GET_SCHEMA()

def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{NODE:{
 'module':'nodes.APQNodes','class':'ColorPalette','sdk_refs':True,'permissions':['raw'],
 'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},
 'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

async def local(prompt,hexes,caps=('raw',)):
 refs=_sdk.InProcessRefResolver()
 plan=_sdk.ExecutionPlan(prompt_id='apq-local',node_id='1',node_type=NODE,inputs={'prompt':prompt,'hexcodes':hexes},permissions=tuple(caps))
 runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
 with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):
  output=await CLS.execute(**plan.inputs)
  return (await _sdk.unwrap_outputs(refs,output)).result

def assert_equal(a,b):
 assert a[0]==b[0]
 assert type(a[1]) is torch.Tensor and a[1].dtype==b[1].dtype and a[1].shape==b[1].shape
 assert torch.equal(a[1],b[1])

def test_actual_census_complete_schema_and_unchanged_algorithm_ast():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[NODE]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS=={NODE:'ColorPalette'}
 old=OLD.NODE_CLASS_MAPPINGS[NODE];schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id==NODE and schema.display_name=='ColorPalette' and schema.category==old.CATEGORY
 assert [o.io_type for o in schema.outputs]==list(old.RETURN_TYPES)
 assert [o.display_name for o in schema.outputs]==list(old.RETURN_NAMES)
 for inp in schema.inputs:
  spec=old.INPUT_TYPES()['required'][inp.id]
  assert inp.io_type==spec[0] and not inp.optional
  for k,v in spec[1].items():assert inp.as_dict()[k]==v
 def algorithm(path):return ast.dump(next(n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,ast.FunctionDef) and n.name=='color_picker'),include_attributes=False)
 assert algorithm(PACK/'nodes/APQNodes.py')==algorithm(V2/'nodes/APQNodes.py')
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_apq_proxy')
 assert list(loaded.node_mappings)==[NODE] and not loaded.routes and loaded.web_directory is None
 assert not list(PACK.rglob('*.js')) and not hasattr(OLD,'WEB_DIRECTORY')
 assert CLS.SDK_REFS is True and CLS.SDK_PERMISSIONS==('raw',)

@pytest.mark.parametrize('hexes',['','#','#FF0000','#00ff00#0000FF','abc','#fa7060#ADB0B0#ffffff','#123456\n#654321','#010101#010101','ffffff#000000','\n#00ffff', '#abc#fff#000', '#fef01b#faf7ee'])
@pytest.mark.parametrize('prompt',['','Hello','α🙂\n<script>x</script>'])
def test_exact_text_color_choice_rgba_pixels_and_empty_width(prompt,hexes):
 try:expected=OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker(prompt,hexes)
 except Exception as error:
  with pytest.raises(type(error)):asyncio.run(local(prompt,hexes))
  return
 assert_equal(asyncio.run(local(prompt,hexes)),expected)

def test_200_seeded_valid_hex_differentials_and_repeat_isolation():
 rng=random.Random(7199)
 for i in range(200):
  hexes='#'+'#'.join(f'{rng.randrange(1<<24):06x}' for _ in range(rng.randrange(1,9)))
  expected=OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker(str(i),hexes)
  assert_equal(asyncio.run(local(str(i),hexes)),expected)

@pytest.mark.parametrize('hexes',['World',' ','#ff','#1','#gggggg','#ffffff#badword','#ffffffffffff','##\n#abcdef'])
def test_native_malformed_hex_and_invalid_default_failure_not_repaired(hexes):
 try: expected=OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker('Hello',hexes)
 except Exception as error:
  with pytest.raises(type(error)):asyncio.run(local('Hello',hexes))
 else:assert_equal(asyncio.run(local('Hello',hexes)),expected)

@pytest.mark.parametrize('prompt,hexes',[('x'*65537,'#000000'),('ok','x'*65537),('ok','#000000'*257)])
def test_work_bounds_refuse_before_source_or_canvas_allocation(monkeypatch,prompt,hexes):
 mod=sys.modules[CLS.__module__]
 def forbidden(*a,**k):raise AssertionError('source algorithm ran before admission')
 monkeypatch.setattr(CLS,'color_picker',forbidden)
 with pytest.raises(ValueError,match='bound|exceeds'):asyncio.run(local(prompt,hexes))

@pytest.mark.parametrize('prompt,hexes',[(None,'#abcdef'),(3,'#abcdef'),('x',None),('x',True)])
def test_direct_nonstring_inputs_fail_closed(prompt,hexes):
 with pytest.raises(TypeError,match='must be strings'):asyncio.run(local(prompt,hexes))

def test_max_admitted_canvas_and_utf8_bound():
 hexes='#010101'*256
 expected=OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker('',hexes)
 result=asyncio.run(local('',hexes));assert_equal(result,expected)
 assert result[1].shape==(1,64,16384,4) and result[1].numel()*result[1].element_size()==16777216
 with pytest.raises(ValueError):asyncio.run(local('🙂'*16385,'#000000'))

def test_trusted_in_process_provider_is_not_a_permission_boundary():
 # Trusted local provider does not enforce transport permissions. The genuine
 # confined guest below must deny the identical public publication without raw.
 assert_equal(asyncio.run(local('x','#abcdef',caps=())),OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker('x','#abcdef'))

def test_two_fresh_required_guests_outer_pixels_errors_denial_limits_and_stateless_reconstruction(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render,tenant in enumerate(('apq-user-a','apq-user-b')):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    fresh_cls=load('ned_apq_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[NODE]
    fresh_cls.GET_SCHEMA()
    session=await GuestSession('ned-apq-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=('raw',),tenant=tenant)
    _sdk.providers.register_execution_backend(Backend())
    async def outer(hexes,prompt='guest'):
     result=await execution._async_map_node_over_list(prompt_id='ned-apq-outer',unique_id=str(render),obj=fresh_cls,input_data_all={'prompt':[prompt],'hexcodes':[hexes]},func=fresh_cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     for hexes in ('#FA7060#ffffff#abc','','#','#00ff00#0000ff'):
      assert_equal(await outer(hexes),OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker('guest',hexes))
     for hexes in ('World',' ','#gggggg'):
      try:OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker('guest',hexes)
      except Exception as native:
       with pytest.raises(Exception,match=re.escape(type(native).__name__+': '+str(native))):await outer(hexes)
      else:raise AssertionError('malformed fixture did not raise in pinned source')
     assert_equal(await outer('#010101'*256),OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker('guest','#010101'*256))
     with pytest.raises(Exception,match='256|exceeds'):await outer('#abcdef'*257)
     with pytest.raises(Exception,match='64 KiB'):await outer('#abcdef',prompt='🙂'*16385)
     refs=_sdk.InProcessRefResolver()
     plan=_sdk.ExecutionPlan(prompt_id='denial',node_id='1',node_type=fresh_cls.__name__,node_module=fresh_cls.__module__,inputs={'prompt':'x','hexcodes':'#abcdef'},permissions=('raw',),method='execute')
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
     with pytest.raises(Exception,match='raw|permission|capabil'):await session.execute(plan,runtime,capabilities=(),tenant=tenant)
     assert_equal(await outer('#abcdef'),OLD.NODE_CLASS_MAPPINGS[NODE]().color_picker('guest','#abcdef'))
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_stubs_git_pristine_resource_and_security_census():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text())
 assert provenance['commit']=='25a7aea3379259f9189a21e56a0160b6f8f8d02c' and provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes']
 for name,sha in pristine.items():assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha or name=='nodes/APQNodes.py'
 assert hashlib.sha256((V2/'comfy-api.pyi').read_bytes()).hexdigest()=='89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'
 assert hashlib.sha256((V2/'comfy-api.d.ts').read_bytes()).hexdigest()=='2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090'
 source=(V2/'nodes/APQNodes.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in source
 assert (V2/'LICENSE').read_bytes()==(PACK/'LICENSE').read_bytes()

def test_stored_pair_and_zip_two_pristine_roundtrips_wrong_source_refusal_cache_hygiene(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected
 assert PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-apqnodes/x25a7aea';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'tampered/comfyui-apqnodes/x25a7aea';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as f:f.write(b'\n#tampered')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))
