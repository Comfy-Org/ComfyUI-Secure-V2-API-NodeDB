"""Exact UniAnimate layout/input consumer; no learned pose/model inference."""
import ast
import asyncio
import copy
import importlib.util
import itertools
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
CORE="/Users/ben/comfy/ComfyUI-secure-nodes"
sys.path[:0]=[CORE,"/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT",CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
ID="WanVideoUniAnimatePoseInput"


def candidate(root=V2):
    name="_wan_unianimate_input_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return pkg.NODE_CLASS_MAPPINGS[ID]


def source():
    cls=next(n for n in ast.parse((PACK/"unianimate/nodes.py").read_text()).body if getattr(n,"name",None)==ID)
    ns={}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/"unianimate/nodes.py"),"exec"),ns)
    return ns[ID]()


def image(batch,height,width,channels,dtype,noncontiguous=False):
    value=(torch.arange(batch*height*width*channels).reshape(batch,height,width,channels)%23).to(dtype)
    if dtype.is_floating_point:
        value/=22
    if noncontiguous:
        value=value.transpose(1,2).contiguous().transpose(1,2)
    return value


def same(expected,actual):
    assert isinstance(actual,tuple) and len(actual)==1 and list(actual[0])==list(expected[0])
    for name in expected[0]:
        left=expected[0][name];right=actual[0][name]
        if isinstance(left,torch.Tensor):
            assert right.shape==left.shape and right.dtype==left.dtype and right.is_contiguous()
            torch.testing.assert_close(right,left,rtol=0,atol=0,equal_nan=True)
        else:
            assert right is left or right==left


def test_exact_schema_and_algorithm_ast_layout_only():
    old=source();cls=candidate();schema=cls.GET_SCHEMA()
    assert schema.node_id==ID and schema.display_name=="WanVideo UniAnimate Pose Input" and schema.category==old.CATEGORY
    specs=old.INPUT_TYPES();fields={**specs["required"],**specs["optional"]}
    assert [field.id for field in schema.inputs]==list(fields)
    for item in schema.inputs:
        spec=fields[item.id]
        assert item.io_type==spec[0] and item.optional==(item.id in specs["optional"])
        for key,value in spec[1].items():
            assert getattr(item,key)==value
    assert tuple(item.io_type for item in schema.outputs)==old.RETURN_TYPES
    assert tuple(item.display_name for item in schema.outputs)==old.RETURN_NAMES
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==("raw",)
    old_fn=next(n for n in ast.parse((PACK/"unianimate/nodes.py").read_text()).body if getattr(n,"name",None)==ID)
    old_fn=next(n for n in old_fn.body if getattr(n,"name",None)=="process")
    new_fn=next(n for n in ast.parse((V2/"secure_unianimate_input_nodes.py").read_text()).body if getattr(n,"name",None)==ID)
    new_fn=next(n for n in new_fn.body if getattr(n,"name",None)=="execute")
    body=old_fn.body[:-1]+ast.parse("return io.NodeOutput(unianim_poses)").body
    assert ast.dump(ast.Module(body=body,type_ignores=[]),include_attributes=False)==ast.dump(ast.Module(body=new_fn.body[1:],type_ignores=[]),include_attributes=False)


def test_96_exact_layout_cases_dtype_reference_order_and_input_integrity():
    count=0
    for batch,(height,width,noncontig),channels,dtype,with_ref in itertools.product(
        (1,3),((5,7,False),(4,6,True)),(1,3,4),
        (torch.uint8,torch.bfloat16,torch.float32,torch.float64),(False,True)):
        poses=image(batch,height,width,channels,dtype,noncontig)
        ref=image(2,height,width,channels,dtype,noncontig) if with_ref else None
        args=dict(pose_images=poses,strength=.75,start_percent=.1,end_percent=.9,reference_pose_image=ref)
        before_poses=poses.clone();before_ref=ref.clone() if with_ref else None
        expected=source().process(**args)
        actual=candidate().execute(**args).result
        same(expected,actual)
        assert actual[0]["pose"].shape==(1,channels,batch,height,width)
        assert (actual[0]["ref"].shape==(2,channels,height,width)) if with_ref else actual[0]["ref"] is None
        assert torch.equal(poses,before_poses)
        if with_ref:assert torch.equal(ref,before_ref)
        count+=1
    assert count==96


