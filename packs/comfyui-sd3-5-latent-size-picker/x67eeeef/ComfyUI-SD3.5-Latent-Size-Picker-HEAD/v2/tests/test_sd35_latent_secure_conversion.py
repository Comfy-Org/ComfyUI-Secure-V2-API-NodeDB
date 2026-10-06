from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import itertools
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
PAIR = (
    PACK_DB
    / "patches/comfyui-sd3-5-latent-size-picker/x67eeeef/comfyui-sd3-5-latent-size-picker-x67eeeef"
)
COMMIT = "67eeeeff12f5f6859a0f4c4853e14cc96a9dc8fe"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"

for root in (COMFYUI, BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession


def import_package(name, root):
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


def secure():
    return import_package("_sd35_latent_secure_test", V2)


def pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return import_package("_sd35_latent_pristine_test", root)


def build_manifest(package):
    return {
        "format": FORMAT,
        "nodes": {
            node_id: {
                "class": node.__name__,
                "methods": {
                    method: method in node.__dict__
                    for method in (
                        "check_lazy_status",
                        "fingerprint_inputs",
                        "validate_inputs",
                    )
                },
                "module": "nodes",
                "permissions": [],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": True,
            }
            for node_id, node in package.NODE_CLASS_MAPPINGS.items()
        },
        "runtime": manifest_declaration(V2),
    }


def tree(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def plan_for(node, inputs):
    return _sdk.ExecutionPlan(
        prompt_id="sd35-latent-conversion",
        node_id="1",
        node_type=node.__name__,
        tier="sandbox",
        node_module=node.__module__,
        inputs=inputs,
        permissions=(),
        method="execute",
    )


def old_execute(package, node_id, inputs):
    old_node = package.NODE_CLASS_MAPPINGS[node_id].__new__(
        package.NODE_CLASS_MAPPINGS[node_id]
    )
    old_node.device = torch.device("cpu")
    return old_node.execute(**inputs)


def test_actual_loader_census_and_exact_schema(tmp_path):
    old = pristine(tmp_path)
    new = secure()
    assert (
        set(old.NODE_CLASS_MAPPINGS)
        == set(new.NODE_CLASS_MAPPINGS)
        == {
            "SD3_5EmptyLatent",
            "FluxEmptyLatent",
        }
    )
    assert new.NODE_DISPLAY_NAME_MAPPINGS == old.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(old, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]
    for node_id, node in new.NODE_CLASS_MAPPINGS.items():
        schema = node.GET_SCHEMA()
        schema.validate()
        original = old.NODE_CLASS_MAPPINGS[node_id]
        assert schema.node_id == node_id
        assert schema.category == original.CATEGORY
        assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        old_inputs = original.INPUT_TYPES()["required"]
        assert [item.id for item in schema.inputs] == list(old_inputs)
        for item in schema.inputs:
            old_type, attrs = old_inputs[item.id]
            assert item.io_type == ("COMBO" if isinstance(old_type, list) else old_type)
            if isinstance(old_type, list):
                assert item.options == old_type
            for key in ("default", "min", "max", "step"):
                if key in attrs:
                    assert getattr(item, key) == attrs[key]
        assert [item.io_type for item in schema.outputs] == list(original.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(
            original.RETURN_NAMES
        )
        assert node.SDK_REFS is True and node.SDK_PERMISSIONS == ()
    extension = asyncio.run(new.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == list(
        new.NODE_CLASS_MAPPINGS.values()
    )


def test_manifest_and_real_pack_load_are_exact():
    package = secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == build_manifest(package)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.sd35_latent_secure_test"
    )
    assert set(loaded.node_mappings) == set(package.NODE_CLASS_MAPPINGS)
    assert not loaded.frontend_permissions and not loaded.routes


@pytest.mark.parametrize(
    "node_id,expected_count", [("SD3_5EmptyLatent", 11), ("FluxEmptyLatent", 72)]
)
def test_every_preset_matches_pristine_dimensions_and_zero_values(
    tmp_path, node_id, expected_count
):
    old = pristine(tmp_path)
    new = secure()
    options = old.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()["required"]["resolution"][
        0
    ]
    assert len(options) == expected_count

    async def run():
        for option in options:
            inputs = {"resolution": option, "batch_size": 1}
            old_value, old_width, old_height = old_execute(old, node_id, inputs)
            node = new.NODE_CLASS_MAPPINGS[node_id]
            refs = _sdk.InProcessRefResolver()
            execution_plan = plan_for(node, inputs)
            host_runtime = runtime(execution_plan, refs)
            with _sdk.bind_runtime(
                host_runtime.refs, host_runtime.ctx, host_runtime.ops
            ):
                result = await node.execute(**inputs)
            latent_ref, width, height = result.result
            value = await refs.resolve(latent_ref)
            assert (width, height) == (old_width, old_height)
            assert torch.equal(value["samples"], old_value["samples"])
            assert value["samples"].dtype == torch.float32

    asyncio.run(run())


@pytest.mark.parametrize("node_id", ["SD3_5EmptyLatent", "FluxEmptyLatent"])
def test_override_lock_invert_channel_cell_matrices_match_pristine(tmp_path, node_id):
    old = pristine(tmp_path)
    new = secure()
    cases = []
    for width, height, invert in itertools.product(
        (0, 1, 65, 1001), (0, 127, 777), ("No", "Yes")
    ):
        base = {
            "resolution": "704x1056 direct",
            "batch_size": 1,
            "width_override": width,
            "height_override": height,
            "invert_ratios": invert,
        }
        if node_id == "SD3_5EmptyLatent":
            cases.append(base)
        else:
            for lock, factor, channels in itertools.product(
                ("Unlocked", "Width", "Height"), ("auto", 4, 8), (1, 4, 16)
            ):
                cases.append(
                    dict(
                        base,
                        aspect_ratio_lock=lock,
                        downsample_factor=factor,
                        latent_channels=channels,
                    )
                )

    async def run():
        for inputs in cases:
            old_value, old_width, old_height = old_execute(old, node_id, inputs)
            node = new.NODE_CLASS_MAPPINGS[node_id]
            refs = _sdk.InProcessRefResolver()
            execution_plan = plan_for(node, inputs)
            host_runtime = runtime(execution_plan, refs)
            with _sdk.bind_runtime(
                host_runtime.refs, host_runtime.ctx, host_runtime.ops
            ):
                result = await node.execute(**inputs)
            value = await refs.resolve(result.result[0])
            assert result.result[1:] == (old_width, old_height)
            assert value["samples"].shape == old_value["samples"].shape
            assert torch.equal(value["samples"], old_value["samples"])

    asyncio.run(run())


@pytest.mark.parametrize(
    "node_id,inputs",
    [
        ("SD3_5EmptyLatent", {"resolution": "1024x1024 (1.0)", "batch_size": 1}),
        (
            "SD3_5EmptyLatent",
            {
                "resolution": "640x1536 (0.98)",
                "batch_size": 2,
                "width_override": 777,
                "height_override": 513,
                "invert_ratios": "Yes",
            },
        ),
        ("SD3_5EmptyLatent", {"resolution": "64x64 direct", "batch_size": 64}),
        ("FluxEmptyLatent", {"resolution": "1024x1024 (1:1)", "batch_size": 1}),
        (
            "FluxEmptyLatent",
            {
                "resolution": "512x768 (2:3)",
                "batch_size": 2,
                "width_override": 1001,
                "aspect_ratio_lock": "Width",
                "downsample_factor": 4,
                "latent_channels": 16,
            },
        ),
        (
            "FluxEmptyLatent",
            {
                "resolution": "768x512 (3:2)",
                "batch_size": 3,
                "height_override": 777,
                "aspect_ratio_lock": "Height",
                "invert_ratios": "Yes",
                "latent_channels": 1,
            },
        ),
    ],
)
def test_real_zero_capability_guest_exact_latent_and_metadata(
    tmp_path, node_id, inputs
):
    old_value, old_width, old_height = old_execute(pristine(tmp_path), node_id, inputs)
    node = secure().NODE_CLASS_MAPPINGS[node_id]

    async def run():
        refs = _sdk.InProcessRefResolver()
        execution_plan = plan_for(node, inputs)
        session = await GuestSession(
            "sd35-latent-conversion", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(
                execution_plan, runtime(execution_plan, refs), capabilities=()
            )
            latent_ref, width, height = result.result
            value = await refs.resolve(latent_ref)
            assert (width, height) == (old_width, old_height)
            assert torch.equal(value["samples"], old_value["samples"])
            assert value["samples"].dtype == torch.float32
            assert value["downscale_ratio_spacial"] == (
                4 if inputs.get("downsample_factor") == 4 else 8
            )
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


@pytest.mark.parametrize("node_id", ["SD3_5EmptyLatent", "FluxEmptyLatent"])
@pytest.mark.parametrize("resolution", ["bad", "1024x", "1x2x3", "", "1024X1024"])
def test_malformed_resolution_errors_match_pristine(tmp_path, node_id, resolution):
    inputs = {"resolution": resolution, "batch_size": 1}
    with pytest.raises(ValueError) as original:
        old_execute(pristine(tmp_path), node_id, inputs)
    with pytest.raises(ValueError) as converted:
        asyncio.run(secure().NODE_CLASS_MAPPINGS[node_id].execute(**inputs))
    assert str(converted.value) == str(original.value)


@pytest.mark.parametrize(
    "inputs,match",
    [
        ({"batch_size": True}, "integer"),
        ({"batch_size": 0}, "batch_size"),
        ({"width_override": True}, "integer"),
        ({"height_override": 16385}, "height_override"),
        ({"latent_channels": 17}, "latent_channels"),
        ({"latent_channels": False}, "integer"),
        ({"aspect_ratio_lock": "unknown"}, "aspect_ratio_lock"),
        ({"invert_ratios": "maybe"}, "invert_ratios"),
        ({"downsample_factor": True}, "downsample_factor"),
        ({"downsample_factor": 16}, "downsample_factor"),
        ({"resolution": "0" * 1025}, "text bound"),
        ({"resolution": "1048577x64"}, "parsed width"),
    ],
)
def test_malformed_and_excessive_direct_inputs_fail_closed(inputs, match):
    defaults = {"resolution": "1024x1024", "batch_size": 1}
    defaults.update(inputs)
    with pytest.raises((ValueError, TypeError), match=match):
        asyncio.run(secure().NODE_CLASS_MAPPINGS["FluxEmptyLatent"].execute(**defaults))


@pytest.mark.parametrize("node_id", ["SD3_5EmptyLatent", "FluxEmptyLatent"])
def test_existing_allocator_safety_bounds_before_ref_creation(node_id):
    node = secure().NODE_CLASS_MAPPINGS[node_id]

    async def run():
        refs = _sdk.InProcessRefResolver()
        for inputs in (
            {"resolution": "64x64", "batch_size": 65},
            {"resolution": "16384x16384", "batch_size": 64},
        ):
            execution_plan = plan_for(node, inputs)
            host_runtime = runtime(execution_plan, refs)
            with (
                _sdk.bind_runtime(
                    host_runtime.refs, host_runtime.ctx, host_runtime.ops
                ),
                pytest.raises(ValueError, match="bounded range"),
            ):
                await node.execute(**inputs)
        assert refs._table == {}

    asyncio.run(run())


def test_authority_canonical_contract_and_provenance():
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert not (PACK / "LICENSE").exists()
    assert "contains no LICENSE file" in report
    source = (V2 / "nodes.py").read_text()
    assert "await sdk.LatentRef.empty(" in source
    for forbidden in (
        "import torch",
        "model_management",
        "folder_paths",
        "PromptServer",
        "subprocess",
        "open(",
        "_from_raw",
        "from_value",
        "ctx()",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert (
        json.loads(PAIR.with_suffix(".json").read_bytes().decode("utf-8")) == manifest
    )
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / SNAPSHOT.parent.name / SNAPSHOT.name
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert tree(rebuilt) == tree(V2)


def test_cache_cleanliness():
    for artifact in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(artifact))


if __name__ == "__main__":
    (V2 / "secure-nodes.json").write_text(
        json.dumps(build_manifest(secure()), indent=2, sort_keys=True) + "\n"
    )
