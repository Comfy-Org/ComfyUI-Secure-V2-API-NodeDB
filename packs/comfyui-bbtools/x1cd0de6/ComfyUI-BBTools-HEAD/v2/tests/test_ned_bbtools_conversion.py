"""Pinned four-node pixels, native failures, approved zero fades and real guests."""
import asyncio,ast,copy,hashlib,importlib.util,itertools,json,os,re,shutil,sys
from pathlib import Path
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ["COMFY_CORE_ROOT"]);sys.path[:0]=[str(CORE),"/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
from comfy.cli_args import args
args.cpu=True
import execution
import comfy.utils
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/"patches/comfyui-bbtools/x1cd0de6/comfyui-bbtools-x1cd0de6"
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/"__init__.py",submodule_search_locations=[str(path)])
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
OLD=load("ned_bbtools_old",PACK);NEW=load("ned_bbtools_new",V2)
CLASSES=NEW.NODE_CLASS_MAPPINGS;SOURCE=OLD.NODE_CLASS_MAPPINGS
for cls in CLASSES.values():cls.GET_SCHEMA()
MOD=sys.modules[next(iter(CLASSES.values())).__module__];ALG=MOD.alg
IDS=list(SOURCE)
def manifest():
 return {"format":FORMAT,"runtime":manifest_declaration(V2),"nodes":{key:{"module":"_secure_nodes","class":cls.__name__,"sdk_refs":cls.SDK_REFS,"permissions":["raw"],"methods":{k:False for k in ("validate_inputs","fingerprint_inputs","check_lazy_status")},"schema":encode_schema(copy.deepcopy(cls.GET_SCHEMA()))} for key,cls in CLASSES.items()}}
def same(actual,expected):
 assert isinstance(actual,torch.Tensor) and actual.shape==expected.shape and actual.dtype==expected.dtype
 assert torch.equal(actual,expected)
def defaults(key):
 return {name:spec[1]["default"] for name,spec in SOURCE[key].INPUT_TYPES()["required"].items() if len(spec)>1 and "default" in spec[1]}
def source(key,data):return getattr(SOURCE[key](),SOURCE[key].FUNCTION)(**data)
class ImageDouble:
 def __init__(self,data):self.data=data;self.calls=[]
 async def raw(self):return self.data
 async def resize(self,width,height,*,method,crop):
  self.calls.append((width,height,method,crop))
  return ImageDouble(comfy.utils.common_upscale(self.data.movedim(-1,1),width,height,method,crop).movedim(1,-1))
def converted(key,data):
 values={k:ImageDouble(v) if CLASSES[key].SDK_REFS and isinstance(v,torch.Tensor) else v for k,v in data.items()}
 async def run():
  refs=_sdk.InProcessRefResolver()
  with _sdk.bind_runtime(refs,None):
   result=CLASSES[key].execute(**values)
   result=(await result if asyncio.iscoroutine(result) else result).result
   return tuple([await refs.resolve(v) if isinstance(v,_sdk.Ref) else v for v in result])
 return asyncio.run(run())
def video(batch=5,height=3,width=4,channels=3,dtype=torch.float32,offset=0):
 return (torch.arange(batch*height*width*channels,dtype=torch.float64).reshape(batch,height,width,channels)/79+offset).to(dtype)
def literal_zero(a,b,n,m):
 if n==0 and m==0:return torch.cat((a,b))
 first=torch.cat([a[[-n+i],]*(1-(i+1)/(n+1))+b[[i],]*((i+1)/(n+1)) for i in range(n)]) if n else a[:0]
 second=torch.cat([b[[-m+i],]*(1-(i+1)/(m+1))+a[[i],]*((i+1)/(m+1)) for i in range(m)]) if m else a[:0]
 return torch.cat((second,a[m:a.shape[0]-n],first,b[n:b.shape[0]-m]))
