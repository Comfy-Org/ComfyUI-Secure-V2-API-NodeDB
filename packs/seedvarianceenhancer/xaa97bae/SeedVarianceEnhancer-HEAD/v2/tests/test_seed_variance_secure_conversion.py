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
COMMIT = "aa97baee8bacbe0dd702e419eb6c39505b631cc3"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "82dea265a0ae3918ece66547a6e413558c419fbcb0a4cc19d52b3fd74057cc49"
PAIR = PACK_DB / "patches" / "seedvarianceenhancer" / "xaa97bae" / (
    "seedvarianceenhancer-xaa97bae"
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
    return _import_package("_secure_seed_variance_test", V2)


def _upstream():
    return _import_package("_upstream_seed_variance_test", PACK)


def _upstream_node():
    package = _upstream()
    module = sys.modules[f"{package.__name__}.seed_variance_enhancer"]
    return module.SeedVarianceEnhancer()


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


def _conditioning(rows=1):
    first = torch.linspace(-1, 1, 1 * 6 * 8).reshape(1, 6, 8)
    first[:, 5] = 0
    result = [[first, {"SVH_tag": "clean", "pooled_output": torch.ones(1, 4)}]]
    if rows == 2:
        second = torch.linspace(2, -2, 1 * 6 * 8).reshape(1, 6, 8)
        second[:, 4:] = 0
        result.append([second, {"SVH_tag": "noisy", "marker": "second"}])
    return result


def _assert_same(actual, expected):
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        torch.testing.assert_close(got[0], want[0], rtol=0, atol=0)
        assert got[1].keys() == want[1].keys()
        for key in want[1]:
            if isinstance(want[1][key], torch.Tensor):
                torch.testing.assert_close(got[1][key], want[1][key])
            else:
                assert got[1][key] == want[1][key]


def test_census_schema_manifest_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert set(_upstream().NODE_CLASS_MAPPINGS) == {"SeedVarianceEnhancer"}
    secure = _secure()
    assert set(secure.NODE_CLASS_MAPPINGS) == {"SeedVarianceEnhancer"}
    assert not list(PACK.rglob("*.js"))
    extension = asyncio.run(secure.comfy_entrypoint())
    assert [node.GET_SCHEMA().node_id for node in asyncio.run(
        extension.get_node_list())] == ["SeedVarianceEnhancer"]
    node = secure.SeedVarianceEnhancer
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ("raw",)
    schema = node.GET_SCHEMA()
    assert [item.id for item in schema.inputs] == [
        "conditioning", "randomize_percent", "strength", "noise_insert",
        "steps_switchover_percent", "seed", "mask_starts_at",
        "mask_percent", "log_to_console",
    ]
    assert [item.io_type for item in schema.outputs] == ["CONDITIONING"]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.seed_variance_secure_test")
    assert set(loaded.node_mappings) == {"SeedVarianceEnhancer"}
    assert loaded.frontend_permissions == frozenset()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


@pytest.mark.parametrize("rows", (1, 2))
@pytest.mark.parametrize("mode", (
    "noise on beginning steps", "noise on ending steps", "noise on all steps",
))
@pytest.mark.parametrize("mask_start", ("beginning", "end"))
@pytest.mark.parametrize("mask_percent", (0.0, 33.0, 75.0))
def test_noise_outputs_are_exactly_differential(
    rows, mode, mask_start, mask_percent,
):
    source = _conditioning(rows)
    upstream = _upstream_node()
    secure = _secure().SeedVarianceEnhancer()
    args = (37.0, 0.25, mode, 41.0, 123456, mask_start, mask_percent, False)
    expected = upstream.randomize_conditioning(copy.deepcopy(source), *args)[0]
    actual = secure._randomize_value(copy.deepcopy(source), *args)[0]
    _assert_same(actual, expected)


@pytest.mark.parametrize("strength,mode", (
    (0.0, "noise on all steps"),
    (20.0, "disabled"),
))
def test_passthrough_modes_match_upstream_without_copying(strength, mode):
    source = _conditioning(2)
    upstream = _upstream_node()
    secure = _secure().SeedVarianceEnhancer()
    args = (50.0, strength, mode, 20.0, 9, "beginning", 0.0, False)
    expected = upstream.randomize_conditioning(source, *args)[0]
    actual = secure._randomize_value(source, *args)[0]
    assert actual is source
    assert expected is source


def test_legacy_v21_seed_mode_and_metadata_ranges_match():
    source = _conditioning(2)
    args = (
        65.0, 1_000_000_004.5, "noise on ending steps", 72.0, 777,
        "end", 20.0, False,
    )
    expected = _upstream_node().randomize_conditioning(
        copy.deepcopy(source), *args)[0]
    actual = _secure().SeedVarianceEnhancer()._randomize_value(
        copy.deepcopy(source), *args)[0]
    _assert_same(actual, expected)


def test_real_isolated_guest_matches_upstream_and_enforces_raw_capability():
    secure = _secure()
    source = _conditioning(2)

    async def run():
        refs = _sdk.InProcessRefResolver()
        cond = _sdk.CondRef._wrap(await refs.create("CONDITIONING", source))
        node = secure.SeedVarianceEnhancer
        plan = _sdk.ExecutionPlan(
            prompt_id="seed-variance-test", node_id="1",
            node_type=node.__name__, tier="sandbox",
            node_module=node.__module__,
            inputs={
                "conditioning": cond, "randomize_percent": 50.0,
                "strength": 0.75, "noise_insert": "noise on beginning steps",
                "steps_switchover_percent": 25.0, "seed": 42,
                "mask_starts_at": "beginning", "mask_percent": 16.0,
                "log_to_console": False,
            },
            permissions=node.SDK_PERMISSIONS,
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps())
        session = await GuestSession(
            "seed-variance-pack", guest_runtime_root=V2).start()
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
    expected = _upstream_node().randomize_conditioning(
        source, 50.0, 0.75, "noise on beginning steps", 25.0, 42,
        "beginning", 16.0, False)[0]
    _assert_same(actual, expected)
    assert guest_pid not in (None, os.getpid())


def test_malformed_inputs_and_resource_bounds_fail_closed():
    secure = _secure()
    node = secure.SeedVarianceEnhancer

    async def call(source, **overrides):
        refs = _sdk.InProcessRefResolver()
        ref = _sdk.CondRef._wrap(await refs.create("CONDITIONING", source))
        values = dict(
            conditioning=ref, randomize_percent=50.0, strength=1.0,
            noise_insert="noise on all steps", steps_switchover_percent=20.0,
            seed=0, mask_starts_at="beginning", mask_percent=0.0,
            log_to_console=False,
        )
        values.update(overrides)
        plan = _sdk.ExecutionPlan(
            prompt_id="bounds", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__, inputs=values,
            permissions=node.SDK_PERMISSIONS)
        with _sdk.bind_runtime(
            refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()
        ):
            return await node.execute(**values)

    with pytest.raises(ValueError, match="bounded list"):
        asyncio.run(call("not conditioning"))
    with pytest.raises(ValueError, match="bounded BxSxD"):
        asyncio.run(call([[torch.empty(
            (1, 1, 268_435_457), device="meta"), {}]]))
    with pytest.raises(ValueError, match="finite"):
        asyncio.run(call(_conditioning(), strength=float("nan")))
    with pytest.raises(ValueError, match="unknown noise"):
        asyncio.run(call(_conditioning(), noise_insert="surprise"))
    with pytest.raises(ValueError, match="seed"):
        asyncio.run(call(_conditioning(), seed=-1))


def test_source_contains_no_ambient_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "import nodes", "node_helpers", "folder_paths",
        "PromptServer", "requests", "subprocess", "open(", "os.", "sys.",
    ):
        assert forbidden not in source
    assert source.count('SDK_PERMISSIONS = ("raw",)') == 1


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "seedvarianceenhancer" / "xaa97bae"
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
