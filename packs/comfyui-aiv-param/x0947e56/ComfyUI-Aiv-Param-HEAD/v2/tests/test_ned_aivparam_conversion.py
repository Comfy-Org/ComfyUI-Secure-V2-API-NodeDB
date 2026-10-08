"""Complete workflow-metadata pack: exact schema/text/serialization and guest."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
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
PAIR=DB/'patches/comfyui-aiv-param/x0947e56/comfyui-aiv-param-x0947e56'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('ned_aiv_old',PACK);NEW=load('ned_aiv_new',V2);ID='AivParam';CLS=NEW.NODE_CLASS_MAPPINGS[ID];CLS.GET_SCHEMA()
def manifest():return {'format':FORMAT,'web_directory':'js','runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':'AivParamSecure','sdk_refs':True,'permissions':[],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_actual_full_census_schema_defaults_tooltips_and_frontend_scope():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 old=OLD.NODE_CLASS_MAPPINGS[ID];schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id==ID and schema.display_name=='Aiv Param' and schema.category==old.CATEGORY
 assert schema.outputs==[] and not schema.is_output_node and not schema.hidden
 for inp,(name,spec) in zip(schema.inputs,old.INPUT_TYPES()['required'].items(),strict=True):
  assert inp.id==name and inp.io_type==spec[0] and not inp.optional
  for key,value in spec[1].items():assert inp.as_dict()[key]==value
 assert CLS.SDK_REFS is True and CLS.SDK_PERMISSIONS==()
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_aiv_proxy')
 assert list(loaded.node_mappings)==[ID] and not loaded.routes and loaded.web_directory.name=='js'
 assert sorted(p.name for p in loaded.web_directory.glob('*.js'))==['check.js']

def test_native_none_and_declared_input_typeerror_are_retained_source_controls():
 source=OLD.NODE_CLASS_MAPPINGS[ID]()
 assert source.execute() is None
 with pytest.raises(TypeError,match='unexpected keyword argument'):source.execute(text_param='[]',text_note='')
 # Deliberate approved metadata-only callability repair, not a source-success claim.
 assert CLS.execute(text_param='[]',text_note='').args==()
 with pytest.raises(TypeError):CLS.execute()

@pytest.mark.parametrize('param',['','[]','{not JSON}','\\{escaped\\}','<script>{x}</script>','中文😀{}','{','\\\\{','x'*131072],ids=['empty','list','invalidJSON','escaped','adversarial','unicode','brace','doubleSlash','maximum'])
@pytest.mark.parametrize('note',['','说明 {untouched}'])
def test_approved_zero_output_no_parse_no_sideeffects_and_text_limits(param,note):
 assert CLS.execute(param,note).args==()

def test_oversize_nonstring_metadata_refusal_without_reset_or_parse():
 for field,value in [('text_param','x'*131073),('text_note','x'*65537),('text_param','😀'*32769)]:
  values={'text_param':'[]','text_note':''};values[field]=value
  with pytest.raises(ValueError,match='byte budget'):CLS.execute(**values)
 for field in ('text_param','text_note'):
  for value in (None,1,False,{},[]):
   values={'text_param':'[]','text_note':''};values[field]=value
   with pytest.raises(TypeError,match='STRING'):CLS.execute(**values)

def test_two_fresh_required_zero_cap_guests_production_outer_empty_outputs_and_recovery(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    cls=load('ned_aiv_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
    session=await GuestSession('ned-aiv-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=(),tenant='aiv-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(param,note):
     result=await execution._async_map_node_over_list(prompt_id='aiv-outer',unique_id=str(render),obj=cls,input_data_all={'text_param':[param],'text_note':[note]},func=cls.FUNCTION,v3_data=None)
     return result[0]
    try:
     assert session.sandbox_kind=='seatbelt'
     for param in ('','[]','{not JSON}','\\{escaped\\}','中文😀{}','\\{'*65536):
      result=await outer(param,'help {text}')
      assert result.args==() and result.result is None and not result.ui
     with pytest.raises(Exception,match='byte budget'):await outer('x'*131073,'')
     with pytest.raises(Exception,match='STRING'):await outer(None,'')
     assert (await outer('recovered','')).args==()
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_actual_opaque_worker_browser_pinned_braces_destination_state_and_cleanup():
 result=subprocess.run(['node','ned_aivparam_browser.mjs'],cwd=V2/'tests',text=True,capture_output=True,timeout=90)
 print(result.stdout);print(result.stderr)
 assert result.returncode==0,result.stdout+result.stderr
 assert 'PASS exact pinned AivApp setter/getter controls' in result.stdout
 assert 'QUALIFIED production bridge' in result.stdout

def test_manifest_full_sources_resource_license_stubs_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 source=json.loads((V2/'source-provenance.json').read_text());assert source['exact_git_blob_and_path_match']
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==source['source_hashes'] and len(pristine)==6
 for name in ('LICENSE','readMe.md','images/node.png'):assert (V2/name).read_bytes()==(PACK/name).read_bytes()
 assert 'Apache License' in (V2/'LICENSE').read_text()
 for name,sha in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 js=(V2/'js/check.js').read_text()
 for forbidden in ('scripts/app.js','Object.defineProperty','document.','window.','fetch(','localStorage','parent.','innerHTML','addEventListener'):assert forbidden not in js
 for name in ('__init__.py','_secure_nodes.py','nodes/aivapp.py'):
  text=(V2/name).read_text()
  for forbidden in ('_from_raw','_wrap(','import nodes','from comfy.','folder_paths','PromptServer','subprocess','requests','sys.path','open('):assert forbidden not in text
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_stored_pair_zip_two_byte_exact_reconstructions_wrong_source(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 # Pristine CRLF is intentional: text-mode universal-newline decoding is not a byte oracle.
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_bytes()==diff.encode('utf-8')
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-aiv-param/x0947e56';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-aiv-param/x0947e56';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as stream:stream.write(b'\n#wrong pristine')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
