"""Pinned Pillow byte/pixel effects, controlled noise and confined value-mode IMAGE."""
import asyncio,ast,copy,hashlib,importlib.util,itertools,json,os,re,shutil,sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
CORE=Path(os.environ["COMFY_CORE_ROOT"]);sys.path[:0]=[str(CORE),"/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
from comfy.cli_args import args
args.cpu=True
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes import packdb,packpatch
V2=Path(__file__).resolve().parents[1];PACK=V2.parent;SNAPSHOT=PACK.parent;DB=SNAPSHOT.parents[2]
PAIR=DB/"patches/comfyui-dequality/xaba850e/comfyui-dequality-xaba850e"
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path/"__init__.py",submodule_search_locations=[str(path)])
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
OLD=load("ned_dequality_old",PACK);NEW=load("ned_dequality_new",V2)
SOURCE=OLD.NODE_CLASS_MAPPINGS["Dequality"];CLS=NEW.NODE_CLASS_MAPPINGS["Dequality"];CLS.GET_SCHEMA()
ALGORITHM=sys.modules[CLS.__module__]
def manifest():
 return {"format":FORMAT,"runtime":manifest_declaration(V2),"nodes":{"Dequality":{"module":"_secure_nodes","class":"DequalitySecure","sdk_refs":False,"permissions":["raw"],"methods":{k:False for k in ("validate_inputs","fingerprint_inputs","check_lazy_status")},"schema":encode_schema(copy.deepcopy(CLS.GET_SCHEMA()))}}}
def fixture(channels=3,dtype=torch.float32,height=13,width=17):
 pixels=((torch.arange(height*width*channels,dtype=torch.float64).reshape(1,height,width,channels)%349)/255-.2).to(dtype)
 return dict(pixels=pixels,noise_level=0,jpeg_artifact_level=65,adjust_color=1,adjust_contrast=1,adjust_brightness=1,seed=54321)
def same(actual,expected):
 assert type(actual) is torch.Tensor and actual.dtype==expected.dtype==torch.float32
 assert actual.shape==expected.shape and torch.equal(actual,expected)
def controlled_source(data,draw_seed=5182):
 rng=np.random.RandomState(draw_seed)
 with patch.object(np.random,"normal",rng.normal),patch.object(np.random,"rand",rng.rand):
  return SOURCE().dequality(**data)[0]
def differential(data,draw_seed=5182):
 before=data["pixels"].clone()
 try:expected=controlled_source(data,draw_seed)
 except Exception as native:
  with pytest.raises(type(native)):ALGORITHM.run_algorithm(**data,noise_rng=np.random.RandomState(draw_seed))
 else:same(ALGORITHM.run_algorithm(**data,noise_rng=np.random.RandomState(draw_seed)),expected)
 assert torch.allclose(data["pixels"],before,equal_nan=True)
def numpy_state_equal(a,b):return a[0]==b[0] and np.array_equal(a[1],b[1]) and a[2:]==b[2:]
def test_actual_schema_census_proxy_and_exact_source_default_workload():
 assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==["Dequality"]
 assert OLD.NODE_DISPLAY_NAME_MAPPINGS==NEW.NODE_DISPLAY_NAME_MAPPINGS=={"Dequality":"Dequality"}
 schema=CLS.GET_SCHEMA();schema.validate();assert schema.node_id=="Dequality" and schema.category==SOURCE.CATEGORY and not schema.is_output_node
 assert [o.io_type for o in schema.outputs]==["IMAGE"]
 for inp,(name,spec) in zip(schema.inputs,SOURCE.INPUT_TYPES()["required"].items(),strict=True):
  assert inp.id==name and inp.io_type==spec[0] and not inp.optional
  if len(spec)>1:
   for key,value in spec[1].items():assert inp.as_dict()[key]==value
 assert CLS.SDK_REFS is False and CLS.SDK_PERMISSIONS==("raw",)
 proxy=packdb.load_pack(SNAPSHOT,mount_name="custom_nodes.ned_dequality_proxy")
 assert list(proxy.node_mappings)==["Dequality"] and not proxy.routes and proxy.web_directory is None
 data=fixture(height=512,width=512);data["noise_level"]=8;data["seed"]=0
 differential(data)
 assert ALGORITHM.run_algorithm(**data,noise_rng=np.random.RandomState(1)).shape==(1,512,512,3)

