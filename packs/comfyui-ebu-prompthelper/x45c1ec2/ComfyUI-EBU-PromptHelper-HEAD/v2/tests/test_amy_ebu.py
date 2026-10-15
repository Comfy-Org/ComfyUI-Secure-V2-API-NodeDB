"""Full source algorithms + actual guest/all twelve public entrypoints."""
import asyncio,ast,copy,datetime,hashlib,importlib.util,json,os,random,shutil,sys
import time
from pathlib import Path
from unittest.mock import patch
import pytest
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution,torch,folder_paths
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-ebu-prompthelper/x45c1ec2/comfyui-ebu-prompthelper-x45c1ec2'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load('amy_ebu_old',PACK);NEW=load('amy_ebu_new',V2)
ALGO=sys.modules['amy_ebu_new.nodes'];WRAP=sys.modules['amy_ebu_new._secure_nodes']
for cls in NEW.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
def cls(short):return NEW.NODE_CLASS_MAPPINGS['EbuPromptHelper'+short]
def defaults(short):
 source=OLD.NODE_CLASS_MAPPINGS['EbuPromptHelper'+short];result={}
 for rows in source.INPUT_TYPES().values():
  for name,spec in rows.items():
   options=spec[1] if len(spec)>1 else {}
   result[name]=options.get('default',spec[0][0] if type(spec[0]) is list else '' if spec[0]=='STRING' else False if spec[0]=='BOOLEAN' else 0)
 return result
def native(short,kwargs):
 source=OLD.NODE_CLASS_MAPPINGS['EbuPromptHelper'+short];state=random.getstate()
 try:return getattr(source(),source.FUNCTION)(**kwargs)
 finally:random.setstate(state)
