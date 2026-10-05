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
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "57b8a372e9291e050c725b987ae1722f11b93143"
COMFY_API_DTS_SHA256 = (
    "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
)
COMFY_API_PYI_SHA256 = (
    "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
)
NODE_ID = "DenoiseChooser|Koushakur"

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


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
    return _import_package(V2, "_secure_denoisechooser_conversion_test")


def _import_pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package(root, "_pristine_denoisechooser_conversion_test")


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


def _plan(node_class, inputs, suffix="case"):
    return _sdk.ExecutionPlan(
        prompt_id=f"denoisechooser-{suffix}",
        node_id="1",
        node_type=node_class.__name__,
        tier="sandbox",
        node_module=node_class.__module__,
        inputs=inputs,
        permissions=("raw",),
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
    assert set(pristine.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "Denoise Chooser"}
    assert not hasattr(pristine, "WEB_DIRECTORY")

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "Denoise Chooser"}
    assert not hasattr(pack, "WEB_DIRECTORY")
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(pack))
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256)
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256)

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.denoisechooser_conversion_test",
    )
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"
    assert not loaded.routes


def test_schema_preserves_node_id_names_bounds_and_outputs():
    node_class = _import_v2().NODE_CLASS_MAPPINGS[NODE_ID]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == NODE_ID
    assert schema.display_name == "Denoise Chooser"
    assert schema.category == "advanced"
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("Latent", "LATENT"),
        ("FloatIfEmpty", "FLOAT"),
        ("FloatIfNot", "FLOAT"),
    ]
    for item, default in zip(schema.inputs[1:], (1.0, 0.75), strict=True):
        assert item.default == default
        assert item.min == 0.0
        assert item.max == 100.0
        assert item.step == 0.05
    assert [(item.id, item.io_type, item.display_name) for item in schema.outputs] == [
        ("LATENT", "LATENT", "LATENT"),
        ("FLOAT", "FLOAT", "FLOAT"),
    ]
    assert node_class.SDK_REFS is True
    assert node_class.SDK_PERMISSIONS == ("raw",)


def test_v2_matches_pristine_for_empty_nonempty_and_percentage_boundaries(tmp_path):
    pristine_class = _import_pristine(tmp_path).NODE_CLASS_MAPPINGS[NODE_ID]
    node_class = _import_v2().NODE_CLASS_MAPPINGS[NODE_ID]
    cases = [
        (torch.zeros((1, 4, 8, 8)), 1.0, 0.75),
        (torch.zeros((1, 4, 8, 8)), 100.0, 75.0),
        (torch.ones((1, 4, 8, 8)), 1.0, 0.75),
        (torch.tensor([[[[0.0, -1.0]]]]), 50.0, 1.0),
        (torch.tensor([[[[float("nan")]]]]), 1.01, 25.0),
    ]

    async def run():
        for index, (samples, when_empty, when_not) in enumerate(cases):
            latent_value = {"samples": samples, "metadata": {"case": index}}
            expected = pristine_class().func(
                latent_value, when_empty, when_not,
            )
            refs = _sdk.InProcessRefResolver()
            plan = _plan(node_class, {}, str(index))
            runtime = _runtime(plan, refs)
            with _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops):
                latent_ref = _sdk.LatentRef._wrap(
                    await refs.create("LATENT", latent_value))
                result = await node_class.execute(
                    latent_ref, when_empty, when_not,
                )
            assert result[0].id == latent_ref.id
            assert result[1] == expected[1]
            assert await refs.resolve(result[0]) is latent_value

    asyncio.run(run())


def test_real_guest_is_out_of_process_preserves_identity_and_fails_closed():
    node_class = _import_v2().NODE_CLASS_MAPPINGS[NODE_ID]

    async def run():
        refs = _sdk.InProcessRefResolver()
        empty_ref = _sdk.LatentRef._wrap(await refs.create(
            "LATENT", {"samples": torch.zeros((1, 4, 8, 8))},
        ))
        nonempty_ref = _sdk.LatentRef._wrap(await refs.create(
            "LATENT", {"samples": torch.nn.functional.pad(
                torch.ones((1, 4, 1, 1)), (0, 7, 0, 7),
            )},
        ))
        session = await GuestSession("denoisechooser-conversion").start()
        try:
            for suffix, latent, expected in (
                ("empty", empty_ref, 0.8),
                ("nonempty", nonempty_ref, 0.35),
            ):
                plan = _plan(node_class, {
                    "Latent": latent,
                    "FloatIfEmpty": 80.0,
                    "FloatIfNot": 35.0,
                }, suffix)
                result = await session.execute(
                    plan, _runtime(plan, refs), capabilities=("raw",),
                )
                assert session.last_guest_pid not in (None, os.getpid())
                assert result.result[0].id == latent.id
                assert result.result[1] == expected

            denied = _plan(node_class, {
                "Latent": empty_ref,
                "FloatIfEmpty": 1.0,
                "FloatIfNot": 0.75,
            }, "denied")
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    denied, _runtime(denied, refs), capabilities=(),
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_source_has_only_declared_raw_tensor_authority():
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
    assert "await Latent.value()" in source
    assert '.count_nonzero().item()' in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-denoisechooser"
        / "x57b8a37" / "comfyui-denoisechooser-x57b8a37"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-denoisechooser" / "x57b8a37"
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