def differential(key,data):
 snapshots={k:v.clone() for k,v in data.items() if isinstance(v,torch.Tensor)}
 try:expected=source(key,data)
 except Exception as native:
  with pytest.raises(type(native)):converted(key,data)
 else:
  actual=converted(key,data);assert len(actual)==len(expected)
  for a,b in zip(actual,expected,strict=True):same(a,b)
 for k,v in snapshots.items():assert torch.equal(v,data[k])

def test_actual_four_node_census_schema_options_display_helpers_and_proxy():
 assert IDS==list(CLASSES)==["EmptyImageBBTools","ReplaceColorBBTools","VideosConcatWithCrossFadeBBTools","VideosConcatWithCrossFadeLoopbackBBTools"]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS
 for key,cls in CLASSES.items():
  original=SOURCE[key];schema=cls.GET_SCHEMA();schema.validate()
  assert schema.node_id==key and schema.category==original.CATEGORY and schema.display_name==NEW.NODE_DISPLAY_NAME_MAPPINGS[key]
  assert tuple(o.io_type for o in schema.outputs)==original.RETURN_TYPES
  if hasattr(original,"RETURN_NAMES"):assert tuple(o.display_name for o in schema.outputs)==original.RETURN_NAMES
  for inp,(name,spec) in zip(schema.inputs,original.INPUT_TYPES()["required"].items(),strict=True):
   assert inp.id==name and inp.io_type==spec[0] and not inp.optional
   for option,value in (spec[1] if len(spec)>1 else {}).items():
    assert inp.as_dict()["display" if option=="display" else option]==value
  assert cls.SDK_PERMISSIONS==("raw",)
 oldfunc={n.name:ast.dump(n,include_attributes=False) for n in ast.parse((PACK/"nodes.py").read_text()).body if isinstance(n,ast.FunctionDef)}
 newfunc={n.name:ast.dump(n,include_attributes=False) for n in ast.parse((V2/"_algorithm.py").read_text()).body if isinstance(n,ast.FunctionDef)}
 assert len(newfunc)==7 and all(oldfunc[k]==v for k,v in newfunc.items())
 proxy=packdb.load_pack(SNAPSHOT,mount_name="custom_nodes.ned_bbtools_proxy")
 assert list(proxy.node_mappings)==IDS and not proxy.routes and proxy.web_directory is None

@pytest.mark.parametrize("shape",[(8,8,1),(17,13,2),(0,9,1),(9,0,1),(9,9,0),(-1,9,1),(9,9,-1),(512,512,1)])
@pytest.mark.parametrize("color",[(0,0,0,0),(255,37,199,1),(19,73,243,.375),(-1,260,17,1.25)])
def test_empty_image_exact_channels_mask_order_defaults_native_allocation(shape,color):
 width,height,batch=shape;red,green,blue,alpha=color
 differential(IDS[0],dict(width=width,height=height,batch=batch,red=red,green=green,blue=blue,alpha=alpha))

@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64,torch.uint8,torch.bfloat16])
@pytest.mark.parametrize("channels",[1,2,3,4,5])
@pytest.mark.parametrize("threshold",[0,.05,1])
def test_replace_color_exact_pillow_squeeze_quantization_alpha_and_dtype(dtype,channels,threshold):
 data=defaults(IDS[1]);data.update(image=video(batch=2,channels=channels,dtype=dtype),threshold=threshold,replace_red=240,replace_green=13,replace_blue=87)
 differential(IDS[1],data)

@pytest.mark.parametrize("shape",[(0,3,4,3),(2,1,4,3),(2,3,1,3),(2,1,1,3),(2,0,4,3),(2,3,0,3)])
def test_replace_native_empty_and_singleton_shapes(shape):
 data=defaults(IDS[1]);data["image"]=torch.zeros(shape);differential(IDS[1],data)

