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
PAIR = (
    PACK_DB
    / "patches/comfyui-latentorientation/x6134758/comfyui-latentorientation-x6134758"
)
MODES = ("portrait", "landscape", "min square", "max square", "avg square")
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
    return _import("_latent_orientation_secure_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import("_latent_orientation_pristine_test", root)


def _manifest(pack):
    node = pack.LatentOrient
    return {
        "format": FORMAT,
        "nodes": {
            "LatentOrient": {
                "class": "LatentOrient",
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
        },
        "runtime": manifest_declaration(V2),
    }


def _inputs(shape=(2, 4, 5, 8), dtype=torch.float32, mode="portrait"):
    count = 1
    for size in shape:
        count *= size
    tensor = torch.linspace(-2, 2, count, dtype=dtype).reshape(shape)
    return {
        "samples": {
            "samples": tensor,
            "noise_mask": torch.linspace(0, 1, 40).reshape(1, 1, 5, 8),
            "batch_index": [3, 9],
            "marker": {"name": "orientation", "stride": 8},
        },
        "orientation": mode,
    }


def _execute(values):
    return _secure().LatentOrient.execute(**values).result[0]


def _equal(actual, expected):
    assert set(actual) == set(expected)
    for key in actual:
        if isinstance(actual[key], torch.Tensor):
            a, b = actual[key], expected[key]
            assert a.shape == b.shape and a.dtype == b.dtype and a.device == b.device
            torch.testing.assert_close(a, b, rtol=0, atol=0, equal_nan=True)
        else:
            assert actual[key] == expected[key]


def test_actual_loader_schema_manifest_and_algorithm_identity(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert (
        set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {"LatentOrient"}
    )
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert (V2 / "algorithm.py").read_bytes() == (PACK / "__init__.py").read_bytes()
    assert {
        p.relative_to(PACK).as_posix()
        for p in PACK.rglob("*")
        if p.is_file() and "v2" not in p.relative_to(PACK).parts
    } == {
        "__init__.py",
        "README.md",
        "pyproject.toml",
        "example_workflows/install.png",
        ".gitattributes",
        ".github/workflows/publish_action.yml",
    }
    assert not hasattr(old, "WEB_DIRECTORY") and not hasattr(new, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    node = new.LatentOrient
    schema = node.GET_SCHEMA()
    schema.validate()
    legacy = old.NODE_CLASS_MAPPINGS["LatentOrient"]
    assert schema.node_id == "LatentOrient" and schema.display_name == "Orient Latent"
    assert schema.category == legacy.CATEGORY
    required = legacy.INPUT_TYPES()["required"]
    assert [x.id for x in schema.inputs] == list(required)
    assert schema.inputs[0].io_type == required["samples"][0]
    assert list(schema.inputs[1].options) == required["orientation"][0] == list(MODES)
    assert tuple(x.io_type for x in schema.outputs) == legacy.RETURN_TYPES
    assert schema.outputs[0].display_name is None and not schema.is_output_node
    assert node.SDK_REFS is False and node.SDK_PERMISSIONS == ("raw",)
    assert _manifest(new) == json.loads((V2 / "secure-nodes.json").read_text())
    assert asyncio.run(asyncio.run(new.comfy_entrypoint()).get_node_list()) == [node]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.latent_orientation_census"
    )
    assert (
        set(loaded.node_mappings) == {"LatentOrient"} and loaded.web_directory is None
    )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    "shape",
    [
        (1, 4, 5, 8),
        (2, 3, 8, 5),
        (1, 16, 6, 6),
        (1, 4, 1, 7),
        (1, 4, 7, 1),
        (2, 4, 4, 8),
        (1, 4, 9, 4),
    ],
)
def test_five_modes_exact_odd_even_portrait_landscape_square_and_singletons(
    tmp_path, mode, shape
):
    values = _inputs(shape, mode=mode)
    expected = _pristine(tmp_path).LatentOrient().op(**values)[0]
    _equal(_execute(values), expected)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("dtype", [torch.float16, torch.float64, torch.bfloat16])
def test_dtype_batch_noncontiguous_differentials(tmp_path, mode, dtype):
    values = _inputs(dtype=dtype, mode=mode)
    values["samples"]["samples"] = values["samples"]["samples"].transpose(2, 3)
    assert not values["samples"]["samples"].is_contiguous()
    _equal(_execute(values), _pristine(tmp_path).LatentOrient().op(**values)[0])


@pytest.mark.parametrize("mode", MODES[:4])
@pytest.mark.parametrize("shape", [(1, 2, 3, 7, 2), (1, 2, 7, 3, 2, 4)])
def test_higher_rank_literal_legacy_axes_and_padding_quirk(tmp_path, mode, shape):
    values = _inputs(shape, mode=mode)
    _equal(_execute(values), _pristine(tmp_path).LatentOrient().op(**values)[0])


def test_higher_rank_square_noop_and_legacy_avg_resize_failure(tmp_path):
    values = _inputs((1, 4, 5, 5, 3), mode="avg square")
    _equal(_execute(values), _pristine(tmp_path).LatentOrient().op(**values)[0])
    values["samples"]["samples"] = torch.ones(1, 4, 5, 8, 3)
    with pytest.raises(ValueError):
        _secure().LatentOrient.execute(**values)
    with pytest.raises(ValueError):
        _pristine(tmp_path / "second").LatentOrient().op(**values)


@pytest.mark.parametrize("mode", MODES)
def test_metadata_and_aliasing_fidelity_without_input_mutation(tmp_path, mode):
    values = _inputs(mode=mode)
    source = values["samples"]
    before = source["samples"].clone()
    mask_before = source["noise_mask"].clone()
    output = _execute(values)
    assert output is not source
    assert output["noise_mask"] is source["noise_mask"]
    assert output["marker"] is source["marker"]
    assert output["batch_index"] is source["batch_index"]
    assert torch.equal(source["samples"], before)
    assert torch.equal(source["noise_mask"], mask_before)
    legacy = _pristine(tmp_path).LatentOrient().op(**values)[0]
    source_ptr = source["samples"].untyped_storage().data_ptr()
    assert (output["samples"].untyped_storage().data_ptr() == source_ptr) == (
        legacy["samples"].untyped_storage().data_ptr() == source_ptr
    )
    assert (output["samples"] is source["samples"]) == (
        legacy["samples"] is source["samples"]
    )
    if mode == "landscape":
        assert output["samples"] is source["samples"]


def test_rotation_direction_asymmetric_crop_padding_and_noop_identity():
    values = _inputs((1, 1, 2, 5))
    original = values["samples"]["samples"]
    assert torch.equal(_execute(values)["samples"], torch.rot90(original, 1, [3, 2]))
    values["orientation"] = "min square"
    assert torch.equal(_execute(values)["samples"], original[:, :, :, 1:3])
    values["orientation"] = "max square"
    out = _execute(values)["samples"]
    assert out.shape == (1, 1, 5, 5) and torch.equal(out[:, :, 1:3, :], original)
    assert torch.count_nonzero(out[:, :, :1, :]) == 0
    assert torch.count_nonzero(out[:, :, 3:, :]) == 0
    square = _inputs((1, 4, 5, 5))
    for mode in MODES:
        square["orientation"] = mode
        assert _execute(square)["samples"] is square["samples"]["samples"]


@pytest.mark.parametrize("mode", MODES)
def test_nan_inf_follow_original_arithmetic(tmp_path, mode):
    values = _inputs(mode=mode)
    values["samples"]["samples"][0, 0, 0, :3] = torch.tensor(
        [float("nan"), float("inf"), -float("inf")]
    )
    _equal(_execute(values), _pristine(tmp_path).LatentOrient().op(**values)[0])


@pytest.mark.parametrize(
    "samples,orientation",
    [
        (None, "portrait"),
        ({}, "portrait"),
        ({"samples": "tensor"}, "portrait"),
        ({"samples": torch.zeros(1, 4, 5)}, "portrait"),
        ({"samples": torch.zeros(1, 1, 1, 1, 1, 1, 1)}, "portrait"),
        ({"samples": torch.zeros(1, 4, 0, 5)}, "portrait"),
        ({"samples": torch.zeros(1, 4, 5, 5, dtype=torch.int64)}, "portrait"),
        ({"samples": torch.zeros(1, 4, 5, 5).to_sparse()}, "portrait"),
        ({"samples": torch.empty(1, 1, 8193, 1, device="meta")}, "portrait"),
        ({"samples": torch.empty(1, 4, 4096, 4096, device="meta")}, "portrait"),
        ({"samples": torch.ones(1, 1, 2, 3)}, "unknown"),
        ({"samples": torch.ones(1, 1, 2, 3)}, None),
        ({"samples": torch.ones(1, 1, 2, 3)}, ["portrait"]),
    ],
)
def test_malformed_requests_and_input_bounds_fail_closed(samples, orientation):
    with pytest.raises((TypeError, ValueError)):
        _secure().LatentOrient.execute(samples, orientation)


def test_bounds_reject_before_algorithm_or_allocation(monkeypatch):
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("algorithm entered before allocation validation")

    monkeypatch.setattr(pack.nodes.algorithm.LatentOrient, "op", forbidden)
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 1000)
    with pytest.raises(ValueError, match="output element"):
        pack.LatentOrient.execute({"samples": torch.ones(1, 1, 2, 50)}, "max square")
    with pytest.raises(ValueError, match="input element"):
        pack.LatentOrient.execute({"samples": torch.ones(1, 1, 40, 40)}, "portrait")
    monkeypatch.setattr(pack.nodes, "MAX_DIMENSION", 10)
    with pytest.raises(ValueError, match="output dimensions"):
        pack.LatentOrient.execute({"samples": torch.ones(1, 1, 2, 9, 8)}, "max square")
    with pytest.raises(ValueError, match="rank 4"):
        pack.LatentOrient.execute({"samples": torch.ones(1, 1, 2, 3, 2)}, "avg square")


def test_repeated_execution_rng_and_warning_policy_are_isolated():
    rng = torch.random.get_rng_state().clone()
    filters = list(warnings.filters)
    values = _inputs(mode="avg square")
    expected = _execute(values)
    _equal(_execute(values), expected)
    _execute(_inputs(mode="max square"))
    _equal(_execute(values), expected)
    assert torch.equal(rng, torch.random.get_rng_state())
    assert warnings.filters == filters


async def _guest(root, values, label="latent-orientation", deny=False):
    pack = _import("_latent_orientation_guest_source", root)
    refs = _sdk.InProcessRefResolver()
    wrapped = dict(values)
    wrapped["samples"] = _sdk.LatentRef._wrap(
        await refs.create("LATENT", values["samples"])
    )
    plan = _sdk.ExecutionPlan(
        prompt_id=label,
        node_id="1",
        node_type="LatentOrient",
        tier="sandbox",
        node_module=pack.LatentOrient.__module__,
        inputs=wrapped,
        input_mode="values",
        permissions=("raw",),
        method="execute",
    )
    runtime = _sdk.Runtime(
        refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps()
    )
    session = await GuestSession(label, guest_runtime_root=root).start()
    try:
        result = await session.execute(plan, runtime, capabilities=("raw",))
        actual = await refs.resolve(result.result[0])
        assert session.last_guest_pid not in (None, os.getpid())
        if deny:
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
        return actual
    finally:
        await session.kill()


@pytest.mark.parametrize("mode", MODES)
def test_real_guest_raw_denial_outer_latent_typing_and_metadata(mode):
    values = _inputs(mode=mode)
    expected = _execute(values)

    async def run():
        _equal(await _guest(V2, values, deny=True), expected)
        loaded = packdb.load_pack(
            SNAPSHOT,
            mount_name="custom_nodes.latent_orientation_outer_"
            + mode.replace(" ", "_"),
        )
        outer = loaded.node_mappings["LatentOrient"]
        assert tuple(outer.RETURN_TYPES) == ("LATENT",)
        previous = _sdk.providers.execution_backend

        class Backend:
            session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "latent-orientation-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            result = await execution._async_map_node_over_list(
                prompt_id="latent-orientation-outer",
                unique_id="1",
                obj=outer,
                input_data_all={key: [value] for key, value in values.items()},
                func=outer.FUNCTION,
                v3_data=None,
            )
            _equal(result[0].result[0], expected)
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()

    asyncio.run(run())


