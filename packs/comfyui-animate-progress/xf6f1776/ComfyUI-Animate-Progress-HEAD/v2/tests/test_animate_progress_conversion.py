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
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).resolve()
COMMIT = "f6f177643e4fd260fbc6419e3ed4690af1ad38d9"
TREE = "b17240b0f39a8cbf43b5d145975a3038ea084b7d"
COMFY_API_DTS_SHA256 = (
    "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
)
COMFY_API_PYI_SHA256 = (
    "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
)
GIFS = {f"giphy{index:02d}.gif" for index in range(1, 35)}
PRISTINE_ROOT_FILES = {
    ".gitattributes", "LICENSE", "README.md", "__init__.py",
    "pyproject.toml", "web/main.js",
}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402


def _import_v2(name="_secure_animate_progress_conversion_test"):
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)],
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
        if any(part in {".git", "__pycache__", ".pytest_cache"}
               for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def test_pinned_pristine_census_route_and_assets_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert TREE in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine_files = set(_tree(PACK, omit_v2=True))
    assert pristine_files == PRISTINE_ROOT_FILES | {
        ".github/workflows/publish.yml",
        *(f"web/runners/{name}" for name in GIFS),
    }

    module = ast.parse((PACK / "__init__.py").read_text())
    assignments = {
        target.id: statement.value
        for statement in module.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }
    assert isinstance(assignments["NODE_CLASS_MAPPINGS"], ast.Dict)
    assert assignments["NODE_CLASS_MAPPINGS"].keys == []
    assert isinstance(assignments["NODE_DISPLAY_NAME_MAPPINGS"], ast.Dict)
    assert assignments["NODE_DISPLAY_NAME_MAPPINGS"].keys == []
    pristine_python = (PACK / "__init__.py").read_text()
    assert pristine_python.count(".routes.get(") == 1
    assert "get_gifs" in pristine_python
    pristine_js = (PACK / "web" / "main.js").read_text()
    assert pristine_js.count("app.registerExtension({") == 1
    assert pristine_js.count("localStorage.") == 2

    pristine_gifs = PACK / "web" / "runners"
    converted_gifs = V2 / "web" / "runners"
    assert {path.name for path in pristine_gifs.glob("*.gif")} == GIFS
    assert {path.name for path in converted_gifs.glob("*.gif")} == GIFS
    for name in GIFS:
        assert (converted_gifs / name).read_bytes() == (pristine_gifs / name).read_bytes()


def test_frontend_only_manifest_entrypoint_and_contract_are_exact():
    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {}
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == {
        "format": "comfy-secure-nodes-v1",
        "nodes": {},
        "runtime": {
            "python": {"requires": ">=3.13,<3.14", "resolved": "3.13"},
        },
        "web_directory": "web",
    }
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.animate_progress_conversion_test",
    )
    assert loaded.node_mappings == {}
    assert loaded.display_mappings == {}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_frontend_uses_only_scoped_v2_services_and_closed_assets():
    source = (V2 / "web" / "animate_progress.js").read_text()
    for forbidden in (
        "app.registerExtension", "window.", "document.", "localStorage",
        "sessionStorage", "fetch(", "api.fetchApi", "innerHTML", ".prototype",
        "PromptServer", "XMLHttpRequest", "WebSocket", "EventSource",
        "MutationObserver", "ResizeObserver", "eval(", "Function(",
        "/extensions/ComfyUI-Animate-Progress",
    ):
        assert forbidden not in source
    for required in (
        'import { comfy } from "/comfy/api/v2.js"',
        "comfy.ui.mountViewportPanel", "comfy.ui.showDialog",
        "comfy.storage.get", "comfy.storage.set",
        'comfy.backend.on("progress"',
        'comfy.backend.on("execution_error"',
        "comfy.queue.onInterrupted", "comfy.queue.onRejected",
        "comfy.queue.onPendingChanged", "comfy.onExecutingNodeChanged",
        "container.ownerDocument", "new URL(`./runners/${name}`, import.meta.url)",
        "removeEventListener", "cancelAnimationFrame", "clearTimeout",
    ):
        assert required in source
    assert "length: 34" in source
    assert source.count('case "') == 7

    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "import os", "import server", "from server", "PromptServer",
        "aiohttp", "open(", "os.listdir", "os.path",
    ):
        assert forbidden not in python_source


def test_frontend_behavior_storage_assets_and_lifecycle():
    source = V2 / "web" / "animate_progress.js"
    syntax = subprocess.run(
        ["node", "--check", str(source)], cwd=V2, text=True,
        capture_output=True, timeout=30, check=False,
    )
    assert syntax.returncode == 0, syntax.stdout + syntax.stderr
    completed = subprocess.run(
        ["node", "--experimental-vm-modules",
         str(V2 / "tests" / "animate_progress_frontend_harness.mjs"),
         str(source)],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Animate Progress behavior, storage, assets, and lifecycle" in completed.stdout


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-animate-progress"
        / "xf6f1776" / "comfyui-animate-progress-xf6f1776"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-animate-progress" / "xf6f1776"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_do_not_dirty_snapshot_with_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
