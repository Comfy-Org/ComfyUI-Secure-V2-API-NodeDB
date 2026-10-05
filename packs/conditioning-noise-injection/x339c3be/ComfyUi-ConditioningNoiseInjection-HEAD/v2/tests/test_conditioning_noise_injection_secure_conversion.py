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
COMMIT = "339c3be4ffaa67a2807e86112a2143620d878b6f"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / (
    "patches/conditioning-noise-injection/x339c3be/"
    "conditioning-noise-injection-x339c3be"
)

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
    return _import_package("_secure_conditioning_noise_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_conditioning_noise_test", root)


def _manifest(pack):
    node = pack.NODE_CLASS_MAPPINGS["ConditioningNoiseInjection"]
    return {
        "format": FORMAT,
        "nodes": {
            "ConditioningNoiseInjection": {
                "module": "nodes",
                "class": "ConditioningNoiseInjection",
                "sdk_refs": True,
                "permissions": ["raw"],
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "validate_inputs", "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


def _prompt(seed=123, batch=3):
    return {
        "noise": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed},
        },
        "latent": {
            "class_type": "EmptyLatentImage",
            "inputs": {"batch_size": batch},
        },
        "sampler": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["noise", 0],
                "latent_image": ["latent", 0],
            },
        },
    }


def _compare_conditioning(actual, expected):
    assert len(actual) == len(expected)
    for actual_row, expected_row in zip(actual, expected, strict=True):
        torch.testing.assert_close(actual_row[0], expected_row[0], rtol=0, atol=0)
        assert actual_row[1] == expected_row[1]


def test_census_schema_manifest_and_authority_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"ConditioningNoiseInjection"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"ConditioningNoiseInjection"}
    assert pristine.WEB_DIRECTORY == "./js"
    assert not hasattr(secure, "WEB_DIRECTORY")
    schema = secure.ConditioningNoiseInjection.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "ConditioningNoiseInjection", "Conditioning Noise Injection",
        "advanced/conditioning",
    )
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("conditioning", "CONDITIONING"),
        ("threshold", "FLOAT"),
        ("strength", "FLOAT"),
    ]
    assert [item.io_type for item in schema.outputs] == ["CONDITIONING"]
    assert [item.value for item in schema.hidden] == ["PROMPT"]
    assert secure.ConditioningNoiseInjection.SDK_PERMISSIONS == ("raw",)
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.conditioning_noise_secure_test",
    )
    assert set(loaded.node_mappings) == {"ConditioningNoiseInjection"}
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


def test_sampler_scan_preserves_legacy_precedence_and_defaults():
    secure = _secure()
    assert secure.nodes.workflow_parameters(_prompt(991, 7)) == (991, 7)
    standard = {
        "model": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "latent": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 4}},
        "sampler": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["model", 0], "latent_image": ["latent", 0],
                "noise_seed": 55,
            },
        },
    }
    assert secure.nodes.workflow_parameters(standard) == (55, 4)
    assert secure.nodes.workflow_parameters({}) == (0, 1)
    assert secure.nodes.workflow_parameters({
        "sampler": {
            "class_type": "KSampler", "inputs": {"seed": 7},
        },
    }) == (0, 1)
    assert secure.nodes.workflow_parameters(_prompt(-1, 9999)) == (0, 1)


@pytest.mark.parametrize("threshold", [0.0, 0.2, 1.0])
@pytest.mark.parametrize("batch", [1, 3])
def test_tensor_algorithm_is_pixel_exact_to_upstream(tmp_path, threshold, batch):
    pristine = _pristine(tmp_path).ConditioningNoiseInjection()
    secure = _secure()
    conditioning = [
        [
            torch.linspace(-1, 1, 24, dtype=torch.float32).reshape(1, 3, 8),
            {"start_percent": 0.1, "end_percent": 0.9, "tag": "keep"},
        ],
        [torch.arange(12, dtype=torch.float32).reshape(1, 2, 6), {"x": 2}],
    ]
    expected = pristine.inject_noise(
        copy.deepcopy(conditioning), threshold, 2.5,
        seed_from_js=404, batch_size_from_js=batch,
    )[0]
    actual = secure.nodes.inject_noise(
        copy.deepcopy(conditioning), threshold, 2.5, 404, batch,
    )
    _compare_conditioning(actual, expected)


def test_local_generator_does_not_mutate_process_rng():
    secure = _secure()
    conditioning = [[torch.zeros((1, 2, 4)), {}]]
    torch.manual_seed(1234)
    before = torch.random.get_rng_state().clone()
    secure.nodes.inject_noise(conditioning, 0.3, 4.0, 99, 2)
    after = torch.random.get_rng_state()
    assert torch.equal(before, after)


def test_fingerprint_uses_derived_sampler_values():
    node = _secure().ConditioningNoiseInjection
    conditioning = object()
    assert node.fingerprint_inputs(
        conditioning, 0.25, 9.0, _prompt(777, 5),
    ) == "777_5_0.25_9.0"


def test_bounds_fail_before_expensive_compute():
    secure = _secure()

    class Ref:
        async def value(self):
            return [[torch.zeros((1, 2, 3)), {}]]

    with pytest.raises(ValueError, match="threshold"):
        asyncio.run(secure.ConditioningNoiseInjection.execute(
            Ref(), float("nan"), 1.0, _prompt(),
        ))
    with pytest.raises(ValueError, match="conditioning batch"):
        asyncio.run(secure.ConditioningNoiseInjection.execute(
            type("Ref", (), {"value": lambda self: asyncio.sleep(
                0, result=[[torch.zeros((257, 1, 1)), {}]],
            )})(),
            0.2, 1.0, _prompt(),
        ))


def test_real_guest_executes_and_raw_denial_fails_closed():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        conditioning = [[torch.zeros((1, 2, 4)), {"tag": "guest"}]]
        conditioning_ref = _sdk.CondRef._wrap(
            await refs.create("CONDITIONING", conditioning),
        )
        prompt = _prompt(808, 2)
        plan = _sdk.ExecutionPlan(
            prompt_id="conditioning-noise", node_id="1",
            node_type=secure.ConditioningNoiseInjection.__name__, tier="raw",
            node_module=secure.ConditioningNoiseInjection.__module__,
            inputs={
                "conditioning": conditioning_ref, "threshold": 0.2,
                "strength": 3.0, "prompt": prompt,
            },
            permissions=("raw",), method="execute",
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "conditioning-noise-conversion", guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=("raw",))
            actual = await refs.resolve(result.result[0])
            expected = secure.nodes.inject_noise(
                conditioning, 0.2, 3.0, 808, 2,
            )
            _compare_conditioning(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception):
                await session.execute(plan, runtime, capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_contract_assets_and_source_boundary_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    for relative in ("README.md", "workflow_Z-image_turbo.json"):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()
    assert not (PACK / "LICENSE").exists()
    assert not (V2 / "LICENSE").exists()
    assert not (V2 / "js").exists()
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "PromptServer", "folder_paths", "requests", "aiohttp", "subprocess",
        "open(", ".raw()", "queuePrompt", "ctx()",
    ):
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "conditioning-noise-injection" / "x339c3be"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