def differential(short,overrides=None):
 kwargs=defaults(short);kwargs.update(overrides or {})
 expected=native(short,kwargs);state=random.getstate()
 actual=asyncio.run(cls(short).execute(**kwargs)).result
 assert random.getstate()==state and actual==expected
 assert all(type(v) is str for v in actual)
 return actual
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{name:{'module':'_secure_nodes','class':c.__name__,'sdk_refs':False,'permissions':list(c.SDK_PERMISSIONS),'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(c.GET_SCHEMA()))} for name,c in NEW.NODE_CLASS_MAPPINGS.items()}}
def test_exact_all_twelve_schema_choices_uint64_options_return_order_proxy_permissions():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS) and len(NEW.NODE_CLASS_MAPPINGS)==12
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 for identity,c in NEW.NODE_CLASS_MAPPINGS.items():
  source=OLD.NODE_CLASS_MAPPINGS[identity];schema=c.GET_SCHEMA();schema.validate()
  assert schema.node_id==identity and schema.category==source.CATEGORY and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[identity]
  expected=[(kind,name,spec) for kind,rows in source.INPUT_TYPES().items() for name,spec in rows.items()]
  assert [i.id for i in schema.inputs]==[name for _,name,_ in expected]
  for item,(kind,name,spec) in zip(schema.inputs,expected):
   assert item.optional==(kind=='optional')
   if type(spec[0]) is list:assert item.options==spec[0]
   else:assert item.io_type==spec[0]
   for key,value in (spec[1] if len(spec)>1 else {}).items():assert item.as_dict()[key]==value
  assert [i.io_type for i in schema.outputs]==list(source.RETURN_TYPES)
  assert [i.display_name for i in schema.outputs]==list(getattr(source,'RETURN_NAMES',['STRING']*len(source.RETURN_TYPES)))
  assert c.SDK_REFS is False
  assert c.SDK_PERMISSIONS==(('assets',) if identity.endswith('LoadFileAsString') else ())
 proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_ebu_proxy')
 assert list(proxy.node_mappings)==list(NEW.NODE_CLASS_MAPPINGS) and proxy.web_directory is None and not proxy.routes

@pytest.mark.parametrize('short',['CombineTwoStrings','ConsumeListItem','ListSampler','RandomColorPalette','Randomize','Replace','SeasonWeatherTimeOfDay','Truncate','CharacterDescriberFemale','CharacterDescriberMale'])
@pytest.mark.parametrize('seed',[0,1,2,7,123,2**64-1])
def test_all_seeded_and_pure_default_algorithms_seed0_source_determinism(short,seed):
 overrides={'seed':seed} if 'seed' in defaults(short) else {}
 differential(short,overrides)

@pytest.mark.parametrize('kind',['analogous','art_house','chaotic','complementary','compound','split_complementary','tetradic','triadic'])
@pytest.mark.parametrize('size',['3 colors','4 colors','5 colors'])
@pytest.mark.parametrize('seed',[0,1,17,255])
def test_each_palette_family_size_order_draws_hex_and_padding(kind,size,seed):
 params={k:False for k in defaults('RandomColorPalette') if k.startswith('include_')}
 field={'analogous':'analogous','art_house':'art_house','chaotic':'chaotic','complementary':'complementary','compound':'compound','split_complementary':'split_complementary','tetradic':'tetradic','triadic':'triadic'}[kind]
 params['include_'+field+'_palettes']=True
 params.update(palette_size=size,seed=seed)
 differential('RandomColorPalette',params)
@pytest.mark.parametrize('preferred,avoided',[('Reds','Blues'),('Warm Colors','Cool Colors'),('Cool Colors','Warm Colors'),('Reds','Reds'),('Metallics','Metallics'),('None','Pastels')])
def test_palette_preferences_retry50_fallback_equal_conditions_and_all_disabled(preferred,avoided):
 params={k:False for k in defaults('RandomColorPalette') if k.startswith('include_')}
 params.update(prefer_color_family=preferred,avoid_color_family=avoided,seed=42)
 differential('RandomColorPalette',params)
@pytest.mark.parametrize('short',['CharacterDescriberFemale','CharacterDescriberMale'])
@pytest.mark.parametrize('enabled',[True,False])
def test_each_character_trait_independent_seed_offsets_and_disabled_branches(short,enabled):
 params={k:enabled for k in defaults(short) if k.endswith('_enabled')};params['seed']=101
 differential(short,params)
@pytest.mark.parametrize('delim,options',[('newlines','1>>blue\n2>>green\n0>>skip\nplain'),('commas','1>>blue,2>>green,0>>skip,plain'),('semi-colons','1>>blue;2>>green;0>>skip;plain'),('unknown','blue\ngreen')])
@pytest.mark.parametrize('case',[True,False])
def test_weighted_random_options_delimiters_zero_weights_native_seed_order_and_case(delim,options,case):
 differential('Randomize',{'prompt_text':'Cat cat dog','word_to_replace':'cat|dog','replacement_options':options,'case_sensitive':case,'seed':17,'delimit_options_with':delim})
@pytest.mark.parametrize('prompt,words,replacement',[('abc abc','abc','xyz'),('AbC ABC','abc','λ😀'),('a.b A.B','a.b','literal'),('a||b','|',''),('abc','x|','Z'),('abc','','Z'),('AA','a',r'\g<0>x')])
@pytest.mark.parametrize('case',[True,False])
def test_replace_sequential_empty_word_unicode_literal_regex_and_backreference(prompt,words,replacement,case):
 differential('Replace',{'prompt_text':prompt,'word_to_replace':words,'replace_with':replacement,'case_sensitive':case})
@pytest.mark.parametrize('delete',['delete before','delete after','unknown'])
@pytest.mark.parametrize('inclusive',[True,False])
@pytest.mark.parametrize('substring',['middle','','absent'])
def test_truncate_literal_first_occurrence_empty_unknown_and_missing(delete,inclusive,substring):
 differential('Truncate',{'prompt':'startmiddleendmiddle','substring':substring,'delete_option':delete,'inclusive':inclusive})
@pytest.mark.parametrize('text',['','1. red\n2. blue\n3. red','   \n🙂\n10. green\n','a\ra\nb\r\nc'])
@pytest.mark.parametrize('seed',[0,12])
def test_list_sampling_numbering_and_consume_first_duplicate_workflow_values(text,seed):
 differential('ListSampler',{'list':text,'seed':seed,'number_of_elements':2,'number_sampled_list':True})
 differential('ConsumeListItem',{'list':text,'seed':seed,'word_to_replace':'x','prompt_text':'x-x'})
@pytest.mark.parametrize('skew',['no skew','choose earliest of three','choose latest of three','choose middle of three','unknown'])
@pytest.mark.parametrize('time_from,time_to',[('6:00am','5:00pm'),('11:00pm','2:00am'),('12:00pm','12:00pm')])
def test_year_day_weather_skew_and_overnight_draw_order(skew,time_from,time_to):
 differential('SeasonWeatherTimeOfDay',{'seed':17,'year_from':1980,'year_to':2024,'time_from':time_from,'time_to':time_to,'year_skew':skew,'time_of_day_skew':skew})
def test_current_clock_fixed_source_formats_without_trusted_clock_claim():
 fixed=datetime.datetime(2024,2,29,13,5,9)
 class Clock:
  @staticmethod
  def now():return fixed
 with patch.object(sys.modules['amy_ebu_old.nodes'],'datetime',Clock),patch.object(ALGO,'datetime',Clock):
  assert differential('CurrentDateTime')==('February 29, 2024','1:05pm','2024-02-29 1:05:09pm','2024-02-29_13-05-09')
def test_concurrent_context_scope_and_reseed_helpers_no_global_rng_mutation():
 rng=sys.modules['amy_ebu_new._rng'];state=random.getstate()
 async def task(seed):
  with rng.scope():
   rng.random.seed(seed);await asyncio.sleep(0)
   expected=random.Random(seed).random()
   assert rng.random.random()==expected
   await asyncio.sleep(0)
   return ALGO.EbuPromptHelperCharacterDescriberFemale.generate(**defaults('CharacterDescriberFemale')|{'seed':seed})
 async def run():return await asyncio.gather(*(task(s) for s in (0,1,9,123)))
 actual=asyncio.run(run())
 assert actual==[native('CharacterDescriberFemale',defaults('CharacterDescriberFemale')|{'seed':s}) for s in (0,1,9,123)] and random.getstate()==state

@pytest.mark.parametrize('short,kwargs',[('Randomize',{'replacement_options':'1000000000000>>a'}),('Replace',{'prompt_text':'a'*10000,'word_to_replace':'a','replace_with':'a'*10}),('ConsumeListItem',{'prompt_text':'a'*10000,'word_to_replace':'a','list':'a'*10}),('CombineTwoStrings',{'str1':'😀'*16385})])
def test_text_tickets_and_projected_growth_refused_before_native_allocation(short,kwargs):
 params=defaults(short);params.update(kwargs)
 with pytest.raises(ValueError,match='budget'):asyncio.run(cls(short).execute(**params))
def test_replacement_cumulative_actual_growth_and_native_invalid_template_controls():
 limits=sys.modules['amy_ebu_new._limits']
 with limits.scope():
  text='a'
  for _ in range(15):text=limits.replace(text,'a','aa')
  assert len(text)==32768
  with pytest.raises(ValueError,match='output'):limits.replace(text,'a','aaa')
 with limits.scope(),patch.object(limits,'MAX_WORK',10):
  text=limits.replace('a'*5,'a','aa')
  with pytest.raises(ValueError,match='work'):limits.replace(text,'x','y')
 for short,params in [('Randomize',{'prompt_text':'abc','word_to_replace':'a','replacement_options':r'\1','case_sensitive':False}),('Replace',{'prompt_text':'abc','word_to_replace':'a','replace_with':r'\1','case_sensitive':False}),('SeasonWeatherTimeOfDay',{'time_from':'invalid'})]:
  kwargs=defaults(short)|params
  try:native(short,kwargs)
  except Exception as expected:
   with pytest.raises(type(expected)):asyncio.run(cls(short).execute(**kwargs))
  else:raise AssertionError('native malformed control unexpectedly succeeded')

def test_managed_loader_inprocess_newlines_empty_missing_utf8_and_refusal(tmp_path):
 input_root=tmp_path/'input';input_root.mkdir();(input_root/'nested').mkdir()
 (input_root/'nested'/'text.txt').write_bytes('λ😀\r\nline\rend\n'.encode())
 (input_root/'invalid.txt').write_bytes(b'\xff')
 (input_root/'large.txt').write_bytes(b'x'*65537)
 prior=folder_paths.get_input_directory();folder_paths.set_input_directory(str(input_root))
 async def run():
  for name,expected in [('nested/text.txt','λ😀\nline\nend\n'),('invalid.txt',''),('missing.txt',''),('','')]:
   result=await cls('LoadFileAsString').execute(directory='',file_name=name)
   assert result.result==(expected,)==native('LoadFileAsString',{'directory':str(input_root),'file_name':name})
  for directory,name in [('/tmp','secret'),('..','secret'),('','../secret'),('','C:\\secret'),('','bad\nlabel'),('','bad\x85label')]:
   with pytest.raises(ValueError,match='logical|traversal'):await cls('LoadFileAsString').execute(directory=directory,file_name=name)
  with pytest.raises(ValueError,match='asset byte budget'):await cls('LoadFileAsString').execute(directory='',file_name='large.txt')
 plan=_sdk.ExecutionPlan(prompt_id='amy-ebu-local',node_id='loader',node_type='EbuPromptHelperLoadFileAsString',tier='in_process',node_module='_secure_nodes',inputs={})
 try:
  with _sdk.bind_runtime(_sdk.InProcessRefResolver(),_sdk.InProcessCtxProvider().build(plan),_sdk.InProcessOps()):asyncio.run(run())
 finally:folder_paths.set_input_directory(prior)

def test_two_fresh_required_guest_all_twelve_outer_STRING_types_and_denials(tmp_path):
 async def run():
  previous=_sdk.providers.execution_backend;prior_input=folder_paths.get_input_directory();pids=[]
  input_root=tmp_path/'input';input_root.mkdir();(input_root/'text.txt').write_bytes('λ\r\nend\r'.encode());(input_root/'invalid.txt').write_bytes(b'\xff');(input_root/'big.txt').write_bytes(b'x'*65537)
  outside=tmp_path/'outside.txt';outside.write_text('secret');(input_root/'escape.txt').symlink_to(outside)
  folder_paths.set_input_directory(str(input_root))
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh);mod=load('amy_ebu_fresh_'+str(render),fresh)
    probe_spec=importlib.util.spec_from_file_location('tests.amy_ebu_permissions',fresh/'tests/amy_ebu_permissions.py')
    probe=importlib.util.module_from_spec(probe_spec);sys.modules[probe_spec.name]=probe;probe_spec.loader.exec_module(probe)
    session=await GuestSession('amy-ebu-'+str(render),guest_runtime_root=fresh).start();caps=()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=caps,tenant='amy-ebu-user')
    _sdk.providers.register_execution_backend(Backend())
    async def outer(short,kwargs):
     c=mod.NODE_CLASS_MAPPINGS['EbuPromptHelper'+short];c.GET_SCHEMA()
     result=await execution._async_map_node_over_list(prompt_id='amy-ebu-outer',unique_id=short+str(render),obj=c,input_data_all={k:[v] for k,v in kwargs.items()},func=c.FUNCTION,v3_data=None)
     return result[0].result
    try:
     assert session.sandbox_kind=='seatbelt'
     clock_plan=_sdk.ExecutionPlan(prompt_id='amy-ebu-clock',node_id='clock',node_type='ClockProbe',tier='sandbox',node_module='tests.amy_ebu_permissions',inputs={},permissions=())
     clock=await session.execute(clock_plan,_sdk.Runtime(refs=_sdk.InProcessRefResolver(),ctx=object(),ops=_sdk.InProcessOps()),capabilities=(),tenant='amy-ebu-user')
     offset=clock[0] if type(clock) is tuple else clock.result[0]
     for identity in NEW.NODE_CLASS_MAPPINGS:
      short=identity.removeprefix('EbuPromptHelper');kwargs=defaults(short)
      cases={'CombineTwoStrings':{'str1':'λ','str2':'🙂','join_str':' | '},'ConsumeListItem':{'word_to_replace':'cat','list':'red\nred\nblue','prompt_text':'cat cat','seed':17},'ListSampler':{'list':'1. red\n2. blue\n3. green','number_of_elements':2,'number_sampled_list':True,'seed':17},'Randomize':{'prompt_text':'Cat dog','word_to_replace':'cat|dog','replacement_options':'2>>blue\n3>>green','case_sensitive':False,'seed':17},'Replace':{'prompt_text':'Cat dog cat','word_to_replace':'cat|dog','replace_with':'λ😀','case_sensitive':False},'Truncate':{'prompt':'beforemiddleafter','substring':'middle','delete_option':'delete after','inclusive':False},'SeasonWeatherTimeOfDay':{'year_from':1980,'year_to':2024,'time_from':'11:00pm','time_to':'2:00am','seed':17}}
      kwargs.update(cases.get(short,{}))
      if short=='LoadFileAsString':kwargs={'directory':'','file_name':'text.txt'};caps=('assets',);expected=('λ\nend\n',)
      elif short=='CurrentDateTime':caps=();expected=None
      else:caps=();expected=native(short,kwargs)
      before=time.time();actual=await outer(short,kwargs);after=time.time()
      assert all(type(v) is str for v in actual)
      if expected is not None:assert actual==expected
      else:
       stamp=datetime.datetime.strptime(actual[3],'%Y-%m-%d_%H-%M-%S')
       epoch=stamp.replace(tzinfo=datetime.timezone(datetime.timedelta(seconds=offset))).timestamp()
       assert int(before)<=epoch<=int(after)
       class GuestClock:
        @staticmethod
        def now():return stamp
       with patch.object(sys.modules['amy_ebu_old.nodes'],'datetime',GuestClock):assert actual==native('CurrentDateTime',kwargs)
     pids.append(session.last_guest_pid)
     for kind in ('analogous','art_house','chaotic','complementary','compound','split_complementary','tetradic','triadic'):
      caps=();params=defaults('RandomColorPalette')
      for key in params:
       if key.startswith('include_'):params[key]=False
      params['include_'+kind+'_palettes']=True;params['seed']=17;params['palette_size']='5 colors'
      assert await outer('RandomColorPalette',params)==native('RandomColorPalette',params)
     caps=('assets',)
     for name in ('invalid.txt','missing.txt'):assert await outer('LoadFileAsString',{'directory':'','file_name':name})==('',)
     for name,pattern in [('big.txt','budget'),('escape.txt','asset name escapes the input directory')]:
      with pytest.raises(Exception,match=pattern):await outer('LoadFileAsString',{'directory':'','file_name':name})
     for directory,name in [('/tmp','secret'),('..','outside.txt'),('','../outside.txt')]:
      with pytest.raises(Exception,match='logical|traversal'):await outer('LoadFileAsString',{'directory':directory,'file_name':name})
     caps=()
     with pytest.raises(Exception,match='assets|permission|capability'):await outer('LoadFileAsString',{'directory':'','file_name':'text.txt'})
     kwargs=defaults('Randomize')|{'replacement_options':'10000000000>>x'}
     with pytest.raises(Exception,match='ticket budget'):await outer('Randomize',kwargs)
     assert await outer('Randomize',defaults('Randomize')|{'replacement_options':'a\nb','seed':7})==native('Randomize',defaults('Randomize')|{'replacement_options':'a\nb','seed':7})
     for module,inputs,pattern in [('AssetProbe',{},'assets'),('RawProbe',{'image':torch.zeros(1,2,2,3)},'raw')]:
      refs=_sdk.InProcessRefResolver();wrapped=await _sdk.wrap_inputs(refs,inputs,{'image':'IMAGE'})
      plan=_sdk.ExecutionPlan(prompt_id='amy-ebu-probe',node_id='deny',node_type=module,tier='sandbox',node_module='tests.amy_ebu_permissions',inputs=wrapped,permissions=())
      with pytest.raises(Exception,match=pattern+'|permission|capability'):await session.execute(plan,_sdk.Runtime(refs=refs,ctx=object(),ops=_sdk.InProcessOps()),capabilities=(),tenant='amy-ebu-user')
    finally:await session.kill()
  finally:folder_paths.set_input_directory(prior_input);_sdk.providers.register_execution_backend(previous)
  assert len(set(pids))==2 and os.getpid() not in pids
  asyncio.run(run())

