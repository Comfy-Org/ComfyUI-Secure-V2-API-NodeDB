"""Pinned ReCam math/resource, raw guests and outer custom array; no models."""
import ast
import asyncio
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
sys.path[:0]=["/Users/ben/comfy/ComfyUI-secure-nodes",
              "/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT","/Users/ben/comfy/ComfyUI-secure-nodes")
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
IDS=("WanVideoReCamMasterDefaultCamera","WanVideoReCamMasterGenerateOrbitCamera")

def candidate(root=V2):
    name="_wan_recam_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return pkg

def original():
    path=PACK/"recammaster/nodes.py"
    body=[x for x in ast.parse(path.read_text()).body if (
        isinstance(x,ast.FunctionDef) and x.name=="parse_matrix" or
        isinstance(x,ast.ClassDef) and x.name in IDS)]
    ns={"np":np,"os":os,"script_directory":str(path.parent)}
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path),"exec"),ns)
    return ns

def same(a,b):
    assert type(a) is np.ndarray and type(b) is np.ndarray
    assert a.shape==b.shape and a.dtype==b.dtype
    np.testing.assert_array_equal(a,b)

def latents(frames=21,dtype=torch.float32):
    return {"samples":torch.arange(4*frames*2*3,dtype=dtype).reshape(1,4,frames,2,3)}

@pytest.mark.parametrize("node_id",IDS)
def test_exact_camera_schema_input_order_outputs_and_source_ast(node_id):
    cls=candidate().NODE_CLASS_MAPPINGS[node_id];old=original()[node_id]
    schema=cls.GET_SCHEMA()
    assert schema.node_id==node_id and schema.category==old.CATEGORY
    assert schema.description==old.DESCRIPTION
    assert [x.id for x in schema.inputs]==list(old.INPUT_TYPES()["required"])
    for field,(name,spec) in zip(schema.inputs,old.INPUT_TYPES()["required"].items()):
        assert field.id==name
        assert (field.options if isinstance(spec[0],list) else field.io_type)==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items():
            assert getattr(field,key)==value
    assert [x.io_type for x in schema.outputs]==list(old.RETURN_TYPES)
    assert [x.display_name for x in schema.outputs]==list(old.RETURN_NAMES)
    assert cls.SDK_PERMISSIONS==("raw",) and cls.SDK_REFS is False
    legacy=ast.parse((PACK/"recammaster/nodes.py").read_text())
    converted=ast.parse((V2/"secure_recam_camera_nodes.py").read_text())
    a=next(x for x in legacy.body if isinstance(x,ast.FunctionDef) and x.name=="parse_matrix")
    b=next(x for x in converted.body if isinstance(x,ast.FunctionDef) and x.name=="parse_matrix")
    assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
    if node_id==IDS[1]:
        cls_old=next(x for x in legacy.body if isinstance(x,ast.ClassDef) and x.name==node_id)
        fn=next(x for x in cls_old.body if isinstance(x,ast.FunctionDef) and x.name=="process")
        helper=next(x for x in converted.body if isinstance(x,ast.FunctionDef) and x.name=="_orbit")
        assert [ast.dump(x,include_attributes=False) for x in fn.body[:-1]]==[
            ast.dump(x,include_attributes=False) for x in helper.body[:-1]]

def test_all_ten_default_trajectories_latent_frame_sampling_and_dtype_independence():
    pkg=candidate();cls=pkg.NODE_CLASS_MAPPINGS[IDS[0]];old=original()[IDS[0]]()
    mod=sys.modules[cls.__module__]
    data=mod._camera_data()
    assert hashlib.sha256((PACK/"recammaster/recam_extrinsics.json").read_bytes()).hexdigest()==mod.RESOURCE_SHA256
    assert len(data)==81
    count=0
    for camera,T,dtype in itertools.product(mod.CAMERAS,(1,2,8,21),(torch.float32,torch.float64)):
        value=latents(T,dtype);before=value["samples"].clone()
        expected=old.process(camera,value)[0]
        actual=cls.execute(camera,value).result[0]
        same(expected,actual)
        assert actual.shape==(T,4,4) and actual.dtype==np.float64
        assert torch.equal(value["samples"],before)
        same(actual[0],mod.parse_matrix(data["frame0"][f"cam{mod.CAMERAS.index(camera)+1:02d}"]).T)
        count+=1
    assert count==80

