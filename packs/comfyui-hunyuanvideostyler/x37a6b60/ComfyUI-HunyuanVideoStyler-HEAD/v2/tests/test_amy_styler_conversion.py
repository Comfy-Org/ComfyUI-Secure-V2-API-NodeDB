"""All pinned style templates, serial composition and zero-capability real guests."""
import asyncio,ast,copy,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
import pytest
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk,io,sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-hunyuanvideostyler/x37a6b60/comfyui-hunyuanvideostyler-x37a6b60'
ID='HunyuanVideoStyler'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('amy_styler_old',PACK);NEW=load('amy_styler_new',V2)
SOURCE=OLD.NODE_CLASS_MAPPINGS[ID];CLS=NEW.NODE_CLASS_MAPPINGS[ID];CLS.GET_SCHEMA()
DATA=sys.modules[SOURCE.__module__].styler_data
NEWDATA=sys.modules[CLS.__module__].styler_data
CHOICES=[(group,name) for group in SOURCE.style_order for name in DATA[group] if name!='None']
PROMPTS=[('',''),('positive',''),('','negative'),('  spaces\n{prompt}, punctuation  ',' comma, '),('<script>alert(1)</script> café 🎬','</textarea> & "雪"'),('/etc/passwd','/Users/ben/secret')]
def inputs(positive='subject',negative='noise',debug=False,**styles):
 return {'text_positive':positive,'text_negative':negative,'debug_prompt':debug,**{group:'None' for group in SOURCE.style_order},**styles}
def differential(value):
 assert CLS.execute(**value).result==SOURCE().style_video_prompt(**value)
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':'HunyuanVideoStylerSecure','sdk_refs':False,'permissions':[],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_actual_census_schema_sorted_none_choices_output_names_and_proxy():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.category==SOURCE.CATEGORY and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[ID]
 assert [o.io_type for o in schema.outputs]==list(SOURCE.RETURN_TYPES)
 assert [o.display_name for o in schema.outputs]==list(SOURCE.RETURN_NAMES)
 assert [inp.id for inp in schema.inputs]==list(SOURCE.INPUT_TYPES()['required'])
 for inp in schema.inputs:
  spec=SOURCE.INPUT_TYPES()['required'][inp.id]
  if isinstance(spec[0],list):
   assert inp.as_dict()['options']==spec[0]
   assert spec[0][0]=='None' and spec[0][1:]==sorted(spec[0][1:])
  else:
   assert inp.io_type==spec[0]
   for key,value in spec[1].items():assert inp.as_dict()[key]==value
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==()
 pack=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_styler_proxy')
 assert list(pack.node_mappings)==[ID] and not pack.routes and pack.web_directory is None

@pytest.mark.parametrize('selection',CHOICES,ids=lambda x:x[0]+':'+x[1])
@pytest.mark.parametrize('prompts',PROMPTS)
def test_every_pinned_template_exact_blank_comma_unicode_braces_and_literal_text(selection,prompts):
 group,name=selection;differential(inputs(*prompts,**{group:name}))

@pytest.mark.parametrize('prompts',PROMPTS)
def test_all_ten_style_order_noncommuting_composition_and_none(prompts):
 styles={group:next(name for name in DATA[group] if name!='None') for group in SOURCE.style_order}
 differential(inputs(*prompts,**styles))
 differential(inputs(*prompts))
 assert len(SOURCE.style_order)==10
 expected=SOURCE().style_video_prompt(**inputs(*prompts,**styles))
 p,n=prompts
 for group in SOURCE.style_order:p,n=DATA[group][styles[group]].replace_prompts(p,n)
 assert expected==(p,n)

def test_debug_each_stage_native_invalid_choice_and_ignored_extra(capsys):
 value=inputs(debug=True,camera=CHOICES[[x[0] for x in CHOICES].index('camera')][1])
 expected=SOURCE().style_video_prompt(**value);old=capsys.readouterr().out
 actual=CLS.execute(**value).result;new=capsys.readouterr().out
 assert actual==expected and old==new and 'After applying camera' in new
 value=inputs(camera='definitely absent')
 with pytest.raises(KeyError):SOURCE().style_video_prompt(**value)
 with pytest.raises(KeyError):CLS.execute(**value)
 for ignored in (None,'',False):
  differential(inputs(camera=ignored,unknown_extra='ignored'))

