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
COMMIT = "2453383e1249054439d81bf53145edecc9ee79a7"
COMFY_API_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
COMFY_API_PYI_SHA256 = "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
PAIR = PACK_DB / "patches" / "comfyui-show-text" / "x2453383" / (
    "comfyui-show-text-x2453383"
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


def _import_v2():
    name = "_secure_show_text_test"
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_upstream():
    name = "_upstream_show_text_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, PACK / "showtext.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def test_pinned_pristine_and_secure_census_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    source = ast.parse((PACK / "showtext.py").read_text())
    classes = {item.name for item in source.body if isinstance(item, ast.ClassDef)}
    assert classes == {"ComfyUIShowText"}
    pristine_frontend = (PACK / "web" / "showtext.js").read_text()
    assert pristine_frontend.count("app.registerExtension({") == 1
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py") if V2 not in path.parents
    )
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"ShowText": pack.ComfyUIShowText}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"ShowText": "Show Text"}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.show_text_test")
    assert set(loaded.node_mappings) == {"ShowText"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_list_aware_input_output_contract():
    node = _import_v2().ComfyUIShowText
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "ShowText", "Show Text", "utils"
    )
    assert schema.is_input_list is True
    assert schema.is_output_node is True
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("text", "STRING", False)
    ]
    assert schema.inputs[0].force_input is True
    assert len(schema.outputs) == 1
    assert schema.outputs[0].io_type == "STRING"
    assert schema.outputs[0].is_output_list is True
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()


@pytest.mark.parametrize(
    "text",
    [
        [],
        ["hello"],
        ["first", "second", "third"],
        ["", "visible after the leading empty item"],
        ["line one\nline two", "Unicode: 雪 ❄"],
    ],
)
def test_python_behavior_is_exactly_differential_to_upstream(text):
    upstream = _import_upstream().ComfyUIShowText().notify(list(text))
    secure = _import_v2().ComfyUIShowText.execute(list(text))
    assert secure.result == upstream["result"]
    assert secure.ui == upstream["ui"]
    assert secure.result[0] == text


def test_python_rejects_malformed_and_oversized_values():
    pack = _import_v2()
    module = sys.modules[pack.ComfyUIShowText.__module__]
    with pytest.raises(TypeError, match="list"):
        pack.ComfyUIShowText.execute("not a list")
    with pytest.raises(TypeError, match="string"):
        pack.ComfyUIShowText.execute(["ok", 4])
    with pytest.raises(ValueError, match="item limit"):
        pack.ComfyUIShowText.execute([""] * (module.MAX_TEXT_ITEMS + 1))
    with pytest.raises(ValueError, match="text item"):
        pack.ComfyUIShowText.execute(["x" * (module.MAX_TEXT_ITEM_BYTES + 1)])
    with pytest.raises(ValueError, match="total limit"):
        pack.ComfyUIShowText.execute(["x" * module.MAX_TEXT_ITEM_BYTES] * 5)


def test_guest_executes_without_capabilities_and_preserves_ui_payload():
    node = _import_v2().ComfyUIShowText

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="show-text-test", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={"text": ["first", "second"]}, permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "show-text-pack", guest_runtime_root=V2
        ).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == (["first", "second"],)
    assert output.ui == {"text": ["first", "second"]}
    assert guest_pid not in (None, os.getpid())


def test_manifest_security_contract_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_SHA256
    )
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256
    )
    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "extra_pnginfo", "unique_id", "folder_paths", "PromptServer", "aiohttp",
        "subprocess", "open(", "unlink(",
    ):
        assert forbidden not in python_source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "/scripts/widgets.js", "LiteGraph", "app.graph",
        "app.canvas", "document.", "window.", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "FileReader", "innerHTML",
    ):
        assert forbidden not in frontend
    assert "serialize: true" in frontend
    assert "sendToPrompt: false" in frontend
    assert "ownerDocument" in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_state_execution_safety_sizing_and_teardown():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "show_text_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure Show Text" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-show-text" / "x2453383"
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
