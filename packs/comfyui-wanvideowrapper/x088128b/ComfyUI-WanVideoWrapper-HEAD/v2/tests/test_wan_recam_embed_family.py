"""Real camera producer→geometry consumer chaining, no learned ReCam model."""
import ast
import copy
import asyncio
import importlib.util
import math
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import pytest
import torch
sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
sys.path[:0]=["/Users/ben/comfy/ComfyUI-secure-nodes","/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT","/Users/ben/comfy/ComfyUI-secure-nodes")
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
ID="WanVideoReCamMasterCameraEmbed"

def candidate(root=V2):
    name="_wan_recam_embed_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return pkg

def original():
    path=PACK/"recammaster/nodes.py";tree=ast.parse(path.read_text())
    body=[x for x in tree.body if isinstance(x,ast.ClassDef) and x.name in ("Camera",ID)]
    ns={"np":np,"torch":torch,"math":math}
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path),"exec"),ns)
    return ns[ID]()

def values(frames=21,dtype=torch.float32):
    return {"samples":torch.arange(4*frames*3*5,dtype=dtype).reshape(1,4,frames,3,5)}

def same(a,b,wire=False):
    assert set(a)==set(b)=={"max_seq_len","target_shape","num_frames","recammaster"}
    assert a["max_seq_len"]==b["max_seq_len"] and a["num_frames"]==b["num_frames"]
    if wire:
        assert list(a["target_shape"])==b["target_shape"]
    else:
        assert type(a["target_shape"]) is torch.Size and type(b["target_shape"]) is torch.Size
        assert a["target_shape"]==b["target_shape"]
    assert set(a["recammaster"])==set(b["recammaster"])
    for key in a["recammaster"]:
        x,y=a["recammaster"][key],b["recammaster"][key]
        assert x.shape==y.shape and x.dtype==y.dtype
        torch.testing.assert_close(x,y,rtol=0,atol=0,equal_nan=True)

def test_camera_embed_exact_schema_and_relative_matrix_ast():
    pkg=candidate();cls=pkg.NODE_CLASS_MAPPINGS[ID];old=original()
    schema=cls.GET_SCHEMA();info=old.INPUT_TYPES()["required"]
    assert schema.node_id==ID and schema.category==old.CATEGORY and schema.description==old.DESCRIPTION
    assert [x.id for x in schema.inputs]==list(info)
    for item,(name,spec) in zip(schema.inputs,info.items()):
        assert item.id==name and item.io_type==spec[0]
        for key,value in (spec[1] if len(spec)>1 else {}).items(): assert getattr(item,key)==value
    assert [x.io_type for x in schema.outputs]==list(old.RETURN_TYPES)
    assert [x.display_name for x in schema.outputs]==list(old.RETURN_NAMES)
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==("raw",)
    source=ast.parse((PACK/"recammaster/nodes.py").read_text())
    target=ast.parse((V2/"secure_recam_camera_nodes.py").read_text())
    a=next(x for x in source.body if isinstance(x,ast.ClassDef) and x.name=="Camera")
    b=next(x for x in target.body if isinstance(x,ast.ClassDef) and x.name=="Camera")
    a.bases=[];assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
    a=next(x for x in source.body if isinstance(x,ast.ClassDef) and x.name==ID)
    b=next(x for x in target.body if isinstance(x,ast.ClassDef) and x.name==ID)
    old_fn=next(x for x in a.body if isinstance(x,ast.FunctionDef) and x.name=="get_relative_pose")
    new_fn=next(x for x in b.body if isinstance(x,ast.FunctionDef) and x.name=="get_relative_pose")
    new_fn.decorator_list=[];new_fn.args.args[0].arg="self"
    assert ast.dump(old_fn,include_attributes=False)==ast.dump(new_fn,include_attributes=False)

def test_geometry_source_aliases_stride_fields_and_sampler_sequence_arithmetic():
    pkg=candidate();cls=pkg.NODE_CLASS_MAPPINGS[ID];old=original()
    count=0
    for frames in (1,2,8,21):
        for dtype in (torch.float32,torch.float64,torch.bfloat16):
            for camera_kind in ("default","orbit"):
                latent=values(frames,dtype)
                if camera_kind=="default":
                    poses=pkg.NODE_CLASS_MAPPINGS["WanVideoReCamMasterDefaultCamera"].execute("arc_left",latent).result[0]
                else:
                    poses=pkg.NODE_CLASS_MAPPINGS["WanVideoReCamMasterGenerateOrbitCamera"].execute(90,max(2,(frames-1)*4+1)).result[0]
                before=poses.copy();expected,back=old.process(poses,latent)
                actual,returned=cls.execute(poses,latent).result
                same(expected,actual)
                assert back is poses and returned is poses
                assert actual["recammaster"]["source_latents"].data_ptr()==latent["samples"].data_ptr()
                assert np.array_equal(poses,before)
                assert actual["recammaster"]["camera_embed"].dtype==torch.float32
                assert actual["recammaster"]["camera_embed"].shape==(len(poses),12)
                count+=1
    assert count==24
    # Source sampling consumer uses indexing/integer arithmetic, not Size APIs.
    source=ast.parse((PACK/"nodes_sampler.py").read_text())
    call=next(x.value for x in ast.walk(source) if isinstance(x,ast.Assign)
        and any(isinstance(y,ast.Name) and y.id=="noise" for y in x.targets)
        and isinstance(x.value,ast.Call) and isinstance(x.value.func,ast.Attribute)
        and x.value.func.attr=="randn" and "target_shape" in ast.dump(x.value))
    assert len(call.args)==4
    expression=ast.fix_missing_locations(ast.Expression(
        ast.Tuple(elts=copy.deepcopy(call.args[1:4]),ctx=ast.Load())))
    projection=compile(expression,str(PACK/"nodes_sampler.py"),"eval")
    for has_ref in (False,True):
        for is_5b in (False,True):
            expected=(21+int(has_ref),1 if is_5b else 3,2 if is_5b else 5)
            for shape in (torch.Size([4,21,3,5]),[4,21,3,5]):
                assert eval(projection,dict(target_shape=shape,has_ref=has_ref,is_5b=is_5b))==expected

