"""Native CPU noise fill; GPU policy pending, no model/inference claim."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import pytest
import torch
import torch.nn.functional as F
from tqdm import tqdm
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
CORE="/Users/ben/comfy/ComfyUI-secure-nodes"
sys.path[:0]=[CORE,"/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT",CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
ID="DrawGaussianNoiseOnImage"

def candidate(root=V2):
    name="_wan_gaussian_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg);return pkg

def source():
    path=PACK/"nodes_utility.py"
    cls=next(x for x in ast.parse(path.read_text()).body if isinstance(x,ast.ClassDef) and x.name==ID)
    ns=dict(torch=torch,F=F,tqdm=tqdm)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(path),"exec"),ns)
    return ns[ID]()

def inputs(batch=3,masks=2,resized=False,dtype=torch.float32,mask_kind="partial"):
    image=(torch.arange(batch*6*8*3,dtype=torch.float32).reshape(batch,6,8,3)%97/96).to(dtype)
    h,w=(3,2) if resized else (6,8)
    mask=((torch.arange(masks*h*w).reshape(masks,h,w)%3)==0).to(dtype)
    if mask_kind=="all":mask.fill_(1)
    if mask_kind=="none":mask.fill_(0)
    return image,mask

def same(a,b):
    assert a.shape==b.shape and a.dtype==b.dtype
    torch.testing.assert_close(a,b,rtol=0,atol=0,equal_nan=True)

def test_exact_optional_schema_and_source_noise_body_without_device_authority():
    old=source();cls=candidate().NODE_CLASS_MAPPINGS[ID];schema=cls.GET_SCHEMA();info=old.INPUT_TYPES()
    assert schema.node_id==ID and schema.category==old.CATEGORY and schema.description==old.DESCRIPTION
    specs={**info["required"],**info["optional"]}
    assert [x.id for x in schema.inputs]==list(specs)
    for item,(name,spec) in zip(schema.inputs,specs.items()):
        assert item.optional==(name in info["optional"])
        if isinstance(spec[0],list):assert item.options==spec[0]
        else:assert item.io_type==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert getattr(item,key)==value
    assert schema.outputs[0].io_type==old.RETURN_TYPES[0]
    assert schema.outputs[0].display_name==old.RETURN_NAMES[0]
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==("raw",)
    a=next(x for x in ast.parse((PACK/"nodes_utility.py").read_text()).body if getattr(x,"name",None)==ID)
    old_fn=next(x for x in a.body if getattr(x,"name",None)=="apply")
    new_fn=next(x for x in ast.parse((V2/"secure_noise_algorithms.py").read_text()).body if getattr(x,"name",None)=="draw_gaussian_noise_cpu")
    # Reuse the already prepared algorithm rather than duplicating it. Normalize
    # only CPU device selection and the explicit removed stderr progress bar.
    old_fn.body[2]=ast.parse("processing_device = torch.device('cpu')").body[0]
    for stmt in ast.walk(old_fn):
        if isinstance(stmt,ast.For) and isinstance(stmt.iter,ast.Call) and isinstance(stmt.iter.func,ast.Name) and stmt.iter.func.id=="tqdm":
            stmt.iter=stmt.iter.args[0]
    assert ast.dump(ast.Module(body=old_fn.body,type_ignores=[]),include_attributes=False)==ast.dump(ast.Module(body=new_fn.body[1:],type_ignores=[]),include_attributes=False)

def test_seed_exact_resize_repeat_statistics_masking_empty_and_no_global_rng():
    cls=candidate().NODE_CLASS_MAPPINGS[ID];old=source();count=0
    rng=torch.random.get_rng_state().clone()
    for batch in (1,3):
        for masks in (1,2,4):
            for resized in (False,True):
                for dtype in (torch.float16,torch.bfloat16,torch.float32,torch.float64):
                    for kind in ("partial","all","none"):
                        image,mask=inputs(batch,masks,resized,dtype,kind);a=image.clone();b=mask.clone()
                        for seed in (0,42,0xffffffffffffffff):
                            expected=old.apply(image,mask,"cpu",seed)[0]
                            actual=cls.execute(image,mask,"cpu",seed).result[0];same(expected,actual);count+=1
                        same(image,a);same(mask,b)
    assert count==432 and torch.equal(torch.random.get_rng_state(),rng)
    image,mask=inputs()
    same(old.apply(image,mask,"not-gpu",17)[0],cls.execute(image,mask,"not-gpu",17).result[0])
    image=image[:0];mask=mask[:0]
    same(old.apply(image,mask,"cpu",-1)[0],cls.execute(image,mask,"cpu",-1).result[0])

def test_native_malformed_channels_single_subject_pixel_seed_and_integer_errors():
    cls=candidate().NODE_CLASS_MAPPINGS[ID];old=source();image,mask=inputs(1,1)
    one=mask*0;one[0,0,0]=1
    cases=[(image[..., :2],mask,0),(torch.cat([image,image[..., :1]],-1),mask,0),
        (image,mask[:0],0),(image,one,0),(image,mask,2**64),(image,mask,"0"),
        (image.to(torch.int64),mask,0),(image.squeeze(0),mask,0),(image,mask.unsqueeze(0),0)]
    for value,masks,seed in cases:
        outcomes=[]
        for call in (lambda:old.apply(value,masks,"cpu",seed),lambda:cls.execute(value,masks,"cpu",seed)):
            try:call();outcomes.append(None)
            except Exception as error:outcomes.append((type(error).__name__,str(error)))
        assert outcomes[0] is not None and outcomes[0]==outcomes[1],outcomes
    same(old.apply(image[..., :1],mask,"cpu",0)[0],cls.execute(image[..., :1],mask,"cpu",0).result[0])

def test_bounds_before_clone_or_rng_and_visible_gpu_choice_fails_closed(monkeypatch):
    cls=candidate().NODE_CLASS_MAPPINGS[ID]
    monkeypatch.setattr(torch.Tensor,"clone",lambda *args:pytest.fail("bound before clones"))
    image=torch.zeros(1,1,1,3).expand(1,1024,1024,3)
    mask=torch.zeros(1,1,1).expand(1,1024,1024)
    with pytest.raises(ValueError,match="projected"):cls.execute(image,mask)
    with pytest.raises(RuntimeError,match="pending host-admitted"):
        cls.execute(torch.zeros(1,6,8,3),torch.zeros(1,6,8),device="gpu")
    assert cls.GET_SCHEMA().inputs[2].options==["cpu","gpu"]

def test_actual_outer_image_order_dtypes_fresh_guests_raw_denial(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required");monkeypatch.syspath_prepend(CORE)
    fresh=tmp_path/"fresh-render";shutil.copytree(V2,fresh)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index,root in enumerate((V2,fresh)):
                cls=candidate(root).NODE_CLASS_MAPPINGS[ID]
                session=await GuestSession("wan-gaussian-cpu",guest_runtime_root=root).start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="noise-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for batch,masks,resize,dtype in ((1,1,False,torch.float32),(3,2,True,torch.float32),(1,4,False,torch.float64)):
                        image,mask=inputs(batch,masks,resize,dtype)
                        args=dict(image=image,mask=mask,device="cpu",seed=42)
                        expected=source().apply(**args)[0];before=image.clone()
                        finalized,missing,data=execution.get_input_data(args,cls,"owner",None);assert not missing
                        result=await execution._async_map_node_over_list(prompt_id="noise",unique_id="owner",
                            obj=cls,input_data_all=finalized,func="execute",v3_data=data)
                        actual=result[0].result[0];same(expected,actual);same(image,before)
                        assert cls.GET_SCHEMA().outputs[0].io_type=="IMAGE"
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id="denied",node_id="owner",node_type=ID,node_module=cls.__module__,
                            inputs=await _sdk.wrap_inputs(refs,args),input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match="raw"):
                            await session.execute(plan,runtime,capabilities=(),tenant="noise-"+str(index))
                    pids.append(session.pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
