from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import inspect
import json
import os
import pathlib
import re
import shutil
import sys

import pytest
import torch

sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[6]
BACKEND = pathlib.Path(os.environ.get(
    "SECURE_NODES_ROOT", "/Users/ben/comfy/ComfyUI_secure_nodes"
)).resolve() / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "5a4f403a2f4aac076cee89ffe8ff4e93511c9acc"
COMFY_API_DTS_SHA256 = (
    "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
)
COMFY_API_PYI_SHA256 = (
    "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
)
NODE_IDS = {
    "SimpleSwitch",
    "SimpleLatentSwitch",
    "SimpleAudioLatentSwitch",
    "SimpleVideoLatentSwitch",
}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession


def _import_package(root: pathlib.Path, name: str):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name,
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_v2():
    return _import_package(V2, "_secure_simple_switch_conversion_test")


def _import_pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package(root, "_pristine_simple_switch_conversion_test")


def _tree(root: pathlib.Path, *, omit_v2: bool = False) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"}
               for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _generated_manifest(pack) -> dict:
    nodes = {}
    prefix = pack.__name__ + "."
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": node_class.__module__.removeprefix(prefix),
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(
                getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
    }


async def _invoke(node_class, values):
    result = node_class.execute(**values)
    if inspect.isawaitable(result):
        result = await result
    return result


def _plan(node_class, inputs, suffix="case"):
    return _sdk.ExecutionPlan(
        prompt_id=f"simple-switch-{suffix}",
        node_id="1",
        node_type=node_class.__name__,
        tier="sandbox",
        node_module=node_class.__module__,
        inputs=inputs,
        permissions=tuple(node_class.SDK_PERMISSIONS),
        method="execute",
    )


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_actual_loader_census_manifest_and_contract_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine = _import_pristine(tmp_path)
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert not hasattr(pristine, "WEB_DIRECTORY")

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == pristine.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pack, "WEB_DIRECTORY")
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(pack))
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256)
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256)

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.simple_switch_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"
    assert not loaded.routes


def test_schemas_preserve_ids_names_category_sockets_and_permissions():
    pack = _import_v2()
    for node_id in NODE_IDS:
        node_class = pack.NODE_CLASS_MAPPINGS[node_id]
        schema = node_class.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.display_name == pack.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == "Simple Switch"
        assert [item.id for item in schema.inputs] == [
            f"input{index:02d}" for index in range(1, 7)
        ]
        assert all(item.optional is True for item in schema.inputs)
        expected_type = "*" if node_id == "SimpleSwitch" else "LATENT"
        assert [item.io_type for item in schema.inputs] == [expected_type] * 6
        assert [(item.id, item.io_type, item.display_name)
                for item in schema.outputs] == [
            ("output", expected_type, "output")
        ]
        assert node_class.SDK_REFS is True
        expected_permissions = () if node_id == "SimpleLatentSwitch" else ("raw",)
        assert node_class.SDK_PERMISSIONS == expected_permissions


def test_direct_behavior_matches_pristine_priority_subtypes_and_errors(tmp_path):
    pristine = _import_pristine(tmp_path)
    converted = _import_v2()
    nested = torch.nested.nested_tensor([
        torch.zeros((2, 3)), torch.zeros((4, 3)),
    ])
    cases = {
        "SimpleSwitch": [
            {},
            {"input01": None, "input02": 0, "input03": "later"},
            {"input01": {"model": None, "clip": None}, "input02": "next"},
            {"input01": {"model": object(), "clip": None}, "input02": "next"},
        ],
        "SimpleLatentSwitch": [
            {},
            {"input01": {"other": 1}, "input02": {"samples": torch.zeros(1)}},
        ],
        "SimpleAudioLatentSwitch": [
            {},
            {"input01": {"samples": torch.zeros((1, 4, 8, 8)), "type": "audio"}},
            {"input01": {"samples": torch.zeros((1, 4, 8, 8)), "sample_rate": 24000}},
            {"input01": {"samples": nested}},
            {"input01": {"samples": torch.zeros((1, 4, 2, 8, 8))}},
        ],
        "SimpleVideoLatentSwitch": [
            {},
            {"input01": {"samples": torch.zeros((1, 4, 2, 8, 8))}},
            {"input01": {"samples": torch.zeros((1, 4, 8, 8)), "type": "audio"}},
        ],
    }

    async def run():
        for node_id, node_cases in cases.items():
            old = pristine.NODE_CLASS_MAPPINGS[node_id]()
            new = converted.NODE_CLASS_MAPPINGS[node_id]
            for values in node_cases:
                try:
                    expected = old.switch(**values)
                except ValueError as error:
                    prefix = str(error).split("Rejected")[0].strip()
                    with pytest.raises(type(error), match=re.escape(prefix)):
                        await _invoke(new, values)
                else:
                    actual = await _invoke(new, values)
                    assert actual[0] is expected[0]

    asyncio.run(run())


