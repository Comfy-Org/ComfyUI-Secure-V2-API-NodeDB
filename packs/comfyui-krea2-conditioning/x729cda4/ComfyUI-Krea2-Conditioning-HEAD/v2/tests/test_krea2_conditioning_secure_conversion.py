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
COMMIT = "729cda4fade982988a375b01928f515458407a5c"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "82dea265a0ae3918ece66547a6e413558c419fbcb0a4cc19d52b3fd74057cc49"
PAIR = PACK_DB / "patches" / "comfyui-krea2-conditioning" / "x729cda4" / (
    "comfyui-krea2-conditioning-x729cda4"
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
    return _import_package("_secure_krea2_test", V2)


def _upstream():
    return _import_package("_upstream_krea2_test", PACK)


def _upstream_nodes():
    package = _upstream()
    return sys.modules[f"{package.__name__}.nodes"]


def _manifest(pack) -> dict:
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


def _assert_same(actual, expected):
    if isinstance(expected, torch.Tensor):
        assert isinstance(actual, torch.Tensor)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        assert actual.dtype == expected.dtype
        return
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            _assert_same(actual[key], expected[key])
        return
    if isinstance(expected, (list, tuple)):
        assert isinstance(actual, type(expected))
        assert len(actual) == len(expected)
        for got, want in zip(actual, expected):
            _assert_same(got, want)
        return
    assert actual == expected


def _sample(dtype=torch.float32, width=24):
    tensor = torch.linspace(-2, 3, 2 * 3 * width, dtype=dtype).reshape(2, 3, width)
    pooled = torch.tensor([[3.0, 4.0]], dtype=dtype)
    return [
        [tensor, {"pooled_output": pooled, "tag": "preserve"}],
        {"nested": tensor.flip(-1), "scalar": 9},
        ("upstream leaves tuples opaque", tensor.clone()),
        "opaque",
    ]


def test_census_schema_manifest_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    upstream = _upstream()
    secure = _secure()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"ConditioningKrea2Rebalance"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"ConditioningKrea2Rebalance"}
    assert not list(PACK.rglob("*.js"))
    extension = asyncio.run(secure.comfy_entrypoint())
    assert [node.GET_SCHEMA().node_id for node in asyncio.run(
        extension.get_node_list())] == ["ConditioningKrea2Rebalance"]
    node = secure.ConditioningKrea2Rebalance
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ("raw",)
    schema = node.GET_SCHEMA()
    assert schema.display_name == "🎛️ Krea 2 Conditioning Control"
    assert [item.id for item in schema.inputs] == [
        "conditioning", "preset", "per_layer_weights", "multiplier",
        "renormalize",
    ]
    assert [item.io_type for item in schema.outputs] == ["CONDITIONING"]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.krea2_conditioning_secure_test")
    assert set(loaded.node_mappings) == {"ConditioningKrea2Rebalance"}
    assert loaded.frontend_permissions == frozenset()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


@pytest.mark.parametrize("preset", ("balanced", "detail", "subtle", "uniform"))
@pytest.mark.parametrize("renormalize", (False, True))
@pytest.mark.parametrize("multiplier", (-0.5, 0.0, 1.0, 3.25))
def test_named_profiles_are_pixel_exact_to_upstream(preset, renormalize, multiplier):
    upstream = _upstream_nodes()
    secure = _secure()
    module = sys.modules[secure.ConditioningKrea2Rebalance.__module__]
    source = _sample()
    actual = module._scale_structure(
        copy.deepcopy(source), multiplier,
        module.PRESET_WEIGHTS[preset], renormalize)
    expected = upstream.scale_conditioning(
        copy.deepcopy(source), multiplier,
        upstream.PRESET_WEIGHTS[preset], renormalize)
    _assert_same(actual, expected)


@pytest.mark.parametrize("text", (
    "1; 2; 3; 4", "-1, 0.5, 2", "1,1,1,1,1,1",
))
def test_custom_weights_and_nondivisible_fallback_match_upstream(text):
    upstream = _upstream_nodes()
    secure = _secure()
    module = sys.modules[secure.ConditioningKrea2Rebalance.__module__]
    weights = module.parse_weights(text)
    assert weights == upstream.parse_weights(text)
    for width in (24, 25):
        source = _sample(dtype=torch.float16, width=width)
        actual = module._scale_structure(source, 1.75, weights, True)
        expected = upstream.scale_conditioning(source, 1.75, weights, True)
        _assert_same(actual, expected)


def test_metadata_is_copied_and_input_is_not_mutated():
    secure = _secure()
    module = sys.modules[secure.ConditioningKrea2Rebalance.__module__]
    source = _sample()
    original_tensor = source[0][0].clone()
    original_metadata = source[0][1]
    output = module._scale_structure(
        source, 1.0, module.PRESET_WEIGHTS["detail"], True)
    torch.testing.assert_close(source[0][0], original_tensor)
    assert output[0][1] == original_metadata
    assert output[0][1] is not original_metadata


def test_invalid_inputs_and_resource_bounds_fail_closed():
    secure = _secure()
    module = sys.modules[secure.ConditioningKrea2Rebalance.__module__]
    for text in ("", "1", "1,nope", "nan,1", "inf,1", "1e9,1"):
        with pytest.raises((TypeError, ValueError)):
            module.parse_weights(text)
    with pytest.raises(ValueError, match="between 2"):
        module.parse_weights("1," * (module.MAX_WEIGHTS + 1))
    with pytest.raises(ValueError, match="too deeply"):
        nested = 0
        for _ in range(module.MAX_DEPTH + 2):
            nested = [nested]
        module._scale_structure(nested, 1, [1, 1], False)
    with pytest.raises(ValueError, match="too large"):
        module._scale_structure(
            torch.empty((1, module.MAX_TENSOR_ELEMENTS + 1), device="meta"),
            1, [1, 1], False)


def test_real_isolated_guest_matches_upstream_and_enforces_raw_capability():
    secure = _secure()
    upstream = _upstream_nodes()
    source = _sample()

    async def run():
        refs = _sdk.InProcessRefResolver()
        cond = _sdk.CondRef._wrap(await refs.create("CONDITIONING", source))
        node = secure.ConditioningKrea2Rebalance
        plan = _sdk.ExecutionPlan(
            prompt_id="krea2-test", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={
                "conditioning": cond,
                "preset": "detail",
                "per_layer_weights": "1,2",
                "multiplier": 1.25,
                "renormalize": True,
            },
            permissions=node.SDK_PERMISSIONS,
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps())
        session = await GuestSession(
            "krea2-conditioning-pack", guest_runtime_root=V2).start()
        try:
            result = await session.execute(
                plan, runtime, capabilities=node.SDK_PERMISSIONS)
            output = await refs.resolve(result.result[0])
            with pytest.raises(Exception, match="raw.*capability"):
                await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    actual, guest_pid = asyncio.run(run())
    expected = upstream.scale_conditioning(
        source, 1.25, upstream.PRESET_WEIGHTS["detail"], True)
    _assert_same(actual, expected)
    assert guest_pid not in (None, os.getpid())


def test_source_contains_no_ambient_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests",
        "subprocess", "open(", "os.", "sys.",
    ):
        assert forbidden not in source
    assert source.count('SDK_PERMISSIONS = ("raw",)') == 1


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-krea2-conditioning" / "x729cda4"
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
