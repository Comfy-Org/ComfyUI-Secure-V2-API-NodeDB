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
import warnings

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
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = PACK_DB / "patches/mask-analyzer/xd9ef58d/mask-analyzer-xd9ef58d"
IDS = ("MaskAnalyze", "MaskStrategySwitch")
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


def _import(name, root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _import("_mask_analyzer_secure_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import("_mask_analyzer_pristine_test", root)


def _manifest(pack):
    nodes = {}
    for name, node in pack.NODE_CLASS_MAPPINGS.items():
        nodes[name] = {
            "class": name,
            "module": "nodes",
            "permissions": list(node.SDK_PERMISSIONS),
            "sdk_refs": False,
            "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            "methods": {
                key: key in node.__dict__
                for key in (
                    "check_lazy_status",
                    "fingerprint_inputs",
                    "validate_inputs",
                )
            },
        }
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}


def _mask_case(name):
    mask = torch.zeros(32, 48)
    if name == "solid":
        mask[:] = 1
    elif name == "one":
        mask[3:10, 5:12] = 1
    elif name == "diagonal":
        for n in range(10):
            mask[n, n] = 1
    elif name == "many":
        mask[::3, ::3] = 1
    elif name == "wide":
        mask[15:17, :] = 1
    elif name == "tall":
        mask[:, 21:23] = 1
    elif name == "ring":
        mask[3:20, 5:30] = 1
        mask[5:18, 7:28] = 0
    elif name == "threshold":
        mask = torch.tensor([[0.0, 0.499, 0.5, 0.501, 1.0], [0.2, 0.5, 0.1, 0.8, 0.9]])
    elif name == "two":
        mask[3:8, 4:9] = 1
        mask[18:25, 30:41] = 1
    elif name == "random":
        mask = torch.rand((32, 48), generator=torch.Generator().manual_seed(7103))
    elif name == "nonfinite":
        mask[0, :3] = torch.tensor([float("nan"), float("inf"), -float("inf")])
    elif name == "grad":
        mask = torch.linspace(0, 1, 32 * 48).reshape(32, 48).requires_grad_()
    return mask


CASES = (
    "empty",
    "solid",
    "one",
    "diagonal",
    "many",
    "wide",
    "tall",
    "ring",
    "threshold",
    "two",
    "random",
    "nonfinite",
    "grad",
)


def _inputs(mask=None, **overrides):
    values = {
        "mask": _mask_case("two") if mask is None else mask,
        "threshold": 0.5,
        "min_component_area": 1,
        "small_component_area": 10,
        "direct_max_components": 4,
        "overlay_min_components": 9,
        "wide_aspect_overlay": 3.2,
        "small_ratio_overlay": 0.45,
    }
    values.update(overrides)
    return values


def _execute(values, fallback=False):
    pack = _secure()
    if fallback:
        pack.nodes.algorithm.cv2 = None
    else:
        assert pack.nodes.algorithm.cv2 is not None, (
            "native CV2 path must be available for this gate"
        )
    return pack.MaskAnalyze.execute(**values).result


def _equal(actual, expected):
    assert tuple(actual) == tuple(expected)
    assert tuple(type(x) for x in actual) == tuple(type(x) for x in expected)


