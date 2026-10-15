"""CPU camera raster consumer proof; not ReCam inference/physical profile."""
import ast
import asyncio
import copy
import importlib
import importlib.util
import io as bytes_io
import os
from pathlib import Path
import shutil
import sys
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import pytest
import torch

sys.dont_write_bytecode=True
V2=Path(__file__).resolve().parents[1];PACK=V2.parent
CORE="/Users/ben/comfy/ComfyUI-secure-nodes"
sys.path[:0]=[CORE,"/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
os.environ.setdefault("COMFY_CORE_ROOT",CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes import packdb
ID="ReCamMasterPoseVisualizer"


def module(root=V2):
    name="_wan_recam_raster_"+str(id(root))
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    pkg=importlib.util.module_from_spec(spec);sys.modules[name]=pkg;spec.loader.exec_module(pkg)
    return importlib.import_module(name+".secure_recam_raster_nodes")


def source():
    tree=ast.parse((PACK/"recammaster/nodes.py").read_text())
    parts=[n for n in tree.body if getattr(n,"name",None) in ("get_c2w",ID)]
    ns=dict(np=np,io=bytes_io,Image=Image)
    exec(compile(ast.Module(body=parts,type_ignores=[]),str(PACK/"recammaster/nodes.py"),"exec"),ns)
    return ns[ID]


def reference(**args):
    value=source()()
    try:
        with mpl.rc_context():
            return value.plot(**args)[0]
    finally:
        if hasattr(value,"fig"):
            plt.close(value.fig)


def poses(count=3,rows=4):
    result=[]
    for i in range(count):
        angle=i*.2
        m=np.array([[np.cos(angle),-np.sin(angle),0,i*.3],
                    [np.sin(angle),np.cos(angle),0,0],[0,0,1,i*.1],[0,0,0,1]],dtype=np.float64)
        result.append(m[:rows])
    return np.stack(result)


def assert_same(expected,actual):
    assert expected.shape==actual.shape and expected.dtype==actual.dtype==torch.float32
    torch.testing.assert_close(expected,actual,rtol=0,atol=0,equal_nan=True)


def test_exact_schema_and_required_camera_surface():
    old=source();cls=module().ReCamMasterPoseVisualizer;schema=cls.GET_SCHEMA()
    assert schema.node_id==ID and schema.display_name=="ReCamMaster Pose Visualizer" and schema.category==old.CATEGORY
    assert schema.description==old.DESCRIPTION
    specs=old.INPUT_TYPES()["required"]
    assert [x.id for x in schema.inputs]==list(specs)
    for field,(name,spec) in zip(schema.inputs,specs.items()):
        assert field.io_type==spec[0] and not field.optional
        for key,value in spec[1].items() if len(spec)>1 else ():
            assert getattr(field,key)==value
    assert schema.outputs[0].io_type==old.RETURN_TYPES[0] and schema.outputs[0].display_name is None
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS==("raw",)


def test_pixel_exact_12_cases_and_scoped_cleanup():
    mod=module();cls=mod.ReCamMasterPoseVisualizer
    before_color=mpl.rcParams["text.color"];before_figures=plt.get_fignums()
    total=0
    for count in (1,3):
        for rows in (3,4):
            for base,z,scale,arrow in ((.2,.3,1.,1.),(0.,0.,.1,0.),(1.,.7,3.,2.)):
                cameras=poses(count,rows);before=cameras.copy()
                args=dict(camera_poses=cameras,scale=scale,base_xval=base,zval=z,arrow_length=arrow)
                expected=reference(**args)
                actual=cls.execute(**args).result[0]
                assert_same(expected,actual)
                assert np.array_equal(cameras,before)
                assert mpl.rcParams["text.color"]==before_color and plt.get_fignums()==before_figures
                total+=1
    assert total==12


@pytest.mark.parametrize("camera", [
 np.empty((0,4,4)), np.zeros((1,4,4)), np.ones((1,2,4)),
 np.array([np.eye(4)],dtype=np.int64), None,
])
def test_native_malformed_camera_error(camera):
    args=dict(camera_poses=camera,scale=1.,base_xval=.2,zval=.3,arrow_length=1.)
    with pytest.raises(Exception) as expected:
        reference(**copy.deepcopy(args))
    with pytest.raises(type(expected.value)) as actual:
        module().ReCamMasterPoseVisualizer.execute(**copy.deepcopy(args))
    assert str(actual.value)==str(expected.value)


def test_preallocation_limits_no_figure_created(monkeypatch):
    mod=module()
    monkeypatch.setattr(mod,"Figure",lambda *a,**k:pytest.fail("Figure allocated before guard"))
    for args in (
      dict(camera_poses=poses(513),scale=1.,base_xval=.2,zval=.3,arrow_length=1.),
      dict(camera_poses=poses(),scale=1.,base_xval=.2,zval=.3,arrow_length=101.),
      dict(camera_poses=poses(),scale=float("nan"),base_xval=.2,zval=.3,arrow_length=1.),
    ):
        with pytest.raises(ValueError):
            mod.ReCamMasterPoseVisualizer.execute(**args)
    with mpl.rc_context({"figure.dpi":200}):
        with pytest.raises(ValueError,match="64MiB"):
            mod.ReCamMasterPoseVisualizer.execute(poses(),1.,.2,.3,1.)


def test_actual_guest_outer_image_native_orbit_chain_and_raw_denial(tmp_path,monkeypatch):
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE","required");monkeypatch.syspath_prepend(CORE)
    fresh=tmp_path/"fresh-render";shutil.copytree(V2,fresh)
    async def run():
        import execution
        previous=_sdk.providers.execution_backend;pids=[]
        try:
            for index,root in enumerate((V2,fresh)):
                snapshot=PACK.parent if index==0 else tmp_path/"snapshot"
                if index:
                    mounted=snapshot/PACK.name
                    mounted.mkdir(parents=True)
                    shutil.copytree(root,mounted/"v2")
                    root=mounted/"v2"
                mappings=packdb.load_pack(snapshot,mount_name="custom_nodes.wan_recam_raster_outer_"+str(index)).node_mappings
                cls=mappings[ID]
                producer=mappings["WanVideoReCamMasterGenerateOrbitCamera"]
                session=await GuestSession("wan-recam-raster",guest_runtime_root=root).start()
                assert session.sandbox_kind=="seatbelt"
                class Backend:
                    async def dispatch(self,plan,local_call,runtime):
                        plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs,plan.input_types)
                        return await session.execute(plan,runtime,capabilities=("raw",),tenant="recam-raster-"+str(index))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    finalized,missing,data=execution.get_input_data(dict(degrees=45,num_frames=9),producer,"orbit",None)
                    assert not missing
                    produced=await execution._async_map_node_over_list(prompt_id="recam-raster",unique_id="orbit",
                        obj=producer,input_data_all=finalized,func="execute",v3_data=data)
                    cameras=produced[0].result[0]
                    assert isinstance(cameras,np.ndarray) and cameras.shape==(3,4,4)
                    for cam,arrow in ((cameras,1.),(cameras[:,:3,:],0.)):
                        args=dict(camera_poses=cam,scale=1.,base_xval=.2,zval=.3,arrow_length=arrow)
                        expected=reference(**args)
                        finalized,missing,data=execution.get_input_data(args,cls,"owner",None);assert not missing
                        result=await execution._async_map_node_over_list(prompt_id="recam-raster",unique_id="owner",
                            obj=cls,input_data_all=finalized,func="execute",v3_data=data)
                        assert_same(expected,result[0].result[0])
                        assert cls.GET_SCHEMA().outputs[0].io_type=="IMAGE"
                        refs=_sdk.InProcessRefResolver()
                        plan=_sdk.ExecutionPlan(prompt_id="denied",node_id="owner",node_type=ID,node_module=cls.__module__,
                            inputs=await _sdk.wrap_inputs(refs,args),input_mode="values",permissions=("raw",),tier="sandbox")
                        runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                        with pytest.raises(Exception,match="raw"):
                            await session.execute(plan,runtime,capabilities=(),tenant="recam-raster-"+str(index))
                    pids.append(session.pid)
                finally:
                    await session.kill()
            assert len(set(pids))==2 and os.getpid() not in pids
        finally:
            _sdk.providers.register_execution_backend(previous)
    asyncio.run(run())
