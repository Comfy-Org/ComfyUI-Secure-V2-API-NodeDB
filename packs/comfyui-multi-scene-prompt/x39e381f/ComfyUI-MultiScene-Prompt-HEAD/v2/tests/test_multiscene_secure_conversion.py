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
COMMIT = "39e381f1146c99b0aa0967d6e1229acb74751055"
COMFY_API_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
COMFY_API_PYI_SHA256 = "82dea265a0ae3918ece66547a6e413558c419fbcb0a4cc19d52b3fd74057cc49"
PAIR = PACK_DB / "patches" / "comfyui-multi-scene-prompt" / "x39e381f" / (
    "comfyui-multi-scene-prompt-x39e381f"
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
    return _import_package("_secure_multiscene_test", V2)


def _import_upstream():
    return _import_package("_upstream_multiscene_test", PACK)


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
    source = ast.parse((PACK / "__init__.py").read_text())
    assert {item.name for item in source.body if isinstance(item, ast.ClassDef)} == {
        "MultiScenePrompt"
    }
    frontend = (PACK / "web" / "js" / "multiScenePrompt.js").read_text()
    assert frontend.count("app.registerExtension({") == 1
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py") if V2 not in path.parents
    )
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"MultiScenePrompt": pack.MultiScenePrompt}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {
        "MultiScenePrompt": "Multi-Scene Prompt Editor"
    }
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.multiscene_test")
    assert set(loaded.node_mappings) == {"MultiScenePrompt"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_upstream_contract_without_authority():
    node = _import_v2().MultiScenePrompt
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "MultiScenePrompt", "Multi-Scene Prompt Editor", "prompt"
    )
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("common_prompt", "STRING", False),
        ("scenes_json", "STRING", False),
    ]
    assert schema.inputs[0].default == ""
    assert schema.inputs[0].multiline is True
    assert schema.inputs[0].placeholder == "公用提示词"
    assert schema.inputs[1].default == '[""]'
    assert schema.inputs[1].multiline is False
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("scene_prompts", "STRING"),
        ("common_prompt", "STRING"),
        ("scene_count", "INT"),
    ]
    assert [item.value for item in schema.hidden] == ["UNIQUE_ID"]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()


@pytest.mark.parametrize(
    ("common_prompt", "scenes_json"),
    [
        ("", '[""]'),
        ("shared", '[" first", " second"]'),
        ("共同：", '["场景一", "雪 ❄", "<script>bad()</script>"]'),
        ("prefix", "[]"),
        ("prefix", '[1, true, null, {"name": "scene"}]'),
        ("fallback", "not json"),
    ],
)
def test_python_behavior_is_exactly_differential_to_upstream(
    common_prompt, scenes_json,
):
    upstream_type = _import_upstream().NODE_CLASS_MAPPINGS["MultiScenePrompt"]
    upstream = upstream_type().execute(common_prompt, scenes_json, unique_id="7")
    secure = _import_v2().MultiScenePrompt.execute(
        common_prompt, scenes_json, unique_id="7"
    ).result
    assert secure == upstream


def test_python_rejects_malformed_shapes_and_oversized_state():
    pack = _import_v2()
    module = sys.modules[pack.MultiScenePrompt.__module__]
    with pytest.raises(TypeError, match="common_prompt"):
        pack.MultiScenePrompt.execute(4, '[""]')
    with pytest.raises(TypeError, match="scenes_json"):
        pack.MultiScenePrompt.execute("", 4)
    with pytest.raises(ValueError, match="JSON array"):
        pack.MultiScenePrompt.execute("", '{"scene": "one"}')
    with pytest.raises(ValueError, match="scene limit"):
        scenes = [""] * (module.MAX_SCENES + 1)
        pack.MultiScenePrompt.execute("", json.dumps(scenes))
    with pytest.raises(ValueError, match="byte limit"):
        pack.MultiScenePrompt.execute(
            "x" * (module.MAX_COMMON_PROMPT_BYTES + 1), '[""]'
        )
    with pytest.raises(ValueError, match="byte limit"):
        pack.MultiScenePrompt.execute(
            "", " " * (module.MAX_SCENES_JSON_BYTES + 1)
        )


def test_guest_executes_pure_prompt_composition_without_capabilities():
    node = _import_v2().MultiScenePrompt

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="multi-scene-test",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={
                "common_prompt": "shared ",
                "scenes_json": '["one", "two"]',
                "unique_id": "1",
            },
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "multi-scene-pack", guest_runtime_root=V2
        ).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == ('["shared one", "shared two"]', "shared ", 2)
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
        "folder_paths", "PromptServer", "aiohttp", "requests", "subprocess",
        "open(", "unlink(", "ctx()",
    ):
        assert forbidden not in python_source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "/scripts/widgets.js", "LiteGraph", "app.graph",
        "app.canvas", "document.", "window.", "localStorage", "sessionStorage",
        "indexedDB", "fetch(", "comfy.backend", "FileReader", "innerHTML",
    ):
        assert forbidden not in frontend
    assert "ownerDocument" in frontend
    assert "serialize: true" in frontend
    assert "sendToPrompt: true" in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_state_safety_bounds_and_teardown():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "multiscene_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure multi-scene" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-multi-scene-prompt" / "x39e381f"
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
