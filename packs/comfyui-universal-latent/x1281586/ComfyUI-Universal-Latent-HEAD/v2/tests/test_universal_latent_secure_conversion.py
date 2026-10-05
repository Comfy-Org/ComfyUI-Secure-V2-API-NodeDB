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
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "1281586aba8861acbcc815b30386d354e0a7798d"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB / "patches/comfyui-universal-latent/x1281586/"
    "comfyui-universal-latent-x1281586"
)

for root in (COMFYUI, BACKEND, CORE):
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
    return _import_package("_secure_universal_latent_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_universal_latent_test", root)


def _manifest(pack) -> dict:
    node = pack.NODE_CLASS_MAPPINGS["UniversalLatent"]
    return {
        "format": FORMAT,
        "nodes": {
            "UniversalLatent": {
                "class": node.__name__,
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "check_lazy_status",
                        "fingerprint_inputs",
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
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file()
        and not any(
            part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in item.relative_to(root).parts
        )
    }


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_actual_loader_census_schema_and_manifest_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"UniversalLatent"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"UniversalLatent"}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]

    old = pristine.NODE_CLASS_MAPPINGS["UniversalLatent"]
    new = secure.NODE_CLASS_MAPPINGS["UniversalLatent"]
    schema = new.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "UniversalLatent",
        pristine.NODE_DISPLAY_NAME_MAPPINGS["UniversalLatent"],
        old.CATEGORY,
    )
    old_inputs = old.INPUT_TYPES()["required"]
    assert [item.id for item in schema.inputs] == list(old_inputs)
    for item in schema.inputs:
        old_type, metadata = old_inputs[item.id]
        if isinstance(old_type, list):
            assert item.io_type == "COMBO"
            assert list(item.options) == old_type
        else:
            assert item.io_type == old_type
        for field in ("default", "min", "max", "step"):
            if field in metadata:
                assert getattr(item, field) == metadata[field]
    assert [(item.id, item.io_type, item.display_name) for item in schema.outputs] == [
        ("LATENT", "LATENT", "LATENT"),
        ("width", "INT", "width"),
        ("height", "INT", "height"),
    ]
    assert list(old.RETURN_TYPES) == [item.io_type for item in schema.outputs]
    assert list(old.RETURN_NAMES) == [item.display_name for item in schema.outputs]
    assert new.SDK_REFS is True
    assert new.SDK_PERMISSIONS == ()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [new]
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.universal_latent_secure_test",
    )
    assert set(loaded.node_mappings) == {"UniversalLatent"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


def test_all_72_presets_and_dimension_rules_match_pristine(tmp_path):
    pristine = _pristine(tmp_path)
    old_class = pristine.NODE_CLASS_MAPPINGS["UniversalLatent"]
    old = old_class()
    secure = _secure()
    old_options = old_class.INPUT_TYPES()["required"]["resolution"][0]
    assert secure.RESOLUTION_OPTIONS == old_options
    assert len(secure.RESOLUTION_OPTIONS) == 72

    cases = [(resolution, 0, 0, "Unlocked", "auto", "No") for resolution in old_options]
    cases.extend(
        [
            ("512x768 (2:3)", 1001, 0, "Width", 8, "No"),
            ("768x512 (3:2)", 0, 1001, "Height", 4, "No"),
            ("1024x576 (16:9)", 513, 777, "Unlocked", 8, "No"),
            ("1024x576 (16:9)", 513, 777, "Unlocked", 4, "Yes"),
            ("1024x1024 direct", 1, 16_384, "Unlocked", "auto", "No"),
            ("16384x64 direct", 0, 0, "Unlocked", 8, "Yes"),
        ]
    )
    for resolution, width, height, lock, factor, invert in cases:
        _, old_width, old_height = old.execute(
            resolution=resolution,
            batch_size=1,
            width_override=width,
            height_override=height,
            aspect_ratio_lock=lock,
            latent_channels=1,
            downsample_factor=factor,
            invert_ratios=invert,
        )
        new_width, new_height, new_factor = secure.calculate_dimensions(
            resolution=resolution,
            width_override=width,
            height_override=height,
            aspect_ratio_lock=lock,
            downsample_factor=factor,
            invert_ratios=invert,
        )
        assert (new_width, new_height) == (old_width, old_height)
        assert new_factor == (8 if factor == "auto" else int(factor))


@pytest.mark.parametrize(
    "inputs,expected_shape,expected_size",
    [
        (
            {"resolution": "1024x1024 (1:1)", "batch_size": 1},
            (1, 4, 128, 128),
            (1024, 1024),
        ),
        (
            {
                "resolution": "512x768 (2:3)",
                "batch_size": 2,
                "width_override": 1001,
                "aspect_ratio_lock": "Width",
                "latent_channels": 16,
                "downsample_factor": 4,
            },
            (2, 16, 376, 251),
            (1004, 1504),
        ),
        (
            {
                "resolution": "1024x576 (16:9)",
                "batch_size": 3,
                "width_override": 513,
                "height_override": 777,
                "invert_ratios": "Yes",
                "latent_channels": 1,
                "downsample_factor": 8,
            },
            (3, 1, 65, 98),
            (784, 520),
        ),
    ],
)
def test_real_zero_capability_guest_returns_exact_zero_latent(
    inputs,
    expected_shape,
    expected_size,
):
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="universal-latent",
            node_id="1",
            node_type=secure.UniversalLatent.__name__,
            tier="sandbox",
            node_module=secure.UniversalLatent.__module__,
            inputs=inputs,
            permissions=(),
            method="execute",
        )
        session = await GuestSession(
            "universal-latent-conversion",
            guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(
                plan,
                _runtime(plan, refs),
                capabilities=(),
            )
            latent_ref, width, height = result.result
            value = await refs.resolve(latent_ref)
            samples = value["samples"]
            assert (width, height) == expected_size
            assert tuple(samples.shape) == expected_shape
            assert samples.dtype == torch.float32
            assert torch.count_nonzero(samples).item() == 0
            assert value["downscale_ratio_spacial"] == (
                8
                if inputs.get("downsample_factor", "auto") == "auto"
                else inputs["downsample_factor"]
            )
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


@pytest.mark.parametrize(
    "inputs,match",
    [
        ({"resolution": "bad", "batch_size": 1}, "Invalid resolution"),
        ({"resolution": "0x1024", "batch_size": 1}, "positive"),
        ({"resolution": "1024x1024", "batch_size": 0}, "batch_size"),
        ({"resolution": "1024x1024", "batch_size": True}, "integer"),
        (
            {"resolution": "1024x1024", "batch_size": 1, "latent_channels": 17},
            "latent_channels",
        ),
        (
            {"resolution": "1024x1024", "batch_size": 1, "aspect_ratio_lock": "broken"},
            "aspect_ratio_lock",
        ),
        (
            {"resolution": "1024x1024", "batch_size": 1, "downsample_factor": 16},
            "downsample_factor",
        ),
        (
            {"resolution": "1024x1024", "batch_size": 1, "invert_ratios": "maybe"},
            "invert_ratios",
        ),
    ],
)
def test_invalid_direct_inputs_fail_closed(inputs, match):
    with pytest.raises((TypeError, ValueError), match=match):
        asyncio.run(_secure().UniversalLatent.execute(**inputs))


def test_host_allocation_bounds_reject_before_creating_a_ref():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        for index, inputs in enumerate(
            (
                {"resolution": "1024x1024", "batch_size": 65},
                {
                    "resolution": "16384x16384",
                    "batch_size": 64,
                    "latent_channels": 16,
                    "downsample_factor": 4,
                },
            )
        ):
            plan = _sdk.ExecutionPlan(
                prompt_id=f"universal-bound-{index}",
                node_id=str(index),
                node_type=secure.UniversalLatent.__name__,
                tier="sandbox",
                node_module=secure.UniversalLatent.__module__,
                inputs=inputs,
                permissions=(),
                method="execute",
            )
            runtime = _runtime(plan, refs)
            with (
                _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops),
                pytest.raises(ValueError, match="bounded range"),
            ):
                await secure.UniversalLatent.execute(**inputs)
        assert refs._table == {}

    asyncio.run(run())


def test_contract_docs_and_authority_boundary_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert not (PACK / "LICENSE").exists()
    assert (
        "does not\ncontain the referenced license file"
        in (V2 / "SECURE_CONVERSION.md").read_text()
    )
    source = (V2 / "nodes.py").read_text()
    assert "await sdk.LatentRef.empty(" in source
    for forbidden in (
        "import torch",
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
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-universal-latent/x1281586"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
    assert not list(PACK.rglob(".ruff_cache"))
