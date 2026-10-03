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
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "ff1021e6c817e352fcec8e499c74a5de78afd9b7"
TREE = "ad187c9bd059979126391b3255235335abff4533"
COMFY_API_DTS_SHA256 = (
    "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
)
COMFY_API_PYI_SHA256 = (
    "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
)
PRISTINE_FILES = {
    ".gitignore", "LICENSE", "README.md", "__init__.py",
    "assets/Calculator.png", "calculator.py", "js/calculator.js",
    "pyproject.toml",
}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_v2(name="_secure_calculator_conversion_test"):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
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


def _generated_manifest(pack) -> dict:
    nodes = {}
    prefix = pack.__name__ + "."
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
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def test_pinned_pristine_census_manifest_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert TREE in (V2 / "SECURE_CONVERSION.md").read_text()
    assert set(_tree(PACK, omit_v2=True)) == PRISTINE_FILES

    pristine_init = ast.parse((PACK / "__init__.py").read_text())
    entrypoints = [
        item for item in pristine_init.body
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "comfy_entrypoint"
    ]
    assert len(entrypoints) == 1
    pristine_nodes = ast.parse((PACK / "calculator.py").read_text())
    node_classes = [
        item.name for item in pristine_nodes.body
        if isinstance(item, ast.ClassDef)
        and any(isinstance(base, ast.Attribute) and base.attr == "ComfyNode"
                for base in item.bases)
    ]
    assert node_classes == ["Calculator"]
    assert (PACK / "js" / "calculator.js").read_text().count(
        "app.registerExtension({"
    ) == 1
    pristine_python = "\n".join(path.read_text() for path in PACK.glob("*.py"))
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == {"Calculator"}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"Calculator": "Calculator 🧮"}
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.calculator_test")
    assert set(loaded.node_mappings) == {"Calculator"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schema_and_noop_execution_preserve_upstream_behavior():
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["Calculator"]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "Calculator"
    assert schema.display_name == "Calculator 🧮"
    assert schema.category == "Calculator 🧮"
    assert schema.inputs == []
    assert schema.outputs == []
    assert schema.is_output_node is False
    assert node_class.SDK_REFS is False
    assert node_class.SDK_PERMISSIONS == ()
    assert node_class.execute().result is None


def test_real_isolated_guest_executes_noop_without_authority():
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["Calculator"]

    async def run():
        session = await GuestSession("calculator-conversion").start()
        try:
            plan = _sdk.ExecutionPlan(
                prompt_id="calculator-1",
                node_id="1",
                node_type="Calculator",
                tier="sandbox",
                node_module=node_class.__module__,
                inputs={},
                permissions=(),
                method="execute",
            )
            runtime = _sdk.Runtime(
                refs=_sdk.InProcessRefResolver(),
                ctx=_sdk.InProcessCtxProvider().build(plan),
                ops=_sdk.InProcessOps(),
            )
            result = await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
            assert result.result is None
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_preserves_calculator_behavior_isolation_and_lifecycle():
    source = (V2 / "web" / "calculator.js").read_text()
    assert source.count("comfy.defs.extend(NODE_TYPE") == 1
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage", "fetch(",
        "app.registerExtension", "addDOMWidget", ".prototype", "eval(",
        "Function(", "ResizeObserver", "MutationObserver", "WebSocket",
        "EventSource", "navigator.",
    ):
        assert forbidden not in source
    for required in (
        "node.widgets.mount", "builder.onCreated", "builder.onRemoved",
        "container.ownerDocument", "removeEventListener", "serialize: false",
        "sendToPrompt: false", "setSizeConstraints",
    ):
        assert required in source

    syntax = subprocess.run(
        ["node", "--check", str(V2 / "web" / "calculator.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert syntax.returncode == 0, syntax.stdout + syntax.stderr
    completed = subprocess.run(
        ["node", "--experimental-vm-modules",
         str(V2 / "tests" / "calculator_frontend_harness.mjs"),
         str(V2 / "web" / "calculator.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Calculator behavior, isolation, and lifecycle" in completed.stdout


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
        REPO / "pack-db" / "patches" / "comfyui-calculator"
        / "xff1021e" / "comfyui-calculator-xff1021e"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-calculator" / "xff1021e"
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