def test_actual_loader_schema_census_manifest_and_algorithm_identity(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == set(IDS)
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert (V2 / "algorithm.py").read_bytes() == (
        PACK / "mask_analyzer_router.py"
    ).read_bytes()
    assert not hasattr(old, "WEB_DIRECTORY") and not hasattr(new, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    for name in IDS:
        node, legacy = new.NODE_CLASS_MAPPINGS[name], old.NODE_CLASS_MAPPINGS[name]
        schema = node.GET_SCHEMA()
        schema.validate()
        assert (
            schema.node_id == name
            and schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[name]
        )
        assert schema.category == legacy.CATEGORY
        required = legacy.INPUT_TYPES()["required"]
        assert [x.id for x in schema.inputs] == list(required)
        for item in schema.inputs:
            declaration = required[item.id]
            assert item.io_type == declaration[0]
            if len(declaration) > 1:
                for key, value in declaration[1].items():
                    assert getattr(item, key) == value
        assert tuple(x.io_type for x in schema.outputs) == legacy.RETURN_TYPES
        assert tuple(x.display_name for x in schema.outputs) == legacy.RETURN_NAMES
        assert node.SDK_REFS is False and not schema.is_output_node
        assert node.SDK_PERMISSIONS == (("raw",) if name == IDS[0] else ())
    extension = asyncio.run(new.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [
        new.NODE_CLASS_MAPPINGS[x] for x in IDS
    ]
    assert _manifest(new) == json.loads((V2 / "secure-nodes.json").read_text())
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.mask_analyzer_census")
    assert set(loaded.node_mappings) == set(IDS) and loaded.web_directory is None


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("fallback", [False, True])
def test_native_and_numpy_fallback_exact_differentials(tmp_path, case, fallback):
    values = _inputs(_mask_case(case))
    old = _pristine(tmp_path)
    if fallback:
        old.mask_analyzer_router.cv2 = None
    expected = old.NODE_CLASS_MAPPINGS[IDS[0]]().analyze(**values)
    _equal(_execute(values, fallback), expected)
    _equal(_execute(values, not fallback), expected)


@pytest.mark.parametrize(
    "dtype", [torch.float16, torch.float64, torch.bool, torch.uint8, torch.int64]
)
@pytest.mark.parametrize("fallback", [False, True])
def test_dtype_noncontiguous_batch_first_frame_only(tmp_path, dtype, fallback):
    first, other = _mask_case("two").to(dtype), torch.ones(32, 48, dtype=dtype)
    mask = torch.stack([first, other]).transpose(1, 2)
    assert not mask.is_contiguous()
    values = _inputs(mask)
    old = _pristine(tmp_path)
    if fallback:
        old.mask_analyzer_router.cv2 = None
    expected = old.NODE_CLASS_MAPPINGS[IDS[0]]().analyze(**values)
    _equal(_execute(values, fallback), expected)
    _equal(_execute(_inputs(mask[0]), fallback), expected)


@pytest.mark.parametrize(
    "overrides",
    [
        {"threshold": 0.0},
        {"threshold": 1.0},
        {"min_component_area": 100000},
        {"small_component_area": 1},
        {"small_component_area": 100000},
        {"direct_max_components": 1},
        {"overlay_min_components": 1},
        {"wide_aspect_overlay": 1.0},
        {"wide_aspect_overlay": 20.0},
        {"small_ratio_overlay": 0.0},
        {"small_ratio_overlay": 1.0},
    ],
)
def test_control_boundaries_filtering_and_priority_match_pristine(tmp_path, overrides):
    values = _inputs(**overrides)
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS[IDS[0]]().analyze(**values)
    _equal(_execute(values), expected)
    _equal(_execute(values, True), expected)


def test_semantic_connectivity_filter_aspect_strategies_and_score_cap():
    assert _execute(_inputs(torch.zeros(3, 4), small_ratio_overlay=0.0)) == (
        0,
        0,
        0.0,
        0.0,
        0.0,
        "direct",
        False,
    )
    diagonal = _execute(_inputs(torch.eye(10), small_component_area=1))
    assert diagonal[0] == 1 and diagonal[5] == "direct"
    assert _execute(_inputs(_mask_case("two"), small_component_area=1))[5] == "direct"
    five = torch.zeros(12, 40)
    for x in range(5):
        five[1:4, 1 + x * 8 : 4 + x * 8] = 1
    values = _inputs(five, small_component_area=1, wide_aspect_overlay=20.0)
    assert _execute(values)[5] == "simplified"
    assert _execute(_inputs(_mask_case("many")))[5] == "overlay"
    wide = torch.zeros(3, 100)
    wide[1, ::3] = 1
    assert _execute(_inputs(wide))[4] == 100.0
    filtered = _execute(_inputs(wide, min_component_area=100000))
    assert filtered[0] == 0 and filtered[3] == 100.0 and filtered[5] == "overlay"


@pytest.mark.parametrize(
    "strategy",
    [
        "direct",
        "overlay",
        "simplified",
        " OVERLAY\n",
        "SiMpLiFiEd",
        "",
        "unknown",
        "直接",
        "\u2003direct\u2003",
        "😀" * 1024,
    ],
)
def test_scalar_switch_exact_case_whitespace_unknown_and_unicode(tmp_path, strategy):
    values = {
        "strategy": strategy,
        "direct_value": -999999,
        "simplified_value": 17,
        "overlay_value": 999999,
    }
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS[IDS[1]]().pick(**values)
    _equal(_secure().MaskStrategySwitch.execute(**values).result, expected)


@pytest.mark.parametrize(
    "override",
    [
        {"threshold": True},
        {"threshold": -0.1},
        {"threshold": 1.1},
        {"threshold": float("nan")},
        {"threshold": float("inf")},
        {"min_component_area": 0},
        {"min_component_area": 100001},
        {"small_component_area": 2.0},
        {"direct_max_components": 1001},
        {"overlay_min_components": True},
        {"wide_aspect_overlay": 0.9},
        {"wide_aspect_overlay": 20.1},
        {"small_ratio_overlay": -0.1},
        {"small_ratio_overlay": 10**1000},
    ],
)
def test_invalid_controls_fail_closed(override):
    with pytest.raises((TypeError, ValueError)):
        _execute(_inputs(**override))


@pytest.mark.parametrize(
    "mask",
    [
        "mask",
        torch.zeros(2),
        torch.zeros(1, 1, 2, 3),
        torch.zeros(0, 2, 3),
        torch.zeros(65, 2, 3),
        torch.zeros(1, 0, 3),
        torch.zeros(1, 2, 3).to_sparse(),
        torch.zeros(2, 3, dtype=torch.bfloat16),
        torch.zeros(2, 3, dtype=torch.complex64),
        torch.empty(8193, 1, device="meta"),
        torch.empty(1025, 1025, device="meta"),
        torch.empty(64, 1024, 1024, device="meta"),
    ],
)
def test_invalid_masks_and_resource_bounds_fail_before_algorithm(mask, monkeypatch):
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("mask conversion/analysis entered before input validation")

    monkeypatch.setattr(pack.nodes.algorithm.MaskAnalyze, "analyze", forbidden)
    with pytest.raises((TypeError, ValueError)):
        pack.MaskAnalyze.execute(**_inputs(mask))


def test_projected_label_storage_and_dfs_work_reject_before_compute(monkeypatch):
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("binary/labels/DFS entered before projected bounds")

    monkeypatch.setattr(pack.nodes.algorithm.MaskAnalyze, "analyze", forbidden)
    monkeypatch.setattr(pack.nodes, "MAX_LABEL_ELEMENTS", 100)
    with pytest.raises(ValueError, match="label/array"):
        pack.MaskAnalyze.execute(**_inputs())
    monkeypatch.setattr(pack.nodes, "MAX_LABEL_ELEMENTS", 12_582_924)
    monkeypatch.setattr(pack.nodes, "MAX_DFS_WORK", 100)
    with pytest.raises(ValueError, match="DFS work"):
        pack.MaskAnalyze.execute(**_inputs())


@pytest.mark.parametrize(
    "override",
    [
        {"strategy": None},
        {"strategy": "😀" * 1025},
        {"strategy": "a" * 4097},
        {"direct_value": True},
        {"simplified_value": -1000000},
        {"overlay_value": 1000000},
    ],
)
def test_switch_contract_and_byte_bounds(override):
    values = {
        "strategy": "direct",
        "direct_value": 0,
        "simplified_value": 1,
        "overlay_value": 2,
    }
    values.update(override)
    with pytest.raises((TypeError, ValueError)):
        _secure().MaskStrategySwitch.execute(**values)


def test_inputs_rng_and_warning_policy_are_not_mutated():
    values = _inputs(_mask_case("two").requires_grad_())
    before = values["mask"].clone()
    rng, filters = torch.random.get_rng_state().clone(), list(warnings.filters)
    first = _execute(values)
    _equal(_execute(values, True), first)
    _execute(_inputs(_mask_case("wide")))
    _equal(_execute(values), first)
    assert torch.equal(values["mask"], before) and values["mask"].requires_grad
    assert (
        torch.equal(rng, torch.random.get_rng_state()) and warnings.filters == filters
    )


async def _guest(root, node_id, values, label="mask-analyzer", deny=False):
    pack = _import("_mask_analyzer_guest_source", root)
    refs = _sdk.InProcessRefResolver()
    wrapped = dict(values)
    if node_id == IDS[0]:
        wrapped["mask"] = _sdk.MaskRef._wrap(await refs.create("MASK", values["mask"]))
    node = pack.NODE_CLASS_MAPPINGS[node_id]
    permissions = node.SDK_PERMISSIONS
    plan = _sdk.ExecutionPlan(
        prompt_id=label,
        node_id="1",
        node_type=node_id,
        tier="sandbox",
        node_module=node.__module__,
        inputs=wrapped,
        input_mode="values",
        permissions=permissions,
        method="execute",
    )
    runtime = _sdk.Runtime(
        refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps()
    )
    session = await GuestSession(label, guest_runtime_root=root).start()
    try:
        result = await session.execute(plan, runtime, capabilities=permissions)
        assert session.last_guest_pid not in (None, os.getpid())
        if deny:
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
        return result.result
    finally:
        await session.kill()


async def _outer(node_id, values):
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.mask_analyzer_outer_" + node_id
    )
    outer = loaded.node_mappings[node_id]
    expected_types = (
        ("INT", "INT", "FLOAT", "FLOAT", "FLOAT", "STRING", "BOOLEAN")
        if node_id == IDS[0]
        else ("INT",)
    )
    assert tuple(outer.RETURN_TYPES) == expected_types
    previous = _sdk.providers.execution_backend
    permissions = ("raw",) if node_id == IDS[0] else ()

    class Backend:
        session = None

        async def dispatch(self, plan, local_call, runtime):
            self.session = await GuestSession(
                "mask-analyzer-outer", guest_runtime_root=V2
            ).start()
            plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await self.session.execute(plan, runtime, capabilities=permissions)

    backend = Backend()
    _sdk.providers.register_execution_backend(backend)
    try:
        result = await execution._async_map_node_over_list(
            prompt_id="mask-analyzer-outer",
            unique_id="1",
            obj=outer,
            input_data_all={key: [value] for key, value in values.items()},
            func=outer.FUNCTION,
            v3_data=None,
        )
        return result[0].result
    finally:
        _sdk.providers.register_execution_backend(previous)
        if backend.session is not None:
            await backend.session.kill()


@pytest.mark.parametrize("case", ["empty", "one", "many", "threshold", "nonfinite"])
def test_real_guest_raw_denial_and_seven_outer_scalar_outputs(case):
    values = _inputs(_mask_case(case))
    expected = _execute(values)

    async def run():
        _equal(await _guest(V2, IDS[0], values, deny=True), expected)
        _equal(await _outer(IDS[0], values), expected)

    asyncio.run(run())


def test_real_permission_free_switch_guest_and_outer_integer():
    async def run():
        for strategy in (" direct ", "SIMPLIFIED", "overlay", "unknown"):
            values = {
                "strategy": strategy,
                "direct_value": -11,
                "simplified_value": 14,
                "overlay_value": 37,
            }
            expected = _secure().MaskStrategySwitch.execute(**values).result
            _equal(await _guest(V2, IDS[1], values), expected)
        _equal(await _outer(IDS[1], values), expected)

    asyncio.run(run())


def _tree(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_fresh_pack_filesystem_and_guest_need_no_durable_state(tmp_path):
    first, second = tmp_path / "render-one", tmp_path / "render-two"
    shutil.copytree(V2, first)
    shutil.copytree(V2, second)
    values = _inputs(_mask_case("many"))

    async def run():
        expected = _execute(values)
        _equal(await _guest(first, IDS[0], values, label="mask-user-a"), expected)
        _equal(
            await _guest(second, IDS[0], values, label="mask-user-a-fresh"), expected
        )
        other = _inputs(_mask_case("empty"))
        _equal(
            await _guest(second, IDS[0], other, label="mask-user-b"), _execute(other)
        )
        switch = {
            "strategy": expected[5],
            "direct_value": 0,
            "simplified_value": 1,
            "overlay_value": 2,
        }
        _equal(
            await _guest(second, IDS[1], switch, label="mask-switch-fresh"),
            _secure().MaskStrategySwitch.execute(**switch).result,
        )

    asyncio.run(run())
    assert _tree(first) == _tree(second) == _tree(V2)


def test_license_stubs_authority_and_persistence_ledger():
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    for filename, digest in [("comfy-api.d.ts", DTS_SHA), ("comfy-api.pyi", PYI_SHA)]:
        assert hashlib.sha256((V2 / filename).read_bytes()).hexdigest() == digest
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert "d9ef58d14e9d016a8888cb3fae50d2cf1059ab8e" in report
    assert "Persistence disposition: no durable state" in report
    source = "\n".join(
        (V2 / name).read_text() for name in ("__init__.py", "nodes.py", "algorithm.py")
    )
    for forbidden in [
        "folder_paths",
        "comfy.utils",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "os.",
        "sys.",
        "_from_raw",
        "ctx()",
    ]:
        assert forbidden not in source


def test_byte_exact_patch_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf8") == diff
    fresh = tmp_path / "mask-analyzer/xd9ef58d"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_cache_hygiene():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))
