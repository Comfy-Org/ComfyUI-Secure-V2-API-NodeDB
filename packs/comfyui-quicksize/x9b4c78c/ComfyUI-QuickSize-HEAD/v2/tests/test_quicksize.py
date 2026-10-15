import asyncio,importlib.util,itertools,json,os,shutil,sys
from dataclasses import replace
from pathlib import Path
import pytest
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;DB=PACK.parents[3];CORE=Path('/Users/ben/comfy/ComfyUI-secure-nodes');OVERLAY=Path('/Users/ben/comfy/ComfyUI_secure_nodes')
sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb,packpatch,packruntime
from comfy_secure_nodes.packmanifest import encode_schema
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.execution import CloudExecutionBackend
def load(name,root):
 s=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)]);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
OLD=load('many_quicksize_original',PACK);NEW=load('many_quicksize',V2);IDS=list(OLD.NODE_CLASS_MAPPINGS)
def cases():
 result=[]
 for node_id,cls in OLD.NODE_CLASS_MAPPINGS.items():
  entries=cls.INPUT_TYPES()['required'];names=list(entries);values=[kind if isinstance(kind,list)else[False,True]for kind,opt in entries.values()]
  for row in itertools.product(*values):result.append((node_id,dict(zip(names,row))))
 return result
CASES=cases();assert len(CASES)==184
@pytest.mark.parametrize('node_id,inputs',CASES)
def test_all_declared_source_presets_tiers_orientations_and_boolean_scales(node_id,inputs):
 source=OLD.NODE_CLASS_MAPPINGS[node_id]().get_size(**inputs);actual=asyncio.run(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**inputs));assert actual.result==source and all(type(x)is int for x in actual.result)
@pytest.mark.parametrize('node_id',IDS)
def test_source_schema_defaults_names_categories_and_algorithm_bytes(node_id):
 original=OLD.NODE_CLASS_MAPPINGS[node_id];cls=NEW.NODE_CLASS_MAPPINGS[node_id];schema=cls.GET_SCHEMA();old=original.INPUT_TYPES()['required'];new=cls.INPUT_TYPES()['required'];assert schema.node_id==node_id and schema.category==original.CATEGORY and not schema.is_output_node
 assert list(old)==list(new)
 for name,(kind,options)in old.items():
  assert new[name][1]['default']==options['default']
  if isinstance(kind,list):assert new[name][0]=='COMBO'and new[name][1]['options']==kind
  else:assert new[name][0]==kind
 assert list(cls.RETURN_TYPES)==list(original.RETURN_TYPES)and list(cls.RETURN_NAMES)==list(original.RETURN_NAMES)
 assert NEW.NODE_DISPLAY_NAME_MAPPINGS==OLD.NODE_DISPLAY_NAME_MAPPINGS
 for p in (PACK/'src').rglob('*.py'):assert p.read_bytes()==(V2/'src'/p.relative_to(PACK/'src')).read_bytes()
 inputs={k:v[1]['default']for k,v in old.items()};assert asyncio.run(cls.execute(**inputs)).result==original().get_size(**inputs)
@pytest.mark.parametrize('node_id',IDS)
def test_native_unknown_selection_and_orientation_fallbacks(node_id):
 original=OLD.NODE_CLASS_MAPPINGS[node_id];inputs={k:v[1]['default']for k,v in original.INPUT_TYPES()['required'].items()}
 for name in inputs:
  if name=='1.5x':continue
  values=inputs|{name:'unknown'};assert asyncio.run(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**values)).result==original().get_size(**values)
def test_native_named_table_quirks_not_repaired():
 q=NEW.NODE_CLASS_MAPPINGS['QuickSizeQwenNode'];assert asyncio.run(q.execute(megapixels='2.0',preset='16:9',orientation='horizontal')).result==(1664,928)
 s=NEW.NODE_CLASS_MAPPINGS['QuickSizeSD15Node'];assert asyncio.run(s.execute(preset='9:16',orientation='vertical',**{'1.5x':True})).result==(768,768)
 w=NEW.NODE_CLASS_MAPPINGS['QuickSizeWanNode'];assert asyncio.run(w.execute(model_size='Wan 5B',video_size='720p',preset='16:9',orientation='horizontal')).result==(1280,708)
@pytest.mark.parametrize('node_id',IDS)
def test_refuse_closed_types_or_oversize_before_native_lookup(node_id,monkeypatch):
 import importlib
 wrappers=importlib.import_module(NEW.__name__+'.wrappers');original=wrappers.ORIGINAL[node_id];inputs={k:v[1]['default']for k,v in original.INPUT_TYPES()['required'].items()}
 def never(*a,**k):raise AssertionError('native work before closed admission')
 monkeypatch.setattr(original,'get_size',never)
 with pytest.raises(ValueError):asyncio.run(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**(inputs|{'preset':'x'*65})))
 with pytest.raises(ValueError):asyncio.run(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**(inputs|{'preset':object()})))
 if '1.5x'in inputs:
  with pytest.raises(ValueError):asyncio.run(NEW.NODE_CLASS_MAPPINGS[node_id].execute(**(inputs|{'1.5x':object()})))