def test_orbit_direction_endpoints_four_frame_stride_and_source_degenerate_cases():
    cls=candidate().NODE_CLASS_MAPPINGS[IDS[1]];old=original()[IDS[1]]()
    count=0
    for frames,degrees in itertools.product((2,4,5,81,1000),(-180,-90,0,90,180)):
        expected=old.process(degrees,frames)[0]
        actual=cls.execute(degrees,frames).result[0]
        same(expected,actual)
        assert actual.shape==((frames+3)//4,4,4)
        assert np.array_equal(actual[:,3,:],np.tile([0,0,0,1],(len(actual),1)))
        count+=1
    assert count==25
    for args in ({"num_frames":1,"degrees":90},{"num_frames":0,"degrees":90},
                 {"num_frames":-3,"degrees":90},{"num_frames":3.0,"degrees":90},
                 {"num_frames":3,"degrees":"bad"}):
        outcomes=[]
        for call in (lambda:old.process(**args),lambda:cls.execute(**args)):
            try:call();outcomes.append(None)
            except Exception as error:outcomes.append((type(error).__name__,str(error)))
        assert outcomes[0] is not None and outcomes[0]==outcomes[1],outcomes

def test_default_native_missing_frame_unknown_camera_rank_and_empty_errors():
    cls=candidate().NODE_CLASS_MAPPINGS[IDS[0]];old=original()[IDS[0]]()
    cases=[("pan_right",latents(22)),("unknown",latents()),("pan_right",latents(0)),
           ("pan_right",{}),("pan_right",{"samples":torch.ones(2,4,3,2,3)}),
           ("pan_right",{"samples":None})]
    for camera,value in cases:
        outcomes=[]
        for call in (lambda:old.process(camera,value),lambda:cls.execute(camera,value)):
            try:call();outcomes.append(None)
            except Exception as error:outcomes.append((type(error).__name__,str(error)))
        assert outcomes[0] is not None and outcomes[0]==outcomes[1],outcomes

def test_closed_resource_hash_size_symlink_and_projected_refusal_before_orbit(tmp_path,monkeypatch):
    pkg=candidate();cls=pkg.NODE_CLASS_MAPPINGS[IDS[0]]
    mod=sys.modules[cls.__module__]
    fake=tmp_path/"pack";(fake/"recammaster").mkdir(parents=True)
    monkeypatch.setattr(mod,"__file__",str(fake/"secure_recam_camera_nodes.py"))
    asset=fake/"recammaster/recam_extrinsics.json"
    source=(PACK/"recammaster/recam_extrinsics.json").read_bytes()
    asset.write_bytes(source);assert len(mod._camera_data())==81
    for bad in (b"{}",source+b"extra",b"x"+source[1:]):
        asset.write_bytes(bad)
        with pytest.raises(ValueError,match="size/hash"):mod._camera_data()
    asset.unlink();asset.symlink_to(PACK/"recammaster/recam_extrinsics.json")
    with pytest.raises(ValueError,match="in-pack"):mod._camera_data()
    orbit=pkg.NODE_CLASS_MAPPINGS[IDS[1]]
    monkeypatch.setattr(mod,"_orbit",lambda *args:pytest.fail("must bound before allocation"))
    with pytest.raises(ValueError,match="projected"):orbit.execute(90,1001)
    with pytest.raises(ValueError,match="finite"):orbit.execute(float("inf"),81)
    monkeypatch.setattr(mod,"_camera_data",lambda:pytest.fail("must bound input before resource/kernel work"))
    large=torch.zeros(1,1,1,1,1).expand(1,4,3000000,1,1)
    with pytest.raises(ValueError,match="work"):cls.execute("pan_right",{"samples":large})

def test_actual_fresh_guests_raw_denial_numpy_values_and_real_outer_camera_type(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required")
    fresh=tmp_path/"fresh-render";shutil.copytree(V2,fresh)
    cases=[(IDS[0],dict(camera_type="arc_left",latents=latents(21))),
           (IDS[0],dict(camera_type="zoom_in",latents=latents(2))),
           (IDS[1],dict(degrees=-90,num_frames=81)),(IDS[1],dict(degrees=180,num_frames=1000))]
    async def run():
        # Pytest prepends the legacy pack root during collection. Select the
        # actual core executor and its sibling modules, not pack latent_preview.
        monkeypatch.syspath_prepend("/Users/ben/comfy/ComfyUI-secure-nodes")
        import execution
        pids=[];previous=_sdk.providers.execution_backend
        try:
            for index,root in enumerate((V2,fresh)):
                pkg=candidate(root);session=await GuestSession("wan-recam-camera",guest_runtime_root=root).start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="camera-owner-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node_id,args in cases:
                        cls=pkg.NODE_CLASS_MAPPINGS[node_id]
                        expected=cls.execute(**args).result[0]
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id="camera",node_id="owner",node_type=node_id,
                            node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,args),
                            input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        result=await session.execute(plan,runtime,capabilities=("raw",),tenant="camera-owner-"+str(index))
                        actual=(await _sdk.unwrap_outputs(refs,result)).result[0];same(expected,actual)
                        with pytest.raises(Exception,match="raw"):
                            await session.execute(plan,runtime,capabilities=(),tenant="camera-owner-"+str(index))
                        inputs,missing,data=execution.get_input_data(args,cls,"1",None)
                        assert not missing
                        output=await execution._async_map_node_over_list(prompt_id="camera-outer",unique_id="1",
                            obj=cls,input_data_all=inputs,func="execute",v3_data=data)
                        assert cls.GET_SCHEMA().outputs[0].io_type=="CAMERAPOSES"
                        same(expected,output[0].result[0])
                    cls=pkg.NODE_CLASS_MAPPINGS[IDS[1]]
                    refs=_sdk.InProcessRefResolver()
                    plan=_sdk.ExecutionPlan(prompt_id="bad-camera",node_id="owner",node_type=IDS[1],
                        node_module=cls.__module__,inputs={"degrees":90,"num_frames":1},
                        input_mode="values",permissions=("raw",),tier="sandbox")
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    with pytest.raises(Exception,match="division by zero"):
                        await session.execute(plan,runtime,capabilities=("raw",),tenant="camera-owner-"+str(index))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())
