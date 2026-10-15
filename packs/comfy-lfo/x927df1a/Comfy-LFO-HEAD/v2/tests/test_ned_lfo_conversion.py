"""Complete five-node scalar math, source quirks, real guest and artifact gate."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import shutil
import struct
import sys
import pytest

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
PAIR=DB/'patches/comfy-lfo/x927df1a/comfy-lfo-x927df1a'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('ned_lfo_original',PACK);NEW=load('ned_lfo_v2',V2)
IDS=list(OLD.NODE_CLASS_MAPPINGS)
for cls in NEW.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{name:{'module':'_secure_nodes','class':cls.__name__,'sdk_refs':False,'permissions':[],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for name,cls in NEW.NODE_CLASS_MAPPINGS.items()}}
def defaults(name):return {k:v[1]['default'] for k,v in OLD.NODE_CLASS_MAPPINGS[name].INPUT_TYPES()['required'].items()}
def old(name,values):
 cls=OLD.NODE_CLASS_MAPPINGS[name];return getattr(cls(),cls.FUNCTION)(**values)[0]
def new(name,values):return NEW.NODE_CLASS_MAPPINGS[name].execute(**values).result[0]
def exact(a,b):assert type(a) is type(b) is float and struct.pack('!d',a)==struct.pack('!d',b)

def test_full_actual_census_schema_original_file_and_proxy():
 assert IDS==list(NEW.NODE_CLASS_MAPPINGS)==['LFO_Triangle','LFO_Sine','LFO_Sawtooth','LFO_Square','LFO_Pulse']
 assert (PACK/'lfonodes.py').read_bytes()==(V2/'lfonodes.py').read_bytes()
 assert not hasattr(OLD,'NODE_DISPLAY_NAME_MAPPINGS') and not hasattr(NEW,'NODE_DISPLAY_NAME_MAPPINGS')
 for name in IDS:
  cls=NEW.NODE_CLASS_MAPPINGS[name];source=OLD.NODE_CLASS_MAPPINGS[name];schema=cls.GET_SCHEMA();schema.validate()
  assert schema.node_id==name and schema.category==source.CATEGORY and [o.io_type for o in schema.outputs]==list(source.RETURN_TYPES)
  assert [i.id for i in schema.inputs]==list(source.INPUT_TYPES()['required'])
  for inp in schema.inputs:
   spec=source.INPUT_TYPES()['required'][inp.id];assert inp.io_type==spec[0] and not inp.optional
   for k,v in spec[1].items():assert inp.as_dict()[k]==v
  assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==()
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_lfo_proxy')
 assert list(loaded.node_mappings)==IDS and loaded.web_directory is None and not loaded.routes

@pytest.mark.parametrize('name',IDS)
@pytest.mark.parametrize('position',[-1000.5,-1.0,-.75,-.5,-.25,-0.0,0.0,.25,.5,.75,1.0,1000.5])
def test_wave_phase_boundaries_exact_double_bits(name,position):
 values=defaults(name);values.update(position=position,phase_offset=0.0)
 exact(new(name,values),old(name,values))

@pytest.mark.parametrize('name',IDS)
def test_300_seeded_vectors_defaults_negative_frequency_and_large_scalar(name):
 rng=random.Random(8317)
 exact(new(name,defaults(name)),old(name,defaults(name)))
 for _ in range(300):
  values={k:rng.uniform(-1000,1000) for k in defaults(name)}
  exact(new(name,values),old(name,values))
 values=defaults(name);values.update(position=1e100,phase_offset=-1e90,frequency=-.75,amplitude=-1e100,offset=1e99)
 exact(new(name,values),old(name,values))

def test_negative_phase_nonperiodic_source_quirks_not_normalized():
 values=defaults('LFO_Triangle');values.update(position=-.25,phase_offset=0.0)
 assert old('LFO_Triangle',values)==new('LFO_Triangle',values)==2.0
 assert old('LFO_Sawtooth',values)==new('LFO_Sawtooth',values)==-1.5

@pytest.mark.parametrize('name',IDS)
@pytest.mark.parametrize('bad',[True,None,'1',[1],float('nan'),float('inf'),-float('inf')])
def test_finite_nonboolean_scalar_admission(name,bad):
 values=defaults(name);values['position']=bad
 with pytest.raises(ValueError,match='finite nonboolean'):new(name,values)

@pytest.mark.parametrize('name',IDS)
def test_native_finite_arithmetic_overflow_error_and_missing_argument(name):
 values=defaults(name);values.update(position=1e308,frequency=1e308)
 try:old(name,values)
 except Exception as source:
  with pytest.raises(type(source),match=str(source)):new(name,values)
 else:raise AssertionError('overflow fixture no longer discriminates')
 values=defaults(name);values.pop('offset')
 with pytest.raises(TypeError):old(name,values)
 with pytest.raises(TypeError):new(name,values)

def test_nonfinite_result_narrowing_preserves_original_control():
 values=defaults('LFO_Triangle');values.update(position=-.25,phase_offset=0.0,amplitude=1e308,offset=1e308)
 assert math.isinf(old('LFO_Triangle',values))
 with pytest.raises(ValueError,match='output must be a finite'):new('LFO_Triangle',values)

def test_all_five_ids_two_fresh_zero_capability_guests_and_real_outer_float(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for index in range(2):
    fresh=tmp_path/str(index);shutil.copytree(V2,fresh)
    # Test-only probe in this disposable runtime, never in released V2 source.
    with (fresh/'_secure_nodes.py').open('a') as probe:
     probe.write('\nclass NedRawDenialProbe(io.ComfyNode):\n    @classmethod\n    async def execute(cls):\n        import torch\n        from comfy_api.latest import sdk\n        return io.NodeOutput(await sdk.TensorRef.from_value(torch.zeros(1)))\n')
    module=load('ned_lfo_fresh_'+str(index),fresh)
    for cls in module.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
    session=await GuestSession('ned-lfo-'+str(index),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):return await session.execute(plan,runtime,capabilities=(),tenant='lfo-user-'+str(index))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(name,values):
     cls=module.NODE_CLASS_MAPPINGS[name]
     result=await execution._async_map_node_over_list(prompt_id='lfo-outer',unique_id=name,obj=cls,input_data_all={k:[v] for k,v in values.items()},func=cls.FUNCTION,v3_data=None)
     return result[0].result[0]
    try:
     for name in IDS:
      for pos in (-.75,-.25,0.0,.5,17.25):
       values=defaults(name);values.update(position=pos,phase_offset=0.0,frequency=-1.75,amplitude=-2.0,offset=3.0)
       exact(await outer(name,values),old(name,values))
      values=defaults(name);values['position']=True
      with pytest.raises(Exception,match='finite nonboolean'):await outer(name,values)
      exact(await outer(name,defaults(name)),old(name,defaults(name)))
     refs=_sdk.InProcessRefResolver()
     plan=_sdk.ExecutionPlan(prompt_id='lfo-raw-denial',node_id='probe',node_type='NedRawDenialProbe',node_module=next(iter(module.NODE_CLASS_MAPPINGS.values())).__module__,inputs={},permissions=('raw',),method='execute')
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
     with pytest.raises(Exception,match='raw|permission|capabil'):await session.execute(plan,runtime,capabilities=(),tenant='lfo-user-'+str(index))
     exact(await outer('LFO_Sine',defaults('LFO_Sine')),old('LFO_Sine',defaults('LFO_Sine')))
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_provenance_resources_permissions_stubs_and_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text());assert provenance['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance['source_hashes']
 assert (V2/'LICENSE').read_bytes()==(PACK/'LICENSE').read_bytes()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 text=(V2/'_secure_nodes.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in text
 assert not list(PACK.rglob('*.js')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_patch_bundle_two_exact_roundtrips_and_wrong_source_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_text()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfy-lfo/x927df1a';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfy-lfo/x927df1a';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'lfonodes.py').open('ab') as f:f.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
