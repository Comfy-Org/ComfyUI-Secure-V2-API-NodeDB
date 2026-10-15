"""Plücker camera geometry and temporal packing, no trained Fun model."""
import ast
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch
from einops import rearrange
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
CORE="/Users/ben/comfy/ComfyUI-secure-nodes"
sys.path[:0]=[CORE,"/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT",CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
ID="WanVideoFunCameraEmbeds"

def candidate(root=V2):
    name="_wan_fun_camera_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return pkg

def source():
    path=PACK/"fun_camera/nodes.py";tree=ast.parse(path.read_text())
    nodes=[x for x in tree.body if isinstance(x,(ast.ClassDef,ast.FunctionDef))]
    ns=dict(np=np,torch=torch,rearrange=rearrange)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),"exec"),ns)
    return ns

def poses(frames,strings=False):
    output=[]
    for i in range(frames):
        matrix=np.eye(4)[:3].copy()
        matrix[0,3]=i*0.03;matrix[1,3]=-i*0.01
        row=[float(i),0.75,0.85,0.5,0.5,0.0,0.0]+matrix.ravel().tolist()
        output.append([str(x) for x in row] if strings else row)
    return output

def same(a,b,wire=False):
    assert set(a)==set(b)=={"target_shape","num_frames","control_embeds"}
    assert list(a["target_shape"])==list(b["target_shape"])
    if not wire:assert type(a["target_shape"]) is tuple and type(b["target_shape"]) is tuple
    assert a["num_frames"]==b["num_frames"]
    x=a["control_embeds"];y=b["control_embeds"]
    assert set(x)==set(y)
    for key in x:
        if isinstance(x[key],torch.Tensor):
            assert x[key].dtype==y[key].dtype and x[key].shape==y[key].shape
            torch.testing.assert_close(x[key],y[key],rtol=0,atol=0,equal_nan=True)
        else:assert x[key]==y[key]

def test_exact_schema_helpers_and_native_unregistered_optional_ref():
    old=source()[ID]();cls=candidate().NODE_CLASS_MAPPINGS[ID];schema=cls.GET_SCHEMA()
    info=old.INPUT_TYPES()["required"]
    assert schema.category==old.CATEGORY and schema.node_id==ID
    assert [x.id for x in schema.inputs]==list(info)
    for item,(name,spec) in zip(schema.inputs,info.items()):
        assert item.io_type==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():assert getattr(item,key)==value
    assert [x.io_type for x in schema.outputs]==list(old.RETURN_TYPES)
    assert [x.display_name for x in schema.outputs]==list(old.RETURN_NAMES)
    assert cls.SDK_PERMISSIONS==("raw",) and cls.SDK_REFS is False
    a=ast.parse((PACK/"fun_camera/nodes.py").read_text());b=ast.parse((V2/"secure_fun_camera_nodes.py").read_text())
    for name in ("Camera","custom_meshgrid","get_relative_pose","ray_condition","process_poses"):
        old_fn=next(x for x in a.body if getattr(x,"name",None)==name)
        new_fn=next(x for x in b.body if getattr(x,"name",None)==name)
        assert ast.dump(old_fn,include_attributes=False)==ast.dump(new_fn,include_attributes=False)
    assert "fun_ref_image" not in info # source method has a latent arg not exposed by its schema