def test_real_guest_preserves_ref_identity_and_subtype_selection():
    pack = _import_v2()

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _sdk.ImageRef._wrap(await refs.create(
            "IMAGE", torch.zeros((1, 2, 2, 3)),
        ))
        empty_context = _sdk.ValueRef._wrap(await refs.create(
            "VALUE", {"model": None, "clip": None},
        ))
        audio = _sdk.LatentRef._wrap(await refs.create(
            "LATENT", {
                "samples": torch.zeros((1, 8, 16, 16)),
                "sample_rate": 24000,
            },
        ))
        video = _sdk.LatentRef._wrap(await refs.create(
            "LATENT", {"samples": torch.zeros((1, 16, 3, 8, 8))},
        ))
        session = await GuestSession(
            "simple-switch-conversion", guest_runtime_root=V2,
        ).start()
        try:
            scenarios = [
                ("SimpleSwitch", {"input01": empty_context, "input02": image}, image),
                ("SimpleLatentSwitch", {"input01": audio, "input02": video}, audio),
                ("SimpleAudioLatentSwitch", {"input01": video, "input02": audio}, audio),
                ("SimpleVideoLatentSwitch", {"input01": audio, "input02": video}, video),
            ]
            for index, (node_id, inputs, expected) in enumerate(scenarios):
                node_class = pack.NODE_CLASS_MAPPINGS[node_id]
                plan = _plan(node_class, inputs, str(index))
                result = await session.execute(
                    plan,
                    _runtime(plan, refs),
                    capabilities=tuple(node_class.SDK_PERMISSIONS),
                )
                assert session.last_guest_pid not in (None, os.getpid())
                assert result.result[0].id == expected.id

            denied_class = pack.NODE_CLASS_MAPPINGS["SimpleAudioLatentSwitch"]
            denied = _plan(denied_class, {"input01": audio}, "denied")
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    denied,
                    _runtime(denied, refs),
                    capabilities=(),
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_source_has_only_declared_raw_structure_authority():
    source = "\n".join(
        path.read_text(errors="replace") for path in sorted(V2.glob("*.py"))
    )
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "import server", "from server", "folder_paths",
        "PromptServer", "open(", "eval(", "exec(", "sdk.ctx(",
        "from_value(", "_from_raw(",
    ):
        assert forbidden not in source
    assert 'SDK_PERMISSIONS = ("raw",)' in source
    assert "await value.value()" in source
    assert "return io.NodeOutput(candidate)" in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "patches" / "comfyui-simple-switch"
        / "x5a4f403" / "comfyui-simple-switch-x5a4f403"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-simple-switch" / "x5a4f403"
    fresh.mkdir(parents=True)
    shutil.copytree(
        PACK,
        fresh / PACK.name,
        ignore=shutil.ignore_patterns("v2"),
    )
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert _tree(PACK, omit_v2=True) == _tree(fresh / PACK.name, omit_v2=True)


def test_no_cache_artifacts_in_pristine_or_v2():
    for root in (PACK, V2):
        assert not list(root.rglob("__pycache__"))
        assert not list(root.rglob("*.pyc"))
