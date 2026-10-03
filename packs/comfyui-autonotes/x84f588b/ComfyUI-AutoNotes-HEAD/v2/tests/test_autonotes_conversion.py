from __future__ import annotations

import ast
import copy
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
COMMIT = "84f588b3ffd96f299d92b20e94ec66d9eec194ef"
DTS_SHA256 = "9b66bc80783e3c27e0df35187fed90a1d456e3865061b3289c320077c9004f9b"
PYI_SHA256 = "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402


def _import_v2():
    name = "_secure_autonotes_conversion_test"
    sys.modules.pop(name, None)
    sys.modules.pop(f"{name}.autonotes", None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _tree(root: pathlib.Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or any(part in {
            ".git", "__pycache__", ".pytest_cache",
        } for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _generated_manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "autonotes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
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
        "web_directory": "web",
    }


def test_exact_pristine_and_secure_census():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    tree = ast.parse((PACK / "autonotes.py").read_text())
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "AutoNotesNode" in classes
    routes = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for decorator in node.decorator_list
        if "PromptServer.instance.routes" in ast.unparse(decorator)
    ]
    assert len(routes) == 8
    # One logical extension. The extra registration is a mutually exclusive
    # startup helper used only while the legacy canvas is unavailable.
    assert (PACK / "web" / "autonotes.js").read_text().count(
        "app.registerExtension({") == 2

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == {"AutoNotesNode"}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"AutoNotesNode": "Auto Notes"}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.autonotes_test")
    assert set(loaded.node_mappings) == {"AutoNotesNode"}
    assert loaded.frontend_permissions == frozenset()
    assert loaded.web_directory == V2 / "web"


def test_presence_node_preserves_schema_and_behavior():
    node = _import_v2().NODE_CLASS_MAPPINGS["AutoNotesNode"]
    schema = node.GET_SCHEMA()
    assert schema.node_id == "AutoNotesNode"
    assert schema.display_name == "Auto Notes"
    assert schema.category == "AutoNotes"
    assert schema.inputs == [] and schema.outputs == []
    assert schema.is_output_node is True
    assert node.SDK_REFS is True and node.SDK_PERMISSIONS == ()
    assert node.execute().result is None


def test_manifest_contract_and_static_boundary_are_exact():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA256

    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in ("folder_paths", "PromptServer", "aiohttp", "subprocess"):
        assert forbidden not in python_source
    frontend = (V2 / "web" / "autonotes.js").read_text()
    for required in (
        "comfy.storage", "comfy.onSelectionChanged", "comfy.onNodeChanged",
        "comfy.workflow.name", "comfy.ui.addSidebarTab", "comfy.ui.showDialog",
    ):
        assert required in frontend
    for forbidden in (
        "localStorage", "indexedDB", "innerHTML", "document.", "window.",
        "fetch(", "setInterval(",
    ):
        assert forbidden not in frontend


def test_frontend_behavior_security_and_failure_atomic_storage():
    completed = subprocess.run(
        ["node", "--experimental-vm-modules",
         str(V2 / "tests" / "autonotes_frontend_harness.mjs")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "AutoNotes frontend behavior and security ok" in completed.stdout


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    fresh = tmp_path / "comfyui-autonotes" / "x84f588b"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
