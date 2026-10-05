from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
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
COMMIT = "b61d0b23eadd802beec2dad5c53d816e995f516d"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-m3d-photo-effects"
    / "xb61d0b2"
    / "comfyui-m3d-photo-effects-xb61d0b2"
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
    return _import_package("_secure_m3d_photo_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_m3d_photo_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node in pack.NODE_CLASS_MAPPINGS.items():
        nodes[node_id] = {
            "module": "nodes",
            "class": node.__name__,
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
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
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


def _image(channels=3):
    generator = torch.Generator().manual_seed(4404 + channels)
    return torch.rand((1, 18, 22, channels), generator=generator)


def _exact(actual, expected):
    assert actual.dtype == expected.dtype == torch.float64
    assert tuple(actual.shape) == tuple(expected.shape)
    assert torch.equal(actual, expected)
    assert torch.isfinite(actual).all()


def test_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"Bleach Bypass", "RGB Curve"}
    assert set(secure.NODE_CLASS_MAPPINGS) == set(pristine.NODE_CLASS_MAPPINGS)
    assert pristine.WEB_DIRECTORY == "./js"
    assert secure.WEB_DIRECTORY == "./web"
    assert len(list((PACK / "js").glob("*.js"))) == 2
    assert len(list((V2 / "web").glob("*.js"))) == 1

    bleach = secure.BleachBypass.GET_SCHEMA()
    curve = secure.RGBCurve.GET_SCHEMA()
    bleach.validate()
    curve.validate()
    assert bleach.node_id == "Bleach Bypass"
    assert curve.node_id == "RGB Curve"
    assert bleach.category == curve.category == "M3D/image-effects/curve"
    assert [item.id for item in bleach.inputs] == [
        "image",
        "slope",
        "shadow_offset",
        "desaturation",
        "overlay_strength",
    ]
    assert [item.id for item in curve.inputs] == ["image", "slope", "shadow_offset"]
    assert [item.default for item in bleach.inputs[1:]] == [4, 0.5, 0.8, 0.9]
    assert [item.default for item in curve.inputs[1:]] == [4, 0.5]
    assert [item.io_type for item in bleach.outputs] == ["IMAGE"]
    assert [item.io_type for item in curve.outputs] == ["IMAGE"]
    assert secure.BleachBypass.SDK_PERMISSIONS == ("raw",)
    assert secure.RGBCurve.SDK_PERMISSIONS == ("raw",)
    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [secure.BleachBypass, secure.RGBCurve]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.m3d_photo_secure_test")
    assert set(loaded.node_mappings) == set(secure.NODE_CLASS_MAPPINGS)
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize("channels", (3, 4))
@pytest.mark.parametrize(
    "values", ((1.0, 0.0, 0.0, 0.0), (4.0, 0.5, 0.8, 0.9), (17.3, 0.82, 0.31, 0.47))
)
def test_bleach_bypass_is_pixel_exact_to_upstream(tmp_path, channels, values):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["Bleach Bypass"]()
    secure = _secure()
    image = _image(channels)
    expected = pristine.apply_bleach_bypass(image, *values)[0]
    actual = secure.BleachBypass.execute(image, *values).result[0]
    _exact(actual, expected)


@pytest.mark.parametrize("channels", (3, 4))
@pytest.mark.parametrize("slope,offset", ((1.0, 0.0), (4.0, 0.5), (50.0, 1.0)))
def test_rgb_curve_is_pixel_exact_to_upstream(tmp_path, channels, slope, offset):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["RGB Curve"]()
    secure = _secure()
    image = _image(channels)
    expected = pristine.apply_curve(image, slope, offset)[0]
    actual = secure.RGBCurve.execute(image, slope, offset).result[0]
    _exact(actual, expected)


def test_malformed_shapes_batches_and_resource_bounds_fail_closed():
    secure = _secure()
    image = _image()
    with pytest.raises(TypeError, match="BHWC"):
        secure.RGBCurve.execute(image[0], 4, 0.5)
    with pytest.raises(ValueError, match="exactly one"):
        secure.RGBCurve.execute(image.repeat(2, 1, 1, 1), 4, 0.5)
    with pytest.raises(ValueError, match="RGB or RGBA"):
        secure.BleachBypass.execute(image[..., :2], 4, 0.5, 0.8, 0.9)
    too_large = torch.empty(
        (1, 1, secure.nodes.MAX_PIXELS + 1, 3), device="meta"
    )
    with pytest.raises(ValueError, match="dimensions"):
        secure.RGBCurve.execute(too_large, 4, 0.5)


def test_real_isolated_guest_runs_both_nodes_and_denies_raw(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _image()
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        session = await GuestSession(
            "m3d-photo-secure-conversion", guest_runtime_root=V2
        ).start()
        try:
            cases = [
                (
                    secure.BleachBypass,
                    {
                        "image": image_ref,
                        "slope": 4.0,
                        "shadow_offset": 0.5,
                        "desaturation": 0.8,
                        "overlay_strength": 0.9,
                    },
                    pristine.NODE_CLASS_MAPPINGS["Bleach Bypass"]().apply_bleach_bypass(
                        image, 4.0, 0.5, 0.8, 0.9
                    )[0],
                ),
                (
                    secure.RGBCurve,
                    {"image": image_ref, "slope": 7.0, "shadow_offset": 0.3},
                    pristine.NODE_CLASS_MAPPINGS["RGB Curve"]().apply_curve(
                        image, 7.0, 0.3
                    )[0],
                ),
            ]
            for index, (node, inputs, expected) in enumerate(cases):
                plan = _sdk.ExecutionPlan(
                    prompt_id="m3d-photo",
                    node_id=str(index),
                    node_type=node.__name__,
                    tier="sandbox",
                    node_module=node.__module__,
                    inputs=inputs,
                    input_mode="values",
                    permissions=("raw",),
                    method="execute",
                )
                runtime = _runtime(plan, refs)
                result = await session.execute(plan, runtime, capabilities=("raw",))
                actual = await refs.resolve(result.result[0])
                _exact(actual, expected)
                with pytest.raises(Exception, match="raw"):
                    await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_typecheck_security_and_lifecycle():
    entry = V2 / "web" / "main.js"
    subprocess.run(["node", "--check", entry], check=True)
    subprocess.run(
        [
            "node",
            "--experimental-vm-modules",
            V2 / "tests" / "m3d_photo_frontend_harness.mjs",
            entry,
        ],
        check=True,
    )
    subprocess.run(
        [
            "/Users/ben/comfy/ComfyUI_frontend-secure-nodes/node_modules/.bin/tsc",
            "-p",
            V2 / "tsconfig.json",
        ],
        check=True,
        cwd=V2,
    )


def test_stubs_license_authority_patch_and_cache_are_exact(tmp_path):
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    python_source = (V2 / "nodes.py").read_text()
    frontend_source = (V2 / "web" / "main.js").read_text()
    for forbidden in (
        "import comfy",
        "folder_paths",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "ctx()",
        "_from_raw",
        "from_value",
    ):
        assert forbidden not in python_source
    for forbidden in (
        'from "../../scripts/app.js"',
        "document.",
        "window.",
        "fetch(",
        "localStorage",
        "indexedDB",
        "innerHTML",
        "prototype.",
    ):
        assert forbidden not in frontend_source

    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-m3d-photo-effects" / "xb61d0b2"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    for name in ("__pycache__", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(name))
    assert not list(PACK.rglob("*.pyc"))