def test_two_fresh_required_guests_all184_options_outer_zero_cap_and_recovery(tmp_path,monkeypatch):
 monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for generation in range(2):
    root=tmp_path/f'pack-{generation}';shutil.copytree(V2,root);mod=load(f'many_quicksize_guest_{generation}',root)
    for cls in mod.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
    session=await GuestSession(f'many-quicksize-{generation}',guest_runtime_root=root).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      assert not plan.permissions
      return await session.execute(plan,runtime,capabilities=(),tenant='many-quicksize-user')
    _sdk.providers.register_execution_backend(Backend())
    async def outer(node_id,inputs):
     cls=mod.NODE_CLASS_MAPPINGS[node_id];mapped=await execution._async_map_node_over_list('many-quicksize-proof','1',cls,{k:[v]for k,v in inputs.items()},cls.FUNCTION);return (await execution.resolve_map_node_over_list_results(mapped))[0]
    try:
     assert session.sandbox_kind=='seatbelt'
     for node_id,inputs in CASES:
      value=await outer(node_id,inputs);assert value.result==OLD.NODE_CLASS_MAPPINGS[node_id]().get_size(**inputs)and all(type(x)is int for x in value.result)
     for node_id,inputs in [CASES[0],CASES[30],CASES[60],CASES[132],CASES[156]]:
      with pytest.raises(Exception):await outer(node_id,inputs|{'preset':'x'*65})
      value=await outer(node_id,inputs);assert value.result==OLD.NODE_CLASS_MAPPINGS[node_id]().get_size(**inputs)
     pids.append(session.last_guest_pid);assert pids[-1]not in(None,os.getpid())
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2;print('required QuickSize guest PIDs',pids)
 asyncio.run(run())
def test_actual_cloud_backend_local_source_selection_all_five(monkeypatch):
 monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required');monkeypatch.delenv('COMFY_SECURE_REALM_ROOT',raising=False);mod=load('custom_nodes.many_quicksize_cloud',V2)
 for cls in mod.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
 real=packruntime.resolve_for_tenant
 def selected(spec,tenant):
  assert spec is None
  resolved=real(spec,tenant);assert resolved.python_executable==Path(sys.executable);return replace(resolved,spec=replace(resolved.spec,pack_root=PACK))
 monkeypatch.setattr(packruntime,'resolve_for_tenant',selected)
 async def run():
  prior=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.register_execution_backend(backend)
  try:
   for node_id,source in OLD.NODE_CLASS_MAPPINGS.items():
    inputs={k:v[1]['default']for k,v in source.INPUT_TYPES()['required'].items()};cls=mod.NODE_CLASS_MAPPINGS[node_id];mapped=await execution._async_map_node_over_list('many-quicksize-cloud','1',cls,{k:[v]for k,v in inputs.items()},cls.FUNCTION);actual=(await execution.resolve_map_node_over_list_results(mapped))[0];assert actual.result==source().get_size(**inputs)
   sessions=list(backend.guests._sessions.values());assert len(sessions)==1 and sessions[0].sandbox_kind=='seatbelt';print('actual QuickSize Cloud backend PID',sessions[0].last_guest_pid)
  finally:_sdk.providers.register_execution_backend(prior);await backend.shutdown()
 asyncio.run(run())
def manifest():
 return dict(format='comfy-secure-nodes-v1',runtime=packruntime.manifest_declaration(V2),nodes={node_id:dict(module='wrappers',**{'class':cls.__name__},sdk_refs=True,permissions=[],methods=dict(validate_inputs=False,fingerprint_inputs=False,check_lazy_status=False),schema=encode_schema(cls.GET_SCHEMA()))for node_id,cls in NEW.NODE_CLASS_MAPPINGS.items()})
def test_manifest_actual_proxy_all5_plain_zip_roundtrips_and_wrong_preimage(tmp_path):
 assert json.loads((V2/'secure-nodes.json').read_bytes())==manifest();pair=DB/'patches/comfyui-quicksize/x9b4c78c/comfyui-quicksize-x9b4c78c';m,d=packpatch.generate(PACK.parent)
 assert json.loads(pair.with_suffix('.json').read_bytes())==m and pair.with_suffix('.diff').read_bytes().decode()==d
 for kind in ['plain','zip']:
  fresh=tmp_path/kind/'comfyui-quicksize/x9b4c78c';fresh.mkdir(parents=True);shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if kind=='plain':packpatch.apply(fresh,m,d)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(m,d))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 bad=tmp_path/'bad/comfyui-quicksize/x9b4c78c';bad.mkdir(parents=True);shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'));(bad/PACK.name/'src/quicksize/flux_quicksize.py').write_text('wrong')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,m,d)
 proxy=packdb.load_pack(PACK.parent,mount_name='custom_nodes.many_quicksize_proxy',pack_id='comfyui-quicksize/x9b4c78c');assert set(proxy.node_mappings)==set(IDS)and not proxy.routes and proxy.web_directory is None
