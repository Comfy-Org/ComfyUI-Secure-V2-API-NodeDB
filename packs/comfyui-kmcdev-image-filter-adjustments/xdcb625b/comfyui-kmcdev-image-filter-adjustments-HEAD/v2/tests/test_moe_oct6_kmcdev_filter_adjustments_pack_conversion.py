from __future__ import annotations
import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
CORE = Path("/Users/ben/comfy/ComfyUI-secure-nodes")
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
sys.path.insert(0,str(BACKEND))
sys.path.insert(0,str(CORE))
sys.path.append("/Users/ben/comfy/ComfyUI")
os.environ["COMFY_CORE_ROOT"] = str(CORE)
import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

PIN = "dcb625b4f9b5b8501016eea8319bfbb02502e99c"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = PACK_DB/"patches/comfyui-kmcdev-image-filter-adjustments/xdcb625b/comfyui-kmcdev-image-filter-adjustments-xdcb625b"
IDS = ("ImageFilterAdjustments","ImageBlankAlpha","ImageBlendMask","ImageMixColorByMask")
PINNED_BLOBS = json.loads('''{
  ".github/workflows/publish.yml": "bdbd27d676f6355c194096729b21b53dbe09bf0a0c4986ebcad28180159301d8",
  ".gitignore": "ecfd4cc5b0851d1212faa15df4bc59d1a14ffcc390fc859e3b5c9864a0027f8d",
  "LICENSE": "5990b9838fce2b3d3b9cc368e2bd2b4bb14adb4831800eadfc8cf59eb7e79d0f",
  "NOTICE": "2b70f4f10caf0fedfa03102477fcf1f5089bc97e714a47cd44bc9f5d92222e6c",
  "README.md": "27938fe7ed023ab9d8c11484abf247b648cd4b4548df4535c177405d4cf0aeea",
  "__init__.py": "4591dc35436f38f84346f4934b962060b4d8c93ab309179b741dd53bbe319595",
  "image_filter_adjustments_node.py": "1619ff87eb6df4af4afd918c94420a8bded078f1e91bdc1dd19179dd6d850593",
  "image_processor.py": "7cefb3b3dae1a61543006f269cc075fef0a7cd591b7d09755480a6de36ec6a4a",
  "pyproject.toml": "f391b8d64ca9b4bbcea239a1f795a341a68459f92404ade62a7e6633087d3c2a",
  "requirements.txt": "c5ca2d0d8592571b2dbd8e52d248c9d4397e459e1d6e22c2802dec30fc42df5a",
  "utils/__init__.py": "5cf2be2deaf68a65c926ab5386cba6ef0a7811673102c3010fc05fb4e5246667",
  "utils/image_utils.py": "0b9d439cda6ef4da3ee757b5730a3c5c45104a5efdc6f2ecc8c0b0f6590e578c",
  "utils/torch_utils.py": "3b41566b560bcba6ccbef3d385c0474fad0abfa3b5424f3e8fb1b60eb7f3266b"
}''')


def _load(name,root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name+"."):
            sys.modules.pop(key)
    spec=importlib.util.spec_from_file_location(name,root/"__init__.py",submodule_search_locations=[str(root)])
    package=importlib.util.module_from_spec(spec)
    sys.modules[name]=package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _load("_moe_kmc_secure",V2)


def _old(tmp_path):
    root=tmp_path/"pristine"
    if not root.exists():
        shutil.copytree(PACK,root,ignore=shutil.ignore_patterns("v2"))
    return _load("_moe_kmc_pristine",root)


def _manifest():
    return {"format":FORMAT,"nodes":{name:{
        "module":"nodes","class":name,"sdk_refs":False,"permissions":["raw"],
        "methods":{m:False for m in ("check_lazy_status","fingerprint_inputs","validate_inputs")},
        "schema":encode_schema(copy.deepcopy(cls.GET_SCHEMA()))}
        for name,cls in _secure().NODE_CLASS_MAPPINGS.items()},"runtime":manifest_declaration(V2)}


