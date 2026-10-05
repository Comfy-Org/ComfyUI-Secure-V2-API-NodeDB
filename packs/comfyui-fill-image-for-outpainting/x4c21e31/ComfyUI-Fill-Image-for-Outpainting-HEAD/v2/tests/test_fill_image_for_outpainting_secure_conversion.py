from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sys

import pytest
import torch

sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMMIT = "4c21e317c04b2e87fe3c2f9c2fcbae94be250b80"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-fill-image-for-outpainting"
    / "x4c21e31"
    / "comfyui-fill-image-for-outpainting-x4c21e31"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession


def _import_package(name: str, root: pathlib.Path):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_fill_outpaint_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_fill_outpaint_test", root)


def _manifest(pack) -> dict:
    node = pack.FillImageForOutpainting
    return {
        "format": FORMAT,
        "nodes": {
            "FillImageForOutpainting": {
                "module": "nodes",
                "class": "FillImageForOutpainting",
                "sdk_refs": False,
                "permissions": ["raw"],
                "methods": {
                    method: method in node.__dict__
                    for method in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    result = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if not item.is_file() or any(
            part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _values():
    height, width = 20, 24
    generator = torch.Generator().manual_seed(90210)
    image = torch.rand((3, height, width, 3), generator=generator)
    mask = torch.zeros((height, width), dtype=torch.float32)
    mask[4:15, 6:19] = 1
    mask[8:11, 2:22] = 1
    return image, mask


def _exact(actual, expected):
    assert actual.dtype == expected.dtype == torch.float32
    assert tuple(actual.shape) == tuple(expected.shape)
    assert torch.equal(actual, expected)
    assert torch.isfinite(actual).all()


def test_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"FillImageForOutpainting"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"FillImageForOutpainting"}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]

    legacy = pristine.NODE_CLASS_MAPPINGS["FillImageForOutpainting"]
    node = secure.FillImageForOutpainting
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "FillImageForOutpainting"
    assert schema.display_name == "Fill Image For Outpainting"
    assert schema.category == legacy.CATEGORY == "image"
    assert [item.id for item in schema.inputs] == ["image", "mask", "fill_method"]
    assert [item.io_type for item in schema.inputs] == ["IMAGE", "MASK", "COMBO"]
    assert schema.inputs[2].options == legacy.fill_methods == secure.FILL_METHODS
    assert schema.inputs[2].default == "cv2_ns"
    assert [item.io_type for item in schema.outputs] == ["IMAGE", "MASK"]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)
    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.fill_outpaint_secure_census_test"
    )
    assert set(loaded.node_mappings) == {"FillImageForOutpainting"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize("method", ("cv2_ns", "cv2_telea", "edge_pad"))
def test_all_three_fill_methods_are_pixel_exact_to_upstream(tmp_path, method):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "FillImageForOutpainting"
    ]()
    secure = _secure()
    image, mask = _values()
    expected_image, expected_mask = pristine.fill_image(image, mask, method)
    result = secure.FillImageForOutpainting.execute(image, mask, method).result
    _exact(result[0], expected_image)
    _exact(result[1], expected_mask)


def test_first_image_quantization_and_mask_result_match_upstream(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "FillImageForOutpainting"
    ]()
    secure = _secure()
    image, mask = _values()
    alternate = image.clone()
    alternate[1:] = 1 - alternate[1:]
    for method in secure.FILL_METHODS:
        expected = pristine.fill_image(alternate, mask, method)
        actual = secure.FillImageForOutpainting.execute(
            alternate, mask, method
        ).result
        _exact(actual[0], expected[0])
        _exact(actual[1], expected[1])
        assert actual[0].shape[0] == 1
        quantized = actual[0] * 255
        torch.testing.assert_close(quantized, quantized.round(), rtol=0, atol=1e-5)


def test_malformed_shapes_method_and_resource_bounds_fail_closed():
    secure = _secure()
    image, mask = _values()
    node = secure.FillImageForOutpainting
    with pytest.raises(ValueError, match="unsupported"):
        node.execute(image, mask, "unknown")
    with pytest.raises(TypeError, match="BHWC"):
        node.execute(image[0], mask, "cv2_ns")
    with pytest.raises(ValueError, match="batch"):
        node.execute(image[:0], mask, "cv2_ns")
    with pytest.raises(ValueError, match="RGB"):
        node.execute(image[..., :2], mask, "cv2_ns")
    with pytest.raises(TypeError, match="two-dimensional"):
        node.execute(image, mask.unsqueeze(0), "cv2_ns")
    with pytest.raises(ValueError, match="dimensions must match"):
        node.execute(image, mask[:-1], "cv2_ns")
    too_large = torch.empty(
        (1, 1, secure.nodes.MAX_PIXELS + 1, 3), device="meta"
    )
    huge_mask = torch.empty((1, secure.nodes.MAX_PIXELS + 1), device="meta")
    with pytest.raises(ValueError, match="dimensions"):
        node.execute(too_large, huge_mask, "cv2_ns")


def test_real_isolated_guest_matches_upstream_and_denies_raw(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "FillImageForOutpainting"
    ]()
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        image, mask = _values()
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        mask_ref = _sdk.MaskRef._wrap(await refs.create("MASK", mask))
        node = secure.FillImageForOutpainting
        plan = _sdk.ExecutionPlan(
            prompt_id="fill-outpaint",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={
                "image": image_ref,
                "mask": mask_ref,
                "fill_method": "edge_pad",
            },
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        runtime = _runtime(plan, refs)
        session = await GuestSession(
            "fill-outpaint-secure-conversion", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=("raw",))
            actual_image = await refs.resolve(result.result[0])
            actual_mask = await refs.resolve(result.result[1])
            expected_image, expected_mask = pristine.fill_image(
                image, mask, "edge_pad"
            )
            _exact(actual_image, expected_image)
            _exact(actual_mask, expected_mask)
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_stubs_license_authority_patch_and_cache_are_exact(tmp_path):
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    assert source.count('SDK_PERMISSIONS = ("raw",)') == 1
    for forbidden in (
        "import comfy",
        "folder_paths",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "os.",
        "sys.",
        "ctx()",
        "_from_raw",
        "from_value",
        "socket",
        "urllib",
    ):
        assert forbidden not in source

    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-fill-image-for-outpainting" / "x4c21e31"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
    assert not list(PACK.rglob(".ruff_cache"))
