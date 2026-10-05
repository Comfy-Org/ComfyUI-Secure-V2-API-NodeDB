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


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
SECURE_ROOT = pathlib.Path(
    os.environ.get("SECURE_NODES_ROOT", "/Users/ben/comfy/ComfyUI_secure_nodes")
).resolve()
BACKEND = SECURE_ROOT / "backend"
CORE = pathlib.Path(
    os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes")
).resolve()
COMMIT = "dbfef86c7c5f2f38c3b49e55acdbc02e7859433b"
TREE = "81cadef8751df8d0fdb9ba421b62ee47456b165c"
COMFY_API_DTS_SHA256 = (
    "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
)
COMFY_API_PYI_SHA256 = (
    "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
)
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    ".gitignore",
    "LICENSE",
    "README.md",
    "__init__.py",
    "example.png",
    "pyproject.toml",
    "web/workflow_prettier.js",
}

for path in (str(SECURE_ROOT), str(BACKEND), str(CORE)):
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


def _tree(root: pathlib.Path, *, omit_v2: bool = False) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
               for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _generated_manifest(pack) -> dict:
    prefix = pack.__name__ + "."
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": node_class.__module__.removeprefix(prefix),
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
        "frontend_permissions": [],
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def test_pinned_pristine_actual_census_manifest_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert TREE == "81cadef8751df8d0fdb9ba421b62ee47456b165c"
    assert set(_tree(PACK, omit_v2=True)) == PRISTINE_FILES

    pristine = _import_package(PACK, "_workflow_prettier_pristine_census")
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"WorkflowPrettifier"}
    assert set(pristine.NODE_DISPLAY_NAME_MAPPINGS) == {"WorkflowPrettifier"}
    assert pristine.WEB_DIRECTORY == "./web"
    assert (PACK / "web" / "workflow_prettier.js").read_text().count(
        "app.registerExtension({"
    ) == 1
    assert not any(
        token in path.read_text(errors="replace")
        for path in PACK.rglob("*.py")
        if "v2" not in path.relative_to(PACK).parts
        for token in ("PromptServer", "routes.", "aiohttp")
    )

    pack = _import_package(V2, "_secure_workflow_prettier_conversion_test")
    assert set(pack.NODE_CLASS_MAPPINGS) == {"WorkflowPrettifier"}
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == {"WorkflowPrettifier"}
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256
    )
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256
    )

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.workflow_prettier_conversion_test",
    )
    assert set(loaded.node_mappings) == {"WorkflowPrettifier"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schema_preserves_all_inputs_defaults_bounds_and_noop_behavior():
    pristine = _import_package(PACK, "_workflow_prettier_pristine_schema")
    secure = _import_package(V2, "_workflow_prettier_secure_schema")
    original = pristine.NODE_CLASS_MAPPINGS["WorkflowPrettifier"]
    assert original().noop(
        layout="Linear",
        direction="Top to Bottom",
        group_handling="Ignore Groups",
        horizontal_spacing=50,
        vertical_spacing=40,
        group_padding=30,
    ) == ()

    schema = secure.NODE_CLASS_MAPPINGS["WorkflowPrettifier"].GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "WorkflowPrettifier"
    assert schema.display_name == "Workflow Prettifier"
    assert schema.category == "utils"
    assert schema.is_output_node is False
    assert schema.outputs == []
    assert [item.id for item in schema.inputs] == [
        "layout", "direction", "group_handling", "horizontal_spacing",
        "vertical_spacing", "group_padding",
    ]
    assert [item.options for item in schema.inputs[:3]] == [
        ["Layered (Vertical Stacks)", "Linear", "Compact (Tight Rectangle)", "Sort by Type"],
        ["Left to Right", "Top to Bottom", "Right to Left"],
        ["Auto (Respect Groups)", "Respect Groups", "Ignore Groups"],
    ]
    assert [
        (item.default, item.min, item.max, item.step)
        for item in schema.inputs[3:]
    ] == [
        (100, 30, 400, 10),
        (100, 20, 200, 10),
        (100, 20, 150, 10),
    ]
    node_class = secure.NODE_CLASS_MAPPINGS["WorkflowPrettifier"]
    assert node_class.SDK_REFS is False
    assert node_class.SDK_PERMISSIONS == ()


def test_real_isolated_guest_executes_noop_without_authority():
    pack = _import_package(V2, "_workflow_prettier_secure_guest")
    node_class = pack.NODE_CLASS_MAPPINGS["WorkflowPrettifier"]

    async def run():
        session = await GuestSession(
            "workflow-prettier-conversion", guest_runtime_root=V2
        ).start()
        refs = _sdk.InProcessRefResolver()
        try:
            plan = _sdk.ExecutionPlan(
                prompt_id="workflow-prettier",
                node_id="1",
                node_type="WorkflowPrettifier",
                tier="sandbox",
                node_module=node_class.__module__,
                inputs={
                    "layout": "Compact (Tight Rectangle)",
                    "direction": "Right to Left",
                    "group_handling": "Respect Groups",
                    "horizontal_spacing": 70,
                    "vertical_spacing": 40,
                    "group_padding": 60,
                },
                permissions=(),
                method="execute",
            )
            context = _sdk.InProcessCtxProvider().build(plan)
            runtime = _sdk.Runtime(
                refs=refs,
                ctx=context,
                ops=_sdk.InProcessOps(),
            )
            result = await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
            assert result.result is None
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_lifecycle_harnesses():
    source = "\n".join(
        path.read_text(errors="replace") for path in sorted((V2 / "web").glob("*.js"))
    )
    for forbidden in (
        "/scripts/app.js", "app.registerExtension", "LGraphCanvas", "LiteGraph",
        "app.graph", "._nodes", "._groups", "window.", "globalThis",
        "document.addEventListener", "localStorage", "sessionStorage", "fetch(",
        "setInterval(", "setTimeout(",
    ):
        assert forbidden not in source
    for required in (
        'from "/comfy/api/v2.js"', "graph.nodes()", "graph.links()", "graph.groups()",
        "graph.selection()", "graph.batch", "node.setPosition", "group.setBounds",
        "api.commands.register", "api.ui.addActionBarButton", "builder.addMenuItem",
        "api.onDocumentClosed", "node.widgets.mount",
    ):
        assert required in source

    for script, marker in (
        ("workflow_prettier_layout_test.mjs", "workflow prettier layout behavior: PASS"),
        ("workflow_prettier_frontend_harness.mjs", "workflow prettier frontend lifecycle: PASS"),
    ):
        command = ["node"]
        if "frontend_harness" in script:
            command.append("--experimental-vm-modules")
        command.extend([str(V2 / "tests" / script)])
        if "frontend_harness" in script:
            command.append(str(V2))
        completed = subprocess.run(
            command,
            cwd=V2,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert marker in completed.stdout


def test_python_surface_has_no_ambient_authority():
    source = "\n".join(path.read_text(errors="replace") for path in sorted(V2.glob("*.py")))
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "import server", "from server", "folder_paths",
        "PromptServer", "open(", "eval(", "exec(", "sdk.ctx(",
    ):
        assert forbidden not in source
    assert "from comfy_api.latest import io" in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        PACK_DB / "patches" / "comfyui-workflow-prettier" / "xdbfef86"
        / "comfyui-workflow-prettier-xdbfef86"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-workflow-prettier" / "xdbfef86"
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
    assert not list(PACK.rglob(".ruff_cache"))
