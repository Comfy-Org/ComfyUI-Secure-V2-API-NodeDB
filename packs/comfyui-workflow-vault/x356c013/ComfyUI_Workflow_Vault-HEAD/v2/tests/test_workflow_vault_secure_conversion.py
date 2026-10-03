from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "356c0130503e216fb24b859289b9a93f44129c3f"
DTS_SHA256 = "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
PYI_SHA256 = "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
PAIR = PACK_DB / "patches" / "comfyui-workflow-vault" / "x356c013" / (
    "comfyui-workflow-vault-x356c013"
)

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402


def _import_v2():
    name = "_secure_workflow_vault_conversion_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _tree(root: pathlib.Path, *, omit_v2: bool = False) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or (omit_v2 and relative.parts[0] == "v2"):
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def test_pinned_pristine_and_secure_census_are_exact():
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    root = ast.parse((PACK / "__init__.py").read_text())
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in root.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"}
    }
    assert assignments == {"NODE_CLASS_MAPPINGS": {}, "NODE_DISPLAY_NAME_MAPPINGS": {}}
    api = (PACK / "workflow_vault" / "api.py").read_text()
    assert api.count("@routes.get(") == 9
    assert api.count("@_post(") == 32
    frontend = "\n".join(path.read_text() for path in (PACK / "web").glob("*.js"))
    assert frontend.count("app.registerExtension({") == 1
    assert len(list((PACK / "web").glob("*.js"))) == 25

    converted = _import_v2()
    assert converted.NODE_CLASS_MAPPINGS == {}
    assert converted.NODE_DISPLAY_NAME_MAPPINGS == {}
    assert converted.WEB_DIRECTORY == "./web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.workflow_vault_secure_test")
    assert loaded.node_mappings == {}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_manifest_stubs_and_sources_are_secure_and_fresh():
    expected = {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": {},
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }
    assert json.loads((V2 / "secure-nodes.json").read_text()) == expected
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA256

    python = "\n".join(path.read_text(errors="replace") for path in V2.glob("*.py"))
    for forbidden in ("PromptServer", "aiohttp", "subprocess", "workflow_vault.api", "import server", "from server"):
        assert forbidden not in python
    frontend = "\n".join(path.read_text(errors="replace") for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "document.", "window.", "localStorage", "indexedDB", "fetch(",
        "comfy.backend", "innerHTML", "eval(", "../../scripts/",
    ):
        assert forbidden not in frontend
    assert 'from "/comfy/api/v2.js"' in frontend
    assert 'scope: "canvas"' in frontend
    assert 'mode: "new"' in frontend
    assert 'mode: "replace"' in frontend


def test_frontend_behavior_limits_security_and_tenant_boundaries():
    completed = subprocess.run(
        ["npm", "test", "--", "--test-reporter=spec"],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "tests 13" in completed.stdout
    assert "fail 0" in completed.stdout


def test_frontend_calls_match_the_pinned_typed_contract():
    completed = subprocess.run(
        ["npm", "run", "typecheck"],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-workflow-vault" / "x356c013"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_pristine_and_v2_remain_free_of_test_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
