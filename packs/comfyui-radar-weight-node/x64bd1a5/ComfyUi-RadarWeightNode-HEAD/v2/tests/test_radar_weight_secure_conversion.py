from __future__ import annotations

import ast
import asyncio
import contextlib
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
COMMIT = "64bd1a505fad852f25ef7b5894669b53e1bb4ed0"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "comfyui-radar-weight-node" / "x64bd1a5" / (
    "comfyui-radar-weight-node-x64bd1a5"
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
    return _import_package(V2, "_secure_radar_weight_test")


class _Routes:
    def __init__(self):
        self.registered = []

    def _register(self, method, route):
        def decorator(function):
            self.registered.append((method, route, function))
            return function
        return decorator

    def get(self, route):
        return self._register("GET", route)

    def post(self, route):
        return self._register("POST", route)


@contextlib.contextmanager
def _upstream_copy(tmp_path: pathlib.Path):
    root = tmp_path / "upstream-radar"
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
        yield _import_package(root, "_upstream_radar_weight_test"), routes
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


def test_pinned_pristine_registration_routes_and_secure_census_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    with _upstream_copy(tmp_path) as (upstream, routes):
        assert set(upstream.NODE_CLASS_MAPPINGS) == {"RadarWeightsNode"}
        assert upstream.NODE_DISPLAY_NAME_MAPPINGS == {
            "RadarWeightsNode": "Radar Weights Node"
        }
        assert upstream.WEB_DIRECTORY == "js"
        assert [(method, route) for method, route, _ in routes.registered] == [
            ("POST", "/radar_weights/update_weights"),
            ("GET", "/radar_weights/get_weights/{node_id}"),
            ("GET", "/radar_weights/get_latest_weights"),
            ("GET", "/radar_weights/get_all_weights"),
        ]
    source = ast.parse((PACK / "radar_weights_node.py").read_text())
    assert {item.name for item in source.body if isinstance(item, ast.ClassDef)} == {
        "RadarWeightsNode"
    }
    frontend = (PACK / "js" / "radar_weights_node.js").read_text()
    assert frontend.count("app.registerExtension({") == 1
    assert "registerNodeType" not in frontend

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"RadarWeightsNode": pack.RadarWeightsNode}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.radar_weight_test")
    assert set(loaded.node_mappings) == {"RadarWeightsNode"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_registered_contract_and_bounded_serialized_state():
    node = _import_v2().RadarWeightsNode
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "RadarWeightsNode", "Radar Weights Node", "Spider/Widgets"
    )
    assert [
        (item.id, item.io_type, item.default, item.min, item.max, item.step)
        for item in schema.inputs[:1]
    ] == [("axes_count", "INT", 5, 3, 10, 1)]
    sync = schema.inputs[1]
    assert (sync.id, sync.io_type, sync.default, sync.socketless, sync.advanced) == (
        "_weights_sync", "STRING", "", True, True
    )
    assert [item.name for item in schema.hidden] == ["unique_id"]
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        (str(index), "FLOAT") for index in range(1, 11)
    ]
    assert node.SDK_REFS is False and node.SDK_PERMISSIONS == ()


@pytest.mark.parametrize(
    "axes_count,weights",
    [
        (3, "1,1,1"),
        (4, "0,0.25,1.234,2"),
        (6, "0.1,0.2,0.3"),
        (3, "0.1,0.2,0.3,0.4,0.5"),
        (10, ",".join(str(index / 10) for index in range(10))),
    ],
)
def test_backend_is_differential_to_upstream(tmp_path, axes_count, weights):
    with _upstream_copy(tmp_path) as (upstream, _routes):
        implementation = sys.modules[upstream.RadarWeightsNode.__module__]
        implementation.CURRENT_WEIGHTS = {"node-1": weights}
        expected = upstream.RadarWeightsNode().generate(
            axes_count, unique_id="node-1", _weights_sync="stale"
        )
    actual = _import_v2().RadarWeightsNode.execute(
        axes_count, _weights_sync=weights, unique_id="node-1"
    ).result
    assert actual == expected


def test_backend_bounds_malformed_state_and_fingerprint_are_fail_closed():
    node = _import_v2().RadarWeightsNode
    assert node.execute(3, "malformed").result == (1.0, 1.0, 1.0) + (0.0,) * 7
    assert node.execute(3, "-1,1,1").result == (1.0, 1.0, 1.0) + (0.0,) * 7
    assert node.execute(3, "1," * 200).result == (1.0, 1.0, 1.0) + (0.0,) * 7
    for axes in (2, 11, True, 4.5):
        with pytest.raises((TypeError, ValueError), match="axes_count"):
            node.execute(axes, "1,1,1")
    assert node.fingerprint_inputs(3, "1,1,1") == "3-1,1,1"
    assert node.fingerprint_inputs(3, "1,1,2") != node.fingerprint_inputs(3, "1,1,1")


def test_real_isolated_guest_executes_without_capabilities():
    node = _import_v2().RadarWeightsNode

    async def run():
        plan = _sdk.ExecutionPlan(
            prompt_id="radar-weight-test", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={
                "axes_count": 4,
                "_weights_sync": "0,0.25,1.25,2",
                "unique_id": "1",
            },
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=_sdk.InProcessRefResolver(),
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession("radar-weight-pack", guest_runtime_root=V2).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == (0.0, 0.25, 1.25, 2.0) + (0.0,) * 6
    assert guest_pid not in (None, os.getpid())


def test_manifest_security_contract_frontend_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "import socket", "open(", "pathlib", "CURRENT_WEIGHTS", "WEIGHTS_FILE",
    ):
        assert forbidden not in python_source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "/scripts/api.js", "LiteGraph", "app.graph",
        "app.canvas", "document.", "window.", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "innerHTML", "setInterval",
    ):
        assert forbidden not in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_mounted_geometry_state_isolation_and_cleanup():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "radar_weight_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure RadarWeight" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-radar-weight-node" / "x64bd1a5"
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
