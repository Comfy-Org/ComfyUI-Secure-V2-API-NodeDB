"""Exact pixel oracle, bounds, recreated confined guests and complete artifacts."""
import asyncio,ast,copy,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
import pytest,torch
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
PAIR=DB/'patches/comfyui-imagemotionguider/xde25e08/comfyui-imagemotionguider-xde25e08'
ID='ImageMotionGuider'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('amy_motion_old',PACK);NEW=load('amy_motion_new',V2)
SOURCE=OLD.NODE_CLASS_MAPPINGS[ID];CLS=NEW.NODE_CLASS_MAPPINGS[ID];CLS.GET_SCHEMA()
def image(dtype=torch.float32,shape=(2,7,11,3)):
 return ((torch.arange(torch.tensor(shape).prod().item(),dtype=torch.float64).reshape(shape)%211+1)/212).to(dtype)
def inputs(im=None,x=5,frames=5,zoom=.25):
 return dict(image=image() if im is None else im,move_range_x=x,frame_num=frames,zoom=zoom)
def same(a,b):
 assert len(a)==len(b)==1
 x,y=a[0],b[0]
 assert type(x) is type(y) is torch.Tensor and x.shape==y.shape and x.dtype==y.dtype and x.device==y.device and torch.equal(x,y)
def differential(value):
 before=value['image'].clone()
 try:expected=SOURCE().guide_motion(**value)
 except Exception as native:
  with pytest.raises(type(native)):CLS.execute(**value)
 else:same(CLS.execute(**value).result,expected)
 assert torch.equal(value['image'],before)
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{ID:{'module':'_secure_nodes','class':'ImageMotionGuiderSecure','sdk_refs':False,'permissions':['raw'],'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}

def test_actual_root_census_schema_proxy_and_normalized_source_AST():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==[ID]
 schema=CLS.GET_SCHEMA();schema.validate()
 assert schema.node_id==ID and schema.category==SOURCE.CATEGORY and [o.io_type for o in schema.outputs]==['IMAGE']
 assert [i.id for i in schema.inputs]==list(SOURCE.INPUT_TYPES()['required'])
 for inp in schema.inputs:
  spec=SOURCE.INPUT_TYPES()['required'][inp.id]
  assert inp.io_type==spec[0]
  for k,v in (spec[1] if len(spec)>1 else {}).items():assert inp.as_dict()[k]==v
 assert not schema.is_output_node and CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==('raw',)
 old=ast.parse((PACK/'nodes_images.py').read_text())
 old.body=[n for n in old.body if not (isinstance(n,ast.Import) and n.names[0].name in ('nodes','folder_paths'))]
 assert ast.dump(old)==ast.dump(ast.parse((V2/'nodes_images.py').read_text()))
 proxy=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_motion_proxy')
 assert list(proxy.node_mappings)==[ID] and not proxy.routes and proxy.web_directory is None

@pytest.mark.parametrize('x',[-150,-12,-5,0,5,12,150])
@pytest.mark.parametrize('zoom',[0,.25,.5])
@pytest.mark.parametrize('frames',[2,5,10])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
def test_source_motion_wrap_direction_firstbatch_zoom_frame_order_and_dtype(x,zoom,frames,dtype):
 differential(inputs(image(dtype),x,frames,zoom))

def test_firstbatch_only_mirrored_coverage_and_default_floating_canvas():
 value=inputs(x=5,zoom=0);actual=CLS.execute(**value).result[0]
 changed=value['image'].clone();changed[1]=0
 assert torch.equal(CLS.execute(**{**value,'image':changed}).result[0],actual)
 assert actual.dtype==torch.float32
 assert torch.count_nonzero(actual)==actual.numel()
 previous=torch.get_default_dtype()
 try:
  torch.set_default_dtype(torch.float64);differential(inputs(image(torch.float64)))
  assert CLS.execute(**inputs()).result[0].dtype==torch.float64
 finally:torch.set_default_dtype(previous)

@pytest.mark.parametrize('shape',[(0,7,11,3),(1,0,11,3),(1,7,0,3),(1,1,1,3),(1,7,11,1),(1,7,11,2),(1,7,11,4)])
def test_native_empty_tiny_channels_noncontiguous_errors(shape):
 differential(inputs(image(shape=shape)))
 im=image(shape=(1,7,22,3))[...,::2,:]
 assert not im.is_contiguous();differential(inputs(im))

def test_default_controls_and_512_connected_pixels():
 value=inputs(image(shape=(1,512,512,3)),x=0,frames=10,zoom=0);differential(value)
 actual=CLS.execute(**value).result[0]
 assert actual.shape==(10,512,512,3)
 assert all(torch.equal(row,value['image'][0]) for row in actual)

@pytest.mark.parametrize('key,bad',[('move_range_x',True),('move_range_x',151),('move_range_x',1.1),('frame_num',True),('frame_num',1),('frame_num',151),('zoom',True),('zoom',float('inf')),('zoom',float('nan')),('zoom',-.01),('zoom',.51)])
def test_closed_scalar_bounds(key,bad):
 value=inputs();value[key]=bad
 with pytest.raises(ValueError):CLS.execute(**value)

def test_whole_input_output_and_workspace_preflight_before_source(monkeypatch):
 module=sys.modules[CLS.__module__]
 def forbidden(self,**values):raise AssertionError('source reached before refusal')
 monkeypatch.setattr(module.Source,'guide_motion',forbidden)
 cases=[(inputs(torch.zeros(1).expand(64,512,512,3)),'input byte'),(inputs(image(shape=(1,512,512,3)),frames=150),'workspace'),(inputs(torch.zeros((7,11,3))),'BHWC'),(inputs(torch.zeros(1).expand(1,4097,2,3)),'axes'),(inputs(torch.zeros(1).expand(65,1,1,3)),'batch')]
 for value,pattern in cases:
  with pytest.raises(ValueError,match=pattern):CLS.execute(**value)

def test_recreated_required_guests_outer_IMAGE_raw_denial_native_errors_and_recovery(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[];allowed=('raw',)
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    cls=load('amy_motion_fresh_'+str(render),fresh).NODE_CLASS_MAPPINGS[ID];cls.GET_SCHEMA()
    session=await GuestSession('amy-motion-'+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=allowed,tenant='amy-motion-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(value):
     r=await execution._async_map_node_over_list(prompt_id='amy-motion-outer',unique_id=str(render),obj=cls,input_data_all={k:[v] for k,v in value.items()},func=cls.FUNCTION,v3_data=None)
     return r[0].result
    try:
     assert session.sandbox_kind=='seatbelt'
     for value in [inputs(),inputs(image(torch.bfloat16),x=-12),inputs(image(torch.float16),zoom=.5),inputs(image(torch.float64),zoom=0),inputs(image(shape=(1,512,512,3)),0,10,0)]:
      same(await outer(value),SOURCE().guide_motion(**value))
     with pytest.raises(Exception,match='workspace'):await outer(inputs(image(shape=(1,512,512,3)),frames=150))
     with pytest.raises(Exception,match='IndexError'):await outer(inputs(image(shape=(0,7,11,3))))
     allowed=()
     with pytest.raises(Exception,match='raw|permission|capability|BHWC'):await outer(inputs())
     allowed=('raw',);same(await outer(inputs()),SOURCE().guide_motion(**inputs()))
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_pristine_resources_manifest_stubs_hygiene_and_no_ambient_authority():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 p=json.loads((V2/'source-provenance.json').read_text())
 pristine={path.relative_to(PACK).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in PACK.rglob('*') if path.is_file() and not path.is_relative_to(V2)}
 assert pristine==p['source_hashes'] and len(pristine)==8 and p['git_blob_path_mode_match']
 for name in pristine:
  if name not in ('__init__.py','nodes_images.py','pyproject.toml'):assert (PACK/name).read_bytes()==(V2/name).read_bytes()
 assert 'MIT License' in (V2/'LICENSE').read_text()
 for name,expected in [('comfy-api.pyi','4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:
  assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==expected
 code=(V2/'_secure_nodes.py').read_text()+(V2/'nodes_images.py').read_text()
 for forbidden in ('_from_raw','_wrap(', 'folder_paths','import nodes','PromptServer','subprocess','requests','eval(', 'exec(', 'open('):assert forbidden not in code
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('*.js'))

def test_exact_stored_pair_zip_twice_and_wrong_pristine_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes().decode())==expected
 assert PAIR.with_suffix('.diff').read_bytes().decode()==diff
 for index in range(2):
  fresh=tmp_path/str(index)/'comfyui-imagemotionguider/xde25e08';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-imagemotionguider/xde25e08';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as out:out.write(b'\n#wrong source')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()
