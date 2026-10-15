"""Four exact exports; retained model metadata seam is an unchanged RED control."""
import asyncio,ast,copy,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
import pytest,torch
sys.dont_write_bytecode=True
CORE=Path(os.environ['COMFY_CORE_ROOT'])
sys.path[:0]=[str(CORE),'/Users/ben/comfy/ComfyUI_secure_nodes/backend']
from comfy.cli_args import args
args.cpu=True
import nodes as core_nodes,execution
import comfy.model_base,comfy.supported_models_base,comfy.latent_formats,comfy.model_patcher
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/'patches/comfyui-hunyuanvideosamplersave/x12da6f2/comfyui-hunyuanvideosamplersave-x12da6f2'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/'__init__.py',submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load('amy_sampler_old',PACK);NEW=load('amy_sampler_new',V2)
IDS=list(OLD.NODE_CLASS_MAPPINGS)
for cls in NEW.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
def image(dtype=torch.float32,shape=(2,7,11,3)):
 return ((torch.arange(torch.tensor(shape).prod().item(),dtype=torch.float64).reshape(shape)%211+1)/212).to(dtype)
async def outer(cls,value):
 result=await execution._async_map_node_over_list(prompt_id='amy-sampler-outer',unique_id='7',obj=cls,input_data_all={k:[v] for k,v in value.items()},func=cls.FUNCTION,v3_data=None)
 return result[0].result
async def guest_outer(cls,value):
 prior=_sdk.providers.execution_backend
 session=await GuestSession('amy-sampler-native',guest_runtime_root=V2).start()
 class Backend:
  async def dispatch(self,plan,local_call,runtime):
   plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
   return await session.execute(plan,runtime,capabilities=tuple(cls.SDK_PERMISSIONS),tenant='amy-native-sampler')
 try:
  assert session.sandbox_kind=='seatbelt'
  _sdk.providers.register_execution_backend(Backend())
  return await outer(cls,value)
 finally:
  _sdk.providers.register_execution_backend(prior);await session.kill()
def same_tensor(a,b):
 assert type(a) is type(b) is torch.Tensor and a.shape==b.shape and a.dtype==b.dtype and a.device==b.device and torch.equal(a,b)
