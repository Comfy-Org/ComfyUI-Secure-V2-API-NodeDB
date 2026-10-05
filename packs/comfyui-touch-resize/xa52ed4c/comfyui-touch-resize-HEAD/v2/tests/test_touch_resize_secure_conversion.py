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
SECURE_ROOT = pathlib.Path(
    os.environ.get(
        "SECURE_NODES_ROOT",
        "/Users/ben/comfy/ComfyUI_secure_nodes-pack2-workspace-manager",
    )
).resolve()
BACKEND = SECURE_ROOT / "backend"
CORE = pathlib.Path(
    os.environ.get(
        "COMFY_CORE_ROOT",
        "/Users/ben/comfy/ComfyUI-secure-nodes",
    )
).resolve()
COMMIT = "a52ed4cc2932151d06a096cf02ef0c4c12cb7708"
COMFY_API_DTS_SHA256 = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
COMFY_API_PYI_SHA256 = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"

for path in (str(SECURE_ROOT), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)

from comfy_secure_nodes import packdb, packpatch  # noqa: E402


def _import_v2(name="_secure_touch_resize_conversion_test"):
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        name,
        V2 / "__init__.py",
        submodule_search_locations=[str(V2)],
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
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def test_pinned_census_manifest_and_authoritative_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine = ast.parse((PACK / "__init__.py").read_text())
    assignments = {
        target.id: node.value
        for node in pristine.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert isinstance(assignments["NODE_CLASS_MAPPINGS"], ast.Dict)
    assert assignments["NODE_CLASS_MAPPINGS"].keys == []
    assert assignments["NODE_DISPLAY_NAME_MAPPINGS"].keys == []
    assert (PACK / "web" / "dist" / "index.js").read_text().count("app.registerExtension({") == 1
    assert not any(
        "PromptServer" in path.read_text(errors="replace")
        for path in PACK.rglob("*.py")
        if "v2" not in path.relative_to(PACK).parts
    )

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {}
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == {
        "format": "comfy-secure-nodes-v1",
        "frontend_permissions": ["ui.graph-overlay"],
        "nodes": {},
        "runtime": {
            "python": {"requires": ">=3.13,<3.14", "resolved": "3.13"},
        },
        "web_directory": "web",
    }
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256
    )
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256
    )

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.touch_resize_conversion_test",
    )
    assert loaded.node_mappings == {}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset({"ui.graph-overlay"})
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_v2_tree_excludes_legacy_ambient_build_and_declares_exact_authority():
    assert set(_tree(V2)) == {
        "CHANGELOG.md",
        "LICENSE",
        "README.md",
        "SECURE_CONVERSION.md",
        "comfy-api.d.ts",
        "comfy-api.pyi",
        "doc/usage.md",
        "__init__.py",
        "pyproject.toml",
        "secure-nodes.json",
        "web/geometry.js",
        "web/index.js",
        "tests/test_touch_resize_secure_conversion.py",
        "tests/touch_resize_geometry_test.mjs",
        "tests/touch_resize_harness.mjs",
        "tests/touch_resize_secure_bridge.mjs",
    }
    source = "\n".join(
        path.read_text(errors="replace") for path in sorted((V2 / "web").rglob("*.js"))
    )
    for forbidden in (
        "/scripts/app.js",
        "app.registerExtension",
        "window.",
        "document.",
        "globalThis",
        "fetch(",
        "selected_nodes",
        "selectedItems",
        "onDrawForeground",
        "setPointerCapture",
        "addEventListener",
    ):
        assert forbidden not in source
    assert 'from "/comfy/api/v2.js"' in source
    assert "mountGraphOverlay" in source
    assert "setHitRegions" in source
    assert "getMinimumSize" in source
    assert "groupSelection" in source
    assert "setBounds" in source


def test_geometry_frontend_and_real_secure_bridge_behavior():
    environment = {
        **os.environ,
        "SECURE_RUNTIME_ROOT": str(SECURE_ROOT),
    }
    for script, marker in (
        ("touch_resize_geometry_test.mjs", "touch resize geometry: PASS"),
        ("touch_resize_harness.mjs", "touch resize frontend behavior: PASS"),
        ("touch_resize_secure_bridge.mjs", "touch resize secure bridge: PASS"),
    ):
        result = subprocess.run(
            ["node", str(V2 / "tests" / script)],
            cwd=PACK,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert marker in result.stdout


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        PACK_DB / "patches" / "comfyui-touch-resize" / "xa52ed4c" / "comfyui-touch-resize-xa52ed4c"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-touch-resize" / "xa52ed4c"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_do_not_dirty_pristine_or_v2_with_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