def test_native_malformed_pose_rank_dtype_singular_and_latent_errors():
    cls=candidate().NODE_CLASS_MAPPINGS[ID];old=original()
    poses=np.stack([np.eye(4),np.eye(4)])
    cases=[(poses[:0],values()),(np.zeros((1,4,4)),values()),
           (np.ones((1,3,4)),values()),(poses.astype(np.int32),values()),
           (np.array(1.0),values()),(poses,{}),(poses,{"samples":torch.ones(2,4,1,2,3)})]
    for camera,latent in cases:
        outcomes=[]
        for call in (lambda:old.process(camera,latent),lambda:cls.execute(camera,latent)):
            try:call();outcomes.append(None)
            except Exception as error:outcomes.append((type(error).__name__,str(error)))
        assert outcomes[0] is not None and outcomes[0]==outcomes[1],outcomes

def test_projected_pose_and_latent_bounds_before_matrix_inverse(monkeypatch):
    cls=candidate().NODE_CLASS_MAPPINGS[ID];mod=sys.modules[cls.__module__]
    monkeypatch.setattr(mod.np.linalg,"inv",lambda *args:pytest.fail("must bound before inverse"))
    with pytest.raises(ValueError,match="1000"):cls.execute(np.tile(np.eye(4),(1001,1,1)),values())
    huge=torch.zeros(1,1,1,1,1).expand(1,4,3000000,1,1)
    with pytest.raises(ValueError,match="work"):cls.execute(np.stack([np.eye(4)]),{"samples":huge})
    with pytest.raises(ValueError,match="work"):cls.execute(torch.zeros(1,1,1).expand(1,3000000,4),values())
    with pytest.raises(ValueError,match="aggregate"):
        cls.execute([np.broadcast_to(np.eye(4),(1000000,4,4))],values())

def test_fresh_actual_outer_producer_consumer_chain_raw_denial_and_typed_payload(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required")
    monkeypatch.syspath_prepend("/Users/ben/comfy/ComfyUI-secure-nodes")
    fresh=tmp_path/"fresh-render";shutil.copytree(V2,fresh)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index,root in enumerate((V2,fresh)):
                pkg=candidate(root);session=await GuestSession("wan-recam-embed-chain",guest_runtime_root=root).start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="geometry-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                async def outer(cls,args):
                    finalized,missing,data=execution.get_input_data(args,cls,"owner",None);assert not missing
                    result=await execution._async_map_node_over_list(prompt_id="chain",unique_id="owner",
                        obj=cls,input_data_all=finalized,func="execute",v3_data=data)
                    return result[0].result
                try:
                    for kind in ("default","orbit"):
                        latent=values(21,torch.float64)
                        if kind=="default":
                            poses,=await outer(pkg.NODE_CLASS_MAPPINGS["WanVideoReCamMasterDefaultCamera"],
                                dict(camera_type="pan_left",latents=latent))
                        else:
                            poses,=await outer(pkg.NODE_CLASS_MAPPINGS["WanVideoReCamMasterGenerateOrbitCamera"],
                                dict(degrees=-180,num_frames=81))
                        cls=pkg.NODE_CLASS_MAPPINGS[ID]
                        expected,_=original().process(poses,latent)
                        payload,returned=await outer(cls,dict(camera_poses=poses,latents=latent))
                        assert [x.io_type for x in cls.GET_SCHEMA().outputs]==["WANVIDIMAGE_EMBEDS","CAMERAPOSES"]
                        same(expected,payload,wire=True)
                        assert type(returned) is np.ndarray and returned.dtype==poses.dtype
                        np.testing.assert_array_equal(poses,returned)
                        refs=_sdk.InProcessRefResolver()
                        args={"camera_poses":poses,"latents":latent}
                        plan=_sdk.ExecutionPlan(prompt_id="denied",node_id="owner",node_type=ID,
                            node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,args),
                            input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match="raw"):
                            await session.execute(plan,runtime,capabilities=(),tenant="geometry-"+str(index))
                    pids.append(session.last_guest_pid)
                finally:await session.kill()
        finally:_sdk.providers.register_execution_backend(previous)
        assert len(set(pids))==2 and os.getpid() not in pids
    asyncio.run(run())