def _tree(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_fresh_render_filesystem_and_guest_need_no_durable_state(tmp_path):
    first, second = tmp_path / "render-one", tmp_path / "render-two"
    shutil.copytree(V2, first)
    shutil.copytree(V2, second)
    values = _inputs(mode="max square")

    async def run():
        _equal(
            await _guest(first, values, label="orientation-user-a"), _execute(values)
        )
        _equal(
            await _guest(second, values, label="orientation-user-a-fresh"),
            _execute(values),
        )
        other = _inputs((1, 4, 9, 4), mode="min square")
        _equal(await _guest(second, other, label="orientation-user-b"), _execute(other))

    asyncio.run(run())
    assert _tree(first) == _tree(second) == _tree(V2)


def test_stub_provenance_authority_and_persistence_ledger():
    for filename, digest in [("comfy-api.d.ts", DTS_SHA), ("comfy-api.pyi", PYI_SHA)]:
        assert hashlib.sha256((V2 / filename).read_bytes()).hexdigest() == digest
    assert not (PACK / "LICENSE.txt").exists() and not (V2 / "LICENSE.txt").exists()
    assert 'file = "LICENSE.txt"' in (PACK / "pyproject.toml").read_text()
    assert "license" not in (V2 / "pyproject.toml").read_text()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert "6134758aba02532e1c1e6226f935d1d129eb24bf" in report
    assert "Persistence disposition: no durable state" in report
    assert "file is absent" in report and "noise_mask" in report
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


def test_patch_roundtrip_byte_exact(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf8") == diff
    fresh = tmp_path / "comfyui-latentorientation/x6134758"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_cache_hygiene():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))