def test_source_geometry_both_aspect_branches_strength_and_time_order():
    old=source()[ID]();cls=candidate().NODE_CLASS_MAPPINGS[ID];count=0
    for frames in (1,5,9):
        for width,height in ((8,12),(16,8),(64,64)):
            for strength in (0.0,0.4,1.0):
                for strings in (False,True):
                    camera=poses(frames,strings);before=copy.deepcopy(camera)
                    args=dict(poses=camera,width=width,height=height,strength=strength,start_percent=0.2,end_percent=0.7)
                    expected=old.process(**args)[0];actual=cls.execute(**args).result[0]
                    same(expected,actual)
                    assert camera==before and actual["control_embeds"]["control_camera_latents"].dtype==torch.float32
                    assert actual["control_embeds"]["control_camera_latents"].shape==(1,24,(frames+3)//4,height,width)
                    assert actual["target_shape"]==(16,(frames-1)//4+1,height//8,width//8)
                    count+=1
    assert count==54
    refs={"samples":torch.arange(1*16*5*2*3,dtype=torch.float64).reshape(1,16,5,2,3)}
    args=dict(poses=poses(5),width=8,height=12,strength=1.0,start_percent=1.0,end_percent=0.0,fun_ref_image=refs)
    expected=old.process(**args)[0];actual=cls.execute(**args).result[0];same(expected,actual)
    assert actual["control_embeds"]["fun_ref_image"].data_ptr()==refs["samples"].data_ptr()
    assert actual["control_embeds"]["fun_ref_image"].shape==(1,16,2,3)
    mod=sys.modules[cls.__module__]
    assert mod.process_poses(poses(5,True),return_poses=True)==source()["process_poses"](poses(5,True),return_poses=True)

def test_native_non_4n_plus_1_malformed_singular_empty_and_zero_dimensions():
    old=source()[ID]();cls=candidate().NODE_CLASS_MAPPINGS[ID]
    singular=poses(1);singular[0][7:]=[0.0]*12
    cases=[(poses(2),8,12),(poses(4),8,12),([],8,12),(singular,8,12),
        ([[1.0]],8,12),(poses(1),8,0),(poses(1),-1,12),([["not-number"]*19],8,12)]
    for camera,width,height in cases:
        outcomes=[]
        for call in (lambda:old.process(camera,width,height,1.0,0.0,1.0),
                     lambda:cls.execute(camera,width,height,1.0,0.0,1.0)):
            try:call();outcomes.append(None)
            except Exception as error:outcomes.append((type(error).__name__,str(error)))
        assert outcomes[0] is not None and outcomes[0]==outcomes[1],outcomes

def test_work_count_aggregate_bounds_before_inverse_or_tensor_allocations(monkeypatch):
    cls=candidate().NODE_CLASS_MAPPINGS[ID];mod=sys.modules[cls.__module__]
    monkeypatch.setattr(mod.np.linalg,"inv",lambda *args:pytest.fail("must refuse before inverse"))
    for camera,width,height,message in (
        (poses(1),2048,29048,"64 MiB"),(poses(1001),8,12,"1000"),
        (np.broadcast_to(np.zeros(19),(1000000,19)),8,12,"work"),
        ([np.broadcast_to(np.zeros(1),(9000000,))],8,12,"aggregate")):
        with pytest.raises(ValueError,match=message):cls.execute(camera,width,height,1.0,0.0,1.0)

def test_actual_outer_guest_custom_input_and_output_fresh_roots_and_raw_denial(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required");monkeypatch.syspath_prepend(CORE)
    fresh=tmp_path/"fresh-render";shutil.copytree(V2,fresh)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index,root in enumerate((V2,fresh)):
                cls=candidate(root).NODE_CLASS_MAPPINGS[ID]
                session=await GuestSession("wan-fun-camera",guest_runtime_root=root).start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="fun-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for frames,width,height,strength in ((1,64,64,0.0),(5,16,8,0.4),(9,8,12,1.0)):
                        args=dict(poses=poses(frames),width=width,height=height,strength=strength,start_percent=0.2,end_percent=0.7)
                        expected=source()[ID]().process(**args)[0]
                        finalized,missing,data=execution.get_input_data(args,cls,"owner",None);assert not missing
                        results=await execution._async_map_node_over_list(prompt_id="fun",unique_id="owner",
                            obj=cls,input_data_all=finalized,func="execute",v3_data=data)
                        actual=results[0].result[0];same(expected,actual,wire=True)
                        assert cls.GET_SCHEMA().outputs[0].io_type=="WANVIDIMAGE_EMBEDS"
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id="denied",node_id="owner",node_type=ID,node_module=cls.__module__,
                            inputs=await _sdk.wrap_inputs(refs,args),input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match="raw"):
                            await session.execute(plan,runtime,capabilities=(),tenant="fun-"+str(index))
                    pids.append(session.pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
