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
COMMIT = "61d10e850a2706ce0be4a070f34b2295624c22bd"
TREE = "dee06327341a23143b0b50b374bf2b6a6f34ef8f"
COMFY_API_DTS_SHA256 = (
    "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
)
COMFY_API_PYI_SHA256 = (
    "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
)
COLORS = ["红色", "绿色", "蓝色", "琥珀", "紫色", "青色", "白色"]
PRISTINE_FILES = {
    ".comfyignore", ".gitignore", "LICENSE", "README.md", "__init__.py",
    "docs/demo.png", "js/nixie_timer.js", "node.zip", "pyproject.toml",
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


def _import_v2(name="_secure_nixie_timer_conversion_test"):
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
    assert "node.zip" not in _tree(V2)
    assert "js/nixie_timer.js" not in _tree(V2)

    pristine = ast.parse((PACK / "__init__.py").read_text())
    mappings = [
        item for item in pristine.body
        if isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Name)
                and target.id == "NODE_CLASS_MAPPINGS" for target in item.targets)
    ]
    assert len(mappings) == 1
    assert len(mappings[0].value.keys) == 1
    assert (PACK / "js" / "nixie_timer.js").read_text().count(
        "app.registerExtension({"
    ) == 1
    pristine_python = "\n".join(path.read_text() for path in PACK.glob("*.py"))
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == {"NixieTimer"}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {
        "NixieTimer": "🕰️ 辉光管计时器",
    }
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.nixie_timer_test")
    assert set(loaded.node_mappings) == {"NixieTimer"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schema_and_noop_execution_preserve_upstream_behavior():
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["NixieTimer"]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "NixieTimer"
    assert schema.display_name == "🕰️ 辉光管计时器"
    assert schema.category == "utils"
    assert schema.is_output_node is False
    assert len(schema.inputs) == 1
    color = schema.inputs[0]
    assert color.id == "tube_color"
    assert color.io_type == "COMBO"
    assert list(color.options) == COLORS
    assert color.default == "红色"
    assert schema.outputs == []
    assert node_class.SDK_REFS is False
    assert node_class.SDK_PERMISSIONS == ()
    assert node_class.execute(tube_color="绿色").result is None


def test_real_isolated_guest_executes_noop_without_authority():
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["NixieTimer"]

    async def run():
        session = await GuestSession("nixie-timer-conversion").start()
        try:
            plan = _sdk.ExecutionPlan(
                prompt_id="nixie-1",
                node_id="1",
                node_type="NixieTimer",
                tier="sandbox",
                node_module=node_class.__module__,
                inputs={"tube_color": "青色"},
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


def test_frontend_preserves_timer_locale_theme_resize_and_lifecycle():
    source = (V2 / "web" / "nixie_timer.js").read_text()
    assert source.count("comfy.defs.extend(NODE_TYPE") == 1
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage", "fetch(",
        "app.registerExtension", "queuePrompt", "addDOMWidget", ".prototype",
        "ResizeObserver", "MutationObserver", "WebSocket", "EventSource",
        "navigator.", "eval(", "Function(",
    ):
        assert forbidden not in source
    for required in (
        "node.widgets.mount", "comfy.queue.onBeforeRun", "comfy.queue.onAfterRun",
        "comfy.queue.onRejected", "comfy.queue.onPendingChanged",
        "comfy.queue.onInterrupted", 'comfy.backend.on("execution_error"',
        'comfy.settings.onChange("Comfy.Locale"', "builder.onResized",
        "builder.onConfigured", "builder.onRemoved", "cancelAnimationFrame",
        "clearInterval", "releaseSharedLifecycle", "ownerDocument",
    ):
        assert required in source

    completed = subprocess.run(
        ["node", str(V2 / "tests" / "nixie_timer_frontend_harness.mjs")],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "nixie timer frontend behavior/security tests passed" in completed.stdout


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
        REPO / "pack-db" / "patches" / "comfyui-nixie-timer"
        / "x61d10e8" / "comfyui-nixie-timer-x61d10e8"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-nixie-timer" / "x61d10e8"
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
