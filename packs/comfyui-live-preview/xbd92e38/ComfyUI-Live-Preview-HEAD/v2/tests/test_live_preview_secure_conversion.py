from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys

import torch

sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = pathlib.Path(__file__).resolve().parents[6]
SECURE_ROOT = pathlib.Path(os.environ.get(
    "SECURE_NODES_ROOT", "/Users/ben/comfy/ComfyUI_secure_nodes"
)).resolve()
BACKEND = SECURE_ROOT / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).resolve()
COMMIT = "bd92e38cc9a8dfbf01bb1a434daac2d4b9f75504"
COMFY_API_DTS_SHA256 = (
    "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
)
COMFY_API_PYI_SHA256 = (
    "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
)

for path in (str(SECURE_ROOT), str(BACKEND), str(CORE)):
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
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_v2():
    return _import_package(V2, "_secure_live_preview_conversion_test")


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
    node_class = pack.NODE_CLASS_MAPPINGS["LivePreview"]
    prefix = pack.__name__ + "."
    return {
        "format": FORMAT,
        "frontend_permissions": ["ui.graph-overlay"],
        "nodes": {
            "LivePreview": {
                "module": node_class.__module__.removeprefix(prefix),
                "class": node_class.__name__,
                "sdk_refs": node_class.SDK_REFS is True,
                "permissions": list(node_class.SDK_PERMISSIONS),
                "methods": {
                    name: name in node_class.__dict__
                    for name in (
                        "validate_inputs", "fingerprint_inputs", "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
            },
        },
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def test_pinned_census_schema_manifest_and_contract_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine_root = tmp_path / "pristine"
    shutil.copytree(PACK, pristine_root, ignore=shutil.ignore_patterns("v2"))
    pristine = _import_package(pristine_root, "_pristine_live_preview_test")
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"LivePreview"}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {
        "LivePreview": "Live Preview (Large)",
    }
    assert pristine.WEB_DIRECTORY == "./js"
    assert (pristine_root / "js" / "live_preview.js").read_text().count(
        "app.registerExtension({") == 1

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == {"LivePreview"}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == pristine.NODE_DISPLAY_NAME_MAPPINGS
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256)
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256)

    schema = pack.LivePreview.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "LivePreview"
    assert schema.display_name == "Live Preview (Large)"
    assert schema.category == "image"
    assert [(value.id, value.io_type) for value in schema.inputs] == [
        ("images", "IMAGE"),
    ]
    assert [(value.id, value.io_type, value.display_name)
            for value in schema.outputs] == [("images", "IMAGE", "images")]
    assert pack.LivePreview.SDK_REFS is True
    assert pack.LivePreview.SDK_PERMISSIONS == ()

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.live_preview_conversion_test",
    )
    assert set(loaded.node_mappings) == {"LivePreview"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset({"ui.graph-overlay"})
    assert not loaded.routes


def test_backend_passthrough_matches_upstream_and_real_isolated_guest():
    pack = _import_v2()
    marker = object()
    assert pack.LivePreview.execute(marker)[0] is marker

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _sdk.ImageRef._wrap(await refs.create(
            "IMAGE", torch.zeros((2, 4, 5, 3)),
        ))
        plan = _sdk.ExecutionPlan(
            prompt_id="live-preview-conversion",
            node_id="1",
            node_type="LivePreview",
            tier="sandbox",
            node_module=pack.LivePreview.__module__,
            inputs={"images": image},
            permissions=(),
            method="execute",
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "live-preview-conversion", guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
            assert result.result[0].id == image.id
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_lifecycle():
    source = (V2 / "web" / "live_preview.js").read_text()
    combined = "\n".join(
        path.read_text(errors="replace") for path in sorted((V2 / "web").glob("*.js"))
    )
    for forbidden in (
        "/scripts/app.js", "app.registerExtension", "window.", "document.",
        "localStorage", "sessionStorage", "indexedDB", "fetch(", "innerHTML",
        "addEventListener", "removeEventListener", "app.graph", "app.canvas",
    ):
        assert forbidden not in combined
    for required in (
        'from "/comfy/api/v2.js"', "mountGraphOverlay", "setHitRegions",
        "addActionBarButton", 'backend.on("b_preview"',
        'backend.on("execution_start"', 'backend.on("status"',
        'backend.on("execution_error"', "storage.get", "storage.set",
        "queryNodes", "createImageBitmap", ".close?.()",
    ):
        assert required in source

    for path in sorted((V2 / "web").glob("*.js")):
        syntax = subprocess.run(
            ["node", "--check", str(path)], cwd=V2, text=True,
            capture_output=True, timeout=30, check=False,
        )
        assert syntax.returncode == 0, syntax.stdout + syntax.stderr
    typecheck = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    completed = subprocess.run(
        ["node", "--experimental-vm-modules",
         str(V2 / "tests" / "live_preview_frontend_harness.mjs"),
         str(V2 / "web" / "live_preview.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Live Preview overlay, frames, geometry, storage, and teardown" in completed.stdout


def test_python_source_has_no_ambient_authority():
    source = "\n".join(path.read_text() for path in sorted(V2.glob("*.py")))
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "import server", "from server", "folder_paths",
        "PromptServer", "open(", "eval(", "exec(", "sdk.ctx(", "SDK_REFS = False",
    ):
        assert forbidden not in source
    assert "SDK_PERMISSIONS = ()" in source
    assert "return io.NodeOutput(images)" in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        PACK_DB / "patches" / "comfyui-live-preview"
        / "xbd92e38" / "comfyui-live-preview-xbd92e38"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-live-preview" / "xbd92e38"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    assert _tree(fresh / PACK.name, omit_v2=True) == _tree(PACK, omit_v2=True)


def test_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
