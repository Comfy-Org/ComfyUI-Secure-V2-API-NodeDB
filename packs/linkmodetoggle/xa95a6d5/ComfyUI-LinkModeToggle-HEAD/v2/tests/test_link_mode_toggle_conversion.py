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
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "a95a6d50603495130c1182ba7c85e9eb587e5e33"
COMFY_API_DTS_SHA256 = (
    "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
)
COMFY_API_PYI_SHA256 = (
    "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
)

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402


def _import_v2(name="_secure_link_mode_toggle_conversion_test"):
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
        if any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in relative.parts
        ):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def test_pinned_frontend_only_census_manifest_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine = ast.parse((PACK / "__init__.py").read_text())
    mappings = {}
    for node in pristine.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                mappings[target.id] = node.value
    assert mappings["NODE_CLASS_MAPPINGS"].keys == []
    assert mappings["NODE_DISPLAY_NAME_MAPPINGS"].keys == []
    pristine_js = "\n".join(
        path.read_text(errors="replace") for path in (PACK / "web").rglob("*.js")
    )
    assert pristine_js.count("app.registerExtension({") == 1

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {}
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == {
        "format": "comfy-secure-nodes-v1",
        "nodes": {},
        "runtime": {
            "python": {"requires": ">=3.13,<3.14", "resolved": "3.13"}
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
        mount_name="custom_nodes.link_mode_toggle_conversion_test",
    )
    assert loaded.node_mappings == {}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_frontend_behavior_security_and_idempotent_teardown():
    sources = "\n".join(
        path.read_text(errors="replace") for path in sorted(V2.rglob("*.js"))
    )
    assert sources.count('from "/comfy/api/v2.js"') == 1
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage",
        "MutationObserver", "app.registerExtension", "links_render_mode",
        "setLinkRenderMode", "render_curved_links", "fetch(",
    ):
        assert forbidden not in sources
    for required in (
        "comfy.settings.get", "comfy.settings.set", "comfy.settings.onChange",
        "comfy.commands.register", 'scope: "canvas"',
        "comfy.ui.addActionBarButton", "comfy.onReady",
        "button?.remove()", "stopSettingChange?.()",
    ):
        assert required in sources

    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "link_mode_toggle_frontend_harness.mjs"),
            str(V2 / "web" / "index.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: LinkModeToggle" in completed.stdout


def test_python_surface_has_no_host_or_mutable_pack_access():
    source = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(V2.glob("*.py"))
    )
    for forbidden in (
        "import folder_paths", "from folder_paths", "import server",
        "from server", "PromptServer", "aiohttp", "open(", "Path(",
        "subprocess", "requests", "socket",
    ):
        assert forbidden not in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "linkmodetoggle" / "xa95a6d5"
        / "linkmodetoggle-xa95a6d5"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "linkmodetoggle" / "xa95a6d5"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_javascript_syntax_and_cache_cleanliness():
    completed = subprocess.run(
        ["node", "--check", str(V2 / "web" / "index.js")],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
