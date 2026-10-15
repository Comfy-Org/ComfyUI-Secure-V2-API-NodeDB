"""Pinned WanMove raster pixel parity; no track detector or model inference."""
import ast
import asyncio
import copy
import importlib.util
import itertools
import logging
import os
from pathlib import Path
import shutil
import sys
import numpy as np
from PIL import Image,ImageDraw
import pytest
import torch
import torchvision.transforms.functional as TF
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
CORE="/Users/ben/comfy/ComfyUI-secure-nodes"
sys.path[:0]=[CORE,"/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT",CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb
from comfy_secure_nodes.transport.host import GuestSession
ID="WanVideoWanDrawWanMoveTracks"


def candidate(root=V2):
    name="_wanmove_raster_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return pkg.NODE_CLASS_MAPPINGS[ID]


def source():
    tree=ast.parse((PACK/"WanMove/trajectory.py").read_text())
    helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ("draw_tracks_on_video","_draw_gradient_polyline_on_overlay")]
    cls=next(n for n in ast.parse((PACK/"WanMove/nodes.py").read_text()).body if getattr(n,"name",None)==ID)
    ns=dict(torch=torch,np=np,Image=Image,ImageDraw=ImageDraw,TF=TF,log=logging.getLogger("pinned-wanmove"))
    exec(compile(ast.Module(body=helpers+[cls],type_ignores=[]),str(PACK/"WanMove/nodes.py"),"exec"),ns)
    return ns[ID]()


def inputs(batch=1,count=6,motion=True,dtype=torch.float32):
    images=(torch.arange(batch*20*24*3).reshape(batch,20,24,3)%273).to(dtype)/255
    # Source quantizes with long(), cycles five colors and accepts off-canvas.
    tracks=torch.tensor([[[n*3-2+t*(2 if motion else 0)+.75,3+n+t*.7] for n in range(count)]
        for t in range(4)],dtype=torch.float32).reshape(4,count,2)
    visibility=torch.ones((4,count),dtype=torch.bool)
    if count:visibility[2,0]=False
    return dict(images=images,tracks={"track_path":tracks,"track_visibility":visibility})


def equal(old,new):
    assert len(old)==len(new)==1
    assert old[0].shape==new[0].shape and old[0].dtype==new[0].dtype
    torch.testing.assert_close(old[0],new[0],rtol=0,atol=0,equal_nan=True)


def test_exact_schema_and_gradient_math():
    old=source();cls=candidate();schema=cls.GET_SCHEMA()
    assert schema.node_id==ID and schema.display_name=="WanVideo Draw WanMove Tracks"
    specs=old.INPUT_TYPES();fields={**specs["required"],**specs["optional"]}
    assert [x.id for x in schema.inputs]==list(fields)
    for x in schema.inputs:
        item=fields[x.id];assert x.io_type==item[0] and x.optional==(x.id in specs["optional"])
        if len(item)>1:
            for k,v in item[1].items():assert getattr(x,k)==v
    assert tuple(x.io_type for x in schema.outputs)==old.RETURN_TYPES
    assert tuple(x.display_name for x in schema.outputs)==old.RETURN_NAMES
    assert schema.category==old.CATEGORY and cls.SDK_REFS is False and cls.SDK_PERMISSIONS==("raw",)
    for file in (PACK/"WanMove/trajectory.py",V2/"secure_wanmove_raster_nodes.py"):
        fn=next(n for n in ast.parse(file.read_text()).body if getattr(n,"name",None)=="_draw_gradient_polyline_on_overlay")
        if file==PACK/"WanMove/trajectory.py":expected=ast.dump(fn,include_attributes=False)
        else:assert expected==ast.dump(fn,include_attributes=False)


def test_75_pixel_cases_repeat_visibility_color_gradient_dtype_input_integrity():
    count=0
    for batch,numtracks,moving,opacity,dtype in itertools.product((1,4),(0,1,6),(False,True),(0.,.5,1.),(torch.float32,torch.float64)):
        args=inputs(batch,numtracks,moving,dtype);args.update(opacity=opacity,line_resolution=4,circle_size=2,line_width=3)
        before=copy.deepcopy(args)
        equal(source().execute(**args),candidate().execute(**args).result)
        assert torch.equal(args["images"],before["images"])
        for k in args["tracks"]:assert torch.equal(args["tracks"][k],before["tracks"][k])
        count+=1
    assert count==72
    # Quantized source behavior remains exact for two additional input dtypes.
    for dtype in (torch.float16,torch.bfloat16):
        args=inputs(dtype=dtype);equal(source().execute(**args),candidate().execute(**args).result)
    # Source repeats only floor(track_frames/image_frames), never pads to length4.
    args=inputs(batch=3);old=source().execute(**args);assert old[0].shape[0]==3
    equal(old,candidate().execute(**args).result)


def test_absent_tracks_passthrough_and_aliasing():
    for tracks in (None,{},{"unused":"state"}):
        args=dict(images=torch.arange(18).reshape(1,2,3,3).to(torch.float64),tracks=tracks)
        equal(source().execute(**args),candidate().execute(**args).result)
    image=torch.ones(1,2,3,3);new=candidate().execute(image,None).result[0]
    assert new is image