def _image(batch=1,channels=3,dtype=torch.float32):
    return torch.linspace(.01,.99,batch*9*13*channels,dtype=dtype).reshape(batch,9,13,channels).transpose(1,2)


def _filter(image,**options):
    return dict(image=image,brightness=0.,contrast=1.,saturation=1.,sharpness=1.,
                blur=0,gaussian_blur=0.,edge_enhance=0.,detail_enhance="false") | options


def _case(node_id):
    if node_id == "ImageFilterAdjustments":
        return _filter(_image(2),brightness=.2,contrast=.7,saturation=.6,sharpness=2.,blur=1,
                       gaussian_blur=.5,edge_enhance=.3,detail_enhance="true")
    if node_id == "ImageBlankAlpha":
        return dict(width=35,height=19,red=11,green=80,blue=222,alpha=137)
    if node_id == "ImageBlendMask":
        return dict(image_a=_image(),image_b=1-_image(),mask=_image(channels=4),blend_percentage=.37)
    return dict(image=_image(2),r=25,g=240,b=117,mask=torch.linspace(0,1,13*9).reshape(1,13,9))


def _run_old(old,node_id,inputs):
    cls=old.NODE_CLASS_MAPPINGS[node_id]
    return getattr(cls(),cls.FUNCTION)(**inputs)[0]


def test_exact_all_node_census_schemas_ast_and_helper_bytes(tmp_path):
    old,new=_old(tmp_path),_secure()
    assert tuple(old.NODE_CLASS_MAPPINGS) == tuple(new.NODE_CLASS_MAPPINGS) == IDS
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    for name in IDS:
        cls=old.NODE_CLASS_MAPPINGS[name]
        schema=new.NODE_CLASS_MAPPINGS[name].GET_SCHEMA()
        schema.validate()
        assert schema.node_id==name and schema.display_name==old.NODE_DISPLAY_NAME_MAPPINGS[name]
        assert schema.category==cls.CATEGORY
        spec=cls.INPUT_TYPES()["required"]
        assert [i.id for i in schema.inputs]==list(spec)
        for item in schema.inputs:
            kind=spec[item.id][0]
            assert item.io_type==("COMBO" if isinstance(kind,list) else kind)
            if isinstance(kind,list):
                assert item.options==kind
            else:
                for key,value in (spec[item.id][1] if len(spec[item.id])>1 else {}).items():
                    assert getattr(item,key)==value
        assert [o.io_type for o in schema.outputs]==list(cls.RETURN_TYPES)==["IMAGE"]
    for filename in ("image_processor.py","image_filter_adjustments_node.py"):
        a,b=ast.parse((PACK/filename).read_text()),ast.parse((V2/filename).read_text())
        assert [ast.dump(n) for n in a.body if isinstance(n,ast.ClassDef)] == [ast.dump(n) for n in b.body if isinstance(n,ast.ClassDef)]
    assert (V2/"utils/image_utils.py").read_bytes()==(PACK/"utils/image_utils.py").read_bytes()
    assert not hasattr(old,"WEB_DIRECTORY") and not hasattr(new,"WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js")) and not list(PACK.rglob("*.mjs"))
    loaded=packdb.load_pack(SNAPSHOT,mount_name="custom_nodes.moe_kmc_census")
    assert set(loaded.node_mappings)==set(IDS) and not loaded.routes and not loaded.frontend_permissions


FILTER_CASES=[
    {},{"brightness":.2},{"brightness":-.3},{"contrast":0.},{"contrast":2.},
    {"saturation":0.},{"saturation":3.},{"sharpness":-2.},{"sharpness":4.},
    {"blur":2},{"gaussian_blur":1.2},{"edge_enhance":.37},{"detail_enhance":"true"},
    {"brightness":-.1,"contrast":1.4,"saturation":.2,"sharpness":2.,"blur":1,
     "gaussian_blur":.8,"edge_enhance":.5,"detail_enhance":"true"}]


