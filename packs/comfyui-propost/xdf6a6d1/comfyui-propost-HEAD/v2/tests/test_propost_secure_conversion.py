"""CPU differential, broker, actual guests/outer types and artifact gates."""
from __future__ import annotations
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import sys
import types
import ast

import pytest
import torch
import numpy as np

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
DB = SNAPSHOT.parents[2]
CORE = Path(os.environ.get("COMFY_CORE_ROOT","/Users/ben/comfy/ComfyUI-secure-nodes"))
sys.path[:0] = [str(CORE), "/Users/ben/comfy/ComfyUI_secure_nodes/backend"]
import execution
import folder_paths
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb,packpatch
from comfy_secure_nodes.packmanifest import FORMAT,encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession
from colour.io.luts.iridas_cube import read_LUT_IridasCube

IDS = ("ProPostVignette","ProPostFilmGrain","ProPostRadialBlur","ProPostDepthMapBlur","ProPostApplyLUT")
PAIR = DB/"patches/comfyui-propost/xdf6a6d1/comfyui-propost-xdf6a6d1"

def load(name,root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name+"."):
            del sys.modules[key]
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec)
    sys.modules[name]=package
    spec.loader.exec_module(package)
    return package

def secure():
    return load("_many_propost_secure",V2)

def old(tmp_path):
    root=tmp_path/"pristine"
    shutil.copytree(PACK,root,ignore=shutil.ignore_patterns("v2"))
    for key in tuple(sys.modules):
        if key=="filmgrainer" or key.startswith("filmgrainer."):
            del sys.modules[key]
    import tempfile
    previous_folder=sys.modules.get("folder_paths")
    previous_path=list(sys.path)
    previous_temp=tempfile.tempdir
    model_root=tmp_path/"models";model_root.mkdir()
    facade=types.ModuleType("folder_paths")
    facade.models_dir=str(model_root);facade.folder_names_and_paths={}
    facade.get_filename_list=lambda name:["identity.cube"]
    sys.modules["folder_paths"]=facade
    tempfile.tempdir=str(tmp_path)
    try:
        return load("_many_propost_pristine",root)
    finally:
        sys.path[:]=previous_path
        tempfile.tempdir=previous_temp
        if previous_folder is None:sys.modules.pop("folder_paths",None)
        else:sys.modules["folder_paths"]=previous_folder

def image(batch=2,dtype=torch.float32,channels=3):
    return torch.linspace(.01,.99,batch*7*11*channels,dtype=dtype).reshape(batch,7,11,channels)

def case(node_id):
    common=dict(image=image())
    if node_id=="ProPostVignette":
        return common|dict(intensity=.7,center_x=.3,center_y=.6)
    if node_id=="ProPostFilmGrain":
        return common|dict(gray_scale=False,grain_type="Fine",grain_sat=.5,grain_power=.7,shadows=.2,highs=.2,scale=1.,sharpen=0,src_gamma=1.,seed=37)
    if node_id=="ProPostRadialBlur":
        return common|dict(blur_strength=4.,center_x=.3,center_y=.6,focus_spread=1.,steps=3)
    if node_id=="ProPostDepthMapBlur":
        return common|dict(depth_map=1-image(),blur_strength=4.,focal_depth=.4,focus_spread=2.,steps=3,focal_range=.2,mask_blur=3)
    return common|dict(lut_name="identity.cube",strength=.7,log=False)

def cube(dim=3,domain=False):
    header="# bounded test cube\nTITLE \"example\"\n"
    if domain:header+="DOMAIN_MIN -1 -2 -3\nDOMAIN_MAX 2 3 4\n"
    if dim==1:
        return (header+"LUT_1D_SIZE 3\n-.2 0 .1\n.5 .3 .7\n1.2 1 1.1\n").encode()
    table=np.array([[r,g,b] for b in [0.,1.] for g in [0.,1.] for r in [0.,1.]])
    table=table*.8+.1
    return (header+"LUT_3D_SIZE 2\n"+"\n".join(" ".join(map(str,row)) for row in table)+"\n").encode()

def run_old(package,node_id,inputs):
    cls=package.NODE_CLASS_MAPPINGS[node_id]
    values=getattr(cls(),cls.FUNCTION)(**inputs)
    return (values,) if isinstance(values,torch.Tensor) else values

def run_new(node_id,inputs):
    return asyncio.run(secure().NODE_CLASS_MAPPINGS[node_id].execute(**inputs)).result

