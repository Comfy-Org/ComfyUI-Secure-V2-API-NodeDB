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
import subprocess
import sys

import cv2
import pytest
import torch
from PIL import Image

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
CORE = Path("/Users/ben/comfy/ComfyUI-secure-nodes")
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(CORE))
sys.path.append("/Users/ben/comfy/ComfyUI")
os.environ["COMFY_CORE_ROOT"] = str(CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession
import execution

PIN = "007acb074a77b8472bd837704442e4056d9de7e7"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = PACK_DB / "patches/comfyui-mosaic-blur/x007acb0/comfyui-mosaic-blur-x007acb0"
PINNED_BLOBS = {
    ".github/workflows/publish.yml": "65c4c39abe1bc57b26182345a995203cd9ad3080cbed9982d033e52a8886d743",
    "README.md": "f68f2d34e39212e0958f711a6d2e1a5d96568f67664d938e3fb3961419c4a625",
    "__init__.py": "430099fb5c17b1187996afa3b06fca87d7a8d87629c32a82c88038dc50233013",
    "mosaicblur.py": "178760f072b92d63ee7e4cd1bea777ae1cba28ca10efb0c0bd2d2fc586dc1c3f",
    "pyproject.toml": "ae5f986687669a60244fabd754d76419c5be21ee899bfccd28b46bb9cafab2e7",
    "requirements.txt": "b10c1e3ae2f654328699b7af65aedd04eb8c73c21882c57ec68ff8bdb7c3a065",
}


def _load(name, root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py",
                                                 submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _load("_moe_mosaic_secure", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _load("_moe_mosaic_pristine", root)


def _manifest():
    cls = _secure().NODE_CLASS_MAPPINGS["ImageMosaic"]
    return {"format": FORMAT, "nodes": {"ImageMosaic": {
        "module": "nodes", "class": "ImageMosaic", "sdk_refs": False,
        "permissions": ["raw"],
        "methods": {name: False for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")},
        "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA()))
    }}, "runtime": manifest_declaration(V2)}


def _image(batch=2, channels=3, dtype=torch.float32, h=7, w=11):
    return torch.linspace(-.2, 1.2, batch * h * w * channels, dtype=dtype).reshape(batch,h,w,channels).transpose(1,2)


def test_pinned_pristine_every_git_blob_byte_identity():
    # Hashes extracted from all six tracked Git blobs of the immutable pin.
    assert set(PINNED_BLOBS) == {str(p.relative_to(PACK)) for p in PACK.rglob("*") if p.is_file() and "v2" not in p.relative_to(PACK).parts}
    for name, expected in PINNED_BLOBS.items():
        assert hashlib.sha256((PACK / name).read_bytes()).hexdigest() == expected


def test_actual_census_exact_schema_and_algorithm_ast(tmp_path):
    old = _pristine(tmp_path)
    new = _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {"ImageMosaic"}
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    schema = new.ImageMosaic.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "ImageMosaic" and schema.display_name == "Image Mosaic"
    assert schema.category == old.NODE_CLASS_MAPPINGS["ImageMosaic"].CATEGORY
    assert [i.id for i in schema.inputs] == ["images", "method", "block_size"]
    assert [i.io_type for i in schema.inputs] == ["IMAGE", "COMBO", "INT"]
    assert schema.inputs[1].options == ["pillow", "cv2"]
    assert (schema.inputs[2].default, schema.inputs[2].min, schema.inputs[2].max) == (10,1,100)
    assert [o.io_type for o in schema.outputs] == ["IMAGE"]
    assert not hasattr(old, "WEB_DIRECTORY") and not hasattr(new, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js")) and not list(PACK.rglob("*.mjs"))
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.moe_mosaic_census")
    assert set(loaded.node_mappings) == {"ImageMosaic"}
    assert not loaded.routes and not loaded.frontend_permissions
    a, b = ast.parse((PACK/"mosaicblur.py").read_text()), ast.parse((V2/"algorithms.py").read_text())
    for name in ("tensor2pil","pil2tensor","mosaic_blur_pillow","mosaic_blur_cv2"):
        left = next(n for n in a.body if isinstance(n, ast.FunctionDef) and n.name == name)
        right = next(n for n in b.body if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.dump(left) == ast.dump(right)
    cls = next(n for n in a.body if isinstance(n,ast.ClassDef))
    left = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name == "image_mosaic")
    right = next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name == "mosaic_images")
    assert [ast.dump(n) for n in left.body] == [ast.dump(n) for n in right.body]


@pytest.mark.parametrize("method", ["pillow","cv2"])
@pytest.mark.parametrize("channels", [3,4])
@pytest.mark.parametrize("dtype", [torch.float16,torch.float32,torch.float64])
@pytest.mark.parametrize("block_size", [1,3,6])
def test_pixel_exact_all_backends_channels_dtypes(tmp_path, method, channels, dtype, block_size):
    image = _image(channels=channels,dtype=dtype)
    before = image.clone()
    old = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageMosaic"]()
    expected = old.image_mosaic(image.clone(),method,block_size)[0]
    result = _secure().ImageMosaic.execute(image,method,block_size).result[0]
    assert torch.equal(expected,result)
    assert result.dtype == torch.float32 and result.device.type == "cpu"
    assert result.shape[-1] == (4 if method == "pillow" else channels)
    assert torch.equal(image,before) and result.data_ptr() != image.data_ptr()


def test_pillow_partial_edge_black_padding_rgba_quirk(tmp_path):
    img = torch.ones(1,5,5,3)
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageMosaic"]().image_mosaic(img,"pillow",4)[0]
    actual = _secure().ImageMosaic.execute(img,"pillow",4).result[0]
    assert torch.equal(actual,expected)
    assert torch.equal(actual[0,-1,-1],torch.zeros(4))
    assert torch.equal(actual[0,0,0],torch.ones(4))


@pytest.mark.parametrize("method,channels", [("pillow",1),("pillow",2),("cv2",2)])
def test_other_native_pillow_channel_modes(tmp_path,method,channels):
    image = _image(batch=1,channels=channels)
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageMosaic"]().image_mosaic(image,method,2)[0]
    actual = _secure().ImageMosaic.execute(image,method,2).result[0]
    assert torch.equal(actual,expected)


@pytest.mark.parametrize("method,shape,block", [
    ("cv2",(1,2,3,3),4),("cv2",(1,7,11,1),2),
    ("cv2",(1,1,7,4),1)])
def test_safe_native_failures_preserved(tmp_path,method,shape,block):
    image = torch.ones(shape)
    old = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageMosaic"]()
    with pytest.raises(Exception) as expected:
        old.image_mosaic(image.clone(),method,block)
    with pytest.raises(type(expected.value)):
        _secure().ImageMosaic.execute(image,method,block)


def test_pillow_single_axis_squeeze_geometry_quirk(tmp_path):
    image = torch.ones(1,1,7,3)
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageMosaic"]().image_mosaic(image,"pillow",2)[0]
    actual = _secure().ImageMosaic.execute(image,"pillow",2).result[0]
    assert actual.shape == expected.shape == (1,7,3,4)
    assert torch.equal(actual,expected)


@pytest.mark.parametrize("args", [
    (None,"pillow",1),(torch.ones(2,3,3),"pillow",1),
    (torch.ones(1,2,2,3,dtype=torch.int32),"pillow",1),
    (torch.ones(0,2,2,3),"pillow",1),(torch.ones(65,2,2,3),"pillow",1),
    (torch.ones(1,2,2,5),"pillow",1),(torch.ones(1,2,2,3),"bad",1),
    (torch.ones(1,2,2,3),"cv2",True),(torch.ones(1,2,2,3),"pillow",0),
    (torch.ones(1,2,2,3),"pillow",101),(torch.ones(1,2,2,3),"pillow",1.5),
    (torch.full((1,2,2,3),float("nan")),"pillow",1),
    (torch.full((1,2,2,3),float("inf")),"cv2",1)])
def test_invalid_inputs_fail_closed(args):
    with pytest.raises((TypeError,ValueError)):
        _secure().ImageMosaic.execute(*args)


@pytest.mark.parametrize("limit", ["MAX_ELEMENTS","MAX_OUTPUT_ELEMENTS","MAX_BLOCKS","MAX_AXIS"])
def test_bounds_checked_before_pixel_work(monkeypatch,limit):
    package = _secure()
    nodes = sys.modules[package.ImageMosaic.__module__]
    monkeypatch.setattr(nodes,limit,1)
    called = []
    monkeypatch.setattr(nodes,"mosaic_images",lambda *a: called.append(a))
    with pytest.raises(ValueError,match="bounded"):
        package.ImageMosaic.execute(torch.ones(1,3,4,3),"pillow",1)
    assert not called


def test_real_guests_pixel_parity_raw_denial_fresh_render_and_outer_image(tmp_path):
    expected_class = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageMosaic"]()
    fresh = tmp_path / "fresh-pack/v2"
    shutil.copytree(V2,fresh)
    async def run():
        pids = []
        for root in (V2,fresh):
            guest_class = _load("_moe_mosaic_guest_root",root).ImageMosaic
            refs = _sdk.InProcessRefResolver()
            session = await GuestSession("moe-mosaic",guest_runtime_root=root).start()
            try:
                for index,(method,channels,block) in enumerate((("pillow",3,3),("pillow",4,6),("cv2",3,3),("cv2",4,2))):
                    image = _image(channels=channels)
                    before = image.clone()
                    expected = expected_class.image_mosaic(image.clone(),method,block)[0]
                    ref = _sdk.ImageRef._wrap(await refs.create("IMAGE",image))
                    cls = guest_class
                    plan = _sdk.ExecutionPlan(prompt_id="mosaic-"+str(index),node_id=str(index),node_type="ImageMosaic",
                        tier="sandbox",node_module=cls.__module__,inputs={"images":ref,"method":method,"block_size":block},
                        input_mode="values",permissions=("raw",),method="execute")
                    runtime = _sdk.Runtime(refs=refs,ctx=_sdk.InProcessCtxProvider().build(plan),ops=_sdk.InProcessOps())
                    result = await session.execute(plan,runtime,capabilities=("raw",))
                    assert isinstance(result.result[0],_sdk.ImageRef)
                    assert torch.equal(await refs.resolve(result.result[0]),expected)
                    assert torch.equal(image,before)
                    with pytest.raises(Exception,match="raw"):
                        await session.execute(plan,runtime,capabilities=())
                pids.append(session.last_guest_pid)
                bad_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE",torch.ones(65,2,2,3)))
                plan.inputs = {"images":bad_ref,"method":"pillow","block_size":1}
                with pytest.raises(Exception,match="bounded"):
                    await session.execute(plan,runtime,capabilities=("raw",))
                assert pids[-1] not in (None,os.getpid())
            finally:
                await session.kill()
        assert len(set(pids)) == 2
        loaded = packdb.load_pack(SNAPSHOT,mount_name="custom_nodes.moe_mosaic_outer")
        node = loaded.node_mappings["ImageMosaic"]
        assert tuple(node.RETURN_TYPES) == ("IMAGE",)
        previous = _sdk.providers.execution_backend
        class Backend:
            session = None
            async def dispatch(self,plan,local_call,runtime):
                self.session = await GuestSession("moe-mosaic-outer",guest_runtime_root=V2).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs,plan.inputs)
                return await self.session.execute(plan,runtime,capabilities=("raw",))
        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            image = _image(channels=4)
            returns = await execution._async_map_node_over_list(prompt_id="moe-mosaic-outer",unique_id="1",obj=node,
                input_data_all={"images":[image],"method":["cv2"],"block_size":[3]},func=node.FUNCTION,v3_data=None)
            assert len(returns) == 1 and isinstance(returns[0].result[0],torch.Tensor)
            assert torch.equal(returns[0].result[0],expected_class.image_mosaic(image,"cv2",3)[0])
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session:
                await backend.session.kill()
    asyncio.run(run())


def test_manifest_stubs_dependencies_license_authority():
    assert json.loads((V2/"secure-nodes.json").read_text()) == _manifest()
    assert hashlib.sha256((V2/"comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2/"comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert not (PACK/"LICENSE").exists() and not (V2/"LICENSE").exists()
    assert (V2/"requirements.txt").read_bytes() == (PACK/"requirements.txt").read_bytes()
    text = "\n".join(p.read_text() for p in V2.glob("*.py"))
    for name in ("folder_paths","PromptServer","requests","subprocess","_from_raw","open(","manual_seed","sys.","os."):
        assert name not in text
    ledger = (V2/"SECURE_CONVERSION.md").read_text()
    assert "<!-- secure-conversion-report-v1 -->" in ledger and PIN in ledger
    assert "no durable state" in ledger


def test_manifest_patch_roundtrip_and_cache_hygiene(tmp_path):
    manifest,diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff
    fresh = tmp_path/"comfyui-mosaic-blur/x007acb0"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK,fresh/PACK.name,ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh,manifest,diff)
    packpatch.validate_tree(fresh/PACK.name/"v2",V2)
    assert not list(PACK.rglob("*.pyc")) and not list(PACK.rglob("__pycache__"))
