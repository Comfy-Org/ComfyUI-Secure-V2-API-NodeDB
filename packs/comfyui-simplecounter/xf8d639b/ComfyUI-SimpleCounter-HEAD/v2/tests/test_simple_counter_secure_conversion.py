from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys

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
COMMIT = "f8d639b2849b0956309eb662b41a264f1dca5d46"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "comfyui-simplecounter" / "xf8d639b" / (
    "comfyui-simplecounter-xf8d639b"
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
    return _import_package(V2, "_secure_simple_counter_test")


def _import_upstream():
    return _import_package(PACK, "_upstream_simple_counter_test")


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


def test_pinned_pristine_registration_load_and_secure_census_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    upstream = _import_upstream()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"Simple Counter"}
    upstream_class = upstream.NODE_CLASS_MAPPINGS["Simple Counter"]
    assert upstream_class.__name__ == "SimpleCounter"
    assert upstream.WEB_DIRECTORY == "./js"
    source = ast.parse((PACK / "SimpleCounter.py").read_text())
    assert {item.name for item in source.body if isinstance(item, ast.ClassDef)} == {
        "SimpleCounter"
    }
    frontend = (PACK / "js" / "SimpleCounter.js").read_text()
    assert frontend.count("app.registerExtension({") == 1
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py") if V2 not in path.parents
    )
    assert "PromptServer" not in pristine_python and "routes." not in pristine_python

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"Simple Counter": pack.SimpleCounter}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.simple_counter_test")
    assert set(loaded.node_mappings) == {"Simple Counter"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_and_always_changed_contract_are_exact():
    node = _import_v2().SimpleCounter
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "Simple Counter", "Simple Counter", "utils"
    )
    assert schema.not_idempotent is True
    assert [(item.id, item.io_type, item.default, item.min, item.step)
            for item in schema.inputs] == [
        ("start", "INT", 0, 0, 1), ("count", "INT", 0, 0, 1),
    ]
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("index", "INT")
    ]
    assert node.SDK_REFS is False and node.SDK_PERMISSIONS == ()
    assert math.isnan(node.fingerprint_inputs(start=0, count=0))


@pytest.mark.parametrize(
    "start,count",
    [(0, 0), (0, 1), (5, 5), (5, 99), (2**31, 2**31 + 3)],
)
def test_backend_is_differential_to_upstream(start, count):
    upstream_pack = _import_upstream()
    upstream = upstream_pack.NODE_CLASS_MAPPINGS["Simple Counter"]().run(start, count)
    secure = _import_v2().SimpleCounter.execute(start, count)
    assert secure.result == upstream == (count,)


def test_backend_rejects_values_outside_the_declared_integer_domain():
    node = _import_v2().SimpleCounter
    for name, values in (("start", (-1, True, 1.5)), ("count", (-1, True, 1.5))):
        for value in values:
            inputs = {"start": 0, "count": 0, name: value}
            with pytest.raises((TypeError, ValueError), match=name):
                node.execute(**inputs)


def test_real_isolated_guest_executes_without_capabilities():
    node = _import_v2().SimpleCounter

    async def run():
        plan = _sdk.ExecutionPlan(
            prompt_id="simple-counter-test", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={"start": 8, "count": 11}, permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=_sdk.InProcessRefResolver(),
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession("simple-counter-pack", guest_runtime_root=V2).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == (11,)
    assert guest_pid not in (None, os.getpid())


def test_manifest_security_contract_frontend_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "socket", "open(", "pathlib", "torch", "numpy",
    ):
        assert forbidden not in python_source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "/scripts/api.js", "LiteGraph", "app.graph",
        "app.canvas", "document.", "window.", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "innerHTML",
    ):
        assert forbidden not in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_queue_ordering_rejection_isolation_and_cleanup():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "simple_counter_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure SimpleCounter" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-simplecounter" / "xf8d639b"
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
