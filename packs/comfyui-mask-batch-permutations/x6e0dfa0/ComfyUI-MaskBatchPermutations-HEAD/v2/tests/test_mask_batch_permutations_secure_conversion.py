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
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = (
    PACK_DB
    / "patches/comfyui-mask-batch-permutations/x6e0dfa0/comfyui-mask-batch-permutations-x6e0dfa0"
)
PRISTINE_FILES = {
    ".gitattributes",
    ".gitignore",
    "LICENSE",
    "README.md",
    "__init__.py",
    "workflow_example.png",
    "workflow_combi.png",
}
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
    return _import("_mask_permutations_secure_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import("_mask_permutations_pristine_test", root)


def _manifest(pack):
    return {
        "format": FORMAT,
        "nodes": {
            name: {
                "class": name,
                "module": "nodes",
                "permissions": ["raw"],
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
            for name, node in pack.NODE_CLASS_MAPPINGS.items()
        },
        "runtime": manifest_declaration(V2),
    }


def _inputs(name, dtype=torch.float32):
    masks = torch.tensor(
        [[[0, 1, 0.5], [1, 1, 0]], [[1, 1, 0], [0, 0.5, 1]]], dtype=dtype
    )
    base = torch.arange(36, dtype=dtype).reshape(2, 2, 3, 3) / 36
    candidates = torch.flip(base, dims=(1, 2))
    if name == "PermuteMaskBatch":
        return {"masks": masks}
    if name == "FlattenAgainstOriginal":
        return {"base_image": base, "candidates": candidates}
    return {"masks": masks, "base_image": base, "candidates": candidates}


def _execute(node, values):
    return node.execute(**values).result[0]


def _equal(actual, expected):
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert actual.device == expected.device
    assert torch.equal(actual, expected)


def test_actual_loader_exact_schema_manifest_and_resource_census(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert (
        set(old.NODE_CLASS_MAPPINGS)
        == set(new.NODE_CLASS_MAPPINGS)
        == {"PermuteMaskBatch", "CombinatorialDetailer", "FlattenAgainstOriginal"}
    )
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert {
        p.relative_to(PACK).as_posix()
        for p in PACK.rglob("*")
        if p.is_file() and "v2" not in p.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert not hasattr(old, "WEB_DIRECTORY") and not hasattr(new, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    for name, node in new.NODE_CLASS_MAPPINGS.items():
        legacy = old.NODE_CLASS_MAPPINGS[name]
        schema = node.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == name
        assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[name]
        assert schema.category == legacy.CATEGORY
        assert [x.id for x in schema.inputs] == list(legacy.INPUT_TYPES()["required"])
        assert tuple(x.io_type for x in schema.inputs) == tuple(
            x[0] for x in legacy.INPUT_TYPES()["required"].values()
        )
        assert tuple(x.io_type for x in schema.outputs) == legacy.RETURN_TYPES
        assert tuple(x.display_name for x in schema.outputs) == legacy.RETURN_NAMES
        assert not schema.is_output_node
        assert node.SDK_REFS is False and node.SDK_PERMISSIONS == ("raw",)
    assert _manifest(new) == json.loads((V2 / "secure-nodes.json").read_text())
    extension = asyncio.run(new.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == list(
        new.NODE_CLASS_MAPPINGS.values()
    )
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.mask_permutations_census"
    )
    assert set(loaded.node_mappings) == set(new.NODE_CLASS_MAPPINGS)
    assert loaded.web_directory is None


@pytest.mark.parametrize(
    "name", ["PermuteMaskBatch", "CombinatorialDetailer", "FlattenAgainstOriginal"]
)
@pytest.mark.parametrize("dtype", [torch.float16, torch.float32, torch.float64])
def test_bit_exact_differential_inputs_dtype_and_rng_isolation(tmp_path, name, dtype):
    old, new = _pristine(tmp_path), _secure()
    values = _inputs(name, dtype)
    copies = {key: value.clone() for key, value in values.items()}
    rng = torch.random.get_rng_state().clone()
    node = old.NODE_CLASS_MAPPINGS[name]
    expected = getattr(node(), node.FUNCTION)(**values)[0]
    _equal(_execute(new.NODE_CLASS_MAPPINGS[name], values), expected)
    _equal(_execute(new.NODE_CLASS_MAPPINGS[name], values), expected)
    for key, original in copies.items():
        assert torch.equal(original, values[key])
    assert torch.equal(rng, torch.random.get_rng_state())


@pytest.mark.parametrize("mask_count", [1, 3, 5])
def test_larger_mask_enumerations_are_exact(tmp_path, mask_count):
    old, new = _pristine(tmp_path), _secure()
    masks = (
        torch.arange(mask_count * 6, dtype=torch.float32).reshape(mask_count, 2, 3) / 20
    )
    expected = old.PermuteMaskBatch().permuteMaskBatch(masks)[0]
    _equal(_execute(new.PermuteMaskBatch, {"masks": masks}), expected)
    assert expected.shape[0] == 2**mask_count


@pytest.mark.parametrize(
    "name", ["PermuteMaskBatch", "CombinatorialDetailer", "FlattenAgainstOriginal"]
)
def test_noncontiguous_and_mixed_float_inputs_match_pristine(tmp_path, name):
    old, new = _pristine(tmp_path), _secure()
    values = _inputs(name)
    for key, value in values.items():
        values[key] = value.transpose(1, 2)
        assert not values[key].is_contiguous()
    if name == "CombinatorialDetailer":
        values["candidates"] = values["candidates"].to(torch.float64)
    legacy = old.NODE_CLASS_MAPPINGS[name]
    expected = getattr(legacy(), legacy.FUNCTION)(**values)[0]
    _equal(_execute(new.NODE_CLASS_MAPPINGS[name], values), expected)


def test_flatten_mixed_dtype_failure_is_not_turned_into_success(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    values = _inputs("FlattenAgainstOriginal")
    values["candidates"] = values["candidates"].double()
    base = values["base_image"].clone()
    with pytest.raises(RuntimeError, match="dtypes match"):
        old.FlattenAgainstOriginal().flattenAgainstOriginal(**values)
    with pytest.raises(RuntimeError, match="dtypes match"):
        _execute(new.FlattenAgainstOriginal, values)
    assert torch.equal(base, values["base_image"])


def test_flatten_order_is_observable_and_rgb_blue_is_alpha():
    node = _secure().FlattenAgainstOriginal
    base = torch.zeros((1, 1, 1, 3))
    candidates = torch.tensor([[[[0.2, 0.2, 0.5]]], [[[0.8, 0.8, 0.5]]]])
    forward = _execute(node, {"base_image": base, "candidates": candidates})
    reverse = _execute(node, {"base_image": base, "candidates": candidates.flip(0)})
    assert forward[0, 0, 0, 0].item() == pytest.approx(0.45)
    assert reverse[0, 0, 0, 0].item() == pytest.approx(0.30)
    assert not torch.equal(forward, reverse)


def test_mask_bit_order_and_empty_mask_batch():
    node = _secure().PermuteMaskBatch
    masks = _inputs("PermuteMaskBatch")["masks"]
    result = _execute(node, {"masks": masks})
    assert result.shape == (4, 2, 3)
    assert torch.equal(result[0], torch.zeros_like(masks[0]))
    assert torch.equal(result[1], masks[0])
    assert torch.equal(result[2], masks[1])
    assert torch.equal(result[3], masks.max(dim=0)[0])
    assert torch.equal(_execute(node, {"masks": masks[:0]}), torch.zeros((1, 2, 3)))


def test_detailer_order_overlap_exact_one_and_first_base():
    node = _secure().CombinatorialDetailer
    masks = torch.tensor([[[1.0, 0.5], [0.0, 1.0]], [[1.0, 0.0], [1.0, 0.0]]])
    base = torch.stack((torch.zeros((2, 2, 3)), torch.full((2, 2, 3), 0.8)))
    candidates = torch.stack((torch.full((2, 2, 3), 0.2), torch.full((2, 2, 3), 0.7)))
    result = _execute(
        node, {"masks": masks, "base_image": base, "candidates": candidates}
    )
    assert result.shape == (9, 2, 2, 3)
    assert torch.equal(result[0], base[0])
    assert result[1, 0, 0, 0] == candidates[0, 0, 0, 0]
    assert result[1, 0, 1, 0] == 0  # fractional masks do not select
    assert result[4, 0, 0, 0] == candidates[0, 0, 0, 0]
    assert result[7, 0, 0, 0] == candidates[1, 0, 0, 0]  # later mask wins
    _equal(
        result,
        _execute(
            node, {"masks": masks, "base_image": base[:1], "candidates": candidates}
        ),
    )
    _equal(
        base[:1],
        _execute(
            node, {"masks": masks[:0], "base_image": base, "candidates": candidates}
        ),
    )
    _equal(
        base[:1],
        _execute(
            node, {"masks": masks, "base_image": base, "candidates": candidates[:0]}
        ),
    )


@pytest.mark.parametrize("base_channels", [3, 4])
@pytest.mark.parametrize("candidate_channels", [3, 4])
@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_flatten_alpha_rgb_quirk_candidate_order_and_empty(
    tmp_path, base_channels, candidate_channels, alpha
):
    old, new = _pristine(tmp_path), _secure()
    base = torch.linspace(0, 1, 2 * 3 * 4 * base_channels).reshape(
        2, 3, 4, base_channels
    )
    if base_channels == 4:
        base[..., -1] = alpha
    candidates = torch.linspace(1, 0, 2 * 3 * 4 * candidate_channels).reshape(
        2, 3, 4, candidate_channels
    )
    candidates[..., -1] = alpha
    for candidate_batch in (candidates, candidates.flip(0), candidates[:0]):
        values = {"base_image": base, "candidates": candidate_batch}
        expected = old.FlattenAgainstOriginal().flattenAgainstOriginal(**values)[0]
        _equal(_execute(new.FlattenAgainstOriginal, values), expected)
    if alpha == 0 and base_channels == 4:
        assert (
            torch.count_nonzero(
                _execute(
                    new.FlattenAgainstOriginal,
                    {"base_image": base, "candidates": candidates},
                )
            )
            == 0
        )


@pytest.mark.parametrize(
    "name,key,value",
    [
        ("PermuteMaskBatch", "masks", "not a tensor"),
        ("PermuteMaskBatch", "masks", torch.zeros(2, 3)),
        ("PermuteMaskBatch", "masks", torch.zeros(2, 0, 3)),
        ("PermuteMaskBatch", "masks", torch.ones(2, 3, 3, dtype=torch.int64)),
        ("PermuteMaskBatch", "masks", torch.full((2, 3, 3), float("nan"))),
        ("PermuteMaskBatch", "masks", torch.full((2, 3, 3), float("inf"))),
        ("PermuteMaskBatch", "masks", torch.zeros(13, 2, 3)),
        ("CombinatorialDetailer", "base_image", torch.zeros(1, 2, 3, 4)),
        ("CombinatorialDetailer", "base_image", torch.zeros(0, 2, 3, 3)),
        ("CombinatorialDetailer", "masks", torch.zeros(1, 4, 3)),
        ("FlattenAgainstOriginal", "candidates", torch.zeros(65, 2, 3, 3)),
        ("FlattenAgainstOriginal", "candidates", torch.zeros(2, 4, 3, 3)),
        ("FlattenAgainstOriginal", "base_image", torch.zeros(1, 2, 3, 2)),
    ],
)
def test_malformed_inputs_reject(name, key, value):
    values = _inputs(name)
    values[key] = value
    with pytest.raises((ValueError, TypeError)):
        _execute(_secure().NODE_CLASS_MAPPINGS[name], values)


@pytest.mark.parametrize(
    "name", ["PermuteMaskBatch", "CombinatorialDetailer", "FlattenAgainstOriginal"]
)
def test_resource_rejection_precedes_algorithm(monkeypatch, name):
    secure = _secure()
    legacy = getattr(secure.nodes.algorithm, name)
    function = legacy.FUNCTION

    def forbidden(*args, **kwargs):
        pytest.fail("algorithm entered before bounds check")

    monkeypatch.setattr(legacy, function, forbidden)
    values = _inputs(name)
    monkeypatch.setattr(secure.nodes, "MAX_ELEMENTS", 8)
    with pytest.raises(ValueError, match="bound"):
        _execute(secure.NODE_CLASS_MAPPINGS[name], values)
    monkeypatch.setattr(secure.nodes, "MAX_ELEMENTS", 16_777_216)
    monkeypatch.setattr(secure.nodes, "MAX_COMBINATIONS", 1)
    with pytest.raises(ValueError, match="bound"):
        _execute(secure.NODE_CLASS_MAPPINGS[name], values)
    monkeypatch.setattr(secure.nodes, "MAX_COMBINATIONS", 4096)
    monkeypatch.setattr(secure.nodes, "MAX_WORK", 1)
    with pytest.raises(ValueError, match="work"):
        _execute(secure.NODE_CLASS_MAPPINGS[name], values)


def test_exponential_output_rejected_before_allocation(monkeypatch):
    secure = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("Torch output allocation attempted")

    monkeypatch.setattr(secure.nodes.algorithm.torch, "zeros", forbidden)
    masks = torch.ones((12, 128, 128))
    with pytest.raises(ValueError, match="output"):
        _execute(secure.PermuteMaskBatch, {"masks": masks})
    with pytest.raises(ValueError, match="output"):
        _execute(
            secure.CombinatorialDetailer,
            {
                "masks": torch.ones((12, 2, 3)),
                "base_image": torch.ones((1, 2, 3, 3)),
                "candidates": torch.ones((64, 2, 3, 3)),
            },
        )


@pytest.mark.parametrize(
    "name", ["PermuteMaskBatch", "CombinatorialDetailer", "FlattenAgainstOriginal"]
)
def test_real_guest_raw_denial_and_outer_declared_tensor_types(name):
    secure = _secure()
    node = secure.NODE_CLASS_MAPPINGS[name]
    values = _inputs(name)
    expected = _execute(node, values)

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "mask-permutation-test", guest_runtime_root=V2
        ).start()
        try:
            wrapped = {}
            for key, value in values.items():
                kind = "MASK" if key == "masks" else "IMAGE"
                cls = _sdk.MaskRef if kind == "MASK" else _sdk.ImageRef
                wrapped[key] = cls._wrap(await refs.create(kind, value))
            plan = _sdk.ExecutionPlan(
                prompt_id="mask-permutations",
                node_id="1",
                node_type=name,
                tier="sandbox",
                node_module=node.__module__,
                inputs=wrapped,
                input_mode="values",
                permissions=("raw",),
                method="execute",
            )
            runtime = _sdk.Runtime(
                refs=refs,
                ctx=_sdk.InProcessCtxProvider().build(plan),
                ops=_sdk.InProcessOps(),
            )
            result = await session.execute(plan, runtime, capabilities=("raw",))
            _equal(await refs.resolve(result.result[0]), expected)
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

        loaded = packdb.load_pack(
            SNAPSHOT, mount_name="custom_nodes.mask_permutations_outer_" + name
        )
        outer = loaded.node_mappings[name]
        assert tuple(outer.RETURN_TYPES) == (
            ("MASK",) if name == "PermuteMaskBatch" else ("IMAGE",)
        )
        previous = _sdk.providers.execution_backend

        class Backend:
            session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "mask-permutations-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            result = await execution._async_map_node_over_list(
                prompt_id="mask-permutations-outer",
                unique_id="1",
                obj=outer,
                input_data_all={k: [v] for k, v in values.items()},
                func=outer.FUNCTION,
                v3_data=None,
            )
            _equal(result[0].result[0], expected)
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()

    asyncio.run(run())


def test_license_algorithm_stubs_authority_and_pin():
    assert (PACK / "__init__.py").read_bytes() == (V2 / "algorithm.py").read_bytes()
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    for filename, digest in [("comfy-api.d.ts", DTS_SHA), ("comfy-api.pyi", PYI_SHA)]:
        assert hashlib.sha256((V2 / filename).read_bytes()).hexdigest() == digest
    assert (
        "6e0dfa07a139f49bb5e8d20799e1e24598208820"
        in (V2 / "SECURE_CONVERSION.md").read_text()
    )
    source = (V2 / "nodes.py").read_text() + (V2 / "algorithm.py").read_text()
    for forbidden in [
        "folder_paths",
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


def test_patch_roundtrip_byte_exact(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf8") == diff
    fresh = tmp_path / "comfyui-mask-batch-permutations/x6e0dfa0"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert {
        p.relative_to(rebuilt): p.read_bytes()
        for p in rebuilt.rglob("*")
        if p.is_file()
    } == {p.relative_to(V2): p.read_bytes() for p in V2.rglob("*") if p.is_file()}


def test_no_cache_artifacts():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))