@pytest.mark.parametrize("channels",[1,2,3,4])
@pytest.mark.parametrize("quality",[0,65,95,100])
@pytest.mark.parametrize("adjustments",list(itertools.product([0,1],repeat=3)))
def test_exact_enhancement_order_channel_modes_and_jpeg_roundtrip(channels,quality,adjustments):
 data=fixture(channels);data["jpeg_artifact_level"]=quality
 data["adjust_brightness"],data["adjust_color"],data["adjust_contrast"]=adjustments
 differential(data)

@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64,torch.uint8,torch.int16,torch.bool,torch.bfloat16])
@pytest.mark.parametrize("quality",[0,65,100])
def test_exact_input_quantization_dtype_and_bfloat_numpy_error(dtype,quality):
 data=fixture(dtype=dtype);data["jpeg_artifact_level"]=quality;differential(data)

@pytest.mark.parametrize("noise",[1,8,100])
@pytest.mark.parametrize("quality",[65,100])
@pytest.mark.parametrize("channels",[2,3,4])
def test_controlled_legacy_noise_gaussians_variation_mask_and_order(noise,quality,channels):
 data=fixture(channels);data.update(noise_level=noise,jpeg_artifact_level=quality)
 for draw_seed in (0,3,999):differential(data,draw_seed)

@pytest.mark.parametrize("seed",[0,1,-1,54321,-54321,1125899906842624,-1125899906842624])
def test_absolute_seed_enhancements_and_unseeded_noise_contract(seed):
 data=fixture();data["seed"]=seed;differential(data)
 opposite=dict(data,seed=-seed)
 same(ALGORITHM.run_algorithm(**data),ALGORITHM.run_algorithm(**opposite))
 data.update(noise_level=8)
 same(ALGORITHM.run_algorithm(**data,noise_rng=np.random.RandomState(11)),controlled_source(data,11))

@pytest.mark.parametrize("shape",[(0,13,17,3),(2,13,17,3),(1,0,17,3),(1,13,0,3),(1,13,17,0),(1,13,17,5),(13,17,3),(1,17,3),(1,1,1,3)])
def test_native_empty_batch_channel_squeeze_and_hwc_errors(shape):
 data=fixture();data["pixels"]=torch.zeros(shape);differential(data)

def test_noncontiguous_nonfinite_and_input_unchanged():
 data=fixture(width=34);data["pixels"]=data["pixels"][:,:,::2,:];assert not data["pixels"].is_contiguous();differential(data)
 data=fixture();data["pixels"][0,0,0,:]=torch.tensor([float("nan"),float("inf"),-float("inf")]);differential(data)

@pytest.mark.parametrize("quality",[0,65,95,99])
@pytest.mark.parametrize("noise",[0,8])
def test_file_and_bytesio_jpeg_encoding_bytes_identical(quality,noise):
 original=ALGORITHM.Image.Image.save;captured=[]
 def record(image,target,*args,**kwargs):
  result=original(image,target,*args,**kwargs)
  captured.append(target.getvalue() if hasattr(target,"getvalue") else Path(target).read_bytes())
  return result
 data=fixture(channels=4);data.update(noise_level=noise,jpeg_artifact_level=quality)
 with patch.object(ALGORITHM.Image.Image,"save",record):
  expected=controlled_source(data,9)
  actual=ALGORITHM.run_algorithm(**data,noise_rng=np.random.RandomState(9))
 same(actual,expected)
 assert len(captured)==2 and captured[0]==captured[1] and captured[0].startswith(b"\xff\xd8")

