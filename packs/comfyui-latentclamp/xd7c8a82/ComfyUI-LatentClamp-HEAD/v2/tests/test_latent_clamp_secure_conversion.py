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
COMMIT = "d7c8a82d08328edfac2d944841a7ed4172b837fa"
TREE = "d805a4e21a0f616b49146707daf0021aa57f4801"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
NODE_ID = "LatentClamp"
PRISTINE_FILES = {
    ".github/workflows/publish_action.yml",
    "README.md",
    "__init__.py",
    "pyproject.toml",
}
PAIR = PACK_DB / "patches/comfyui-latentclamp/xd7c8a82/comfyui-latentclamp-xd7c8a82"

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

import execution
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
    return _import_package("_secure_latent_clamp_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_latent_clamp_test", root)


def _manifest(pack) -> dict:
    node = pack.NODE_CLASS_MAPPINGS[NODE_ID]
    return {
        "format": FORMAT,
        "nodes": {
            NODE_ID: {
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
                "permissions": ["raw"],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": False,
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


def _inputs(samples: dict, **overrides):
    values = {
        "samples": samples,
        "min": -1.0,
        "max": 1.0,
        "inside_multiplier": 1.0,
        "outside_multiplier": 0.5,
        "extra_noise": 0.0,
    }
    values.update(overrides)
    return values


def test_actual_loader_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert TREE == "d805a4e21a0f616b49146707daf0021aa57f4801"
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert pristine.NODE_CLASS_MAPPINGS == {NODE_ID: pristine.LatentClamp}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "Latent Clamp"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert set(secure.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "Latent Clamp"}
    assert not hasattr(secure, "WEB_DIRECTORY")
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()

    old = pristine.LatentClamp
    node = secure.LatentClamp
    schema = node.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        NODE_ID,
        "Latent Clamp",
        old.CATEGORY,
    )
    old_inputs = old.INPUT_TYPES()["required"]
    assert [item.id for item in schema.inputs] == list(old_inputs)
    for item in schema.inputs:
        declaration = old_inputs[item.id]
        old_type = declaration[0]
        metadata = declaration[1] if len(declaration) > 1 else {}
        assert item.io_type == old_type
        for field in ("default", "min", "max", "step", "tooltip"):
            if field in metadata:
                assert getattr(item, field) == metadata[field]
    assert [(item.id, item.io_type, item.display_name) for item in schema.outputs] == [
        ("samples", "LATENT", "samples"),
    ]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.latent_clamp_secure_test",
    )
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.frontend_permissions == frozenset()
    assert loaded.web_directory is None
    assert not loaded.routes
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"min": -0.25, "max": 0.5, "inside_multiplier": 2.0, "outside_multiplier": 0.1},
        {
            "min": 0.75,
            "max": -0.75,
            "inside_multiplier": 0.25,
            "outside_multiplier": 1.5,
        },
        {
            "min": -10.0,
            "max": 10.0,
            "inside_multiplier": 0.0,
            "outside_multiplier": 10.0,
        },
    ],
)
def test_thresholds_overlap_and_multiplier_edges_match_pristine(
    tmp_path,
    overrides,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    tensor = torch.tensor(
        [-2.0, -1.0, -0.75, -0.25, 0.0, 0.5, 0.75, 1.0, 2.0],
        dtype=torch.float64,
    ).reshape(1, 1, 3, 3)
    latent = {"samples": tensor, "batch_index": [17], "marker": "kept"}
    values = _inputs(latent, **overrides)
    expected = pristine.LatentClamp().op(**values)[0]
    actual = secure.LatentClamp.execute(**values).result[0]
    assert torch.equal(actual["samples"], expected["samples"])
    assert actual["samples"].dtype == tensor.dtype
    assert actual["samples"].device == tensor.device
    assert actual["batch_index"] is latent["batch_index"]
    assert actual["marker"] == "kept"
    assert actual is not latent
    assert latent["samples"] is tensor


@pytest.mark.parametrize(
    "seed,inside,outside,noise",
    [(0, 1.0, 0.5, 1.0), (42, 0.0, 1.0, 2.5), (2**31, 1.75, 0.25, 100.0)],
)
def test_seeded_gaussian_noise_path_is_exactly_differential(
    tmp_path,
    seed,
    inside,
    outside,
    noise,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    tensor = torch.linspace(-2.0, 2.0, 2 * 4 * 5 * 6).reshape(2, 4, 5, 6)
    values = _inputs(
        {"samples": tensor.clone(), "marker": seed},
        min=-0.4,
        max=0.8,
        inside_multiplier=inside,
        outside_multiplier=outside,
        extra_noise=noise,
    )
    torch.manual_seed(seed)
    expected = pristine.LatentClamp().op(**copy.deepcopy(values))[0]
    torch.manual_seed(seed)
    actual = secure.LatentClamp.execute(**copy.deepcopy(values)).result[0]
    assert torch.equal(actual["samples"], expected["samples"])
    assert actual["marker"] == seed


@pytest.mark.parametrize(
    "samples,match",
    [
        (None, "dictionary"),
        ({}, "tensor"),
        ({"samples": torch.zeros((1, 2), dtype=torch.int64)}, "floating"),
        ({"samples": torch.empty((1, 1, 1, 1, 1, 1, 1), device="meta")}, "rank"),
        ({"samples": torch.empty((1, 16_385), device="meta")}, "dimensions"),
        ({"samples": torch.empty((1, 5, 8192, 8192), device="meta")}, "element"),
    ],
)
def test_malformed_and_excessive_latents_fail_closed(samples, match):
    secure = _secure()
    with pytest.raises((TypeError, ValueError), match=match):
        secure.LatentClamp.execute(**_inputs(samples))


@pytest.mark.parametrize(
    "name,value,match",
    [
        ("min", float("nan"), "finite"),
        ("max", float("inf"), "finite"),
        ("inside_multiplier", -0.1, "finite"),
        ("outside_multiplier", 10.1, "finite"),
        ("extra_noise", 100.1, "finite"),
        ("extra_noise", True, "number"),
    ],
)
def test_invalid_numeric_inputs_fail_closed(name, value, match):
    inputs = _inputs({"samples": torch.zeros((1, 4, 2, 2))})
    inputs[name] = value
    with pytest.raises((TypeError, ValueError), match=match):
        _secure().LatentClamp.execute(**inputs)


def test_real_guest_value_mode_metadata_noise_and_raw_denial():
    secure = _secure()
    tensor = torch.linspace(-2.0, 2.0, 2 * 4 * 5 * 6).reshape(2, 4, 5, 6)
    latent = {"samples": tensor, "batch_index": [7, 9], "marker": "guest"}
    inputs = _inputs(
        latent,
        min=-0.3,
        max=0.7,
        inside_multiplier=0.8,
        outside_multiplier=0.25,
        extra_noise=1.5,
    )

    async def run():
        refs = _sdk.InProcessRefResolver()
        latent_ref = _sdk.LatentRef._wrap(await refs.create("LATENT", latent))
        plan_inputs = dict(inputs)
        plan_inputs["samples"] = latent_ref
        plan = _sdk.ExecutionPlan(
            prompt_id="latent-clamp",
            node_id="1",
            node_type=secure.LatentClamp.__name__,
            tier="sandbox",
            node_module=secure.LatentClamp.__module__,
            inputs=plan_inputs,
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        session = await GuestSession(
            "latent-clamp-conversion",
            guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(
                plan,
                _runtime(plan, refs),
                capabilities=("raw",),
            )
            value = await refs.resolve(result.result[0])
            assert tuple(value["samples"].shape) == tuple(tensor.shape)
            assert value["samples"].dtype == tensor.dtype
            assert torch.isfinite(value["samples"]).all()
            assert not torch.equal(value["samples"], tensor)
            assert value["batch_index"] == [7, 9]
            assert value["marker"] == "guest"
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, _runtime(plan, refs), capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_real_outer_executor_preserves_declared_latent_type_and_metadata():
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.latent_clamp_outer_test",
    )
    node = loaded.node_mappings[NODE_ID]
    assert node.RETURN_TYPES == ["LATENT"]
    tensor = torch.tensor([-2.0, 0.0, 2.0]).reshape(1, 1, 1, 3)
    latent = {"samples": tensor, "marker": "outer"}
    inputs = _inputs(latent)

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "latent-clamp-outer",
                    guest_runtime_root=V2,
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(
                    plan,
                    runtime,
                    capabilities=("raw",),
                )

            async def shutdown(self):
                if self.session is not None:
                    await self.session.kill()

        backend = OuterGuestBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            returns = await execution._async_map_node_over_list(
                prompt_id="latent-clamp-outer",
                unique_id="1",
                obj=node,
                input_data_all={key: [value] for key, value in inputs.items()},
                func=node.FUNCTION,
                v3_data=None,
            )
            output = returns[0]
            assert isinstance(output.result[0], dict)
            assert output.result[0]["marker"] == "outer"
            assert torch.equal(
                output.result[0]["samples"],
                torch.tensor([-1.0, 0.0, 1.0]).reshape(1, 1, 1, 3),
            )
            assert tuple(node.RETURN_TYPES) == ("LATENT",)
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_docs_and_stub_surface_are_exact():
    source = (V2 / "nodes.py").read_text()
    for required in (
        "SDK_REFS = False",
        'SDK_PERMISSIONS = ("raw",)',
        "MAX_ELEMENTS",
        "MAX_DIMENSION",
        "torch.randn_like",
        "io.NodeOutput(",
    ):
        assert required in source
    for forbidden in (
        "import comfy",
        "model_management",
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
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert not (PACK / "LICENSE").exists()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-latentclamp/xd7c8a82"
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