@pytest.mark.parametrize("options",FILTER_CASES)
@pytest.mark.parametrize("batch",[1,2])
@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64])
def test_filter_every_control_combination_batch_path_pixel_parity(tmp_path,options,batch,dtype):
    old=_old(tmp_path)
    image=_image(batch=batch,dtype=dtype)
    before=image.clone()
    inputs=_filter(image,**options)
    expected=_run_old(old,"ImageFilterAdjustments",inputs)
    actual=_secure().NODE_CLASS_MAPPINGS["ImageFilterAdjustments"].execute(**inputs).result[0]
    assert torch.equal(expected,actual) and expected.dtype==actual.dtype
    assert torch.equal(image,before)
    if batch==1 and not options:
        assert actual is image


@pytest.mark.parametrize("channels",[1,2,4])
def test_filters_other_channel_modes_and_single_axis_geometry(tmp_path,channels):
    old=_old(tmp_path)
    for image in (_image(channels=channels),torch.ones(1,1,7,channels)):
        inputs=_filter(image,saturation=.5)
        try:
            expected=_run_old(old,"ImageFilterAdjustments",inputs)
        except Exception as exc:
            with pytest.raises(type(exc)):
                _secure().NODE_CLASS_MAPPINGS["ImageFilterAdjustments"].execute(**inputs)
        else:
            assert torch.equal(_secure().NODE_CLASS_MAPPINGS["ImageFilterAdjustments"].execute(**inputs).result[0],expected)