def test_strict_color_distance_boundary_and_threshold_zero():
 pixel=(3,4,0);distance=ALG.color_variance(pixel,(0,0,0));assert distance==5/(255*3**.5)
 for threshold in (0,distance,distance+1e-12):
  data=defaults(IDS[1]);data.update(image=torch.tensor(pixel).float().reshape(1,1,1,3).expand(1,2,2,3)/255,threshold=threshold,replace_red=200)
  differential(IDS[1],data)
  result=converted(IDS[1],data)[0]
  assert result[0,0,0,0]==(200/255 if threshold>distance else 3/255)

@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64,torch.uint8,torch.bfloat16])
@pytest.mark.parametrize("n",[1,2,4])
@pytest.mark.parametrize("resize",[False,True])
def test_plain_positive_transition_exact_order_weights_and_canonical_resize(dtype,n,resize):
 data=dict(images1=video(dtype=dtype),images2=video(height=5 if resize else 3,width=7 if resize else 4,dtype=dtype,offset=1),cross_fade_frames=n)
 differential(IDS[2],data)

@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64,torch.uint8,torch.bfloat16])
@pytest.mark.parametrize("n,m",[(1,1),(1,2),(2,1),(2,3)])
@pytest.mark.parametrize("resize",[False,True])
def test_loopback_positive_exact_rotated_frames_dtype_and_resize(dtype,n,m,resize):
 data=dict(images1=video(dtype=dtype),images2=video(height=5 if resize else 3,width=7 if resize else 4,dtype=dtype,offset=1),cross_fade_frames1=n,cross_fade_frames2=m)
 differential(IDS[3],data)

@pytest.mark.parametrize("n,m",[(0,0),(0,1),(0,3),(1,0),(3,0)])
@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64,torch.uint8,torch.bfloat16])
def test_native_zero_cat_failure_preserved_and_approved_zero_transition_controls(n,m,dtype):
 a=video(dtype=dtype);b=video(dtype=dtype,offset=1)
 with pytest.raises(ValueError,match="non-empty"):source(IDS[3],dict(images1=a,images2=b,cross_fade_frames1=n,cross_fade_frames2=m))
 same(converted(IDS[3],dict(images1=a,images2=b,cross_fade_frames1=n,cross_fade_frames2=m))[0],literal_zero(a,b,n,m))
 with pytest.raises(ValueError,match="non-empty"):source(IDS[2],dict(images1=a,images2=b,cross_fade_frames=0))
 same(converted(IDS[2],dict(images1=a,images2=b,cross_fade_frames=0))[0],torch.cat((a,b)))

@pytest.mark.parametrize("n,m",[(-1,1),(1,-1),(5,1),(1,5),(6,0),(0,6)])
def test_native_length_sum_negative_and_shape_failures(n,m):
 data=dict(images1=video(),images2=video(offset=1),cross_fade_frames1=n,cross_fade_frames2=m)
 differential(IDS[3],data)
 data=dict(images1=video(),images2=video(offset=1),cross_fade_frames=n)
 if n!=0:differential(IDS[2],data)

@pytest.mark.parametrize("channels",[1,2,4])
@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64,torch.uint8])
def test_native_video_extra_channels_same_canvas_noncontiguous_and_input_identity(channels,dtype):
 a=video(width=8,channels=channels,dtype=dtype)[:,:,::2,:];b=video(channels=channels,dtype=dtype,offset=1)
 assert not a.is_contiguous()
 differential(IDS[2],dict(images1=a,images2=b,cross_fade_frames=2))
 differential(IDS[3],dict(images1=a,images2=b,cross_fade_frames1=1,cross_fade_frames2=2))

@pytest.mark.parametrize("key",IDS[2:])
def test_video_source_empty_positive_errors_and_approved_empty_zero_dispositions(key):
 a=video(batch=0);b=video()
 data=dict(images1=a,images2=b)
 data.update(dict(cross_fade_frames=1) if key==IDS[2] else dict(cross_fade_frames1=1,cross_fade_frames2=0))
 differential(key,data)
 data.update(defaults(key))
 if key==IDS[2]:
  # Plain source first-frame shape check is retained before repaired zero.
  with pytest.raises(IndexError):converted(key,data)
 else:same(converted(key,data)[0],torch.cat((a,b)))