def manifest():
 return {'format':FORMAT,'runtime':manifest_declaration(V2),'nodes':{node:{'module':'nodes','class':node,'sdk_refs':cls.SDK_REFS,'permissions':list(cls.SDK_PERMISSIONS),'methods':{k:False for k in ('validate_inputs','fingerprint_inputs','check_lazy_status')},'schema':encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for node,cls in NEW.NODE_CLASS_MAPPINGS.items()}}

class Format(comfy.latent_formats.LatentFormat):
 latent_channels=16
 latent_dimensions=3
class Config(comfy.supported_models_base.BASE):
 latent_format=Format
class Kernel(torch.nn.Module):
 def __init__(self):
  super().__init__();self.bias=torch.nn.Parameter(torch.zeros(()));self.dtype=torch.float32
 def forward(self,x,timesteps,context=None,**kwargs):
  shape=(x.shape[0],)+(1,)*(x.ndim-1)
  c=0 if context is None else context.mean()*0.001
  return x*.125+timesteps.to(x).reshape(shape)*0.00001+c+self.bias
def model():
 config=Config({'disable_unet_model_creation':True,'in_channels':16})
 value=comfy.model_base.BaseModel(config,comfy.model_base.ModelType.FLOW,device=torch.device('cpu'))
 value.diffusion_model=Kernel()
 return comfy.model_patcher.ModelPatcher(value,torch.device('cpu'),torch.device('cpu'))
def sampling_inputs(ratios=False,seed=123,denoise=1):
 latent={'samples':torch.arange(1*16*2*4*4,dtype=torch.float32).reshape(1,16,2,4,4)/500,'custom':'retained'}
 if ratios:latent.update(downscale_ratio_spacial=8,downscale_ratio_temporal=4)
 return dict(model=model(),video_latents=latent,positive=[[torch.ones((1,2,4)),{}]],negative=[[torch.zeros((1,2,4)),{}]],seed=seed,steps=3,cfg=2,sampler_name='euler',scheduler='normal',denoise=denoise)

def test_actual_all_four_census_exact_ids_schema_choices_defaults_and_permissions():
 pack=packdb.load_pack(SNAPSHOT,mount_name='custom_nodes.amy_sampler_proxy')
 assert list(pack.node_mappings)==IDS and not pack.routes and pack.web_directory is None
 assert IDS==list(NEW.NODE_CLASS_MAPPINGS) and len(IDS)==4
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 for node in IDS:
  source=OLD.NODE_CLASS_MAPPINGS[node];cls=NEW.NODE_CLASS_MAPPINGS[node];schema=cls.GET_SCHEMA();schema.validate()
  assert schema.node_id==node and schema.category==source.CATEGORY and schema.display_name==OLD.NODE_DISPLAY_NAME_MAPPINGS[node]
  assert [o.io_type for o in schema.outputs]==list(source.RETURN_TYPES)
  assert [i.id for i in schema.inputs]==list(source.INPUT_TYPES()['required'])
  for inp in schema.inputs:
   spec=source.INPUT_TYPES()['required'][inp.id]
   if isinstance(spec[0],list):assert inp.as_dict()['options']==spec[0]
   else:
    assert inp.io_type==spec[0]
    for key,value in (spec[1] if len(spec)>1 else {}).items():assert inp.as_dict()[key]==value
 assert NEW.NODE_CLASS_MAPPINGS['HunyuanVideoSamplerSave'].SDK_PERMISSIONS==('sample',)
 assert NEW.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan'].SDK_PERMISSIONS==('inspect',)
 for node in ('ImageMotionInfluance','EmptyVideoLatentForHunyuan'):assert NEW.NODE_CLASS_MAPPINGS[node].SDK_PERMISSIONS==('raw',)
 ast_old=ast.parse((PACK/'nodes.py').read_text())
 source_class=next(n for n in ast_old.body if isinstance(n,ast.ClassDef) and n.name=='ImageMotionInfluance')
 ast_new=ast.parse((V2/'_motion.py').read_text())
 assert ast.dump(source_class)==ast.dump(next(n for n in ast_new.body if isinstance(n,ast.ClassDef)))
 # Unregistered helper is not the released sampling algorithm.
 source_sampler=next(n for n in ast_old.body if isinstance(n,ast.ClassDef) and n.name=='HunyuanVideoSamplerSave')
 assert 'common_ksampler' in ast.unparse(source_sampler) and 'MotionGuidedSampler(' not in ast.unparse(source_sampler)

@pytest.mark.parametrize('resolution',OLD.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan'].INPUT_TYPES()['required']['resolution'][0])
@pytest.mark.parametrize('length',[1,2,4,5,25])
def test_all36_empty_resolution_floor16_temporal_ceiling_channels_exact_CPU(resolution,length):
 cls=NEW.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan'];source=OLD.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan']
 expected=source().generate(resolution,length,1)[0];actual=cls.execute(resolution,length,1).result[0]
 assert set(expected)==set(actual)=={'samples'};same_tensor(actual['samples'],expected['samples'])
 assert torch.count_nonzero(actual['samples'])==0 and actual['samples'].shape[2]==((length-1)//4)+1

@pytest.mark.parametrize('size',OLD.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan'].INPUT_TYPES()['required']['size_preset'][0])
def test_all36_resize_ordered_sizes_canonical_pixels(size):
 value=image(shape=(1,7,11,3));expected=OLD.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan']().resize(value,size,'bilinear','center')[0]
 actual=asyncio.run(outer(NEW.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan'],dict(image=value,size_preset=size,upscale_method='bilinear',crop='center')))[0]
 same_tensor(actual,expected)

@pytest.mark.parametrize('method',['nearest-exact','bilinear','area','bicubic'])
@pytest.mark.parametrize('crop',['disabled','center'])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
def test_resize_every_method_crop_dtype_exact(method,crop,dtype):
 value=image(dtype);size='1:1 (256x256)'
 expected=OLD.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan']().resize(value,size,method,crop)[0]
 actual=asyncio.run(outer(NEW.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan'],dict(image=value,size_preset=size,upscale_method=method,crop=crop)))[0]
 same_tensor(actual,expected)

@pytest.mark.parametrize('x',[-150,-15,-1,0,1,15,150])
@pytest.mark.parametrize('zoom',[0,.25,.5])
@pytest.mark.parametrize('dtype',[torch.float16,torch.float32,torch.float64,torch.bfloat16])
def test_motion_exact_mirror_wrap_firstbatch_zoom_floor_canvas_and_frame_order(x,zoom,dtype):
 value=image(dtype);before=value.clone()
 expected=OLD.NODE_CLASS_MAPPINGS['ImageMotionInfluance']().guide_motion(value,x,5,zoom)[0]
 actual=NEW.NODE_CLASS_MAPPINGS['ImageMotionInfluance'].execute(value,x,5,zoom).result[0]
 same_tensor(actual,expected);assert torch.equal(value,before)
 assert actual.shape[0]==5
 changed=value.clone();changed[1]=0
 assert torch.equal(NEW.NODE_CLASS_MAPPINGS['ImageMotionInfluance'].execute(changed,x,5,zoom).result[0],actual)

@pytest.mark.parametrize('seed',[0,123,(1<<64)-1])
@pytest.mark.parametrize('denoise',[0,.6,1])
def test_actual_canonical_FLOW_sampling_noise_seed_5D_native_loop(seed,denoise):
 value=sampling_inputs(seed=seed,denoise=denoise)
 expected=OLD.NODE_CLASS_MAPPINGS['HunyuanVideoSamplerSave']().sample(**value)[0]
 actual=asyncio.run(guest_outer(NEW.NODE_CLASS_MAPPINGS['HunyuanVideoSamplerSave'],value))[0]
 assert set(actual)==set(expected);same_tensor(actual['samples'],expected['samples'])
 assert actual['custom']=='retained'
 if denoise==0:assert actual['samples'] is value['video_latents']['samples'] and expected['samples'] is value['video_latents']['samples']
 assert torch.equal(value['video_latents']['samples'],sampling_inputs()['video_latents']['samples'])

def test_unchanged_source_ratio_metadata_canonical_sampling_and_typed_output():
 value=sampling_inputs(ratios=True)
 expected=OLD.NODE_CLASS_MAPPINGS['HunyuanVideoSamplerSave']().sample(**value)[0]
 actual=asyncio.run(guest_outer(NEW.NODE_CLASS_MAPPINGS['HunyuanVideoSamplerSave'],value))[0]
 assert set(actual)==set(expected)
 same_tensor(actual['samples'],expected['samples'])

def test_actual_sampler_declared_defaults_with_empty_node_generated5D_connection():
 latent=OLD.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan']().generate('256x256 (1:1)',25,1)[0]
 value=sampling_inputs(seed=0,denoise=.6)
 value.update(video_latents=latent,steps=20,cfg=8)
 expected=OLD.NODE_CLASS_MAPPINGS['HunyuanVideoSamplerSave']().sample(**value)[0]
 actual=asyncio.run(guest_outer(NEW.NODE_CLASS_MAPPINGS['HunyuanVideoSamplerSave'],value))[0]
 assert set(actual)==set(expected);same_tensor(actual['samples'],expected['samples'])
 assert actual['samples'].shape==(1,16,7,32,32)

def test_resize_preflight_before_broker_allocation_and_without_raw(monkeypatch):
 async def forbidden(*a,**k):pytest.fail('resize allocator entered before full batch preflight')
 monkeypatch.setattr(_sdk.InProcessOps,'_image_resize',forbidden)
 cls=NEW.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan']
 for value in (torch.ones(1).expand(64,7,11,3),torch.ones(1).expand(1,4096,4096,1)):
  with pytest.raises(ValueError,match='budget'):asyncio.run(outer(cls,dict(image=value,size_preset='1:1 (768x768)',upscale_method='bilinear',crop='disabled')))
 assert cls.SDK_PERMISSIONS==('inspect',) and 'raw' not in cls.SDK_PERMISSIONS


def test_unchanged_source_LA_two_channel_resize():
 value=image(shape=(1,7,11,2));size='1:1 (256x256)'
 expected=OLD.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan']().resize(value,size,'bilinear','center')[0]
 actual=asyncio.run(outer(NEW.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan'],dict(image=value,size_preset=size,upscale_method='bilinear',crop='center')))[0]
 same_tensor(actual,expected)

def test_preflight_before_local_zero_and_motion_allocations(monkeypatch):
 module=sys.modules[NEW.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan'].__module__]
 monkeypatch.setattr(module.torch,'zeros',lambda *a,**k:pytest.fail('entered allocation'))
 with pytest.raises(ValueError,match='byte budget'):NEW.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan'].execute('768x768 (1:1)',16384,4096)
 value=torch.ones(1).expand(1,512,512,3)
 with pytest.raises(ValueError,match='budget'):NEW.NODE_CLASS_MAPPINGS['ImageMotionInfluance'].execute(value,10,500,.5)

def test_manifest_pristine_and_current_public_artifacts_hygiene():
 assert json.loads((V2/'secure-nodes.json').read_text())==manifest()
 p=json.loads((V2/'source-provenance.json').read_text())
 pristine={f.relative_to(PACK).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in PACK.rglob('*') if f.is_file() and not f.is_relative_to(V2)}
 assert pristine==p['source_hashes'] and len(pristine)==9
 for name in pristine:
  if name not in ('nodes.py','pyproject.toml'):assert (PACK/name).read_bytes()==(V2/name).read_bytes()
 for name,digest in [('comfy-api.pyi','4dc57da1480e02f57a022e398971595a7aa46d13fe58882b71b09c9ca04fc183'),('comfy-api.d.ts','2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090')]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==digest
 assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc')) and not list(PACK.rglob('*.js'))
 text=(V2/'nodes.py').read_text()+(V2/'_motion.py').read_text()
 for forbidden in ('_from_raw','folder_paths','import nodes','PromptServer','subprocess','requests','comfy.model_management','eval(', 'exec('):assert forbidden not in text

@pytest.mark.parametrize('shape',[(0,7,11,3),(1,0,11,3),(1,7,0,3),(1,1,1,3),(1,7,11,1),(1,7,11,4)])
def test_motion_native_empty_errors_noncontiguous_and_channels(shape):
 source=OLD.NODE_CLASS_MAPPINGS['ImageMotionInfluance'];cls=NEW.NODE_CLASS_MAPPINGS['ImageMotionInfluance'];value=image(shape=shape)
 try:expected=source().guide_motion(value,-5,5,.25)[0]
 except Exception as native:
  with pytest.raises(type(native)):cls.execute(value,-5,5,.25)
 else:same_tensor(cls.execute(value,-5,5,.25).result[0],expected)
 value=image(shape=(1,7,22,3))[...,::2,:]
 assert not value.is_contiguous()
 same_tensor(cls.execute(value,15,5,.5).result[0],source().guide_motion(value,15,5,.5)[0])

def test_empty_default_declared_batch_dtype_and_local_float64_normalization():
 source=OLD.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan'];cls=NEW.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan']
 for resolution,length,batch in [('256x256 (1:1)',25,1),('216x384 (9:16)',6,3),('0x256 (malformed)',1,1)]:
  same_tensor(cls.execute(resolution,length,batch).result[0]['samples'],source().generate(resolution,length,batch)[0]['samples'])
 previous=torch.get_default_dtype()
 try:
  torch.set_default_dtype(torch.float64)
  same_tensor(cls.execute('256x256 (1:1)',5,1).result[0]['samples'],source().generate('256x256 (1:1)',5,1)[0]['samples'])
 finally:torch.set_default_dtype(previous)

def test_two_fresh_required_guests_all_four_outer_types_capability_denials_and_recovery(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh);package=load('amy_sampler_fresh_'+str(render),fresh)
    for cls in package.NODE_CLASS_MAPPINGS.values():cls.GET_SCHEMA()
    session=await GuestSession('amy-sampler-all-four-'+str(render),guest_runtime_root=fresh).start()
    allowed=()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=allowed,tenant='amy-sampler-user-'+str(render))
    _sdk.providers.register_execution_backend(Backend())
    try:
     assert session.sandbox_kind=='seatbelt'
     for node,value in [
     ('ResizeImageForHunyuan',dict(image=image(torch.bfloat16),size_preset='9:16 (216x384)',upscale_method='bicubic',crop='center')),
     ('ResizeImageForHunyuan',dict(image=image(torch.float32,shape=(1,7,11,2)),size_preset='1:1 (256x256)',upscale_method='bilinear',crop='disabled')),
      ('EmptyVideoLatentForHunyuan',dict(resolution='384x216 (16:9)',length=6,batch_size=2)),
      ('ImageMotionInfluance',dict(image=image(torch.float16),move_range_x=-15,frame_num=5,zoom=.5)),
      ('HunyuanVideoSamplerSave',sampling_inputs(ratios=True))]:
      cls=package.NODE_CLASS_MAPPINGS[node];allowed=tuple(cls.SDK_PERMISSIONS)
      source=OLD.NODE_CLASS_MAPPINGS[node];expected=getattr(source(),source.FUNCTION)(**value)[0]
      actual=(await outer(cls,value))[0]
      if node in ('EmptyVideoLatentForHunyuan','HunyuanVideoSamplerSave'):
       assert set(actual)==set(expected);same_tensor(actual['samples'],expected['samples'])
      else:same_tensor(actual,expected)
      if allowed:
       allowed=()
       with pytest.raises(Exception,match='capability|permission|raw|BHWC'):await outer(cls,value)
       allowed=tuple(cls.SDK_PERMISSIONS)
       await outer(cls,value)
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_exact_stored_pair_and_zip_roundtrips_wrong_source_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix('.json').read_bytes().decode())==expected and PAIR.with_suffix('.diff').read_bytes().decode()==diff
 for index in range(2):
  fresh=tmp_path/str(index)/'comfyui-hunyuanvideosamplersave/x12da6f2';fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/'v2',V2)
 fresh=tmp_path/'bad/comfyui-hunyuanvideosamplersave/x12da6f2';fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns('v2'))
 with (fresh/PACK.name/'__init__.py').open('ab') as file:file.write(b'\n#wrong pristine')
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/'v2').exists()

@pytest.mark.parametrize('size',['missing','1:1 (notxvalid)','1:1 (2x2x2)'])
def test_resize_native_parse_errors(size):
 source=OLD.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan'];cls=NEW.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan']
 try:source().resize(image(),size,'bilinear','disabled')
 except Exception as native:
  with pytest.raises(type(native)):asyncio.run(outer(cls,dict(image=image(),size_preset=size,upscale_method='bilinear',crop='disabled')))
 else:pytest.fail('source malformed preset unexpectedly succeeded')

@pytest.mark.parametrize('resolution',['missing','axb (bad)','2x2x2 (bad)'])
def test_empty_native_parse_errors(resolution):
 source=OLD.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan'];cls=NEW.NODE_CLASS_MAPPINGS['EmptyVideoLatentForHunyuan']
 try:source().generate(resolution,5,1)
 except Exception as native:
  with pytest.raises(type(native)):cls.execute(resolution,5,1)
 else:pytest.fail('source malformed resolution unexpectedly succeeded')

@pytest.mark.parametrize('changes',[{'frame_num':501},{'move_range_x':True},{'move_range_x':151},{'zoom':float('nan')},{'zoom':True},{'zoom':.6},{'frame_num':1}])
def test_motion_closed_scalar_bounds(changes):
 value=dict(image=image(),move_range_x=0,frame_num=5,zoom=0);value.update(changes)
 with pytest.raises(ValueError):NEW.NODE_CLASS_MAPPINGS['ImageMotionInfluance'].execute(**value)

def test_whole_resize_source_batch_channels_native_outputs():
 source=OLD.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan'];cls=NEW.NODE_CLASS_MAPPINGS['ResizeImageForHunyuan']
 for shape in ((1,7,11,1),(2,7,11,3),(1,7,11,4)):
  value=image(shape=shape)
  actual=asyncio.run(outer(cls,dict(image=value,size_preset='1:1 (256x256)',upscale_method='area',crop='disabled')))[0]
  same_tensor(actual,source().resize(value,'1:1 (256x256)','area','disabled')[0])