@pytest.mark.parametrize("values",[(8,8,0,0,0,0),(35,19,11,80,222,137),(64,80,255,255,255,255)])
def test_blank_alpha_floor_to_eight_rgba_quantization(tmp_path,values):
    inputs=dict(zip(("width","height","red","green","blue","alpha"),values))
    expected=_run_old(_old(tmp_path),"ImageBlankAlpha",inputs)
    actual=_secure().NODE_CLASS_MAPPINGS["ImageBlankAlpha"].execute(**inputs).result[0]
    assert torch.equal(actual,expected)
    assert actual.shape==(1,values[1]//8*8,values[0]//8*8,4)


@pytest.mark.parametrize("channels",[1,3,4])
@pytest.mark.parametrize("percentage",[0.,.37,1.])
def test_blend_mask_image_socket_inversion_resize_rounding(tmp_path,channels,percentage):
    inputs=_case("ImageBlendMask")
    inputs["mask"]=_image(channels=channels)[:,:5,:7]
    inputs["blend_percentage"]=percentage
    expected=_run_old(_old(tmp_path),"ImageBlendMask",inputs)
    actual=_secure().NODE_CLASS_MAPPINGS["ImageBlendMask"].execute(**inputs).result[0]
    assert torch.equal(actual,expected)


@pytest.mark.parametrize("mask_batch",[1,2])
@pytest.mark.parametrize("dtype",[torch.float16,torch.float32,torch.float64])
def test_mix_fractional_mask_broadcast_dtype_and_input_isolation(tmp_path,mask_batch,dtype):
    inputs=_case("ImageMixColorByMask")
    inputs["image"]=inputs["image"].to(dtype)
    inputs["mask"]=inputs["mask"].to(dtype).repeat(mask_batch,1,1)
    before={k:v.clone() for k,v in inputs.items() if isinstance(v,torch.Tensor)}
    expected=_run_old(_old(tmp_path),"ImageMixColorByMask",inputs)
    actual=_secure().NODE_CLASS_MAPPINGS["ImageMixColorByMask"].execute(**inputs).result[0]
    assert torch.equal(actual,expected) and actual.dtype==expected.dtype
    for name,saved in before.items():
        assert torch.equal(inputs[name],saved)


@pytest.mark.parametrize("node_id,change",[
    ("ImageBlendMask",{"image_a":_image(2)}),
    ("ImageMixColorByMask",{"image":_image(channels=4)}),
    ("ImageMixColorByMask",{"mask":torch.ones(2,3)})])
def test_safe_native_malformed_shape_failures_not_fabricated(tmp_path,node_id,change):
    inputs=_case(node_id)|change
    with pytest.raises(Exception) as error:
        _run_old(_old(tmp_path),node_id,inputs)
    with pytest.raises(type(error.value)):
        _secure().NODE_CLASS_MAPPINGS[node_id].execute(**inputs)


def test_native_blend_mismatched_image_geometry_result_uses_second_image(tmp_path):
    for second in (torch.ones(1,2,2,3),torch.ones(1,19,17,4)):
        inputs=_case("ImageBlendMask")|{"image_b":second}
        expected=_run_old(_old(tmp_path),"ImageBlendMask",inputs)
        actual=_secure().NODE_CLASS_MAPPINGS["ImageBlendMask"].execute(**inputs).result[0]
        assert actual.shape==expected.shape==second.shape
        assert torch.equal(actual,expected)


def test_pinned_pristine_every_git_blob_byte_identity():
    assert set(PINNED_BLOBS) == {str(p.relative_to(PACK)) for p in PACK.rglob("*")
        if p.is_file() and "v2" not in p.relative_to(PACK).parts}
    for name,expected in PINNED_BLOBS.items():
        assert hashlib.sha256((PACK/name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("node_id,name,value",[
    ("ImageFilterAdjustments","brightness",float("nan")),("ImageFilterAdjustments","blur",True),
    ("ImageFilterAdjustments","gaussian_blur",1025.),("ImageFilterAdjustments","detail_enhance","TRUE"),
    ("ImageBlankAlpha","width",4097),("ImageBlankAlpha","alpha",-1),
    ("ImageBlendMask","blend_percentage",float("inf")),("ImageMixColorByMask","r",256),
    ("ImageMixColorByMask","image",torch.ones(65,2,2,3)),
    ("ImageBlendMask","mask",torch.ones(0,2,2,3))])
def test_invalid_controls_and_tensors_fail_closed(node_id,name,value):
    with pytest.raises((TypeError,ValueError)):
        _secure().NODE_CLASS_MAPPINGS[node_id].execute(**(_case(node_id)|{name:value}))


@pytest.mark.parametrize("node_id",IDS)
def test_preallocation_output_workspace_guard_rejection_before_algorithm(monkeypatch,node_id):
    package=_secure()
    cls=package.NODE_CLASS_MAPPINGS[node_id]
    nodes=sys.modules[cls.__module__]
    monkeypatch.setattr(nodes,"MAX_ELEMENTS",1)
    algorithms={"ImageFilterAdjustments":nodes.Filters,"ImageBlankAlpha":nodes.Blank,
                "ImageBlendMask":nodes.Blend,"ImageMixColorByMask":nodes.Mix}
    method={"ImageFilterAdjustments":"apply_filters","ImageBlankAlpha":"blank_image_alpha",
            "ImageBlendMask":"image_blend_mask","ImageMixColorByMask":"mix"}[node_id]
    called=[]
    monkeypatch.setattr(algorithms[node_id],method,lambda *a,**k:called.append(True))
    with pytest.raises(ValueError,match="bounded"):
        cls.execute(**_case(node_id))
    assert not called


def test_mask_broadcast_projected_allocation_and_aggregate_before_work(monkeypatch):
    package=_secure()
    nodes=sys.modules[package.NODE_CLASS_MAPPINGS["ImageMixColorByMask"].__module__]
    monkeypatch.setattr(nodes,"MAX_ELEMENTS",1000)
    inputs=dict(image=torch.empty(1,20,1,3,device="meta"),mask=torch.empty(1,1,20,device="meta"),r=0,g=0,b=0)
    with pytest.raises(ValueError,match="projected"):
        package.NODE_CLASS_MAPPINGS["ImageMixColorByMask"].execute(**inputs)
    monkeypatch.setattr(nodes,"MAX_AGGREGATE",1)
    with pytest.raises(ValueError,match="aggregate"):
        package.NODE_CLASS_MAPPINGS["ImageBlendMask"].execute(**_case("ImageBlendMask"))


def test_real_fresh_guests_all_four_nodes_raw_denial_and_outer_IMAGE(tmp_path):
    old=_old(tmp_path)
    fresh=tmp_path/"fresh-render"
    shutil.copytree(V2,fresh)
    async def run():
        pids=[]
        for index,root in enumerate((V2,fresh)):
            classes=_load("_moe_kmc_guest_"+str(index),root).NODE_CLASS_MAPPINGS
            refs=_sdk.InProcessRefResolver()
            session=await GuestSession("moe-kmc",guest_runtime_root=root).start()
            try:
                for node_id in IDS:
                    inputs=_case(node_id)
                    cls=classes[node_id]
                    expected=_run_old(old,node_id,inputs)
                    wrapped=await _sdk.wrap_inputs(refs,inputs)
                    plan=_sdk.ExecutionPlan(prompt_id="moe-kmc",node_id=node_id,node_type=cls.__name__,tier="sandbox",
                        node_module=cls.__module__,inputs=wrapped,input_mode="values",permissions=("raw",),method="execute")
                    runtime=_sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result=await session.execute(plan,runtime,capabilities=("raw",))
                    assert isinstance(result.result[0],_sdk.ImageRef)
                    assert torch.equal(await refs.resolve(result.result[0]),expected)
                    with pytest.raises(Exception,match="raw"):
                        await session.execute(plan,runtime,capabilities=())
                cls=classes["ImageBlankAlpha"]
                plan.node_type=cls.__name__
                plan.node_module=cls.__module__
                plan.inputs=dict(width=4096,height=4096,red=0,green=0,blue=0,alpha=255)
                with pytest.raises(Exception,match="bounded"):
                    await session.execute(plan,runtime,capabilities=("raw",))
                pids.append(session.last_guest_pid)
                assert pids[-1] not in (None,os.getpid())
            finally:
                await session.kill()
        assert len(set(pids))==2
        loaded=packdb.load_pack(SNAPSHOT,mount_name="custom_nodes.moe_kmc_outer")
        previous=_sdk.providers.execution_backend
        class Backend:
            session=None
            async def dispatch(self,plan,local_call,runtime):
                if self.session is None:
                    self.session=await GuestSession("moe-kmc-outer",guest_runtime_root=V2).start()
                plan.inputs=await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                return await self.session.execute(plan,runtime,capabilities=("raw",))
        backend=Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            for node_id in IDS:
                node=loaded.node_mappings[node_id]
                assert tuple(node.RETURN_TYPES)==("IMAGE",)
                inputs=_case(node_id)
                result=await execution._async_map_node_over_list(prompt_id="moe-kmc-outer",unique_id=node_id,obj=node,
                    input_data_all={k:[v] for k,v in inputs.items()},func=node.FUNCTION,v3_data=None)
                assert len(result)==1 and isinstance(result[0].result[0],torch.Tensor)
                assert torch.equal(result[0].result[0],_run_old(old,node_id,inputs))
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session:
                await backend.session.kill()
    asyncio.run(run())


def test_manifest_contracts_license_and_no_ambient_authority():
    assert json.loads((V2/"secure-nodes.json").read_text())==_manifest()
    assert hashlib.sha256((V2/"comfy-api.d.ts").read_bytes()).hexdigest()==DTS_SHA
    assert hashlib.sha256((V2/"comfy-api.pyi").read_bytes()).hexdigest()==PYI_SHA
    for name in ("LICENSE","NOTICE"):
        assert (V2/name).read_bytes()==(PACK/name).read_bytes()
    text="\n".join(p.read_text() for p in V2.glob("*.py"))
    for forbidden in ("folder_paths","PromptServer","requests","subprocess","_from_raw","open(","manual_seed","sys.","os.","torchvision"):
        assert forbidden not in text
    ledger=(V2/"SECURE_CONVERSION.md").read_text()
    assert "<!-- secure-conversion-report-v1 -->" in ledger and PIN in ledger and "no durable state" in ledger


def test_patch_pair_exact_bytes_roundtrip_and_no_cache(tmp_path):
    manifest,diff=packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_bytes())==manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf8")==diff
    fresh=tmp_path/"comfyui-kmcdev-image-filter-adjustments/xdcb625b"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh,manifest,diff)
    packpatch.validate_tree(fresh/PACK.name/"v2",V2)
    assert not list(PACK.rglob("*.pyc")) and not list(PACK.rglob("__pycache__"))
