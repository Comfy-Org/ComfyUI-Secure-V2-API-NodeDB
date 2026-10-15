import ast,asyncio,contextlib,importlib.util,io as streamio,json,os,shutil,sys
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
from comfy_secure_nodes.execution import CloudExecutionBackend
from comfy_secure_nodes.packmanifest import encode_schema
from comfy_secure_nodes.transport.host import GuestSession
def load(name,root):
 s=importlib.util.spec_from_file_location(name,root/'__init__.py',submodule_search_locations=[str(root)]);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
OLD=load('many_console_original',PACK);NEW=load('many_console',V2);CLASS=NEW.NODE_CLASS_MAPPINGS['ShowAnyTextInCMDconsoleSG']
COLORS=['white','red','green','yellow','blue','magenta','cyan','black','unknown']
HEXES=['','#FF0055','00ff55','  ##abcdef  ','#ABCDEF','bad','   ','#12GG34','1234567','+10000','abcdef']
def oracle(text='line 😀\nsecond',show=True,color='white',hex=''):
 out=streamio.StringIO()
 with contextlib.redirect_stdout(out):result=OLD.NODE_CLASS_MAPPINGS['ShowAnyTextInCMDconsoleSG']().display_text(text,show,color,hex)
 return result,out.getvalue()
@pytest.mark.parametrize('show',[False,True])
@pytest.mark.parametrize('color',COLORS)
@pytest.mark.parametrize('hex',HEXES)
def test_literal_source_results_ui_and_complete_ansi_stdout(show,color,hex):
 expected,log=oracle(show=show,color=color,hex=hex);out=streamio.StringIO()
 with contextlib.redirect_stdout(out):result=asyncio.run(CLASS.execute('line 😀\nsecond',show,color,hex))
 assert result.result==expected['result']and result.ui==expected['ui']and out.getvalue()==log
def test_source_algorithm_bytes_census_and_native_schema():
 assert (V2/'_algorithm.py').read_bytes()==(PACK/'Show_Any_Text_in_CMD_console_SG.py').read_bytes()
 assert set(OLD.NODE_CLASS_MAPPINGS)==set(NEW.NODE_CLASS_MAPPINGS)=={'ShowAnyTextInCMDconsoleSG'}
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 schema=CLASS.GET_SCHEMA();inputs=CLASS.INPUT_TYPES()['required'];original=OLD.NODE_CLASS_MAPPINGS['ShowAnyTextInCMDconsoleSG'].INPUT_TYPES()['required']
 assert schema.node_id=='ShowAnyTextInCMDconsoleSG'and schema.category=='utils'and schema.is_output_node
 for name in original:
  assert name in inputs
  for key,value in original[name][1].items():assert inputs[name][1][key]==value
 assert inputs['color_preset'][0]=='COMBO'and inputs['color_preset'][1]['options']==original['color_preset'][0]
 assert CLASS.RETURN_TYPES==('STRING',)or CLASS.RETURN_TYPES==['STRING']
 assert not list(V2.rglob('*.js'))and not list(PACK.rglob('*.pyc'))
@pytest.mark.parametrize('values',[
 dict(text='x'*65281),dict(text=object()),dict(hex_color='x'*257),dict(color_preset='x'*65),dict(show_any_text_in_console='yes'),dict(text='\ud800')])
def test_before_print_closed_profile_refusal(values):
 out=streamio.StringIO()
 with contextlib.redirect_stdout(out),pytest.raises((ValueError,UnicodeError)):
  asyncio.run(CLASS.execute(**(dict(text='ok',show_any_text_in_console=True,color_preset='white',hex_color='')|values)))
 assert out.getvalue()==''
def test_full_text_profile_does_not_consume_entire_guest_stdout_budget():
 _,out=oracle(text='x'*65280,hex='#ffffff');assert len(out)<65536
def manifest():
 return dict(format='comfy-secure-nodes-v1',runtime=packruntime.manifest_declaration(V2),nodes={'ShowAnyTextInCMDconsoleSG':dict(module='Show_Any_Text_in_CMD_console_SG',**{'class':'ShowAnyTextInCMDconsoleSG'},sdk_refs=True,permissions=[],methods=dict(validate_inputs=False,fingerprint_inputs=False,check_lazy_status=False),schema=encode_schema(CLASS.GET_SCHEMA()))})