@pytest.mark.parametrize("case",["missing_visibility","short_visibility","short_tracks","empty_tracks","bad_image_channels","rank3_images"])
def test_native_malformed_errors(case):
    args=inputs()
    if case=="missing_visibility":del args["tracks"]["track_visibility"]
    if case=="short_visibility":args["tracks"]["track_visibility"]=torch.ones(1,6,dtype=torch.bool)
    if case=="short_tracks":args["images"]=torch.ones(3,20,24,3);args["tracks"]["track_path"]=args["tracks"]["track_path"][:2]
    if case=="empty_tracks":args["tracks"]["track_path"]=torch.empty(0,6,2)
    if case=="bad_image_channels":args["images"]=torch.ones(1,20,24,4)
    if case=="rank3_images":args["images"]=torch.ones(2,3,4)
    with pytest.raises(Exception) as old:source().execute(**copy.deepcopy(args))
    with pytest.raises(type(old.value)) as new:candidate().execute(**copy.deepcopy(args))
    assert str(old.value)==str(new.value)


def test_preallocation_and_step_bounds_no_renderer_call(monkeypatch):
    cls=candidate();module=sys.modules[cls.__module__]
    def forbidden(*a,**kw):raise AssertionError("renderer must not run")
    monkeypatch.setattr(module,"draw_tracks_on_video",forbidden)
    cases=[]
    args=inputs();args["tracks"]["track_path"][0,0,0]=float("nan");cases.append((args,"finite"))
    args=inputs();args["tracks"]["track_path"]=torch.full((4,6,2),-(2**63),dtype=torch.int64);cases.append((args,"bounded4096"))
    args=inputs();args["tracks"]["track_path"][::2,:,0]=-4000;args["tracks"]["track_path"][1::2,:,0]=4000;cases.append((args,"drawing work"))
    args=inputs();args["opacity"]=float("inf");cases.append((args,"opacity"))
    args=dict(images=torch.empty((4,1024,1024,3),device="meta"),tracks=None);cases.append((args,"CPU values"))
    # Fixed geometry refuses excessive output projection before scaling/repeating.
    args=dict(images=torch.zeros(1,1024,1024,3),tracks=None);cases.append((args,"projected raster"))
    for args,message in cases:
        with pytest.raises(ValueError,match=message):cls.execute(**args)


def test_overlay_and_result_images_closed_on_success_and_failure(monkeypatch):
    cls=candidate();closed=[];original=Image.Image.close
    def closing(self):
        closed.append(self);return original(self)
    monkeypatch.setattr(Image.Image,"close",closing)
    args=inputs();cls.execute(**args)
    # Four circle overlays+three line overlays+four returned frames.
    assert len(closed)==11
    closed.clear();args=inputs();args["tracks"]["track_visibility"]=torch.ones(1,6,dtype=torch.bool)
    with pytest.raises(IndexError):cls.execute(**args)
    assert len(closed)==3 # one returned frame, first overlay and failing overlay


def test_actual_outer_render_to_pose_two_fresh_guests_raw_denial(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required");monkeypatch.syspath_prepend(CORE)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index in range(2):
                snapshot=PACK.parent
                if index:
                    snapshot=tmp_path/"snapshot";shutil.copytree(V2,snapshot/PACK.name/"v2")
                mappings=packdb.load_pack(snapshot,mount_name="custom_nodes.wanmove_raster_"+str(index)).node_mappings
                cls=mappings[ID];pose=mappings["WanVideoUniAnimatePoseInput"]
                root=snapshot/PACK.name/"v2"
                session=await GuestSession("wanmove-raster",guest_runtime_root=root).start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        assert plan.permissions==("raw",)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="wanmove-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for args in (inputs(),dict(images=inputs()["images"],tracks={})):
                        expected=source().execute(**args)
                        fields,missing,meta=execution.get_input_data(args,cls,"raster",None);assert not missing
                        result=await execution._async_map_node_over_list(prompt_id="wanmove",unique_id="raster",obj=cls,input_data_all=fields,func="execute",v3_data=meta)
                        equal(expected,result[0].result)
                        assert cls.GET_SCHEMA().outputs[0].io_type=="IMAGE"
                        pose_args=dict(pose_images=result[0].result[0],strength=1.,start_percent=0.,end_percent=1.)
                        fields,missing,meta=execution.get_input_data(pose_args,pose,"pose",None);assert not missing
                        composed=await execution._async_map_node_over_list(prompt_id="wanmove",unique_id="pose",obj=pose,input_data_all=fields,func="execute",v3_data=meta)
                        torch.testing.assert_close(composed[0].result[0]["pose"],expected[0].permute(3,0,1,2).unsqueeze(0).contiguous(),rtol=0,atol=0)
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id="denied",node_id="raster",node_type=ID,node_module=cls.__module__,
                            inputs=await _sdk.wrap_inputs(refs,args),input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match="raw"):await session.execute(plan,runtime,capabilities=(),tenant="wanmove-"+str(index))
                    pids.append(session.pid)
                finally:await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:_sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