def test_actual_public_resize_callshape_and_zero_frame_order():
 async def run():
  refs=_sdk.InProcessRefResolver()
  for key in IDS[2:]:
   a=ImageDouble(video());b=ImageDouble(video(height=5,width=7,offset=1))
   with _sdk.bind_runtime(refs,None):
    out=await CLASSES[key].execute(images1=a,images2=b,**defaults(key))
    result=await refs.resolve(out.result[0])
   assert b.calls==[(4,3,"bilinear","center")]
   resized=comfy.utils.common_upscale(b.data.movedim(-1,1),4,3,"bilinear","center").movedim(1,-1)
   same(result,torch.cat((a.data,resized)))
 asyncio.run(run())

def test_bounds_before_pillow_allocation_resize_and_whole_backing(monkeypatch):
 def forbid(*a,**k):raise AssertionError("algorithm before bounds")
 monkeypatch.setattr(ALG,"emptyimage",forbid);monkeypatch.setattr(ALG,"tensor2pil",forbid)
 for data in (dict(defaults(IDS[0]),width=4097),dict(defaults(IDS[0]),batch=65),dict(defaults(IDS[0]),width=2048,height=2048)):
  with pytest.raises(ValueError,match="bounds|budget"):converted(IDS[0],data)
 for image in (torch.empty(65,2,2,3),torch.empty(1,4097,2,3),torch.empty(1,2048,2048,3,device="meta")):
  with pytest.raises(ValueError,match="bounds|budget"):converted(IDS[1],dict(defaults(IDS[1]),image=image))
 backing=torch.empty(17*1024*1024);view=backing[:12].reshape(1,2,2,3)
 with pytest.raises(ValueError,match="input byte"):MOD.image_bounds((view,))
 with pytest.raises(ValueError,match="video output/workspace"):MOD.preflight_video(torch.empty(1,1024,1024,3,device="meta"),torch.empty(4,2,2,3,device="meta"))
 for value in (False,1.5,"0",10001):
  with pytest.raises(ValueError):MOD.integer(value,"frames")