def compare(actual,expected):
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        assert a.shape==b.shape and a.dtype==b.dtype
        assert torch.equal(a,b) or torch.allclose(a,b,rtol=0,atol=0,equal_nan=True)

def manifest():
    nodes={}
    for name,cls in secure().NODE_CLASS_MAPPINGS.items():
        nodes[name]=dict(module="nodes",**{"class":name},sdk_refs=False,
            permissions=list(cls.SDK_PERMISSIONS),
            methods={m:False for m in ("validate_inputs","fingerprint_inputs","check_lazy_status")},
            schema=encode_schema(copy.deepcopy(cls.GET_SCHEMA())))
    return dict(format=FORMAT,runtime=manifest_declaration(V2),nodes=nodes)

def test_census_contract_and_compute_method_identity(tmp_path):
    pristine,new=old(tmp_path),secure()
    assert tuple(pristine.NODE_CLASS_MAPPINGS)==tuple(new.NODE_CLASS_MAPPINGS)==IDS
    for name in IDS:
        cls=pristine.NODE_CLASS_MAPPINGS[name];schema=new.NODE_CLASS_MAPPINGS[name].GET_SCHEMA()
        schema.validate()
        assert schema.node_id==name and schema.category==cls.CATEGORY
        assert [x.id for x in schema.inputs]==list(cls.INPUT_TYPES()["required"])
        assert [o.io_type for o in schema.outputs]==list(cls.RETURN_TYPES)
        for inp in schema.inputs:
            spec=cls.INPUT_TYPES()["required"][inp.id]
            if inp.id=="lut_name":
                assert inp.remote.route=="/secure-nodes/assets/input?kind=lut"
            else:
                if isinstance(spec[0],list):assert inp.options==spec[0]
                else:
                    for key,value in (spec[1] if len(spec)>1 else {}).items():
                        assert getattr(inp,key)==value
    a=ast.parse((PACK/"nodes.py").read_text())
    b=ast.parse((V2/"_algorithms.py").read_text())
    methods_a={c.name:{m.name:ast.dump(m) for m in c.body if isinstance(m,ast.FunctionDef)}
               for c in a.body if isinstance(c,ast.ClassDef)}
    methods_b={c.name:{m.name:ast.dump(m) for m in c.body if isinstance(m,ast.FunctionDef)}
               for c in b.body if isinstance(c,ast.ClassDef)}
    for name in IDS:
        for method,value in methods_a[name].items():
            if name=="ProPostApplyLUT" and method in ("INPUT_TYPES","lut_image"):continue
            assert methods_b[name][method]==value
    assert (PACK/"utils/processing.py").read_bytes()==(V2/"utils/processing.py").read_bytes()

@pytest.mark.parametrize("node_id",IDS[:4])
@pytest.mark.parametrize("dtype",[torch.float32,torch.float64])
def test_pixels_all_compute_nodes(tmp_path,node_id,dtype):
    pristine=old(tmp_path)
    inputs=case(node_id)
    for name in ("image","depth_map"):
        if name in inputs:inputs[name]=inputs[name].to(dtype)
    before=inputs["image"].clone()
    # Pinned cvtColor rejects RGB float64 depth maps. Preserve its native
    # failure instead of inventing a conversion result for that branch.
    if node_id == "ProPostDepthMapBlur" and dtype == torch.float64:
        import cv2
        with pytest.raises(cv2.error,match="Unsupported depth"):
            run_old(pristine,node_id,inputs)
        with pytest.raises(cv2.error,match="Unsupported depth"):
            run_new(node_id,inputs)
        return
    expected=run_old(pristine,node_id,inputs)
    compare(run_new(node_id,inputs),expected)
    assert torch.equal(before,inputs["image"])

@pytest.mark.parametrize("grain_type",["Fine","Fine Simple","Coarse","Coarser"])
@pytest.mark.parametrize("gray",[False,True])
@pytest.mark.parametrize("scale",[.75,1.,1.5])
def test_seeded_grain_modes_and_repeated_render_parity(tmp_path,grain_type,gray,scale):
    pristine=old(tmp_path)
    inputs=case("ProPostFilmGrain")|dict(grain_type=grain_type,gray_scale=gray,scale=scale,sharpen=1)
    expected=run_old(pristine,"ProPostFilmGrain",inputs)
    random.seed(1234);before=random.getstate()
    actual=run_new("ProPostFilmGrain",inputs)
    assert random.getstate()==before
    compare(actual,expected)
    compare(run_new("ProPostFilmGrain",inputs),expected)

