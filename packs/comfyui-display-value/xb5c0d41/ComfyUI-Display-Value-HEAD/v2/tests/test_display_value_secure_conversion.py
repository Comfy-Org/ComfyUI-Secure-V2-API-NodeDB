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
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes",
)).expanduser().resolve()
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "b5c0d414b70f179cb278a7b7203966d925c2fe7c"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches" / "comfyui-display-value" / "xb5c0d41" / (
    "comfyui-display-value-xb5c0d41"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_package(name: str, root: pathlib.Path):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_display_value_test", V2)


def _upstream():
    return _import_package("_upstream_display_value_test", PACK)


def _manifest(pack) -> dict:
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


def test_pinned_actual_loader_census_and_entrypoint_are_exact():
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "1 supported, 0 rejected, 0 pending" in report
    source = ast.parse((PACK / "display_value.py").read_text())
    classes = {item.name for item in source.body if isinstance(item, ast.ClassDef)}
    assert classes == {"DisplayValue"}
    frontend = (PACK / "web" / "display_value.js").read_text()
    assert frontend.count("app.registerExtension({") == 1
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py") if V2 not in path.parents
    )
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    upstream = _upstream()
    secure = _secure()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"DisplayValue"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"DisplayValue"}
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == upstream.NODE_DISPLAY_NAME_MAPPINGS
    assert secure.WEB_DIRECTORY == "web"
    extension = asyncio.run(secure.comfy_entrypoint())
    assert [node.GET_SCHEMA().node_id for node in asyncio.run(
        extension.get_node_list()
    )] == ["DisplayValue"]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.display_value_secure_test",
    )
    assert set(loaded.node_mappings) == {"DisplayValue"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_list_aware_any_input_and_list_output():
    node = _secure().DisplayValue
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "DisplayValue", "Display Value", "utils",
    )
    assert schema.is_input_list is True
    assert schema.is_output_node is True
    assert [(item.id, item.get_io_type(), item.optional) for item in schema.inputs] == [
        ("value", "*", False),
    ]
    assert len(schema.outputs) == 1
    assert schema.outputs[0].get_io_type() == "STRING"
    assert schema.outputs[0].is_output_list is True
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ()


@pytest.mark.parametrize(
    "value",
    [
        None,
        [None],
        ["hello"],
        [42],
        [3.25],
        [True],
        [{"b": [2, False], "a": "snow 雪"}],
        [[1, "two", None]],
    ],
)
def test_python_formatting_and_ui_payload_are_differential(value):
    upstream = _upstream().DisplayValue().main(copy.deepcopy(value))
    secure = _secure().DisplayValue.execute(copy.deepcopy(value))
    assert secure.result == upstream["result"]
    assert secure.ui == upstream["ui"]


def test_fallback_formatting_empty_list_and_resource_bound_match_policy():
    upstream = _upstream().DisplayValue
    secure_pack = _secure()
    secure = secure_pack.DisplayValue

    class Opaque:
        def __str__(self):
            return "opaque-display"

    class Broken:
        def __str__(self):
            raise RuntimeError("broken")

    for value in ([Opaque()], [Broken()]):
        expected = upstream().main(value)
        actual = secure.execute(value)
        assert actual.result == expected["result"]
        assert actual.ui == expected["ui"]
    with pytest.raises(IndexError):
        upstream().main([])
    with pytest.raises(IndexError):
        secure.execute([])
    module = sys.modules[secure.__module__]
    with pytest.raises(ValueError, match="formatted value"):
        secure.execute(["x" * (module.MAX_VALUE_CHARS + 1)])


def test_real_guest_executes_without_capabilities_and_preserves_ui_payload():
    node = _secure().DisplayValue

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="display-value-test",
            node_id="display-value",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={"value": [{"answer": 42, "ready": True}]},
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "display-value-pack", guest_runtime_root=V2,
        ).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == ([json.dumps({"answer": 42, "ready": True})],)
    assert output.ui == {"value": [json.dumps({"answer": 42, "ready": True})]}
    assert guest_pid not in (None, os.getpid())


def test_manifest_security_contract_typecheck_and_frontend_harness():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "folder_paths", "PromptServer", "requests", "aiohttp", "subprocess",
        "open(", "os.", "sys.", "ctx()", "torch", "numpy", "eval(", "exec(",
    ):
        assert forbidden not in python_source
    frontend = (V2 / "web" / "main.js").read_text()
    for forbidden in (
        "/scripts/app.js", "/scripts/widgets.js", "LiteGraph", "app.graph",
        "app.canvas", "document.", "window.", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "FileReader", "innerHTML",
    ):
        assert forbidden not in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "display_value_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure Display Value" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-display-value" / "xb5c0d41"
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