def test_isolated_unseeded_noise_does_not_touch_global_rng_and_is_sampled():
 data=fixture(height=31,width=41);data.update(noise_level=100,jpeg_artifact_level=100,adjust_brightness=0,adjust_color=0,adjust_contrast=0)
 before=np.random.get_state();torch_before=torch.random.get_rng_state().clone()
 a=CLS.execute(**data).result[0];b=CLS.execute(**data).result[0]
 assert numpy_state_equal(before,np.random.get_state()) and torch.equal(torch_before,torch.random.get_rng_state())
 assert a.shape==b.shape==(1,31,41,3) and a.dtype==torch.float32 and not torch.equal(a,b)
 assert torch.isfinite(a).all() and a.min()>=0 and a.max()<=1
 # Source global continuation is measured separately; it is not preserved.
 state=np.random.get_state()
 try:SOURCE().dequality(**data);assert not numpy_state_equal(state,np.random.get_state())
 finally:np.random.set_state(state)

def test_bounds_before_numpy_or_pillow_and_backing_bytes(monkeypatch):
 def forbid(*a,**k):raise AssertionError("PIL work ran before admission")
 monkeypatch.setattr(ALGORITHM.Image,"fromarray",forbid)
 for pixels,message in [(torch.empty(65,2,2,3),"dimensions"),(torch.empty(1,4097,2,3),"dimensions"),
   (torch.empty(1,1024,1024,3,dtype=torch.float64).expand(4,-1,-1,-1),"input byte"),
   (torch.empty(1,2048,2048,3,device="meta"),"workspace"),
   (torch.empty(1,1,1,3,device="meta").expand(1,4096,4096,3),"input byte"),
   (torch.empty(1,3),"dense")]:
  data=fixture();data["pixels"]=pixels
  with pytest.raises(ValueError,match=message):CLS.execute(**data)
 backing=torch.empty(17*1024*1024);data=fixture();data["pixels"]=backing[:12].reshape(1,2,2,3)
 with pytest.raises(ValueError,match="input byte"):CLS.execute(**data)
 for key,value in [("seed",False),("noise_level",float("nan")),("jpeg_artifact_level","65"),("seed",1125899906842625),("noise_level",10001)]:
  data=fixture();data[key]=value
  with pytest.raises(ValueError):ALGORITHM.validate_scalars(**{k:v for k,v in data.items() if k!="pixels"})

def test_two_fresh_required_raw_guests_outer_image_dtype_codec_noise_and_denial(tmp_path):
 async def run():
  prior=_sdk.providers.execution_backend;pids=[]
  try:
   for render in range(2):
    fresh=tmp_path/str(render);shutil.copytree(V2,fresh)
    with (fresh/"_secure_nodes.py").open("a") as stream:
     stream.write("\nclass NedDequalityRawProbe(io.ComfyNode):\n @classmethod\n async def execute(cls):\n  from comfy_api.latest import sdk\n  return io.NodeOutput(await sdk.TensorRef.from_value(torch.zeros(1)))\n")
    cls=load("ned_dequality_fresh_"+str(render),fresh).NODE_CLASS_MAPPINGS["Dequality"];cls.GET_SCHEMA()
    session=await GuestSession("ned-dequality-"+str(render),guest_runtime_root=fresh).start()
    class Backend:
     async def dispatch(self,plan,local_call,runtime):
      plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
      return await session.execute(plan,runtime,capabilities=("raw",),tenant="dequality-"+str(render))
    _sdk.providers.register_execution_backend(Backend())
    async def outer(data):
     result=await execution._async_map_node_over_list(prompt_id="dequality-outer",unique_id=str(render),obj=cls,input_data_all={k:[v] for k,v in data.items()},func=cls.FUNCTION,v3_data=None)
     return result[0].result[0]
    try:
     assert session.sandbox_kind=="seatbelt"
     for dtype in (torch.float16,torch.float32,torch.float64,torch.uint8):
      for quality in (65,100):
       data=fixture(dtype=dtype);data["jpeg_artifact_level"]=quality
       same(await outer(data),SOURCE().dequality(**data)[0])
     data=fixture(channels=4,height=512,width=512);same(await outer(data),SOURCE().dequality(**data)[0])
     data=fixture();data.update(noise_level=100,jpeg_artifact_level=100)
     a=await outer(data);b=await outer(data)
     assert a.shape==b.shape==data["pixels"].shape and not torch.equal(a,b) and torch.isfinite(a).all() and a.min()>=0 and a.max()<=1
     for data in (fixture(channels=2),fixture(dtype=torch.bfloat16),dict(fixture(),pixels=torch.zeros(2,13,17,3))):
      try:SOURCE().dequality(**data)
      except Exception as native:
       with pytest.raises(Exception,match=re.escape(type(native).__name__)):await outer(data)
      else:raise AssertionError("native error fixture not discriminating")
     with pytest.raises(Exception,match="workspace"):await outer(dict(fixture(),pixels=torch.zeros(1,2048,2048,3)))
     refs=_sdk.InProcessRefResolver()
     plan=_sdk.ExecutionPlan(prompt_id="dequality-probe",node_id="probe",node_type="NedDequalityRawProbe",node_module=cls.__module__,inputs={},permissions=("raw",),method="execute")
     runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
     with pytest.raises(Exception,match="raw|permission|capabil"):await session.execute(plan,runtime,capabilities=(),tenant="dequality-"+str(render))
     data=fixture();same(await outer(data),SOURCE().dequality(**data)[0]);pids.append(session.last_guest_pid)
    finally:await session.kill()
  finally:_sdk.providers.register_execution_backend(prior)
  assert len(set(pids))==2 and os.getpid() not in pids
 asyncio.run(run())

