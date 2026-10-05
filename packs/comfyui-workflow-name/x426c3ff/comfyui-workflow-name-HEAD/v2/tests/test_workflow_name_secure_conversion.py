from __future__ import annotations

import asyncio
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import types

import pytest


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "426c3ff09e24485b06b3df2565ca7380e100aa56"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "comfyui-workflow-name" / "x426c3ff" / (
    "comfyui-workflow-name-x426c3ff"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402


def _import_package(root: pathlib.Path, name: str):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_v2():
    return _import_package(V2, "_secure_workflow_name_test")


class _Routes:
    def __init__(self):
        self.registered = []

    def post(self, route):
        def decorator(function):
            self.registered.append(("POST", route, function))
            return function
        return decorator


@contextlib.contextmanager
def _upstream_copy(tmp_path: pathlib.Path):
    root = tmp_path / "upstream-workflow-name"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2", "__pycache__"))
    routes = _Routes()
    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=routes)
    )
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.web = types.SimpleNamespace(
        json_response=lambda value, status=200: {"value": value, "status": status}
    )
    previous = {name: sys.modules.get(name) for name in ("server", "aiohttp")}
    sys.modules["server"] = server
    sys.modules["aiohttp"] = aiohttp
    try:
        yield _import_package(root, "_upstream_workflow_name_test"), routes
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def _generated_manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status"
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


def _tree(root: pathlib.Path) -> dict[str, str]:
    result = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if not item.is_file() or any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def test_pinned_pristine_registration_route_and_secure_census_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    with _upstream_copy(tmp_path) as (upstream, routes):
        assert upstream.NODE_CLASS_MAPPINGS == {
            "WorkflowName": upstream.WorkflowNameNode
        }
        assert upstream.NODE_DISPLAY_NAME_MAPPINGS == {
            "WorkflowName": "Workflow Name"
        }
        assert upstream.WEB_DIRECTORY == "./web"
        assert [(method, route) for method, route, _ in routes.registered] == [
            ("POST", "/workflow_name/set")
        ]
    pristine_frontend = (PACK / "web" / "workflow_name.js").read_text()
    assert pristine_frontend.count("app.registerExtension({") == 1
    assert "registerNodeType" not in pristine_frontend

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"WorkflowName": pack.WorkflowNameNode}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.workflow_name_test")
    assert set(loaded.node_mappings) == {"WorkflowName"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_is_exact_and_backend_is_differential_to_upstream(tmp_path):
    node = _import_v2().WorkflowNameNode
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "WorkflowName", "Workflow Name", "utils"
    )
    assert [(item.id, item.io_type, item.default) for item in schema.inputs] == [
        ("workflow_name", "STRING", "NO_WORKFLOW_NAME")
    ]
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("workflow_name", "STRING")
    ]
    assert node.SDK_REFS is False and node.SDK_PERMISSIONS == ()
    with _upstream_copy(tmp_path) as (upstream, _routes):
        legacy = upstream.WorkflowNameNode()
        for value in (
            "workflow", "  spaced workflow  ", "", "\t\n",
            "NO_WORKFLOW_NAME", "日本語 workflow",
        ):
            assert node.execute(value).result == legacy.get_name(value)
    with pytest.raises(TypeError, match="workflow_name"):
        node.execute(42)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("folder/My: Flow.json", "My_ Flow"),
        (r"C:\bad<name>.json", "C__bad_name"),
        (" ...__ ", "NO_WORKFLOW_NAME"),
        ("name.JSON", "name.JSON"),
        ("bad\x01name.json", "bad_name"),
        ("", "NO_WORKFLOW_NAME"),
    ],
)
def test_frontend_sanitizer_cases_match_the_pristine_route_policy(tmp_path, raw, expected):
    with _upstream_copy(tmp_path) as (upstream, _routes):
        assert upstream.sanitize_filename(raw) == expected


def test_real_isolated_guest_executes_without_capabilities():
    node = _import_v2().WorkflowNameNode

    async def run():
        plan = _sdk.ExecutionPlan(
            prompt_id="workflow-name-test", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={"workflow_name": "  secure workflow  "}, permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=_sdk.InProcessRefResolver(),
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession("workflow-name-pack", guest_runtime_root=V2).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == ("secure workflow",)
    assert guest_pid not in (None, os.getpid())


def test_manifest_security_contract_frontend_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "PromptServer", "aiohttp", "folder_paths", "subprocess", "requests",
        "import socket", "open(", "pathlib", "os.",
    ):
        assert forbidden not in python_source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "/scripts/api.js", "LiteGraph", "app.graph",
        "app.queuePrompt", "document.", "window.", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "innerHTML", "setInterval",
    ):
        assert forbidden not in frontend
    assert len(re.findall(r"comfy\.queue\.onBeforeRun|api\.queue\.onBeforeRun", frontend)) == 1
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_first_run_subgraph_sync_sanitization_and_teardown():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "workflow_name_frontend_harness.mjs"),
            str(V2 / "web" / "workflow_name.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure WorkflowName" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-workflow-name" / "x426c3ff"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_bytecode_or_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
