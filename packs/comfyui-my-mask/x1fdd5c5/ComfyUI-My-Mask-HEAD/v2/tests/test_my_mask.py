"""Source bits, typed identity, pre-raw bounds, required guest and artifact gates."""
import asyncio, importlib.util, itertools, json, os, shutil, sys
from dataclasses import replace
from pathlib import Path
import pytest
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;DB=PACK.parents[3]
CORE=Path(os.environ.get('COMFY_CORE_ROOT','/Users/ben/comfy/ComfyUI-secure-nodes'))
OVERLAY=Path(os.environ.get('MANY_OVERLAY_ROOT','/Users/ben/comfy/ComfyUI_secure_nodes'))
sys.path[:0]=[str(CORE),str(OVERLAY/'backend')]
from comfy.cli_args import args
args.cpu=True
import torch
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb,packpatch,packruntime
from comfy_secure_nodes.packmanifest import encode_schema
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.execution import CloudExecutionBackend
def load(name,root):
 s=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)])
 m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
OLD=load('many_my_mask_original',PACK);NEW=load('many_my_mask',V2);IDS=list(OLD.NODE_CLASS_MAPPINGS)
DTYPES=[torch.bool,torch.int8,torch.uint8,torch.int16,torch.int32,torch.int64,torch.float16,torch.float32,torch.float64,torch.complex64,torch.complex128,torch.bfloat16]
def pixels(dtype,kind):
 a=torch.zeros((1,9,12),dtype=dtype)
 if kind=='concave':a[:,1:8,2]=1;a[:,7,2:10]=1;a[:,1:8,9]=1
 elif kind=='separate':a[:,1,1]=1;a[:,7,10]=1
 elif kind=='fractional':a=a.to(torch.float32);a[:,1:8,2:10]=0.75;a=a.to(dtype)
 elif kind=='top_only':a[:,1:3,2:7]=1
 elif kind=='noncontiguous':a[:,1:8,2]=1;a[:,7,2:10]=1;a=a.transpose(-2,-1)
 return a
CASES=list(itertools.product(IDS,DTYPES,['zero','concave','separate','fractional','top_only','noncontiguous']))
def bits(a,b):
 assert a.shape==b.shape and a.dtype==b.dtype and a.device.type==b.device.type=='cpu'
 assert torch.equal(a.contiguous().reshape(-1).view(torch.uint8),b.contiguous().reshape(-1).view(torch.uint8))
async def in_process(node_id,value):
 refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan('my-mask','1',node_id,permissions=('inspect','raw'))
 with _sdk.bind_runtime(refs,_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):
  source_ref=_sdk.MaskRef._wrap(await refs.create('MASK',value))
  result=await NEW.NODE_CLASS_MAPPINGS[node_id].execute(source_ref)
  return await refs.resolve(result.result[0]),result.result[0].id==source_ref.id
def native(node_id,value):return OLD.NODE_CLASS_MAPPINGS[node_id]().generate_convex_mask(value)[0]
@pytest.mark.parametrize('node_id,dtype,kind',CASES)
def test_every_source_dtype_contour_branch_bits_and_no_contour_identity(node_id,dtype,kind):
 value=pixels(dtype,kind);before=value.clone()
 try:expected=native(node_id,value)
 except Exception as error:
  with pytest.raises(type(error)):asyncio.run(in_process(node_id,value))
 else:
  actual,identity=asyncio.run(in_process(node_id,value));bits(expected,actual);assert identity==(expected is value)
 bits(before,value)
@pytest.mark.parametrize('node_id',IDS)
@pytest.mark.parametrize('shape',[(5,7),(1,1,7),(1,0,4),(1,4,0),(2,5,7),(1,1,1)])
def test_native_small_geometry_quirks_and_errors(node_id,shape):
 value=torch.ones(shape)
 try:expected=native(node_id,value)
 except Exception as error:
  with pytest.raises(type(error)):asyncio.run(in_process(node_id,value))
 else:actual,identity=asyncio.run(in_process(node_id,value));bits(actual,expected);assert identity==(expected is value)
@pytest.mark.parametrize('node_id',IDS)
def test_source_schema_census_and_algorithm_byte_exact(node_id):
 assert (PACK/'nodes.py').read_bytes()==(V2/'nodes.py').read_bytes()
 old=OLD.NODE_CLASS_MAPPINGS[node_id];new=NEW.NODE_CLASS_MAPPINGS[node_id]
 assert new.GET_SCHEMA().node_id==node_id and new.GET_SCHEMA().category==old.CATEGORY
 assert new.INPUT_TYPES()['required']=={'mask':('MASK',{})}
 assert old.INPUT_TYPES()['required']=={'mask':('MASK',)}
 assert tuple(new.RETURN_TYPES)==old.RETURN_TYPES
 assert NEW.NODE_DISPLAY_NAME_MAPPINGS==OLD.NODE_DISPLAY_NAME_MAPPINGS
 assert new.SDK_REFS and new.SDK_PERMISSIONS==('inspect','raw')
@pytest.mark.parametrize('shape',[[1,1025,1024],[1,4097,1],[1,1,1,1],[1,-1,3],None,[1,True,3]])
def test_metadata_preflight_refuses_before_any_raw_or_native_work(shape):
 class Held:
  async def describe(self):return {'shape':shape}
  async def raw(self):raise AssertionError('raw materialized before admission')
 with pytest.raises(ValueError):asyncio.run(NEW.MaskToConvexMask.execute(Held()))
