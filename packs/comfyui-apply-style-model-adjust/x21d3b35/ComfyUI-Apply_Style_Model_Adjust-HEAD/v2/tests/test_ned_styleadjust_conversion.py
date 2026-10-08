"""Exact pinned style-balance math against actual canonical tiny Redux."""
import asyncio,copy,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT']);sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import execution,comfy.sd,comfy.clip_vision,comfy.controlnet
from comfy.ldm.flux.redux import ReduxImageEncoder
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-apply-style-model-adjust/x21d3b35/comfyui-apply-style-model-adjust-x21d3b35'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('ned_style_old',PACK);NEW=load('ned_style_new',V2)
ID='ApplyStyleModelAdjust';SOURCE=OLD.NODE_CLASS_MAPPINGS[ID];CLS=NEW.NODE_CLASS_MAPPINGS[ID];CLS.GET_SCHEMA()
def manifest():return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':'ApplyStyleModelAdjustSecure','sdk_refs':True,'permissions':[],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}
def fixtures(dtype=torch.float32,rows=2,batch=2,tokens=3):
 module=ReduxImageEncoder(redux_dim=4,txt_in_features=6,dtype=dtype)
 with torch.no_grad():
  for index,parameter in enumerate(module.parameters()):
   parameter.copy_(torch.linspace(-.25,.25,parameter.numel(),dtype=dtype).reshape(parameter.shape)+(index*.03))
   parameter.requires_grad_(False)
 style=comfy.sd.StyleModel(module)
 vision=comfy.clip_vision.Output()
 vision.last_hidden_state=torch.linspace(-.4,.6,batch*tokens*4,dtype=dtype).reshape(batch,tokens,4)
 conditioning=[[torch.linspace(-.2,.8,5*6,dtype=dtype).reshape(1,5,6)+i,
   {'label':'literal<script>{中文}</script>','pooled_output':torch.arange(3,dtype=dtype),'start_percent':.25,'flag':False}] for i in range(rows)]
 return {'conditioning':conditioning,'style_model':style,'clip_vision_output':vision,'strength':.5}
async def outer(values,cls=CLS):
 result=await execution._async_map_node_over_list(prompt_id='ned-style',unique_id='1',obj=cls,input_data_all={k:[v] for k,v in values.items()},func=cls.FUNCTION,v3_data=None)
 return result[0].result[0]
def same(actual,expected):
 assert len(actual)==len(expected)
 for a,b in zip(actual,expected,strict=True):
  assert torch.equal(a[0],b[0]) and a[0].shape==b[0].shape and a[0].dtype==b[0].dtype and a[0].device==b[0].device
  assert set(a[1])==set(b[1])
  for key in a[1]:
   if isinstance(b[1][key],torch.Tensor):assert torch.equal(a[1][key],b[1][key]) and a[1][key].dtype==b[1][key].dtype
   else:assert a[1][key]==b[1][key]
def test_actual_registration_exact_schema_resources_and_no_frontend():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 assert (V2/'nodes.py').read_bytes()==(PACK/'nodes.py').read_bytes()
 schema=CLS.GET_SCHEMA();schema.validate();assert schema.node_id==ID and schema.category==SOURCE.CATEGORY and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[ID]
 assert [o.io_type for o in schema.outputs]==['CONDITIONING'] and not schema.is_output_node
 for inp,(name,spec) in zip(schema.inputs,SOURCE.INPUT_TYPES()['required'].items(),strict=True):
  assert inp.id==name and inp.io_type==spec[0] and not inp.optional
  if len(spec)>1:
   for key,value in spec[1].items():assert inp.as_dict()[key]==value
 assert CLS.SDK_REFS is True and CLS.SDK_PERMISSIONS==()
 loaded=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.ned_style_proxy')
 assert list(loaded.node_mappings)==[ID] and not loaded.routes and loaded.web_directory is None

@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
@pytest.mark.parametrize('strength',[0,.1,.25,.5,.7,1,-2,2])
@pytest.mark.parametrize('rows',[0,1,3])
def test_actual_canonical_redux_exact_prompt_boost_flatten_style_scale_metadata(dtype,strength,rows):
 values=fixtures(dtype,rows);values['strength']=strength
 before=[(row[0].clone(),{k:v.clone() if isinstance(v,torch.Tensor) else v for k,v in row[1].items()}) for row in values['conditioning']]
 rng=torch.random.get_rng_state().clone()
 expected=SOURCE().apply_stylemodel(**values)[0]
 actual=asyncio.run(outer(values));same(actual,expected)
 for row,(tensor,metadata) in zip(values['conditioning'],before,strict=True):
  assert torch.equal(row[0],tensor);same([[tensor,row[1]]],[[tensor,metadata]])
 assert torch.equal(torch.random.get_rng_state(),rng)
 if rows and strength==0:
  assert actual[0][0].shape==(1,11,6)
  assert torch.equal(actual[0][0][:,:5],values['conditioning'][0][0]*3)
  assert torch.equal(actual[0][0][:,5:],torch.zeros((1,6,6),dtype=dtype))

