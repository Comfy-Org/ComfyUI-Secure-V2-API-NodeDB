from __future__ import annotations

import ast
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
import types


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "e6591c62c3187c71f70133dfe3dbb9fbe5f8d3cc"
COMFY_API_DTS_SHA256 = (
    "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
)
COMFY_API_PYI_SHA256 = (
    "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
)
NODE_IDS = {"SolidlimeMultiBoolPanel"}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_v2(name="_secure_multi_bool_panel_conversion_test"):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
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
        "web_directory": "web",
    }


def _runtime():
    return _sdk.Runtime(
        refs=_sdk.InProcessRefResolver(),
        ctx=types.SimpleNamespace(),
        ops=_sdk.InProcessOps(),
    )


def test_pinned_census_manifest_and_authoritative_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine_mapping = ast.parse((PACK / "multi_bool_panel.py").read_text())
    mapping = next(
        node for node in pristine_mapping.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name)
                and target.id == "NODE_CLASS_MAPPINGS" for target in node.targets)
    )
    assert isinstance(mapping.value, ast.Dict)
    assert {key.value for key in mapping.value.keys} == NODE_IDS
    assert sum(
        path.read_text(errors="replace").count("app.registerExtension({")
        for path in (PACK / "web").rglob("*.js")
    ) == 1

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(pack))
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256)
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256)

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.multi_bool_panel_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schema_and_noop_behavior_preserve_upstream_contract():
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["SolidlimeMultiBoolPanel"]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "SolidlimeMultiBoolPanel"
    assert schema.display_name == "Multi Bool Panel"
    assert schema.category == "Logic"
    assert [item.id for item in schema.inputs] == ["mode"]
    assert schema.inputs[0].io_type == "COMBO"
    assert schema.inputs[0].options == ["widgets", "bypass", "mute"]
    assert schema.inputs[0].default == "widgets"
    assert schema.outputs == []
    assert schema.is_output_node is False
    assert node_class.SDK_REFS is True
    assert node_class.SDK_PERMISSIONS == ()
    assert node_class.execute(mode="widgets").result is None


def test_node_executes_in_real_isolated_guest():
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.multi_bool_panel_guest_test",
    )
    node_class = loaded.node_mappings["SolidlimeMultiBoolPanel"]

    async def run():
        session = await GuestSession("multi-bool-panel-conversion").start()
        try:
            result = await session.execute(
                _sdk.ExecutionPlan(
                    prompt_id="multi-bool-panel-conversion",
                    node_id="1",
                    node_type="SolidlimeMultiBoolPanel",
                    tier="sandbox",
                    node_module=node_class.__module__,
                    inputs={"mode": "widgets"},
                    method="execute",
                ),
                _runtime(),
                capabilities=set(),
            )
            assert session.last_guest_pid not in (None, os.getpid())
            assert result.result is None
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_teardown():
    source = (V2 / "web" / "js" / "multi_bool_panel.js").read_text()
    assert source.count("comfy.defs.extend(PANEL_TYPE") == 1
    for forbidden in (
        "fetch(", "window.", "document.", "localStorage", "sessionStorage",
        "MutationObserver", "app.registerExtension", "addDOMWidget",
        "app.graph", "._nodes", "._groups", "setDirtyCanvas",
    ):
        assert forbidden not in source
    for required in (
        "node.widgets.mount", "graph.nodes()", "comfy.graph",
        "graph.groups()", "comfy.onNodeChanged", "comfy.onWorkflowLoaded",
        "clearInterval", "setSizeConstraints", "setProperty",
    ):
        assert required in source

    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "multi_bool_panel_frontend_harness.mjs"),
            str(V2 / "web" / "js" / "multi_bool_panel.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: Multi Bool Panel" in completed.stdout


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
        REPO / "pack-db" / "patches" / "comfyui-multi-bool-panel"
        / "xe6591c6" / "comfyui-multi-bool-panel-xe6591c6"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-multi-bool-panel" / "xe6591c6"
    fresh.mkdir(parents=True)
    shutil.copytree(
        PACK,
        fresh / PACK.name,
        ignore=shutil.ignore_patterns("v2"),
    )
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_do_not_dirty_pristine_or_v2_with_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
