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
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "02f84ccb230a3dcbe1215556780799fd7484f847"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/comfyui-resolutionselectorplus/x02f84cc/" \
    "comfyui-resolutionselectorplus-x02f84cc"

for root in (COMFYUI, BACKEND, CORE):
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
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_resolution_selector_plus_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_resolution_selector_plus_test", root)


def _manifest(pack) -> dict:
    node = pack.NODE_CLASS_MAPPINGS["ResolutionSelectorPlus"]
    return {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": {
            "ResolutionSelectorPlus": {
                "class": node.__name__,
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "check_lazy_status", "fingerprint_inputs",
                        "validate_inputs",
                    )
                },
                "module": "nodes",
                "permissions": [],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": True,
            },
        },
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file() and not any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in item.relative_to(root).parts
        )
    }


def test_actual_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"ResolutionSelectorPlus"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"ResolutionSelectorPlus"}
    assert pristine.WEB_DIRECTORY == "./js"
    assert secure.WEB_DIRECTORY == "web"
    assert sum(
        path.read_text().count("app.registerExtension(")
        for path in (PACK / "js").glob("*.js")
    ) == 1

    old = pristine.NODE_CLASS_MAPPINGS["ResolutionSelectorPlus"]
    new = secure.NODE_CLASS_MAPPINGS["ResolutionSelectorPlus"]
    schema = new.GET_SCHEMA()
    old_inputs = old.INPUT_TYPES()
    expected_inputs = [*old_inputs["required"], *old_inputs["optional"]]
    assert (schema.node_id, schema.display_name, schema.category) == (
        "ResolutionSelectorPlus", "Resolution Selector Plus", old.CATEGORY,
    )
    assert [item.id for item in schema.inputs] == expected_inputs
    assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES)
    assert [item.display_name for item in schema.outputs] == list(old.RETURN_NAMES)
    for item in schema.inputs:
        declared = (old_inputs["required"] | old_inputs["optional"])[item.id]
        old_type, metadata = declared
        assert item.optional is (item.id in old_inputs["optional"])
        if isinstance(old_type, list):
            assert item.io_type == "COMBO"
            assert list(item.options) == old_type
        else:
            assert item.io_type == old_type
        for name in ("default", "min", "max", "step", "tooltip"):
            if name in metadata:
                assert getattr(item, name) == metadata[name]

    assert new.SDK_REFS is True
    assert new.SDK_PERMISSIONS == ()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.resolution_selector_plus_secure_test",
    )
    assert set(loaded.node_mappings) == {"ResolutionSelectorPlus"}
    assert loaded.web_directory == V2 / "web"
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