def test_immutable_resources_no_duplicate_collision_and_loaded_semantics():
 assert (PACK/'HunyuanVideoStyler.py').read_bytes()==(V2/'HunyuanVideoStyler.py').read_bytes()
 seen={}
 for path in (PACK/'data').glob('*/*.json'):
  group=path.parent.name
  for template in json.loads(path.read_text()):
   key=group,template['name'];assert key not in seen;seen[key]=template
 assert len(CHOICES)==206 and len(list((PACK/'data').glob('*/*.json')))==11
 assert {g:{n:(t.prompt,t.negative_prompt) for n,t in DATA[g].items()} for g in DATA.keys()}=={g:{n:(t.prompt,t.negative_prompt) for n,t in NEWDATA[g].items()} for g in NEWDATA.keys()}
 # Misfiled time-of-day entries in weather remain usable, not silently relocated.
 assert 'weather/timeofday_styles.json' in json.loads((V2/'source-provenance.json').read_text())['source_hashes'] or (V2/'data/weather/timeofday_styles.json').exists()

@pytest.mark.parametrize('value',[inputs('x'*65537),inputs('', '🎬'*16385),inputs(debug=1),inputs(positive=[])])
def test_closed_text_byte_boolean_admission(value):
 with pytest.raises(ValueError):CLS.execute(**value)

def test_projected_work_bound_before_source_execution(monkeypatch):
 module=sys.modules[CLS.__module__];selected=CHOICES[0];template=NEWDATA[selected[0]][selected[1]]
 original=template.prompt
 try:
  template.prompt='{prompt}'*8
  monkeypatch.setattr(module.Source,'style_video_prompt',lambda *a,**k:pytest.fail('entered source before bounds'))
  with pytest.raises(ValueError,match='projected'):CLS.execute(**inputs('x'*16384,**{selected[0]:selected[1]}))
 finally:template.prompt=original

def test_two_fresh_zero_capability_guests_outer_STRING_owned_resources_and_no_state(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    cls=load('amy_styler_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
    session=await GuestSession('amy-styler-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=(),tenant='amy-styler-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(value):
     result=await execution._async_map_node_over_list(prompt_id='amy-styler-outer',unique_id=str(render),obj=cls,input_data_all={k:[v] for k,v in value.items()},func=cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     assert session.sandbox_kind=='seatbelt'
     controls=[inputs(*p) for p in PROMPTS]
     for group in SOURCE.style_order:
      names=[n for n in DATA[group] if n!='None']
      controls.extend(inputs('<img src=x onerror=alert(1)> {prompt} 🎬','negative',**{group:name}) for name in (names[0],names[-1]))
     controls.append(inputs(**{g:next(n for n in DATA[g] if n!='None') for g in SOURCE.style_order}))
     for value in controls:
      expected=SOURCE().style_video_prompt(**value);actual=await outer(value)
      assert actual==expected and len(actual)==2 and all(type(x) is str for x in actual)
     with pytest.raises(Exception,match='KeyError'):await outer(inputs(camera='missing'))
     with pytest.raises(Exception,match='byte bound'):await outer(inputs('x'*65537))
     assert await outer(inputs())==SOURCE().style_video_prompt(**inputs())
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_hashes_complete_pristine_license_stubs_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 p=json.loads((V2/'source-provenance.json').read_text())
 pristine={f.relative_to(PACK).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in PACK.rglob('*') if f.is_file() and not f.is_relative_to(V2)}
 assert pristine==p['source_hashes'] and len(pristine)==18 and p['exact_git_blob_path_mode_match']
 for name in pristine:
  if name!='__init__.py':assert (PACK/name).read_bytes()==(V2/name).read_bytes()
 assert 'MIT License' in (V2/'LICENSE').read_text()
 for name,digest in [('comfy-api.pyi','89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==digest
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('*.js'))
 wrapper=(V2/'_secure_nodes.py').read_text()
 for forbidden in ('_from_raw','folder_paths','import nodes','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in wrapper

def test_stored_pair_zip_two_byte_exact_roundtrips_wrong_source_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes().decode())==expected and PAIR.with_suffix('.diff').read_bytes().decode()==diff
 for index in range(2):
  fresh=tmp_path/str(index)/'comfyui-hunyuanvideostyler/x37a6b60';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-hunyuanvideostyler/x37a6b60';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as file:file.write(b'\n#wrong pristine')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
