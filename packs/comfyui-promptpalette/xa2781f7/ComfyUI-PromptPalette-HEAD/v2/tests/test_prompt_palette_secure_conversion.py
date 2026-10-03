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
COMMIT = "a2781f7fb279722933b3d2c78aa2f7fb84e7163f"
COMFY_API_SHA256 = "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
COMFY_API_PYI_SHA256 = "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
PAIR = PACK_DB / "patches" / "comfyui-promptpalette" / "xa2781f7" / (
    "comfyui-promptpalette-xa2781f7"
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


def _import_package(name: str, root: pathlib.Path):
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
    return _import_package("_secure_prompt_palette_test", V2)


def _import_upstream():
    return _import_package("_upstream_prompt_palette_test", PACK)


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
                for method in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")
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
            part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def test_pinned_pristine_and_secure_census_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    source = ast.parse((PACK / "nodes.py").read_text())
    assert {item.name for item in source.body if isinstance(item, ast.ClassDef)} == {
        "PromptPalette"
    }
    assert (PACK / "web" / "index.js").read_text().count("app.registerExtension({") == 1
    backend = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py")
        if V2 not in path.parents
    )
    assert "PromptServer" not in backend
    assert "routes." not in backend

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"PromptPalette": pack.PromptPalette}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"PromptPalette": "Prompt Palette"}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.prompt_palette_test")
    assert set(loaded.node_mappings) == {"PromptPalette"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_upstream_contract_without_authority():
    node = _import_v2().PromptPalette
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "PromptPalette", "Prompt Palette", "utils"
    )
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("text", "STRING", False),
        ("delimiter", "COMBO", False),
        ("line_break", "BOOLEAN", False),
        ("prefix", "STRING", True),
    ]
    assert schema.inputs[0].default == "" and schema.inputs[0].multiline is True
    assert schema.inputs[1].options == ["comma", "space", "none"]
    assert schema.inputs[1].default == "comma"
    assert schema.inputs[2].default is True
    assert schema.inputs[3].force_input is True
    assert [(item.io_type, item.is_output_list) for item in schema.outputs] == [
        ("STRING", False)
    ]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()


@pytest.mark.parametrize(
    ("text", "delimiter", "line_break", "prefix"),
    [
        ("", "comma", True, None),
        ("\n  \n", "space", False, "prefix"),
        ("cat\ndog", "comma", True, None),
        ("cat\ndog", "space", False, "PRE:"),
        ("cat\ndog", "none", True, "PRE"),
        ("// cat\ndog // trailing\n bird", "comma", True, ""),
        ("(cat:1.2),\n// (dog:0.8)", "none", False, None),
        ("alpha // one // two\nbeta", "space", True, "prefix"),
    ],
)
def test_python_output_is_exactly_differential_to_upstream(
    text, delimiter, line_break, prefix,
):
    upstream_type = _import_upstream().NODE_CLASS_MAPPINGS["PromptPalette"]
    upstream = upstream_type().process(
        text, delimiter, line_break, prefix
    )[0]
    secure = _import_v2().PromptPalette.execute(
        text, delimiter, line_break, prefix
    ).result[0]
    assert secure == upstream


def test_malformed_and_oversized_inputs_fail_closed():
    pack = _import_v2()
    module = sys.modules[pack.PromptPalette.__module__]
    with pytest.raises(ValueError, match="delimiter"):
        pack.PromptPalette.execute("cat", "slash", True)
    with pytest.raises(TypeError, match="line_break"):
        pack.PromptPalette.execute("cat", "comma", 1)
    with pytest.raises(TypeError, match="text"):
        pack.PromptPalette.execute(4, "comma", True)
    with pytest.raises(ValueError, match="byte limit"):
        pack.PromptPalette.execute("x" * (module.MAX_TEXT_BYTES + 1), "none", True)
    with pytest.raises(ValueError, match="byte limit"):
        pack.PromptPalette.execute("x", "none", True, "é" * module.MAX_TEXT_BYTES)


def test_guest_executes_pure_string_node_in_isolated_process():
    node = _import_v2().PromptPalette

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="prompt-palette-test",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={
                "text": "cat\n// dog\nbird // note",
                "delimiter": "comma",
                "line_break": True,
                "prefix": "style",
            },
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "prompt-palette-pack", guest_runtime_root=V2
        ).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == ("style\ncat, \nbird, ",)
    assert guest_pid not in (None, os.getpid())


def test_manifest_frontend_security_contract_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_SHA256
    )
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256
    )
    source = "\n".join(path.read_text(errors="replace") for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "app.graph", "localStorage", "indexedDB", "fetch(",
        "comfy.backend", "document.", "window.", "innerHTML", "FileReader",
        "addEventListener(\"key", "addEventListener('key",
    ):
        assert forbidden not in source
    assert "node.widgets.mount(" in source
    assert "textContent" in source
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_parsing_state_safety_lifecycle_and_teardown():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "prompt_palette_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure PromptPalette" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-promptpalette" / "xa2781f7"
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