@pytest.mark.parametrize('batch,tokens',[(0,3),(1,0),(1,1),(3,4)])
def test_native_style_empty_and_multiple_batches_order(batch,tokens):
 values=fixtures(batch=batch,tokens=tokens)
 expected=SOURCE().apply_stylemodel(**values)[0]
 same(asyncio.run(outer(values)),expected)

def test_existing_control_metadata_stays_host_owned_and_identical():
 data=fixtures();control=comfy.controlnet.ControlNet()
 data['conditioning'][0][1]['control']=control
 result=asyncio.run(outer(data))
 assert result[0][1]['control'] is control
 same(result,SOURCE().apply_stylemodel(**data)[0])

def test_bounds_before_boost_and_native_concat_mismatch():
 for rows in ([[torch.empty(1,16777217,1,device='meta'),{}]],[[torch.empty(1,1,1),{}]]*4097):
  data=fixtures();data['conditioning']=rows
  with pytest.raises((TypeError,ValueError),match='conditioning|element|rows|bound'):asyncio.run(outer(data))
 for value in (None,False,'1',float('nan'),float('inf'),1000001):
  data=fixtures();data['strength']=value
  with pytest.raises(ValueError,match='strength'):asyncio.run(outer(data))
 data=fixtures();data['conditioning'][0][0]=torch.zeros((2,5,6))
 with pytest.raises(RuntimeError):SOURCE().apply_stylemodel(**data)
 with pytest.raises(RuntimeError):asyncio.run(outer(data))

def test_fresh_required_zero_cap_guests_real_redux_outer_conditioning_denial_and_recovery(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    with (fresh/'_secure_nodes.py').open('a') as stream:
     stream.write('\nclass NedStyleRawProbe(io.ComfyNode):\n @classmethod\n async def execute(cls,conditioning):\n  return io.NodeOutput(await conditioning.value())\n')
    cls=load('ned_style_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
    session=await GuestSession('ned-style-'+str(render),guest_runtime_root=fresh).start()
    capabilities=()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=capabilities,tenant='style-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    try:
     assert session.sandbox_kind=='seatbelt'
     for dtype in (torch.float16,torch.float32,torch.float64,torch.bfloat16):
      for strength in (0,.25,.7,1):
       data=fixtures(dtype);data['strength']=strength
       expected=SOURCE().apply_stylemodel(**data)[0]
       same(await outer(data,cls),expected)
     empty=fixtures(rows=0);same(await outer(empty,cls),SOURCE().apply_stylemodel(**empty)[0])
     data=fixtures();control=comfy.controlnet.ControlNet()
     data['conditioning'][0][1]['control']=control
     actual=await outer(data,cls)
     assert actual[0][1]['control'] is control
     same(actual,SOURCE().apply_stylemodel(**data)[0])
     refs=_sdk.InProcessRefResolver()
     plan=_sdk.ExecutionPlan(prompt_id='style-denial',node_id='probe',node_type='NedStyleRawProbe',node_module=cls.__module__,inputs={'conditioning':fixtures()['conditioning']},permissions=(),method='execute',input_types={'conditioning':'CONDITIONING'})
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
     plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
     with pytest.raises(Exception,match='raw|capability|permission'):await session.execute(plan,runtime,capabilities=(),tenant='style-'+str(render))
     same(await outer(fixtures(),cls),SOURCE().apply_stylemodel(**fixtures())[0])
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_resources_exact_stubs_source_hashes_no_license_and_cache():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 source=json.loads((V2/'source-provenance.json').read_text())
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob('*') if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==source['source_hashes'] and len(pristine)==6
 for path in ('README.md','.gitignore','examples/flux_redux style model 1 input.json','examples/flux_redux style model 2 inputs.json'):
  assert (V2/path).read_bytes()==(PACK/path).read_bytes()
 assert not (PACK/'LICENSE').exists()
 for name,sha in [('comfy-api.pyi','66f96a76ea39af855af448d1e6b77ae43d20f09ada9aefd221ba9edef9c8a553'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:
  assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 text=(V2/'_secure_nodes.py').read_text()
 for forbidden in ('_from_raw','_wrap(','import comfy.','folder_paths','PromptServer','load_torch_file','subprocess','requests','open('):assert forbidden not in text
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

def test_pair_zip_two_exact_reconstructions_and_wrong_pristine_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_text())==expected and PAIR.with_suffix('.diff').read_bytes()==diff.encode()
 for index in range(2):
  fresh=tmp_path/str(index)/'comfyui-apply-style-model-adjust/x21d3b35';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-apply-style-model-adjust/x21d3b35';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'nodes.py').open('ab') as stream:stream.write(b'\n# wrong pinned source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