def test_tables_helpers_and_validation_are_differential(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    old_nodes = sys.modules[f"{pristine.__name__}.nodes"]
    assert secure.nodes.MODEL_RESOLUTIONS == old_nodes.MODEL_RESOLUTIONS
    assert secure.nodes.get_all_resolutions() == old_nodes.get_all_resolutions()
    for model in ("All", *secure.nodes.MODEL_RESOLUTIONS):
        assert secure.nodes.get_latent_channels(model) == old_nodes.get_latent_channels(model)
    for resolution in secure.nodes.get_all_resolutions():
        assert secure.nodes.parse_resolution_string(resolution) == (
            old_nodes.parse_resolution_string(resolution)
        )
    for invalid in ("", "bad", "1024", "1x2x3"):
        with pytest.raises(ValueError) as old_error:
            old_nodes.parse_resolution_string(invalid)
        with pytest.raises(type(old_error.value)) as new_error:
            secure.nodes.parse_resolution_string(invalid)
        assert str(new_error.value) == str(old_error.value)

    old = pristine.NODE_CLASS_MAPPINGS["ResolutionSelectorPlus"]()
    for model, width, height in (
        ("Flux", 1024, 1024), ("Qwen Image", 1328, 1328),
        ("SD 1.5", 512, 512), ("All", 1024, 1024),
        ("Flux", 513, 1024), ("SDXL", 64, 64), ("All", 65, 64),
    ):
        try:
            old._validate_dimensions(model, width, height)
        except Exception as error:
            with pytest.raises(type(error), match=str(error).replace("(", "\\(").replace(")", "\\)")):
                secure.ResolutionSelector._validate_dimensions(model, width, height)
        else:
            secure.ResolutionSelector._validate_dimensions(model, width, height)


@pytest.mark.parametrize(
    "inputs,expected_shape,expected_custom",
    [
        ({"model": "SD 1.5", "resolution": "512x512      (1:1 Square)"}, (1, 4, 64, 64), (1, 4, 1, 1)),
        ({"model": "Flux", "resolution": "1024x1024    (1:1 Square)", "batch_size": 2}, (2, 16, 128, 128), (1, 16, 1, 1)),
        ({"model": "SDXL", "resolution": "1024x1024    (1:1 Square)", "resolution_multiplier": "2x", "custom_width": 512, "custom_height": 768, "custom_multiplier": "2x", "custom_batch": 3}, (1, 4, 256, 256), (3, 4, 192, 128)),
    ],
)
def test_real_guest_shapes_channels_custom_placeholder_and_zero_values(
    inputs, expected_shape, expected_custom,
):
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="resolution-selector", node_id="1",
            node_type=secure.ResolutionSelector.__name__, tier="sandbox",
            node_module=secure.ResolutionSelector.__module__, inputs=inputs,
            permissions=(), method="execute",
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "resolution-selector-plus", guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            width, height, latent_ref, custom_width, custom_height, custom_ref = result.result
            latent = await refs.resolve(latent_ref)
            custom = await refs.resolve(custom_ref)
            assert tuple(latent["samples"].shape) == expected_shape
            assert tuple(custom["samples"].shape) == expected_custom
            assert torch.count_nonzero(latent["samples"]).item() == 0
            assert torch.count_nonzero(custom["samples"]).item() == 0
            assert (width, height) == (expected_shape[3] * 8, expected_shape[2] * 8)
            if inputs.get("custom_width", 0):
                assert (custom_width, custom_height) == (
                    expected_custom[3] * 8, expected_custom[2] * 8,
                )
            else:
                assert (custom_width, custom_height) == (0, 0)
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


@pytest.mark.parametrize(
    "inputs,match",
    [
        ({"model": "missing", "resolution": "1024x1024"}, "unknown model"),
        ({"model": "Flux", "resolution": "1025x1024"}, "divisible"),
        ({"model": "SDXL", "resolution": "64x64"}, "between"),
        ({"model": "All", "resolution": "1024x1024", "batch_size": 65}, "batch size"),
    ],
)
def test_invalid_direct_inputs_fail_closed(inputs, match):
    with pytest.raises(ValueError, match=match):
        asyncio.run(_secure().ResolutionSelector.execute(**inputs))


def test_frontend_behavior_security_and_typecheck():
    source = (V2 / "web/main.js").read_text()
    for forbidden in (
        "/scripts/app.js", "app.registerExtension", "LiteGraph", "document.",
        "window.", "localStorage", "indexedDB", "fetch(", "innerHTML",
        "setTimeout", "setInterval", ".prototype", ".callback",
    ):
        assert forbidden not in source
    completed = subprocess.run(
        ["node", "--experimental-vm-modules", str(
            V2 / "tests/resolution_selector_frontend_harness.mjs",
        ), str(V2 / "web/main.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: ResolutionSelectorPlus" in completed.stdout
    completed = subprocess.run(
        ["node", "--check", str(V2 / "web/main.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    completed = subprocess.run(
        [str(pathlib.Path(
            "/Users/ben/comfy/ComfyUI_frontend-secure-nodes/node_modules/.bin/tsc",
        )), "--project", str(V2 / "tsconfig.json")],
        cwd=V2, text=True, capture_output=True, timeout=60, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_contract_assets_and_authority_boundary_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    for relative in ("README.md", "LICENSE", "node_preview.png"):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import torch", "import comfy", "folder_paths", "PromptServer",
        "requests", "aiohttp", "subprocess", "open(", "ctx()", "_from_raw",
    ):
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-resolutionselectorplus/x02f84cc"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
