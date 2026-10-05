from __future__ import annotations

import asyncio
import ast
import copy
import hashlib
import json
import os
import pathlib
import shutil
import stat
import sys

import pytest
import torch


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = pathlib.Path(__file__).resolve().parents[6]
REPO = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes")
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).resolve()
PAIR = PACK_DB / "patches/comfyui-cache-cleaner/x13b4b64/comfyui-cache-cleaner-x13b4b64"
COMMIT = "13b4b64fefdd4bffdf95c0ff06cc328081979ca9"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PRISTINE_PATHS = (
    ".github/workflows/publish.yml", ".gitignore", "LICENSE", "README.md",
    "__init__.py", "cache_cleaner.py", "pyproject.toml",
)
PRISTINE_DIGEST = "2c316ed45605bece5297fa664f42529bf531b83f49583afaedba718a88a76f2c"

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


V2_PACKAGE = packdb.load(
    "custom_nodes.cache_cleaner_secure_test", V2, "cache_cleaner"
)


def _manifest() -> dict:
    nodes = {}
    for node_id, node_class in sorted(V2_PACKAGE.NODE_CLASS_MAPPINGS.items()):
        module = sys.modules[node_class.__module__]
        relative = pathlib.Path(module.__file__).resolve().relative_to(V2)
        nodes[node_id] = {
            "module": ".".join(relative.with_suffix("").parts),
            "class": node_class.__name__,
            "sdk_refs": node_class.SDK_REFS is True,
            "permissions": list(node_class.SDK_PERMISSIONS),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status"
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _pristine_digest():
    paths, rows = [], []
    for path in sorted(PACK.rglob("*")):
        relative = path.relative_to(PACK)
        if not path.is_file() or "v2" in relative.parts:
            continue
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        logical = relative.as_posix()
        paths.append(logical)
        mode = "755" if path.stat().st_mode & stat.S_IXUSR else "644"
        rows.append(
            f"{logical}\0{mode}\0{hashlib.sha256(path.read_bytes()).hexdigest()}"
        )
    return tuple(paths), hashlib.sha256("\n".join(rows).encode()).hexdigest()


def _tree(root: pathlib.Path):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not any(
            part in {"__pycache__", ".pytest_cache"}
            for part in path.relative_to(root).parts
        )
    }


def test_actual_census_schema_manifest_and_contract_are_exact():
    assert _pristine_digest() == (PRISTINE_PATHS, PRISTINE_DIGEST)
    source = (PACK / "__init__.py").read_text()
    assert "NODE_CLASS_MAPPINGS" in source
    assert set(V2_PACKAGE.NODE_CLASS_MAPPINGS) == {"CacheCleaner"}
    assert V2_PACKAGE.NODE_DISPLAY_NAME_MAPPINGS == {
        "CacheCleaner": "Cache Cleaner"
    }
    node = V2_PACKAGE.CacheCleaner
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ("models.manage",)
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.category == "utils/system"
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("clean_cache", "BOOLEAN", False),
        ("anything", "*", True),
        ("image_pass", "IMAGE", True),
        ("model_pass", "MODEL", True),
    ]
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("anything", "*"), ("image_pass", "IMAGE"),
        ("model_pass", "MODEL"), ("status", "STRING"),
    ]
    assert schema.inputs[0].default is True
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest()
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.cache_cleaner_gate")
    assert set(loaded.node_mappings) == {"CacheCleaner"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


def test_skip_path_preserves_all_inputs_without_invoking_broker():
    node = V2_PACKAGE.CacheCleaner

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", torch.zeros(1, 2, 3, 3)))
        model_value = object()
        model = _sdk.ModelRef._wrap(await refs.create("MODEL", model_value))
        plan = _sdk.ExecutionPlan(
            prompt_id="skip", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={
                "clean_cache": False, "anything": {"kept": True},
                "image_pass": image, "model_pass": model,
            },
            permissions=node.SDK_PERMISSIONS,
        )
        lines = []
        session = await GuestSession(
            "cache-cleaner-skip", guest_runtime_root=V2, tap=lines.append
        ).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=node.SDK_PERMISSIONS
            )
            assert result.result[:3] == ({"kept": True}, image, model)
            assert result.result[3] == (
                "Status: Cache cleaning skipped\n"
                "Server address: managed by secure host"
            )
            assert not any("models.memory_cleanup" in line for line in lines)
        finally:
            await session.kill()

    asyncio.run(run())


def test_cleanup_executes_in_real_guest_preserves_refs_and_requires_permission():
    node = V2_PACKAGE.CacheCleaner

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", torch.zeros(1, 2, 2, 3)))
        model = _sdk.ModelRef._wrap(await refs.create("MODEL", object()))
        inputs = {
            "clean_cache": True, "anything": "sentinel",
            "image_pass": image, "model_pass": model,
        }
        plan = _sdk.ExecutionPlan(
            prompt_id="clean", node_id="2", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__, inputs=inputs,
            permissions=node.SDK_PERMISSIONS,
        )
        lines = []
        session = await GuestSession(
            "cache-cleaner-clean", guest_runtime_root=V2, tap=lines.append
        ).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=node.SDK_PERMISSIONS
            )
            assert result.result[:3] == ("sentinel", image, model)
            assert result.result[3] == (
                "Status: Cache cleaned successfully\n"
                "Server address: managed by secure host"
            )
            assert any("models.memory_cleanup" in line for line in lines)
            assert session.last_guest_pid not in (None, os.getpid())
            denied = await session.execute(
                plan, _runtime(plan, refs), capabilities=()
            )
            assert denied.result[:3] == ("sentinel", image, model)
            assert "models.manage" in denied.result[3]
        finally:
            await session.kill()

    asyncio.run(run())


def test_broker_failure_is_reported_and_passthroughs_survive(monkeypatch):
    node = V2_PACKAGE.CacheCleaner

    class Models:
        async def memory_cleanup(self, **_kwargs):
            raise RuntimeError("cleanup unavailable")

    class Ctx:
        models = Models()

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="failure", node_id="3", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__, inputs={},
            permissions=node.SDK_PERMISSIONS,
        )
        with _sdk.bind_runtime(refs, Ctx(), _sdk.InProcessOps()):
            result = await node.execute(True, "x", None, None)
        assert result.result[:3] == ("x", None, None)
        assert "cleanup unavailable" in result.result[3]

    asyncio.run(run())


def test_source_has_no_loopback_or_ambient_authority():
    source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    imports = set()
    for path in V2.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    assert not any(name.split(".")[0] in {
        "requests", "server", "folder_paths", "subprocess", "socket"
    } for name in imports)
    for forbidden in (
        "import requests", "127.0.0.1", "0.0.0.0",
        "http://", "open(", "subprocess", "socket", "folder_paths",
    ):
        assert forbidden not in source
    assert source.count('SDK_PERMISSIONS = ("models.manage",)') == 1
    assert "models.memory_cleanup" in source


def test_patch_roundtrip_and_cache_cleanliness(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-cache-cleaner" / "x13b4b64"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