def test_two_required_fresh_guests_production_outer_zero_caps_stdout_ui_and_recovery(tmp_path,monkeypatch):
 monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required')
 async def run():
  previous=_sdk.providers.execution_backend;pids=[]
  try:
   for generation in range(2):
    root=tmp_path/f'pack-{generation}';shutil.copytree(V2,root);mod=load(f'many_console_guest_{generation}',root);cls=mod.NODE_CLASS_MAPPINGS['ShowAnyTextInCMDconsoleSG'];cls.GET_SCHEMA()
    session=await GuestSession(f'many-console-{generation}',guest_runtime_root=root).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      assert plan.permissions==()or not plan.permissions
      return await session.execute(plan,runtime,capabilities=(),tenant='many-console-user')
    _sdk.providers.register_execution_backend(Backend())
    async def outer(text,show,color,hex):
     values=dict(text=[text],show_any_text_in_console=[show],color_preset=[color],hex_color=[hex]);mapped=await execution._async_map_node_over_list('many-console-proof','1',cls,values,cls.FUNCTION);return (await execution.resolve_map_node_over_list_results(mapped))[0]
    try:
     assert session.sandbox_kind=='seatbelt'
     for show,color,hex in [(False,'red','#aa0011'),(True,'cyan',''),(True,'black','bad'),(True,'white','##abcdef'),(True,'unknown','FF0055')]:
      expected,stdout=oracle(show=show,color=color,hex=hex);actual=await outer('line 😀\nsecond',show,color,hex)
      assert actual.result==expected['result']and actual.ui==expected['ui']and session.last_stdout==stdout
     expected,stdout=oracle(text='x'*65280);actual=await outer('x'*65280,True,'white','');assert actual.result==expected['result']and actual.ui==expected['ui']and session.last_stdout==stdout
     with pytest.raises(Exception):await outer('x'*65281,True,'white','')
     assert session.last_stdout==''
     expected,stdout=oracle(text='recovered',show=False);actual=await outer('recovered',False,'white','');assert actual.result==expected['result']and actual.ui==expected['ui']and session.last_stdout==stdout
     assert session.last_guest_pid not in (None,os.getpid());pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(previous)
  assert len(set(pids))==2;print('required console guest PIDs',pids)
 asyncio.run(run())
def test_actual_cloud_backend_local_source_selection(monkeypatch):
 monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE','required');monkeypatch.delenv('COMFY_SECURE_REALM_ROOT',raising=False)
 mod=load('custom_nodes.many_console_cloud',V2);cls=mod.NODE_CLASS_MAPPINGS['ShowAnyTextInCMDconsoleSG'];cls.GET_SCHEMA();original=packruntime.resolve_for_tenant
 def selected(spec,tenant):
  assert spec is None
  resolved=original(spec,tenant);assert resolved.python_executable==Path(sys.executable)
  return replace(resolved,spec=replace(resolved.spec,pack_root=PACK))
 monkeypatch.setattr(packruntime,'resolve_for_tenant',selected)
 async def run():
  previous=_sdk.providers.execution_backend;backend=CloudExecutionBackend();_sdk.providers.register_execution_backend(backend)
  try:
   expected,stdout=oracle(text='actual cloud local',hex='#123ABC');values=dict(text=['actual cloud local'],show_any_text_in_console=[True],color_preset=['white'],hex_color=['#123ABC']);mapped=await execution._async_map_node_over_list('many-console-cloud','1',cls,values,cls.FUNCTION);actual=(await execution.resolve_map_node_over_list_results(mapped))[0];session=next(iter(backend.guests._sessions.values()))
   assert actual.result==expected['result']and actual.ui==expected['ui']and session.last_stdout==stdout and session.sandbox_kind=='seatbelt';print('actual Cloud backend guest PID',session.last_guest_pid)
  finally:_sdk.providers.register_execution_backend(previous);await backend.shutdown()
 asyncio.run(run())
def test_manifest_actual_proxy_plain_zip_roundtrips_and_wrong_preimage(tmp_path):
 assert json.loads((V2/'secure-nodes.json').read_bytes())==manifest()
 pair=DB/'patches/comfyui-show-any-text-in-cmd-console-sg/x8f58b4b/comfyui-show-any-text-in-cmd-console-sg-x8f58b4b';m,d=packpatch.generate(PACK.parent)
 assert json.loads(pair.with_suffix('.json').read_bytes())==m and pair.with_suffix('.diff').read_bytes().decode()==d
 for kind in ['plain','zip']:
  fresh=tmp_path/kind/'comfyui-show-any-text-in-cmd-console-sg/x8f58b4b';fresh.mkdir(parents=True);shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if kind=='plain':packpatch.apply(fresh,m,d)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(m,d))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 bad=tmp_path/'bad/comfyui-show-any-text-in-cmd-console-sg/x8f58b4b';bad.mkdir(parents=True);shutil.copytree(PACK,bad/PACK.name,ignore=shutil.ignore_patterns('v2'));(bad/PACK.name/'Show_Any_Text_in_CMD_console_SG.py').write_text('wrong')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(bad,m,d)
 proxy=packdb.load_pack(PACK.parent,mount_name='custom_nodes.many_console_proxy',pack_id='comfyui-show-any-text-in-cmd-console-sg/x8f58b4b');assert set(proxy.node_mappings)=={'ShowAnyTextInCMDconsoleSG'}and not proxy.routes and proxy.web_directory is None
