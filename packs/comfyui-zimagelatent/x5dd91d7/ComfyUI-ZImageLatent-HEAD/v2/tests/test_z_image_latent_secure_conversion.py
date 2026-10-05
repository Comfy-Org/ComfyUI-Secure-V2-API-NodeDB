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
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "5dd91d71bff801e5cb1daa56ca5f85d08490e089"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches" / "comfyui-zimagelatent" / "x5dd91d7" / (
    "comfyui-zimagelatent-x5dd91d7"
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
    return _import_package("_secure_z_image_latent_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_z_image_latent_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(
                node_class, "SDK_PERMISSIONS", (),
            ) or ()),
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


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_pinned_actual_loader_census_entrypoint_and_schema_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "1 supported, 0 rejected, 0 pending" in report
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"ZImageLatent"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"ZImageLatent"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]

    pristine_nodes = sys.modules[f"{pristine.__name__}.nodes"]
    assert pristine_nodes.NODE_DISPLAY_NAME_MAPPINGS == {
        "ZImageLatent": "Z Image Latent",
    }
    assert not hasattr(pristine, "NODE_DISPLAY_NAME_MAPPINGS")
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == (
        pristine_nodes.NODE_DISPLAY_NAME_MAPPINGS
    )

    schema = secure.ZImageLatent.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "ZImageLatent", "Z Image Latent", "Utilities",
    )
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("resolution", "COMBO"), ("batch_size", "INT"),
    ]
    pristine_inputs = pristine.NODE_CLASS_MAPPINGS["ZImageLatent"].INPUT_TYPES()
    assert schema.inputs[0].options == pristine_inputs["required"]["resolution"][0]
    assert len(schema.inputs[0].options) == 33
    assert schema.inputs[0].default is None
    assert (schema.inputs[1].default, schema.inputs[1].min,
            schema.inputs[1].max, schema.inputs[1].step) == (1, 1, 64, None)
    assert [(item.id, item.io_type, item.display_name) for item in schema.outputs] == [
        ("Latent", "LATENT", "Latent"),
        ("Width", "INT", "Width"),
        ("Height", "INT", "Height"),
    ]
    assert schema.is_output_node is False
    assert secure.ZImageLatent.SDK_REFS is True
    assert secure.ZImageLatent.SDK_PERMISSIONS == ()

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [secure.ZImageLatent]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.z_image_latent_secure_test",
    )
    assert set(loaded.node_mappings) == {"ZImageLatent"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


def test_all_33_ordered_choices_are_preserved_exactly(tmp_path):
    pristine = _pristine(tmp_path)
    options = pristine.NODE_CLASS_MAPPINGS["ZImageLatent"].INPUT_TYPES()[
        "required"
    ]["resolution"][0]
    secure = _secure()
    assert secure.RESOLUTION_OPTIONS == options
    assert secure.RESOLUTION_OPTIONS[:3] == [
        "1024x1024 ( 1:1 )", "1152x896 ( 9:7 )", "896x1152 ( 7:9 )",
    ]
    assert secure.RESOLUTION_OPTIONS[11:14] == [
        "1280x1280 ( 1:1 )", "1440x1120 ( 9:7 )", "1120x1440 ( 7:9 )",
    ]
    assert secure.RESOLUTION_OPTIONS[-3:] == [
        "1152x2048 ( 9:16 )", "2016x864 ( 21:9 )", "864x2016 ( 9:21 )",
    ]


@pytest.mark.parametrize(
    "value",
    ("", "nonsense", "abcx1024", "1024x", "1024x1024x1", "1024 x 1024"),
)
def test_direct_malformed_resolution_parsing_matches_upstream(tmp_path, value):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ZImageLatent"]()
    secure = _secure()
    with pytest.raises(Exception) as upstream_error:
        pristine.generate(value, 1)
    with pytest.raises(type(upstream_error.value)) as secure_error:
        secure.parse_dimensions(value)
    assert str(secure_error.value) == str(upstream_error.value)


def test_real_zero_capability_guest_matches_every_preset_shape_and_value(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ZImageLatent"]()
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "z-image-latent-conversion", guest_runtime_root=V2,
        ).start()
        try:
            cases = [(option, 1) for option in secure.RESOLUTION_OPTIONS]
            cases.extend([
                ("1536x1536 ( 1:1 )", 64),
                ("1025x1039 direct-input", 2),
            ])
            for index, (resolution, batch_size) in enumerate(cases):
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"z-image-{index}",
                    node_id=str(index),
                    node_type=secure.ZImageLatent.__name__,
                    tier="sandbox",
                    node_module=secure.ZImageLatent.__module__,
                    inputs={
                        "resolution": resolution,
                        "batch_size": batch_size,
                    },
                    permissions=(),
                    method="execute",
                )
                result = await session.execute(
                    plan, _runtime(plan, refs), capabilities=(),
                )
                latent_ref, width, height = result.result
                value = await refs.resolve(latent_ref)
                expected_latent, expected_width, expected_height = (
                    pristine.generate(resolution, batch_size)
                )
                samples = value["samples"]
                assert (width, height) == (expected_width, expected_height)
                assert tuple(samples.shape) == tuple(expected_latent["samples"].shape)
                assert samples.dtype == expected_latent["samples"].dtype
                assert torch.equal(samples, expected_latent["samples"].cpu())
                assert torch.count_nonzero(samples).item() == 0
                await refs.release(latent_ref)
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_empty_latent_bounds_fail_closed_before_allocation():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "z-image-latent-bounds", guest_runtime_root=V2,
        ).start()
        try:
            for index, inputs in enumerate((
                {"resolution": "63x63", "batch_size": 1},
                {"resolution": "16400x1024", "batch_size": 1},
                {"resolution": "1024x1024", "batch_size": 0},
                {"resolution": "1024x1024", "batch_size": 65},
            )):
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"z-image-bound-{index}",
                    node_id=str(index),
                    node_type=secure.ZImageLatent.__name__,
                    tier="sandbox",
                    node_module=secure.ZImageLatent.__module__,
                    inputs=inputs,
                    permissions=(),
                    method="execute",
                )
                with pytest.raises(Exception, match="bounded range"):
                    await session.execute(
                        plan, _runtime(plan, refs), capabilities=(),
                    )
            assert refs._table == {}
        finally:
            await session.kill()

    asyncio.run(run())


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    assert "await sdk.LatentRef.empty(" in source
    for forbidden in (
        "import comfy", "import torch", "folder_paths", "PromptServer",
        "requests", "aiohttp", "subprocess", "open(", "os.", "sys.",
        "ctx()", "_from_raw", "from_value",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-zimagelatent" / "x5dd91d7"
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
