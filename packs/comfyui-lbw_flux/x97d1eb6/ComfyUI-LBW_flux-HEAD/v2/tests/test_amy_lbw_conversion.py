"""Byte-exact parser oracle, zero-capability guests, full resource/pair gates."""
import asyncio,copy,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
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
PAIR=DB/'patches/comfyui-lbw_flux/x97d1eb6/comfyui-lbw_flux-x97d1eb6'
ID='LoraBlockWeight_Flux'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('amy_lbw_old',PACK);NEW=load('amy_lbw_new',V2)
SOURCE=OLD.NODE_CLASS_MAPPINGS[ID];CLS=NEW.NODE_CLASS_MAPPINGS[ID];CLS.GET_SCHEMA()
def oracle(text):
 expected=SOURCE().test(text);actual=CLS.execute(text).result
 assert actual==expected and type(actual[0]) is str
 assert len(actual[0].split(','))==58 and set(actual[0].split(','))<={'0','1'}
 return actual
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':'LoraBlockWeightFluxSecure','sdk_refs':False,'permissions':[],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}
def test_full_source_census_schema_lazy_default_name_and_proxy():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id==ID and schema.display_name==ID and schema.category==SOURCE.CATEGORY
 assert [o.io_type for o in schema.outputs]==['STRING'] and schema.outputs[0].display_name=='block_vector'
 assert len(schema.inputs)==1 and schema.inputs[0].id=='layer_or_multi_layer' and schema.inputs[0].io_type=='STRING'
 for key,value in SOURCE.INPUT_TYPES()['required']['layer_or_multi_layer'][1].items():assert schema.inputs[0].as_dict()[key]==value
 assert schema.inputs[0].as_dict()['lazy'] is True
 assert CLS.check_lazy_status(layer_or_multi_layer=None)==['layer_or_multi_layer']
 assert CLS.check_lazy_status(layer_or_multi_layer='1')==[]
 proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_lbw_proxy')
 assert list(proxy.node_mappings)==[ID] and not proxy.routes and proxy.web_directory is None
 assert CLS.SDK_PERMISSIONS==() and CLS.SDK_REFS is False
 assert (PACK/'LBW_flux.py').read_bytes()==(V2/'LBW_flux.py').read_bytes()

@pytest.mark.parametrize('index',range(-3,64))
def test_all_indices_one_based58_negative_zero_outofbounds(index):
 actual=oracle(str(index))[0].split(',')
 assert actual.count('0')==(1 if 1<=index<=58 else 0)
 if 1<=index<=58:assert actual[index-1]=='0'

@pytest.mark.parametrize('start',[-5,0,1,2,15,57,58,59,100])
@pytest.mark.parametrize('width',[-10,-1,0,1,5,58])
def test_range_expansion_order_negative_syntax_clamped_final_not_input(start,width):
 oracle(str(start)+'-'+str(start+width))

TEXTS=['', ' ', '1,2,58', '2-10,15', '2-10,4-6,2,15,15','58-1','1--2','1-2-3','-5','+5','1.0,NaN,inf','text,1,2','１,５,５８','1，2',' 2 - 10 , 15 ','0-100','<script>alert(1)</script>,2','../../etc/passwd,3','emoji😀,4',SOURCE.INPUT_TYPES()['required']['layer_or_multi_layer'][1]['default']]
@pytest.mark.parametrize('text',TEXTS)
def test_blank_invalid_unicode_comments_literal_adversarial_and_default(text):
 oracle(text)

def test_modification_helpers_duplicate_ranges_outofbounds_and_no_input_mutation():
 values=['1','2-5','58', '-1','59','invalid','2-3-4']
 before=values.copy()
 assert SOURCE().modify_numbers(values)==[0 if 1<=i<=5 or i==58 else 1 for i in range(1,59)]
 assert values==before
 oracle('1,1,2-3,2-3')

@pytest.mark.parametrize('text',['1-65536','999999-1065534',','.join(['58']*10000),'invalid-'*2000])
def test_supported_expanded_work_and_long_text_boundary(text):
 oracle(text)

def test_preflight_before_native_range_materialization_and_cumulative_work(monkeypatch):
 import importlib
 module=importlib.import_module(CLS.__module__)
 def forbidden(*args,**kwargs):raise AssertionError('native parser entered before refusal')
 monkeypatch.setattr(module.Source,'test',forbidden)
 for text,pattern in [('1-65537','expanded'),('1-40000,1-40000','expanded'),('1-999999999999999999999999999999','expanded'),('1'*65537,'text byte'),('😀'*16385,'text byte')]:
  with pytest.raises(ValueError,match=pattern):CLS.execute(text)
 with pytest.raises(TypeError):CLS.execute(['1'])

def test_two_fresh_zero_permission_guest_outer_STRING_work_refusals_and_asset_denial(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    cls=load('amy_lbw_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
    session=await GuestSession('amy-lbw-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=(),tenant='amy-lbw-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(text):
     r=await execution._async_map_node_over_list(prompt_id='amy-lbw-outer',unique_id=str(render),obj=cls,input_data_all={'layer_or_multi_layer':[text]},func=cls.FUNCTION,v3_data=None)
     return r[0].result
    try:
     assert session.sandbox_kind=='seatbelt'
     for text in TEXTS:assert await outer(text)==SOURCE().test(text)
     with pytest.raises(Exception,match='expanded'):await outer('1-65537')
     assert await outer('2-10,15')==SOURCE().test('2-10,15')
     refs=_sdk.InProcessRefResolver()
     plan=_sdk.ExecutionPlan(prompt_id='amy-lbw-probe',node_id='deny',node_type='AssetDenialProbe',tier='sandbox',node_module='tests.amy_lbw_permissions',inputs={},permissions=())
     with pytest.raises(Exception,match='assets|permission|capability'):
      await session.execute(plan,_sdk.Runtime(refs=refs,ctx=object(),ops=_sdk.InProcessOps()),capabilities=(),tenant='amy-lbw-user-'+str(render))
     assert await outer('58')==SOURCE().test('58')
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_complete_manifest_resources_stubs_authority_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 p=json.loads((V2/'source-provenance.json').read_text())
 pristine={f.relative_to(PACK).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in PACK.rglob('*') if f.is_file() and not f.is_relative_to(V2)}
 assert pristine==p['source_hashes'] and len(pristine)==15 and p['git_blob_path_mode_match']
 for name in pristine:
  if name not in ('__init__.py','pyproject.toml'):assert (PACK/name).read_bytes()==(V2/name).read_bytes()
 assert not (PACK/'LICENSE').exists() and 'license = {file = "LICENSE"}' in (PACK/'pyproject.toml').read_text()
 for name,expected in [('comfy-api.pyi','4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==expected
 code=(V2/'_secure_nodes.py').read_text()+(V2/'LBW_flux.py').read_text()
 for forbidden in ('_from_raw','folder_paths','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in code
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('*.js'))

def test_exact_pair_and_zip_twice_wrong_source_atomic_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes().decode())==expected
 assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
 for index in range(2):
  fresh=tmp_path/str(index)/'comfyui-lbw_flux/x97d1eb6';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-lbw_flux/x97d1eb6';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as out:out.write(b'\n#badsource')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