def test_manifest_exact_pristine_stubs_imports_no_license_or_cache():
 assert json.loads((V2/"secure-nodes.json").read_text())==manifest()
 source=json.loads((V2/"source-provenance.json").read_text())
 pristine={p.relative_to(PACK).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in PACK.rglob("*") if p.is_file() and not p.is_relative_to(V2)}
 assert pristine==source["source_hashes"] and len(pristine)==4
 assert not list(PACK.glob("*LICENSE*")) and (V2/"README.md").read_bytes()==(PACK/"README.md").read_bytes()
 for name,sha in [("comfy-api.pyi","89347b67e8ac93aceaa006ae76cfafd6985ec797de504faa0b72268520baeada"),("comfy-api.d.ts","2747a5dd0ef4c30dfaa40e45b7ab3e4b0967301644647138287b42cbbe653090")]:
  assert hashlib.sha256((V2/name).read_bytes()).hexdigest()==sha
 for path in V2.glob("*.py"):
  text=path.read_text()
  for forbidden in ("_from_raw","_wrap(","folder_paths","PromptServer","subprocess","requests","tempfile"):assert forbidden not in text
  tree=ast.parse(text)
  for node in ast.walk(tree):
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id not in ("open","exec","eval","__import__")
   if isinstance(node,ast.Import):assert all(alias.name not in ("os","sys","pathlib","tempfile","subprocess","requests") for alias in node.names)
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="open":
    assert isinstance(node.func.value,ast.Name) and node.func.value.id=="Image"
    assert len(node.args)==1 and isinstance(node.args[0],ast.Name) and node.args[0].id=="stream"
 assert not list(PACK.rglob("*.js")) and not list(PACK.rglob("__pycache__")) and not list(PACK.rglob("*.pyc"))

def test_pair_zip_two_exact_reconstructions_and_wrong_source_refusal(tmp_path):
 expected,diff=packpatch.generate(SNAPSHOT)
 assert json.loads(PAIR.with_suffix(".json").read_text())==expected and PAIR.with_suffix(".diff").read_bytes()==diff.encode()
 for index in range(2):
  fresh=tmp_path/str(index)/"comfyui-dequality/xaba850e";fresh.mkdir(parents=True)
  shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns("v2"))
  if index==0:packpatch.apply(fresh,expected,diff)
  else:packpatch.apply_bundle(fresh,packpatch.bundle(expected,diff))
  packpatch.validate_tree(fresh/PACK.name/"v2",V2)
 fresh=tmp_path/"bad/comfyui-dequality/xaba850e";fresh.mkdir(parents=True)
 shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns("v2"))
 with (fresh/PACK.name/"dequality.py").open("ab") as stream:stream.write(b"\n# wrong source")
 with pytest.raises(packpatch.PackPatchError):packpatch.apply(fresh,expected,diff)
 assert not (fresh/PACK.name/"v2").exists()
