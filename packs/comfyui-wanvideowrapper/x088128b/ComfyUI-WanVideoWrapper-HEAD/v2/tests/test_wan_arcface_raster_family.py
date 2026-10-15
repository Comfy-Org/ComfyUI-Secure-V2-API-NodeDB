"""ArcFace debug raster scoped to explicit landmarks, not learned producer."""
import ast
import asyncio
import copy
import importlib.util
import itertools
import os
from pathlib import Path
import shutil
import sys
import cv2
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
ID="DrawArcFaceLandmarks"


def candidate(root=V2):
    name="_wan_arcface_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return pkg.NODE_CLASS_MAPPINGS[ID]


def source():
    cls=next(n for n in ast.parse((PACK/"lynx/nodes.py").read_text()).body if getattr(n,"name",None)==ID)
    ns=dict(torch=torch);exec(compile(ast.Module(body=[cls],type_ignores=[]),str(PACK/"lynx/nodes.py"),"exec"),ns)
    return ns[ID]()


def equal(old,new):
    assert len(old)==len(new)==1 and new[0].dtype==old[0].dtype and new[0].shape==old[0].shape
    torch.testing.assert_close(old[0],new[0],rtol=0,atol=0,equal_nan=True)


def test_schema_required_image_precedence_exact_method_ast(monkeypatch):
    monkeypatch.syspath_prepend(CORE)
    from comfy_execution.graph import get_input_info
    old=source();cls=candidate();schema=cls.GET_SCHEMA()
    assert schema.node_id==ID and schema.display_name=="Draw ArcFace Landmarks"
    assert schema.description==old.DESCRIPTION and schema.category==old.CATEGORY
    assert get_input_info(type(old),"image")[1]=="required"
    assert [(x.id,x.optional,x.io_type,x.tooltip) for x in schema.inputs]==[
        ("lynx_face_embeds",False,"LYNXIP","lynx resampler model"),("image",False,"IMAGE","Input images for the model")]
    assert [x.io_type for x in schema.outputs]==list(old.RETURN_TYPES)
    assert [x.display_name for x in schema.outputs]==list(old.RETURN_NAMES)
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==("raw",)
    old_cls=next(n for n in ast.parse((PACK/"lynx/nodes.py").read_text()).body if getattr(n,"name",None)==ID)
    old_fn=next(n for n in old_cls.body if getattr(n,"name",None)=="draw")
    new_cls=next(n for n in ast.parse((V2/"secure_arcface_raster_nodes.py").read_text()).body if getattr(n,"name",None)==ID)
    new_fn=next(n for n in new_cls.body if getattr(n,"name",None)=="execute")
    expected=old_fn.body[1:-1]+ast.parse("return io.NodeOutput(image_out)").body
    assert ast.dump(ast.Module(body=expected,type_ignores=[]),include_attributes=False)==ast.dump(ast.Module(body=new_fn.body[1:],type_ignores=[]),include_attributes=False)


def test_72_pixel_or_native_dtype_cases_first_image_channels_container_geometry():
    success=errors=0
    for batch,channels,dtype,container in itertools.product((1,3),(1,3,4),
            (torch.float16,torch.bfloat16,torch.float32,torch.float64),("list","numpy","tensor")):
        image=(torch.arange(batch*18*24*channels).reshape(batch,18,24,channels)%300).to(dtype)/255
        points=[[-2.5,3.5],[7.75,8.25],[27.,19.]]
        if container=="numpy":points=np.array(points,dtype=np.float32)
        elif container=="tensor":points=torch.tensor(points)
        embeds={"landmarks":points,"ip_x":torch.ones(1,2,3)};before=image.clone()
        try:old=source().draw(embeds,image)
        except Exception as error:
            with pytest.raises(type(error)) as new:candidate().execute(embeds,image)
            assert str(new.value)==str(error);errors+=1
        else:
            equal(old,candidate().execute(embeds,image).result)
            assert old[0].shape==(1,18,24,channels) and old[0].dtype==torch.float32;success+=1
        assert torch.equal(image,before)
    assert success+errors==72 and success>0 and errors>0


@pytest.mark.parametrize("case",["no_landmarks","empty_images","short_point","missing_image","requires_grad"])
def test_native_malformed_cases(case):
    embeds={"landmarks":[[3,4]]};image=torch.ones(1,20,24,3)
    if case=="no_landmarks":embeds={"ip_x":torch.ones(1,2,3),"ip_x_uncond":torch.zeros(1,2,3)}
    if case=="empty_images":image=torch.empty(0,20,24,3)
    if case=="short_point":embeds["landmarks"]=[[2]]
    if case=="missing_image":image=None
    if case=="requires_grad":image.requires_grad_(True)
    with pytest.raises(Exception) as old:source().draw(embeds,image)
    with pytest.raises(type(old.value)) as new:candidate().execute(embeds,image)
    assert str(old.value)==str(new.value)