@pytest.mark.parametrize("intensity",[0.,1.,2.])
@pytest.mark.parametrize("channels",[1,3,4])
def test_vignette_zero_container_and_alpha(tmp_path,intensity,channels):
    pristine=old(tmp_path)
    inputs=case("ProPostVignette")|dict(image=image(channels=channels),intensity=intensity)
    compare(run_new("ProPostVignette",inputs),run_old(pristine,"ProPostVignette",inputs))

@pytest.mark.parametrize("dim",[1,3])
@pytest.mark.parametrize("domain",[False,True])
@pytest.mark.parametrize("strength",[0.,.4,1.])
@pytest.mark.parametrize("log",[False,True])
def test_cube_parser_and_interpolation_real_colour_library(tmp_path,dim,domain,strength,log):
    payload=cube(dim,domain);file=tmp_path/"grade.cube";file.write_bytes(payload)
    package=secure();loading=sys.modules[package.NODE_CLASS_MAPPINGS["ProPostApplyLUT"].__module__.rsplit(".",1)[0]+".utils.loading"]
    expected=read_LUT_IridasCube(file)
    if expected.table.ndim==2:
        for i in range(3):expected.table[:,i]=np.clip(expected.table[:,i],expected.domain[0,i],expected.domain[1,i])
    else:
        for i in range(3):expected.table[:,:,:,i]=np.clip(expected.table[:,:,:,i],expected.domain[0,i],expected.domain[1,i])
    actual=loading.read_lut_bytes(payload,"grade")
    assert np.array_equal(actual.table,expected.table)
    assert np.array_equal(actual.domain,expected.domain)
    algo=sys.modules[package.NODE_CLASS_MAPPINGS["ProPostApplyLUT"].__module__].algorithms.ProPostApplyLUT()
    with np.errstate(invalid="ignore"):
        a=algo.apply_lut(image()[0].numpy(),actual,strength,log)
        b=algo.apply_lut(image()[0].numpy(),expected,strength,log)
    assert np.array_equal(a,b,equal_nan=True)

@pytest.mark.parametrize("node_id,name,value",[
    ("ProPostVignette","image",torch.empty(65,2,2,3)),
    ("ProPostFilmGrain","scale",1e-8),
    ("ProPostFilmGrain","sharpen",100000),
    ("ProPostRadialBlur","steps",100000),
    ("ProPostDepthMapBlur","mask_blur",999999),
    ("ProPostVignette","intensity",float("nan"))])
def test_resource_failures_before_compute(monkeypatch,node_id,name,value):
    package=secure();cls=package.NODE_CLASS_MAPPINGS[node_id]
    invoked=[]
    monkeypatch.setattr(cls.LEGACY,cls.LEGACY.FUNCTION,lambda *a,**k:invoked.append(True))
    with pytest.raises((ValueError,TypeError)):
        asyncio.run(cls.execute(**(case(node_id)|{name:value})))
    assert invoked==[]

def test_cube_malformed_and_oversized_fail_before_colour(monkeypatch):
    package=secure();module=sys.modules[package.NODE_CLASS_MAPPINGS["ProPostApplyLUT"].__module__]
    for data in [b"LUT_3D_SIZE 100000\n",b"LUT_1D_SIZE 3\nnan 0 1\n",b"DOMAIN_MIN 1 1 1\nDOMAIN_MAX 0 0 0\n",b"\xff"]:
        with pytest.raises((ValueError,UnicodeDecodeError)):
            module.read_lut_bytes(data,"bad")
    with pytest.raises(ValueError,match="byte"):
        module.read_lut_bytes(b" "*(8*1024*1024+1),"large")

