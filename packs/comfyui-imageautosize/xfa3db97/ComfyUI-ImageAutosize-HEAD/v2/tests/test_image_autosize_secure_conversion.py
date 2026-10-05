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
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "fa3db9751d84a254985a07c91e58cee4d25a9779"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "82dea265a0ae3918ece66547a6e413558c419fbcb0a4cc19d52b3fd74057cc49"
PAIR = PACK_DB / "patches" / "comfyui-imageautosize" / "xfa3db97" / (
    "comfyui-imageautosize-xfa3db97"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


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
    return _import_package("_secure_image_autosize_test", V2)


def _upstream():
    return _import_package("_upstream_image_autosize_test", PACK)


def _generated_manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(
                node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs",
                    "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    result = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if not item.is_file() or any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def test_pinned_census_schema_manifest_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    upstream = _upstream()
    secure = _secure()
    expected = {
        "ImageAutosize", "ImageAutosizeApplyTransform",
        "ImageAutosizeRestore",
    }
    upstream_extension = asyncio.run(upstream.comfy_entrypoint())
    assert {node.define_schema().node_id for node in asyncio.run(
        upstream_extension.get_node_list())} == expected
    assert set(secure.NODE_CLASS_MAPPINGS) == expected
    assert not list(PACK.rglob("*.js"))
    assert not list(PACK.rglob("*_routes.py"))

    extension = asyncio.run(secure.comfy_entrypoint())
    assert {node.GET_SCHEMA().node_id for node in asyncio.run(
        extension.get_node_list())} == expected
    for node in secure.NODE_CLASS_MAPPINGS.values():
        assert node.SDK_REFS is True
        assert node.SDK_PERMISSIONS == ("raw",)
    schema = secure.ImageAutosize.GET_SCHEMA()
    assert [item.id for item in schema.inputs] == [
        "image", "max_size", "min_size", "divisible_by",
        "interpolation_mode", "crop_mode", "constraint_priority",
    ]
    assert [item.io_type for item in schema.outputs] == [
        "COMFY_MATCHTYPE_V3", "INT", "INT", "FLOAT", "FLOAT",
        "AUTOSIZE_TRANSFORM",
    ]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(secure))
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.image_autosize_secure_test")
    assert set(loaded.node_mappings) == expected
    assert loaded.frontend_permissions == frozenset()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


@pytest.mark.parametrize("priority", ("min_size", "max_size"))
@pytest.mark.parametrize("size", ((10, 100, 50, 10, 1), (1, 100, 1, 1, 32)))
def test_target_dimension_calculation_matches_upstream(priority, size):
    width, height, max_size, min_size, divisible = size
    upstream = _upstream()
    secure = _secure()
    module = sys.modules[secure.ImageAutosize.__module__]
    assert module._calculate_target_dimensions(
        width, height, max_size, min_size, priority, divisible,
    ) == upstream._calculate_target_dimensions(
        width, height, max_size, min_size, priority, divisible,
    )


@pytest.mark.parametrize("mode", (
    "center", "top", "bottom", "left", "right", "top_left",
    "top_right", "bottom_left", "bottom_right",
))
def test_crop_origins_match_upstream(mode):
    upstream = _upstream()
    secure = _secure()
    module = sys.modules[secure.ImageAutosize.__module__]
    assert module._get_crop_origin(7, 9, 4, 6, mode) == (
        upstream._get_crop_origin(7, 9, 4, 6, mode))


@pytest.mark.parametrize("mode", (
    "nearest-exact", "bilinear", "area", "bicubic", "lanczos",
))
def test_resize_pixels_match_upstream(mode):
    upstream = _upstream()
    secure = _secure()
    module = sys.modules[secure.ImageAutosize.__module__]
    samples = torch.linspace(0, 1, 2 * 3 * 5 * 7).reshape(2, 3, 5, 7)
    expected = upstream._resize_samples(samples, 9, 8, mode)
    actual = module._resize_samples(samples, 9, 8, mode)
    assert torch.equal(actual, expected)


def test_transform_validation_rejects_malformed_and_oversized_objects():
    secure = _secure()
    module = sys.modules[secure.ImageAutosize.__module__]
    valid = {
        "original_width": 3, "original_height": 5,
        "target_width": 4, "target_height": 8,
        "resize_width": 4, "resize_height": 7,
        "offset_x": 0, "offset_y": 0, "crop_mode": "pad",
    }
    assert module._decode_transform(valid).crop_mode == "pad"
    with pytest.raises(ValueError, match="invalid fields"):
        module._decode_transform({**valid, "path": "/tmp"})
    with pytest.raises(ValueError, match="dimensions"):
        module._decode_transform({**valid, "target_width": 16_385})
    with pytest.raises(ValueError, match="target canvas"):
        module._decode_transform({**valid, "offset_x": 2})
    with pytest.raises(ValueError, match="pixel limit|too large"):
        module._validate_raw(torch.empty((1, 8192, 8193, 4), device="meta"))


def test_all_nodes_run_in_isolated_guest_and_raw_capability_is_enforced():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        ops = _sdk.InProcessOps()
        image = torch.linspace(0, 1, 1 * 5 * 3 * 3).reshape(1, 5, 3, 3)
        mask = torch.ones((1, 5, 3))
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        mask_ref = _sdk.MaskRef._wrap(await refs.create("MASK", mask))
        session = await GuestSession(
            "image-autosize-pack", guest_runtime_root=V2).start()
        try:
            node = secure.ImageAutosize
            plan = _sdk.ExecutionPlan(
                prompt_id="autosize-test", node_id="1",
                node_type=node.__name__, tier="sandbox",
                node_module=node.__module__,
                inputs={
                    "image": image_ref, "max_size": 8, "min_size": 1,
                    "constraint_priority": "min_size", "divisible_by": 4,
                    "interpolation_mode": "nearest-exact", "crop_mode": "pad",
                },
                permissions=node.SDK_PERMISSIONS,
            )
            runtime = _sdk.Runtime(
                refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=ops)
            resized_result = await session.execute(
                plan, runtime, capabilities=node.SDK_PERMISSIONS)
            resized = await refs.resolve(resized_result.result[0])
            transform = resized_result.result[5]

            apply_node = secure.ImageAutosizeApplyTransform
            apply_plan = _sdk.ExecutionPlan(
                prompt_id="autosize-test", node_id="2",
                node_type=apply_node.__name__, tier="sandbox",
                node_module=apply_node.__module__,
                inputs={
                    "image": mask_ref, "transform": transform,
                    "interpolation_mode": "nearest-exact",
                },
                permissions=apply_node.SDK_PERMISSIONS,
            )
            apply_runtime = _sdk.Runtime(
                refs=refs, ctx=_sdk.InProcessCtxProvider().build(apply_plan), ops=ops)
            applied_result = await session.execute(
                apply_plan, apply_runtime, capabilities=apply_node.SDK_PERMISSIONS)
            applied = await refs.resolve(applied_result.result[0])

            restore_node = secure.ImageAutosizeRestore
            resized_ref = resized_result.result[0]
            restore_plan = _sdk.ExecutionPlan(
                prompt_id="autosize-test", node_id="3",
                node_type=restore_node.__name__, tier="sandbox",
                node_module=restore_node.__module__,
                inputs={
                    "image": resized_ref, "transform": transform,
                    "interpolation_mode": "nearest-exact",
                },
                permissions=restore_node.SDK_PERMISSIONS,
            )
            restore_runtime = _sdk.Runtime(
                refs=refs, ctx=_sdk.InProcessCtxProvider().build(restore_plan), ops=ops)
            restored_result = await session.execute(
                restore_plan, restore_runtime,
                capabilities=restore_node.SDK_PERMISSIONS)
            restored = await refs.resolve(restored_result.result[0])
            with pytest.raises(Exception, match="raw.*capability"):
                await session.execute(plan, runtime, capabilities=())
            return (
                resized_result.result[1:5], transform, resized, applied,
                restored, image, session.last_guest_pid,
            )
        finally:
            await session.kill()

    metadata, transform, resized, applied, restored, image, guest_pid = (
        asyncio.run(run()))
    assert guest_pid not in (None, os.getpid())
    assert metadata == (4, 8, 4 / 3, 7 / 5)
    assert transform == {
        "original_width": 3, "original_height": 5,
        "target_width": 4, "target_height": 8,
        "resize_width": 4, "resize_height": 7,
        "offset_x": 0, "offset_y": 0, "crop_mode": "pad",
    }
    assert tuple(resized.shape) == (1, 8, 4, 3)
    assert tuple(applied.shape) == (1, 8, 4)
    assert torch.all(applied[:, :7] == 1)
    assert torch.all(applied[:, 7:] == 0)
    assert tuple(restored.shape) == tuple(image.shape)


def test_source_has_no_ambient_host_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests",
        "subprocess", "open(", "os.", "sys.",
    ):
        assert forbidden not in source
    assert source.count("SDK_PERMISSIONS = (\"raw\",") == 3


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-imageautosize" / "xfa3db97"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_bytecode_or_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