def test_no_points_noncontiguous_image_and_int_quantization():
    for dtype in (torch.uint8,torch.int16,torch.float32):
        image=torch.arange(2*9*11*3).reshape(2,9,11,3).to(dtype).transpose(1,2)
        for points in ([],[[2,3]]):
            try:old=source().draw({"landmarks":points},image)
            except Exception as error:
                with pytest.raises(type(error)) as new:candidate().execute({"landmarks":points},image)
                assert str(new.value)==str(error)
            else:equal(old,candidate().execute({"landmarks":points},image).result)


def test_bounds_before_cv2_or_array_materialization(monkeypatch):
    cls=candidate();module=sys.modules[cls.__module__]
    def forbidden(*a,**kw):raise AssertionError("draw must not run")
    monkeypatch.setattr(module.cv2,"circle",forbidden)
    for points,match in (([[float("nan"),1]],"finite"),([[1000001,2]],"bounded"),([[1,2]]*513,"512points")):
        with pytest.raises(ValueError,match=match):cls.execute({"landmarks":points},torch.ones(1,2,3,3))
    # Input remains a meta descriptor; no excessive physical raster allocation.
    with pytest.raises(ValueError,match="CPU image"):cls.execute({"landmarks":[[1,2]]},torch.empty((1,1024,1024,3),device="meta"))
    with pytest.raises(ValueError,match="projected"):cls.execute({"landmarks":[[1,2]]},torch.zeros(1,768,768,3))


def test_actual_outer_image_layout_fresh_guests_raw_denial_and_missing_landmarks(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required");monkeypatch.syspath_prepend(CORE)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index in range(2):
                snapshot=PACK.parent
                if index:
                    snapshot=tmp_path/"snapshot";shutil.copytree(V2,snapshot/PACK.name/"v2")
                mapping=packdb.load_pack(snapshot,mount_name="custom_nodes.arcface_"+str(index)).node_mappings
                cls=mapping[ID];consumer=mapping["WanVideoUniAnimatePoseInput"]
                session=await GuestSession("wan-arcface-raster",guest_runtime_root=snapshot/PACK.name/"v2").start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        assert plan.permissions==("raw",)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="arcface-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for points in ([],np.array([[3.5,4.25],[9,8]],dtype=np.float32)):
                        args=dict(lynx_face_embeds={"landmarks":points},image=torch.arange(3*18*24*3).reshape(3,18,24,3).float()/255)
                        fields,missing,meta=execution.get_input_data(args,cls,"raster",None);assert not missing
                        rendered=await execution._async_map_node_over_list(prompt_id="arcface",unique_id="raster",obj=cls,input_data_all=fields,func="execute",v3_data=meta)
                        expected=source().draw(**args);equal(expected,rendered[0].result)
                        assert rendered[0].result[0].shape==(1,18,24,3)
                        ca=dict(pose_images=rendered[0].result[0],strength=1.,start_percent=0.,end_percent=1.)
                        fields,missing,meta=execution.get_input_data(ca,consumer,"layout",None);assert not missing
                        composed=await execution._async_map_node_over_list(prompt_id="arcface",unique_id="layout",obj=consumer,input_data_all=fields,func="execute",v3_data=meta)
                        torch.testing.assert_close(composed[0].result[0]["pose"],expected[0].permute(3,0,1,2).unsqueeze(0),rtol=0,atol=0)
                        refs=_sdk.InProcessRefResolver();plan=_sdk.ExecutionPlan(prompt_id="denied",node_id="raster",node_type=ID,node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,args),input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match="raw"):await session.execute(plan,runtime,capabilities=(),tenant="arcface-"+str(index))
                    # Pinned producer's declared ip_x/ip_x_uncond fields do not
                    # contain landmarks. Preserve failure, don't synthesize them.
                    args=dict(lynx_face_embeds={"ip_x":torch.ones(1,2,3),"ip_x_uncond":torch.zeros(1,2,3)},image=torch.zeros(1,18,24,3))
                    fields,missing,meta=execution.get_input_data(args,cls,"missing",None);assert not missing
                    with pytest.raises(Exception,match="landmarks"):await execution._async_map_node_over_list(prompt_id="arcface",unique_id="missing",obj=cls,input_data_all=fields,func="execute",v3_data=meta)
                    pids.append(session.pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
