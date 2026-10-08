"""Whole-pinned scheduler schema/math, actual guest/outer and release integrity."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
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
PAIR=DB/'patches/comfyui-customscheduler/x1d98936/comfyui-customscheduler-x1d98936'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_cs_original',PACK);NEW=load('ned_cs_v2',V2)
CLS=NEW.NODE_CLASS_MAPPINGS['CustomScheduler'];CLS.GET_SCHEMA()
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'web_directory':'js','nodes':{'CustomScheduler':{'module':'node','class':'CustomScheduler','sdk_refs':True,'permissions':[],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}
def inputs(steps,seed=17):
 rng=random.Random(seed);return {'steps':steps,**{f'sigma_{i}':rng.uniform(0,100) for i in range(26)}}
async def local(values):
 refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id='cs-local',node_id='1',node_type='CustomScheduler',inputs=values,permissions=())
 runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
 with _sdk.bind_runtime(runtime.refs,runtime.ctx,runtime.ops):
  return (await _sdk.unwrap_outputs(refs,await CLS.execute(**values))).result[0]
def test_actual_census_schema_and_proxy():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==['CustomScheduler']
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 old=OLD.NODE_CLASS_MAPPINGS['CustomScheduler'];original=old.INPUT_TYPES();schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.category==old.CATEGORY and [o.io_type for o in schema.outputs]==list(old.RETURN_TYPES)
 assert len(schema.inputs)==27
 for inp in schema.inputs:
  section='optional' if inp.optional else 'required';spec=original[section][inp.id]
  assert inp.io_type==spec[0]
  for k,v in spec[1].items():assert inp.as_dict()[k]==v
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_cs_proxy')
 assert list(loaded.node_mappings)==['CustomScheduler'] and not loaded.routes and loaded.web_directory==V2/'js'

@pytest.mark.parametrize('steps',range(1,26))
@pytest.mark.parametrize('seed',[1,101,999])
def test_float32_exact_order_length_and_values(steps,seed):
 value=inputs(steps,seed);expected=OLD.NODE_CLASS_MAPPINGS['CustomScheduler']().get_sigmas(**value)[0]
 result=asyncio.run(local(value));assert result.dtype==torch.float32 and result.device.type=='cpu'
 assert torch.equal(result,expected) and tuple(result.shape)==(steps+1,)

@pytest.mark.parametrize('steps',range(1,26))
def test_source_missing_active_optional_key_error(steps):
 value=inputs(steps);value.pop(f'sigma_{steps}')
 with pytest.raises(KeyError) as old:OLD.NODE_CLASS_MAPPINGS['CustomScheduler']().get_sigmas(**value)
 with pytest.raises(KeyError) as new:asyncio.run(local(value))
 assert str(old.value)==str(new.value)

@pytest.mark.parametrize('steps',[True,False,0,26,-1,1.5,'4',None])
def test_bounded_steps_refusal(steps):
 with pytest.raises(ValueError,match='1..25'):asyncio.run(local(inputs(steps)))

@pytest.mark.parametrize('sigma',[True,-1,float('nan'),float('inf'),[1],'1'])
def test_public_finite_nonnegative_scalar_contract_refusal(sigma):
 value=inputs(1);value['sigma_0']=sigma
 with pytest.raises((TypeError,ValueError)):asyncio.run(local(value))

def test_exact_source_defaults_and_unused_optional_values():
 source=OLD.NODE_CLASS_MAPPINGS['CustomScheduler'].INPUT_TYPES();value={'steps':4,**{k:v[1]['default'] for k,v in source['optional'].items()}}
 assert torch.equal(asyncio.run(local(value)),OLD.NODE_CLASS_MAPPINGS['CustomScheduler']().get_sigmas(**value)[0])
 value['sigma_25']=object() # ignored exactly; no container crosses the guest here
 assert torch.equal(asyncio.run(local(value)),torch.FloatTensor([4.12,1.62,.7,.04,0]))

def test_two_fresh_zero_capability_guests_real_outer_sigmas_and_reconstruction(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for index in range(2):
    fresh=tmp_path/str(index);shutil.copytree(V2,fresh)
    cls=load('ned_cs_fresh_'+str(index),fresh).NODE_CLASS_MAPPINGS['CustomScheduler'];cls.GET_SCHEMA()
    session=await GuestSession('ned-cs-'+str(index),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=(),tenant='cs-user-'+str(index))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(value):return (await execution._async_map_node_over_list(prompt_id='cs-outer',unique_id=str(index),obj=cls,input_data_all={k:[v] for k,v in value.items()},func=cls.FUNCTION,v3_data=None))[0].result[0]
    try:
     for steps in (1,4,7,25):
      value=inputs(steps);result=await outer(value)
      assert type(result) is torch.Tensor and result.dtype==torch.float32 and torch.equal(result,OLD.NODE_CLASS_MAPPINGS['CustomScheduler']().get_sigmas(**value)[0])
     value=inputs(4);value.pop('sigma_3')
     with pytest.raises(Exception,match='KeyError.*sigma_3'):await outer(value)
     value=inputs(1);value['sigma_0']=-1
     with pytest.raises(Exception,match='nonnegative|negative'):await outer(value)
     with pytest.raises(Exception,match='1..25'):await outer(inputs(26))
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_provenance_stubs_license_boundary_and_cache():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes']
 assert (V2/'LICENSE').read_bytes()==(PACK/'LICENSE').read_bytes()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 py=(V2/'node.py').read_text();js=(V2/'js/extension.js').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in py
 for forbidden in ('document','window','localStorage','indexedDB','fetch(', 'Object.defineProperty','app.js','addEventListener'):assert forbidden not in js
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_pair_and_zip_two_exact_roundtrips(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-customscheduler/x1d98936';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