def test_projected_budget_boundary_no_large_allocation():
 from many_my_mask.admission import geometry
 assert geometry({'shape':[1,1024,1024]})==[1,1024,1024]
 with pytest.raises(ValueError):geometry({'shape':[1,1024,1025]})
def test_two_fresh_required_guests_all_nodes_dtype_identity_denials_recovery(tmp_path,monkeypatch):
 monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for generation in range(2):
    root=tmp_path/f'pack-{generation}';shutil.copytree(V2,root);mod=load(f'many_my_mask_guest_{generation}',root)
    for cls in mod.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
    session=await GuestSession(f'many-my-mask-{generation}',guest_runtime_root=root).start();grants=['inspect','raw']
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      assert plan.permissions==('inspect','raw')
      return await session.execute(plan,runtime,capabilities=tuple(grants),tenant='many-my-mask-user')
    _sdk.providers.register_execution_backend(Backend())
    async def outer(node_id,value):
     cls=mod.NODE_CLASS_MAPPINGS[node_id]
     mapped=await execution._async_map_node_over_list('my-mask-proof','1',cls,{'mask':[value]},cls.FUNCTION)
     return (await execution.resolve_map_node_over_list_results(mapped))[0].result[0]
    try:
     assert session.sandbox_kind=='seatbelt'
     for node_id,dtype,kind in CASES:
      if dtype==torch.bfloat16:continue
      value=pixels(dtype,kind);owned=value.contiguous()
      # The public raw channel supplies contiguous snapshots. Noncontiguous
      # source-layout errors are separate in-process controls, not guest parity.
      try:expected=native(node_id,owned)
      except Exception:
       with pytest.raises(Exception):await outer(node_id,value)
      else:
       actual=await outer(node_id,value)
       bits(actual,expected);assert (actual is value)==(expected is owned)
     for node_id in IDS:
      value=pixels(torch.float32,'concave')
      for missing in ['raw','inspect']:
       grants.remove(missing)
       with pytest.raises(Exception):await outer(node_id,value)
       grants[:]=['inspect','raw'];bits(await outer(node_id,value),native(node_id,value))
      with pytest.raises(Exception):await outer(node_id,torch.empty((1,4096,4096),device='meta'))
      bits(await outer(node_id,value),native(node_id,value))
      with pytest.raises(Exception):await outer(node_id,pixels(torch.bfloat16,'concave'))
      bits(await outer(node_id,value),native(node_id,value))
     pids.append(session.last_guest_pid);assert pids[-1]not in (None,os.getpid())
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2;print('required My-Mask PIDs',pids)
 asyncio.run(run())
def test_actual_cloud_backend_local_source_selection_both_nodes(monkeypatch):
 monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required');monkeypatch.delenv('COMFY_SECURE_REALM_ROOT',raising=False)
 mod=load('custom_nodes.many_my_mask_cloud',V2)
 for cls in mod.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
 real=packruntime.resolve_for_tenant
 def selected(spec,tenant):
  assert spec is None
  resolved=real(spec,tenant);assert resolved.python_executable==Path(sys.executable)
  return replace(resolved,spec=replace(resolved.spec,pack_root=PACK))
 monkeypatch.setattr(packruntime,'resolve_for_tenant',selected)
 async def run():
  prior=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.register_execution_backend(backend)
  try:
   for node_id in IDS:
    value=pixels(torch.float64,'concave');cls=mod.NODE_CLASS_MAPPINGS[node_id]
    mapped=await execution._async_map_node_over_list('my-mask-cloud','1',cls,{'mask':[value]},cls.FUNCTION)
    actual=(await execution.resolve_map_node_over_list_results(mapped))[0].result[0];bits(actual,native(node_id,value))
   sessions=list(backend.guests._sessions.values());assert len(sessions)==1 and sessions[0].sandbox_kind=='seatbelt'
   print('actual My-Mask Cloud backend PID',sessions[0].last_guest_pid)
  finally:_sdk.providers.register_execution_backend(prior);await backend.shutdown()
 asyncio.run(run())
def manifest():
 return dict(format='comfy-secure-nodes-v1',runtime=packruntime.manifest_declaration(V2),nodes={node_id:dict(module='wrappers',**{'class':cls.__name__},sdk_refs=True,permissions=['inspect','raw'],methods=dict(validate_inputs=False,fingerprint_inputs=False,check_lazy_status=False),schema=encode_schema(cls.GET_SCHEMA()))for node_id,cls in NEW.NODE_CLASS_MAPPINGS.items()})
def test_manifest_actual_proxy_plain_zip_reconstruction_and_wrong_source(tmp_path):
 assert json.loads((V2/'secure-nodes.json').read_bytes())==manifest()
 pair=DB/'patches/comfyui-my-mask/x1fdd5c5/comfyui-my-mask-x1fdd5c5';m,d=packpatch.generate(PACK.parent)
 assert json.loads(pair.with_suffix('.json').read_bytes())==m and pair.with_suffix('.diff').read_bytes().decode()==d
 for kind in ['plain','zip']:
  fresh=tmp_path/kind/'comfyui-my-mask/x1fdd5c5';fresh.mkdir(parents=True);shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if kind=='plain':packpatch.apply(fresh,m,d)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(m,d))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 bad=tmp_path/'bad/comfyui-my-mask/x1fdd5c5';bad.mkdir(parents=True);shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'));(bad/PACK.name/'nodes.py').write_text('wrong')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,m,d)
 proxy=packdb.load_pack(PACK.parent,mount_name='custom_nodes.many_my_mask_proxy',pack_id='comfyui-my-mask/x1fdd5c5')
 assert set(proxy.node_mappings)==set(IDS)and not proxy.routes and proxy.web_directory is None
