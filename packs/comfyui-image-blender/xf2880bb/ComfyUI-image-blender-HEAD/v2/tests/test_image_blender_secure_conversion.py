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
CORE = (
    pathlib.Path(
        os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes")
    )
    .expanduser()
    .resolve()
)
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "f2880bb8db5ed007823eccc43b8918728c4890dc"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-image-blender"
    / "xf2880bb"
    / "comfyui-image-blender-xf2880bb"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
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
    return _import_package("_secure_image_blender_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_image_blender_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs",
                    "fingerprint_inputs",
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


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _images(dtype=torch.float32):
    base = torch.tensor(
        [
            [
                [[0.17, 0.31, 0.73], [0.83, 0.27, 0.41], [0.39, 0.67, 0.21]],
                [[0.58, 0.46, 0.29], [0.24, 0.79, 0.62], [0.71, 0.19, 0.54]],
            ],
            [
                [[0.35, 0.64, 0.48], [0.69, 0.38, 0.76], [0.28, 0.52, 0.87]],
                [[0.77, 0.23, 0.57], [0.43, 0.86, 0.34], [0.61, 0.72, 0.18]],
            ],
        ],
        dtype=dtype,
    )
    blend = torch.flip(base, dims=(0, 1, 2, 3)) * 0.71 + 0.11
    return base, blend


def _assert_same(actual: torch.Tensor, expected: torch.Tensor):
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    torch.testing.assert_close(
        actual,
        expected,
        rtol=1e-6,
        atol=1e-7,
        equal_nan=True,
    )


def test_pinned_actual_loader_census_entrypoint_and_schema_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "1 supported, 0 rejected, 0 pending" in report
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"ImageBlender"}
    assert set(secure.NODE_CLASS_MAPPINGS) == set(pristine.NODE_CLASS_MAPPINGS)
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {"ImageBlender": "ImageBlender"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]

    legacy = pristine.NODE_CLASS_MAPPINGS["ImageBlender"]
    node = secure.NODE_CLASS_MAPPINGS["ImageBlender"]
    schema = node.GET_SCHEMA()
    schema.validate()
    inputs = legacy.INPUT_TYPES()
    assert [item.id for item in schema.inputs] == [
        "base_image",
        "blend_image",
        "strength",
        "blend_mode",
        "mask",
    ]
    assert schema.category == legacy.CATEGORY
    assert [item.io_type for item in schema.outputs] == list(legacy.RETURN_TYPES)
    assert [item.io_type for item in schema.inputs] == [
        "IMAGE",
        "IMAGE",
        "FLOAT",
        "COMBO",
        "MASK",
    ]
    strength = schema.inputs[2]
    assert (strength.default, strength.min, strength.max, strength.step) == (
        1.0,
        0.0,
        1.0,
        0.01,
    )
    assert schema.inputs[3].options == [mode.value for mode in secure.nodes.BlendModes]
    assert schema.inputs[3].default == secure.nodes.BlendModes.MIX_NORMAL.value
    assert schema.inputs[4].optional is True
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)
    assert len(list(secure.nodes.BlendModes)) == 88
    assert set(secure.nodes.BlendModes) == set(secure.nodes.blend_functions)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [secure.ImageBlender]
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.image_blender_census_test",
    )
    assert set(loaded.node_mappings) == {"ImageBlender"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


def test_all_88_blend_modes_are_differentially_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    legacy = pristine.NODE_CLASS_MAPPINGS["ImageBlender"]()
    base, blend = _images()
    assert [mode.value for mode in pristine.BlendModes] == [
        mode.value for mode in secure.nodes.BlendModes
    ]
    for mode in pristine.BlendModes:
        expected = legacy.blend(base.clone(), blend.clone(), 1.0, mode.value)[0]
        actual = secure.ImageBlender.execute(
            base.clone(), blend.clone(), 1.0, mode.value
        ).result[0]
        _assert_same(actual, expected)


@pytest.mark.parametrize("strength", (0.0, 0.25, 0.73, 1.0))
@pytest.mark.parametrize(
    "mode",
    (
        "arithmetic: multiply",
        "hsl: color hsl",
        "lighten: soft light (svg)",
        "mix: overlay",
        "negative: exclusion",
    ),
)
def test_opacity_across_mode_families_is_exact(tmp_path, strength, mode):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageBlender"]()
    secure = _secure()
    base, blend = _images()
    expected = pristine.blend(base, blend, strength, mode)[0]
    actual = secure.ImageBlender.execute(base, blend, strength, mode).result[0]
    _assert_same(actual, expected)
    assert torch.isfinite(actual).all()
    assert ((actual >= 0) & (actual <= 1)).all()


def test_masks_batches_and_dtypes_preserve_upstream_behavior(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageBlender"]()
    secure = _secure()
    for dtype in (torch.float32, torch.float64):
        base, blend = _images(dtype)
        masks = (
            torch.tensor(
                [
                    [[0.0, 0.25, 1.0], [0.5, 0.75, 0.1]],
                    [[1.0, 0.0, 0.4], [0.2, 0.9, 0.6]],
                ],
                dtype=dtype,
            ),
            torch.full_like(base, 0.42),
            torch.ones((1, 1, 1), dtype=dtype),
        )
        for mask in masks:
            expected = pristine.blend(
                base, blend, 0.63, "lighten: screen", mask
            )[0]
            actual = secure.ImageBlender.execute(
                base, blend, 0.63, "lighten: screen", mask
            ).result[0]
            _assert_same(actual, expected)


def test_direct_failures_and_resource_bounds_are_fail_closed(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageBlender"]()
    secure = _secure()
    base, blend = _images()
    for fn in (
        lambda: pristine.blend(base, blend[:1], 1.0, "mix: normal"),
        lambda: secure.ImageBlender.execute(base, blend[:1], 1.0, "mix: normal"),
    ):
        with pytest.raises(AssertionError, match="same shape"):
            fn()
    bad_channels = base[..., :2]
    for fn in (
        lambda: pristine.blend(bad_channels, bad_channels, 1.0, "mix: normal"),
        lambda: secure.ImageBlender.execute(
            bad_channels, bad_channels, 1.0, "mix: normal"
        ),
    ):
        with pytest.raises(AssertionError, match="3 channels"):
            fn()
    with pytest.raises(ValueError):
        secure.ImageBlender.execute(base, blend, 1.0, "unknown mode")

    oversized = (
        torch.empty((257, 1, 1, 3), device="meta"),
        torch.empty((1, 16385, 1, 3), device="meta"),
        torch.empty((2, 4097, 8192, 3), device="meta"),
    )
    for image in oversized:
        with pytest.raises(ValueError, match="limit"):
            secure.ImageBlender.execute(image, image, 1.0, "mix: normal")


def test_retained_blend_algorithm_sources_are_byte_identical():
    for relative in (
        "blend_modes_enum.py",
        "helpers.py",
        *(
            path.relative_to(PACK).as_posix()
            for path in sorted((PACK / "blend_modes").glob("*.py"))
        ),
    ):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()


def test_real_isolated_guest_matches_masked_execution_and_denies_raw(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageBlender"]()
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("image-blender", guest_runtime_root=V2).start()
        try:
            base, blend = _images()
            mask = torch.tensor(
                [
                    [[0.0, 0.25, 1.0], [0.5, 0.75, 0.1]],
                    [[1.0, 0.0, 0.4], [0.2, 0.9, 0.6]],
                ],
                dtype=base.dtype,
            )
            expected = pristine.blend(
                base, blend, 0.57, "hsv: hue hsv", mask
            )[0]
            inputs = {
                "base_image": _sdk.ImageRef._wrap(await refs.create("IMAGE", base)),
                "blend_image": _sdk.ImageRef._wrap(await refs.create("IMAGE", blend)),
                "strength": 0.57,
                "blend_mode": "hsv: hue hsv",
                "mask": _sdk.MaskRef._wrap(await refs.create("MASK", mask)),
            }
            plan = _sdk.ExecutionPlan(
                prompt_id="image-blender-guest",
                node_id="7",
                node_type=secure.ImageBlender.__name__,
                tier="sandbox",
                node_module=secure.ImageBlender.__module__,
                inputs=inputs,
                input_mode="values",
                permissions=("raw",),
                method="execute",
            )
            result = await session.execute(
                plan,
                _runtime(plan, refs),
                capabilities=("raw",),
            )
            actual = await refs.resolve(result.result[0])
            _assert_same(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    plan,
                    _runtime(plan, refs),
                    capabilities=(),
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = "\n".join(
        path.read_text()
        for path in sorted(V2.rglob("*.py"))
        if "tests" not in path.parts
    )
    assert "import torch" in source
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


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-image-blender" / "xf2880bb"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_no_generated_caches_are_committed():
    assert not [
        path
        for path in PACK.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"} or path.suffix == ".pyc"
    ]