def test_actual_guests_all_outputs_raw_and_asset_denial_and_outer(tmp_path,monkeypatch):
    pristine=old(tmp_path)
    assets=tmp_path/"input";assets.mkdir()
    (assets/"identity.cube").write_bytes(cube())
    # The authoritative managed root is injected in the trusted provider only.
    monkeypatch.setattr(folder_paths,"get_input_directory",lambda:str(assets))
    fresh=tmp_path/"fresh-render";shutil.copytree(V2,fresh)
    async def run():
        pids=[]
        for index,root in enumerate([V2,fresh]):
            package=load("_many_propost_guest_"+str(index),root)
            refs=_sdk.InProcessRefResolver()
            session=await GuestSession("many-propost",guest_runtime_root=root).start()
            try:
                for name in IDS:
                    cls=package.NODE_CLASS_MAPPINGS[name];inputs=case(name)
                    if name=="ProPostApplyLUT":
                        lut=read_LUT_IridasCube(assets/"identity.cube")
                        expected=(pristine.NODE_CLASS_MAPPINGS[name]().apply_lut(inputs["image"][0].numpy(),lut,inputs["strength"],False),)
                        expected=(torch.from_numpy(np.stack([pristine.NODE_CLASS_MAPPINGS[name]().apply_lut(x.numpy(),lut,inputs["strength"],False) for x in inputs["image"]])).to(inputs["image"].dtype),)
                    else:expected=run_old(pristine,name,inputs)
                    plan=_sdk.ExecutionPlan(prompt_id="many-propost",node_id=name,node_type=cls.__name__,
                        tier="sandbox",node_module=cls.__module__,inputs=await _sdk.wrap_inputs(refs,inputs),
                        input_mode="values",permissions=tuple(cls.SDK_PERMISSIONS),method="execute")
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result=await session.execute(plan,runtime,capabilities=plan.permissions)
                    compare([await refs.resolve(v) for v in result.result],expected)
                    with pytest.raises(Exception,match="raw"):
                        await session.execute(plan,runtime,capabilities=tuple(c for c in plan.permissions if c!="raw"))
                    if name=="ProPostApplyLUT":
                        with pytest.raises(Exception,match="assets"):
                            await session.execute(plan,runtime,capabilities=("raw",))
                        for logical in ("../identity.cube","/private.cube","absent.cube","escape\\path.cube"):
                            plan.inputs=await _sdk.wrap_inputs(refs,inputs|dict(lut_name=logical))
                            with pytest.raises(Exception):
                                await session.execute(plan,runtime,capabilities=plan.permissions)
                pids.append(session.last_guest_pid)
                assert pids[-1] not in (None,os.getpid())
            finally:await session.kill()
        assert len(set(pids))==2
        loaded=packdb.load_pack(SNAPSHOT,mount_name="custom_nodes.many_propost_outer")
        previous=_sdk.providers.execution_backend
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                if self.session is None:self.session=await GuestSession("many-propost-outer",guest_runtime_root=V2).start()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                return await self.session.execute(plan,runtime,capabilities=plan.permissions)
        backend=Backend();_sdk.providers.register_execution_backend(backend)
        try:
            for name in IDS:
                cls=loaded.node_mappings[name];inputs=case(name)
                result=await execution._async_map_node_over_list(prompt_id="many-propost-outer",unique_id=name,obj=cls,
                    input_data_all={k:[v] for k,v in inputs.items()},func=cls.FUNCTION,v3_data=None)
                assert len(result)==1
                assert len(result[0].result)==(2 if name=="ProPostDepthMapBlur" else 1)
                assert all(isinstance(v,torch.Tensor) for v in result[0].result)
                if name=="ProPostDepthMapBlur":
                    assert result[0].result[1].shape==(2,7,11)
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session:await backend.session.kill()
    asyncio.run(run())

def test_manifest_patch_pristine_and_no_ambient_cache(tmp_path):
    pinned=json.loads((V2/"tests/pristine-sha256.json").read_text())
    assert set(pinned)=={str(p.relative_to(PACK)) for p in PACK.rglob("*") if p.is_file() and "v2" not in p.relative_to(PACK).parts}
    for name,sha in pinned.items():
        assert hashlib.sha256((PACK/name).read_bytes()).hexdigest()==sha
    assert json.loads((V2/"secure-nodes.json").read_text())==manifest()
    for name in ["LICENSE","utils/processing.py"]:
        assert (V2/name).read_bytes()==(PACK/name).read_bytes()
    text="\n".join(p.read_text() for p in V2.rglob("*.py") if "tests" not in p.parts)
    for forbidden in ["folder_paths","sys.path","open(","os.","subprocess","mask.save","random.seed","saveToFile"]:
        assert forbidden not in text
    assert not list(PACK.rglob("__pycache__")) and not list(PACK.rglob("*.pyc"))
    metadata,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text())==metadata
    assert PAIR.with_suffix(".diff").read_text()==diff
    dest=tmp_path/"reconstruct"/"comfyui-propost"/"xdf6a6d1";dest.mkdir(parents=True)
    shutil.copytree(PACK,dest/PACK.name,ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(dest,metadata,diff)
    packpatch.validate_tree(dest/PACK.name/"v2",V2)
