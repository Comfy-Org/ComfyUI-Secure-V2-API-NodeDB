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
COMMIT = "3117b024ae3756cda0b3b88e0c265256aa48e53c"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches/comfyui-conditioning-multiply-advanced/x3117b02/comfyui-conditioning-multiply-advanced-x3117b02"
)

for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import(name, root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _import("_secure_conditioning_multiply_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import("_pristine_conditioning_multiply_test", root)


def _manifest(pack):
    node = pack.ConditioningMultiplyAdvanced
    return {
        "format": FORMAT,
        "nodes": {
            "ConditioningMultiplyAdvanced": {
                "module": "nodes",
                "class": "ConditioningMultiplyAdvanced",
                "sdk_refs": True,
                "permissions": ["raw"],
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


def _value():
    return [
        [
            torch.linspace(-1, 1, 24).reshape(1, 3, 8),
            {
                "pooled_output": torch.arange(6, dtype=torch.float32).reshape(1, 6),
                "t5xxl_weights": torch.ones((1, 2), dtype=torch.float16),
                "t5xxl_ids": torch.arange(4, dtype=torch.int64),
                "other": torch.full((1, 2), 3.0),
                "start_percent": 0.1,
                "end_percent": 0.9,
                "tag": "keep",
            },
        ]
    ]


def _run(module, value, **overrides):
    args = {
        "start_multiplier": -0.5,
        "end_multiplier": 2.25,
        "start_percent": 0.25,
        "end_percent": 0.75,
        "curve": "linear",
        "outside_window": "hold",
        "segments": 5,
        "tensor_scope": "main_conditioning_and_float_metadata",
        "non_float_behavior": "preserve",
        "metadata_keys": "pooled_output,t5xxl_weights",
        "log_summary": False,
    }
    args.update(overrides)
    return module.nodes.algorithm.ConditioningMultiplyAdvanced().multiply(
        value,
        args["start_multiplier"],
        args["end_multiplier"],
        args["start_percent"],
        args["end_percent"],
        args["curve"],
        args["outside_window"],
        args["segments"],
        args["tensor_scope"],
        args["non_float_behavior"],
        args["metadata_keys"],
        args["log_summary"],
    )[0]


def _same(actual, expected):
    if isinstance(expected, torch.Tensor):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        return
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            _same(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            _same(a, b)
    else:
        assert actual == expected


def test_census_schema_manifest_and_contract(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert (
        set(old.NODE_CLASS_MAPPINGS)
        == set(new.NODE_CLASS_MAPPINGS)
        == {"ConditioningMultiplyAdvanced"}
    )
    assert not hasattr(old, "WEB_DIRECTORY") and not list(PACK.rglob("*.js"))
    legacy = old.ConditioningMultiplyAdvanced.INPUT_TYPES()["required"]
    schema = new.ConditioningMultiplyAdvanced.GET_SCHEMA()
    schema.validate()
    assert [item.id for item in schema.inputs] == list(legacy)
    for item, (name, specification) in zip(schema.inputs, legacy.items()):
        legacy_type, legacy_options = specification
        assert item.id == name
        assert item.io_type == (
            "COMBO" if isinstance(legacy_type, list) else legacy_type
        )
        if isinstance(legacy_type, list):
            assert item.options == legacy_type
        for attribute in (
            "default",
            "min",
            "max",
            "step",
            "round",
            "multiline",
            "tooltip",
        ):
            if attribute in legacy_options:
                assert getattr(item, attribute) == legacy_options[attribute]
    assert [item.io_type for item in schema.outputs] == ["CONDITIONING"]
    assert [item.display_name for item in schema.outputs] == list(
        old.ConditioningMultiplyAdvanced.RETURN_NAMES
    )
    assert schema.category == old.ConditioningMultiplyAdvanced.CATEGORY
    assert schema.description == old.ConditioningMultiplyAdvanced.DESCRIPTION
    assert schema.search_aliases == old.ConditioningMultiplyAdvanced.SEARCH_ALIASES
    assert new.ConditioningMultiplyAdvanced.SDK_REFS is True
    assert new.ConditioningMultiplyAdvanced.SDK_PERMISSIONS == ("raw",)
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(new)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.conditioning_multiply_test"
    )
    assert set(loaded.node_mappings) == {"ConditioningMultiplyAdvanced"}
    assert not loaded.routes and loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize(
    "curve", ("linear", "cosine", "smoothstep", "ease_in", "ease_out", "sigmoid")
)
@pytest.mark.parametrize("outside", ("hold", "baseline", "linear_extrapolate"))
def test_all_curves_and_outside_policies_are_exact(tmp_path, curve, outside):
    old, new = _pristine(tmp_path), _secure()
    args = (
        -0.5,
        2.25,
        0.25,
        0.75,
        curve,
        outside,
        5,
        "main_conditioning_and_float_metadata",
        "preserve",
        "pooled_output,t5xxl_weights",
        False,
    )
    expected = old.ConditioningMultiplyAdvanced().multiply(
        copy.deepcopy(_value()), *args
    )[0]
    actual = _run(new, copy.deepcopy(_value()), curve=curve, outside_window=outside)
    _same(actual, expected)


@pytest.mark.parametrize(
    "scope",
    (
        "main_conditioning_and_float_metadata",
        "main_conditioning_only",
        "float_metadata_only",
        "all_float_tensors",
    ),
)
def test_all_tensor_scopes_and_nonmutation_are_exact(tmp_path, scope):
    old, new = _pristine(tmp_path), _secure()
    source = _value()
    original = copy.deepcopy(source)
    args = (
        3.0,
        3.0,
        0.0,
        1.0,
        "linear",
        "hold",
        1,
        scope,
        "preserve",
        "pooled_output,t5xxl_weights",
        False,
    )
    expected = old.ConditioningMultiplyAdvanced().multiply(
        copy.deepcopy(source), *args
    )[0]
    actual = _run(
        new,
        source,
        start_multiplier=3.0,
        end_multiplier=3.0,
        start_percent=0.0,
        end_percent=1.0,
        segments=1,
        tensor_scope=scope,
    )
    _same(actual, expected)
    _same(source, original)


def test_integer_error_invalid_fallbacks_and_resource_bounds(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    with pytest.raises(TypeError):
        _run(new, _value(), non_float_behavior="error")
    args = (1.0, 2.0, 0.0, 1.0, "bad", "bad", 2, "bad", "bad", "", False)
    expected = old.ConditioningMultiplyAdvanced().multiply(
        copy.deepcopy(_value()), *args
    )[0]
    actual = _run(
        new,
        _value(),
        start_multiplier=1.0,
        end_multiplier=2.0,
        start_percent=0.0,
        end_percent=1.0,
        curve="bad",
        outside_window="bad",
        segments=2,
        tensor_scope="bad",
        non_float_behavior="bad",
        metadata_keys="",
    )
    _same(actual, expected)
    nested = 0
    for _ in range(new.nodes.MAX_DEPTH + 2):
        nested = [nested]
    with pytest.raises(ValueError, match="deeply"):
        new.nodes._validate_structure(nested)
    huge = [[torch.empty((1, new.nodes.MAX_TENSOR_ELEMENTS + 1), device="meta"), {}]]
    with pytest.raises(ValueError, match="size bound"):
        new.nodes._validate_structure(huge)


def test_real_guest_matches_and_denies_raw(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    source = _value()

    async def run():
        refs = _sdk.InProcessRefResolver()
        cond = _sdk.CondRef._wrap(await refs.create("CONDITIONING", source))
        node = new.ConditioningMultiplyAdvanced
        inputs = {
            "conditioning": cond,
            "start_multiplier": 0.2,
            "end_multiplier": 1.8,
            "start_percent": 0.2,
            "end_percent": 0.8,
            "curve": "cosine",
            "outside_window": "baseline",
            "segments": 7,
            "tensor_scope": "all_float_tensors",
            "non_float_behavior": "preserve",
            "metadata_keys": "pooled_output",
            "log_summary": False,
        }
        plan = _sdk.ExecutionPlan(
            prompt_id="cm",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs=inputs,
            permissions=("raw",),
            method="execute",
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "conditioning-multiply", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=("raw",))
            actual = await refs.resolve(result.result[0])
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
            return actual
        finally:
            await session.kill()

    actual = asyncio.run(run())
    expected = old.ConditioningMultiplyAdvanced().multiply(
        source,
        0.2,
        1.8,
        0.2,
        0.8,
        "cosine",
        "baseline",
        7,
        "all_float_tensors",
        "preserve",
        "pooled_output",
        False,
    )[0]
    _same(actual, expected)


def test_stubs_authority_patch_and_no_cache(tmp_path):
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    source = (V2 / "nodes.py").read_text() + (V2 / "_algorithm.py").read_text()
    for forbidden in (
        "import comfy",
        "folder_paths",
        "PromptServer",
        "requests",
        "subprocess",
        "open(",
        "ctx()",
        "_from_raw",
    ):
        assert forbidden not in source
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-conditioning-multiply-advanced" / "x3117b02"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("__pycache__")) and not list(PACK.rglob("*.pyc"))