def test_loader_unknown_broker_failures_changes_and_refusals_are_not_empty_parity():
 class Assets:
  async def exists(self,*args):return True
  async def resolve(self,*args):return 'test-ref'
  async def size(self,*args):return 1
  async def read_range(self,*args,**kwargs):return b'ab'
 class Context:
  assets=Assets()
 with patch.object(WRAP.sdk,'ctx',return_value=Context()):
  with pytest.raises(ValueError,match='changed'):asyncio.run(cls('LoadFileAsString').execute(directory='',file_name='text.txt'))
 class Broken(Assets):
  async def exists(self,*args):raise RuntimeError('unknown broker failure')
 Context.assets=Broken()
 with patch.object(WRAP.sdk,'ctx',return_value=Context()):
  with pytest.raises(RuntimeError,match='unknown broker failure'):asyncio.run(cls('LoadFileAsString').execute(directory='',file_name='text.txt'))

def test_maximum_admitted_tickets_and_precise_overlength_refusal():
 assert differential('Randomize',{'replacement_options':'65536>>x'})==('x', 'x')
 with pytest.raises(ValueError,match='ticket'):asyncio.run(cls('Randomize').execute(**(defaults('Randomize')|{'replacement_options':'65537>>x'})))

def test_all_preserved_helper_and_nonfile_algorithm_ASTs_with_closed_adaptations():
 class Normalize(ast.NodeTransformer):
  def visit_Import(self,node):
   if any(a.name=='os' for a in node.names):return None
   return node
  def visit_ImportFrom(self,node):
   if node.module=='_rng':return ast.Import(names=[ast.alias(name='random')])
   if node.module is None and any(a.name=='_limits' for a in node.names):return None
   return node
  def visit_FunctionDef(self,node):
   if node.name=='load_file':return None
   return self.generic_visit(node)
  def visit_Call(self,node):
   node=self.generic_visit(node)
   if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='_limits' and node.func.attr in ('replace','sub'):
    node.func=ast.Attribute(value=node.args.pop(0),attr=node.func.attr,ctx=ast.Load())
   return node
 for path in [PACK/'nodes.py',PACK/'weather_utils.py',*PACK.glob('make_palette_*.py')]:
  old=Normalize().visit(ast.parse(path.read_text()));new=Normalize().visit(ast.parse((V2/path.name).read_text()))
  assert ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False),path.name

def test_manifest_resources_census_stubs_and_cache_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 provenance=json.loads((V2/'source-provenance.json').read_text())
 hashes={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert hashes==provenance['source_hashes'] and len(hashes)==47
 for name in hashes:
  if name not in ('nodes.py','__init__.py','pyproject.toml') and not name.startswith('make_palette_') and name!='weather_utils.py':assert (PACK/name).read_bytes()==(V2/name).read_bytes()
 for name,sha in [('comfy-api.pyi','4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 code='\n'.join(p.read_text() for p in V2.glob('*.py'))
 for bad in ('_from_raw','folder_paths','PromptServer','subprocess','requests','open(','eval(','exec('):assert bad not in code
 assert not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.js'))
def test_exact_pair_zip_twice_and_wrong_source_atomic_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes())==expected and PAIR.with_suffix('.diff').read_bytes().decode()==diff
 for i in range(2):
  fresh=tmp_path/str(i)/'comfyui-ebu-prompthelper/x45c1ec2';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if i:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  else:packpatch.apply(fresh,expected,diff)
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-ebu-prompthelper/x45c1ec2';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'nodes.py').open('ab') as stream:stream.write(b'\n#wrongsource')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