def test_two_required_fresh_guests_all_four_real_outer_types_defaults_zero_asymmetry_and_denial(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    with (fresh/"_secure_nodes.py").open("a") as stream:
     stream.write("\nclass NedBBRawProbe(io.ComfyNode):\n @classmethod\n async def execute(cls):\n  from comfy_api.latest import sdk\n  return io.NodeOutput(await sdk.TensorRef.from_value(torch.zeros(1)))\n")
    classes=load("ned_bbtools_fresh_"+str(render),fresh).NODE_CLASS_MAPPINGS
    for cls in classes.values():cls.GET_SCHEMA()
    session=await GuestSession("ned-bbtools-"+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=("raw",),tenant="bbtools-"+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(key,data):
     cls=classes[key]
     result=await execution._async_map_node_over_list(prompt_id="bbtools-outer",unique_id=key,obj=cls,input_data_all={k:[v] for k,v in data.items()},func=cls.FUNCTION,v3_data=None)
     return result[0].result
    try:
     assert session.sandbox_kind=="seatbelt"
     data=defaults(IDS[0]);actual=await outer(IDS[0],data)
     for a,b in zip(actual,source(IDS[0],data),strict=True):same(a,b)
     assert actual[1].shape==(1,512,512) and len(actual)==3
     for dtype in (torch.float16,torch.float32,torch.float64):
      for channels in (3,4):
       data=dict(defaults(IDS[1]),image=video(batch=2,channels=channels,dtype=dtype),threshold=.5)
       same((await outer(IDS[1],data))[0],source(IDS[1],data)[0])
     for dtype in (torch.float16,torch.float32,torch.float64,torch.uint8,torch.bfloat16):
      a=video(dtype=dtype);b=video(dtype=dtype,offset=1)
      for n in (0,1,2):
       data=dict(images1=a,images2=b,cross_fade_frames=n)
       same((await outer(IDS[2],data))[0],torch.cat((a,b)) if n==0 else source(IDS[2],data)[0])
      for n,m in ((0,0),(0,2),(2,0),(1,1),(1,2)):
       data=dict(images1=a,images2=b,cross_fade_frames1=n,cross_fade_frames2=m)
       expected=literal_zero(a,b,n,m) if n==0 or m==0 else source(IDS[3],data)[0]
       same((await outer(IDS[3],data))[0],expected)
     for key in IDS[2:]:
      data=dict(images1=video(),images2=video(height=5,width=7,offset=1))
      data.update(dict(cross_fade_frames=1) if key==IDS[2] else dict(cross_fade_frames1=1,cross_fade_frames2=2))
      same((await outer(key,data))[0],source(key,data)[0])
     data=dict(defaults(IDS[1]),image=video(dtype=torch.bfloat16))
     with pytest.raises(Exception,match="TypeError|BFloat16"):await outer(IDS[1],data)
     with pytest.raises(Exception,match="budget"):await outer(IDS[0],dict(defaults(IDS[0]),width=2048,height=2048))
     with pytest.raises(Exception,match="Video Length|image lengths"):await outer(IDS[3],dict(images1=video(),images2=video(offset=1),cross_fade_frames1=3,cross_fade_frames2=3))
     refs=_sdk.InProcessRefResolver();cls=classes[IDS[0]]
     plan=_sdk.ExecutionPlan(prompt_id="bbtools-probe",node_id="probe",node_type="NedBBRawProbe",node_module=cls.__module__,inputs={},permissions=("raw",),method="execute")
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
     with pytest.raises(Exception,match="raw|permission|capabil"):await session.execute(plan,runtime,capabilities=(),tenant="bbtools-"+str(render))
     for key in IDS[2:]:
      data=dict(images1=video(),images2=video(offset=1));data.update(defaults(key))
      same((await outer(key,data))[0],torch.cat((data["images1"],data["images2"])))
     pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_pristine_exact_git_resources_stubs_no_ambient_state_or_cache():
 assert json.loads((V2/"secure-nodes.json").read_text())==manifest()
 provenance=json.loads((V2/"source-provenance.json").read_text())
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob("*") if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==provenance["source_hashes"] and len(pristine)==6
 for name in ("README.md","LICENSE",".github/workflows/publish_action.yml"):assert (V2/name).read_bytes()==(PACK/name).read_bytes()
 for name,sha in [("comfy-api.pyi","89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada"),("comfy-api.d.ts","2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090")]:assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 for path in V2.glob("*.py"):
  text=path.read_text()
  for forbidden in ("_from_raw","_wrap(","folder_paths","PromptServer","subprocess","requests","tempfile"):assert forbidden not in text
  tree=ast.parse(text)
  for node in ast.walk(tree):
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id not in ("open","exec","eval","__import__")
   if isinstance(node,ast.Import):assert all(alias.name not in ("os","sys","pathlib","tempfile","subprocess","requests","nodes","comfy") for alias in node.names)
 assert not list(PACK.rglob("*.js")) and not list(PACK.rglob("__pycache__")) and not list(PACK.rglob("*.pyc"))

def test_pair_zip_two_exact_reconstructions_and_wrong_source_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix(".json").read_text())==expected and PAIR.with_suffix(".diff").read_bytes()==diff.encode()
 for index in range(2):
  fresh=tmp_path/str(index)/"comfyui-bbtools/x1cd0de6";fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns("v2"))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/"v2",V2)
 fresh=tmp_path/"bad/comfyui-bbtools/x1cd0de6";fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns("v2"))
 with (fresh/PACK.name/"nodes.py").open("ab") as stream:stream.write(b"\n#wrong source")
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/"v2").exists()