def test_degenerate_alias_empty_and_direct_metadata_native_outcomes():
    cls=candidate()
    for tensor in (torch.ones(1,1,1,1),torch.empty(0,2,3,3),torch.empty(1,2,3,0)):
        args=dict(pose_images=tensor,strength="native",start_percent=None,end_percent=-2.,reference_pose_image=tensor)
        old=source().process(**args);new=cls.execute(**args).result;same(old,new)
        assert (old[0]["pose"].untyped_storage().data_ptr()==tensor.untyped_storage().data_ptr())==(new[0]["pose"].untyped_storage().data_ptr()==tensor.untyped_storage().data_ptr())
        assert (old[0]["ref"].untyped_storage().data_ptr()==tensor.untyped_storage().data_ptr())==(new[0]["ref"].untyped_storage().data_ptr()==tensor.untyped_storage().data_ptr())
    # Empty/channel0 results are direct source parity only, not IMAGE broker admission.


@pytest.mark.parametrize("pose,ref",[
 (None,None),(torch.ones(2,3,4),None),(torch.ones(1,2,3,4,5),None),
 (np.ones((1,2,3,3),dtype=np.float32),None),
 (torch.ones(1,2,3,3),torch.ones(2,3,4)),
])
def test_native_malformed_input_errors(pose,ref):
    args=dict(pose_images=pose,strength=1.,start_percent=0.,end_percent=1.,reference_pose_image=ref)
    with pytest.raises(Exception) as expected:source().process(**copy.deepcopy(args))
    with pytest.raises(type(expected.value)) as actual:candidate().execute(**copy.deepcopy(args))
    assert str(actual.value)==str(expected.value)


def test_preallocation_copy_overlap_guard_without_materializing_meta_storage():
    big=torch.empty((1,1792,1792,3),device="meta",dtype=torch.float32)
    with pytest.raises(ValueError,match="projected"):
        candidate().execute(big,1.,0.,1.)
    with pytest.raises(ValueError,match="64 KiB"):
        candidate().execute(torch.zeros(1,2,3,3),"x"*65537,0.,1.)


def test_actual_outer_landmark_producer_pose_consumer_fresh_guests_and_raw_denial(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required");monkeypatch.syspath_prepend(CORE)
    fresh=tmp_path/"fresh-render";shutil.copytree(V2,fresh)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index,root in enumerate((V2,fresh)):
                snapshot=PACK.parent if index==0 else tmp_path/"snapshot"
                if index:
                    mounted=snapshot/PACK.name;mounted.mkdir(parents=True);shutil.copytree(root,mounted/"v2");root=mounted/"v2"
                mappings=packdb.load_pack(snapshot,mount_name="custom_nodes.wan_unianimate_outer_"+str(index)).node_mappings
                cls=mappings[ID];producer=mappings["LandmarksToImage"]
                settings=mappings["WanVideoSamplerExtraArgs"]
                session=await GuestSession("wan-unianimate-input",guest_runtime_root=root).start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        assert plan.permissions in ((),("raw",))
                        capabilities=("raw",) if plan.permissions==("raw",) else ()
                        return await session.execute(plan,runtime,capabilities=capabilities,tenant="uni-pose-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    producer_args=dict(landmarks=[[[1,2],[9,8]],[[3,4]]],width=32,height=24)
                    finalized,missing,meta=execution.get_input_data(producer_args,producer,"raster",None);assert not missing
                    rendered=await execution._async_map_node_over_list(prompt_id="unianimate",unique_id="raster",obj=producer,
                        input_data_all=finalized,func="execute",v3_data=meta)
                    poses=rendered[0].result[0]
                    assert poses.shape==(2,24,32,3) and poses.dtype==torch.float32
                    for ref in (None,poses[:1]):
                        args=dict(pose_images=poses,strength=.75,start_percent=.1,end_percent=.9,reference_pose_image=ref)
                        expected=source().process(**args)
                        finalized,missing,meta=execution.get_input_data(args,cls,"layout",None);assert not missing
                        result=await execution._async_map_node_over_list(prompt_id="unianimate",unique_id="layout",obj=cls,
                            input_data_all=finalized,func="execute",v3_data=meta)
                        same(expected,result[0].result)
                        assert cls.GET_SCHEMA().outputs[0].io_type=="UNIANIMATE_POSE"
                        forwarded_input=dict(unianimate_poses=result[0].result[0])
                        fields,missing,meta=execution.get_input_data(forwarded_input,settings,"settings",None);assert not missing
                        forwarded=await execution._async_map_node_over_list(prompt_id="unianimate",unique_id="settings",obj=settings,
                            input_data_all=fields,func="execute",v3_data=meta)
                        assert list(forwarded[0].result[0])==["unianimate_poses"]
                        same(expected,(forwarded[0].result[0]["unianimate_poses"],))
                        assert settings.SDK_PERMISSIONS==()
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id="denied",node_id="layout",node_type=ID,node_module=cls.__module__,
                            inputs=await _sdk.wrap_inputs(refs,args),input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match="raw"):
                            await session.execute(plan,runtime,capabilities=(),tenant="uni-pose-"+str(index))
                    pids.append(session.pid)
                finally:
                    await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
