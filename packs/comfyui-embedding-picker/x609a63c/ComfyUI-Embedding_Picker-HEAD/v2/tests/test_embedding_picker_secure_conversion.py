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
COMMIT = "609a63c8457c92cc83126e594d7c95b6be363863"
COMFY_API_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
COMFY_API_PYI_SHA256 = "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
PAIR = PACK_DB / "patches" / "comfyui-embedding-picker" / "x609a63c" / (
    "comfyui-embedding-picker-x609a63c"
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
    name = "_secure_embedding_picker_test"
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


def _import_upstream_node():
    name = "_upstream_embedding_picker_node_test"
    sys.modules.pop(name, None)
    prior = sys.modules.get("folder_paths")
    sys.modules["folder_paths"] = types.SimpleNamespace(
        get_filename_list=lambda folder: (
            ["EasyNegative.pt", "nested/detail.safetensors"]
            if folder == "embeddings" else []
        )
    )
    try:
        spec = importlib.util.spec_from_file_location(name, PACK / "node.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if prior is None:
            sys.modules.pop("folder_paths", None)
        else:
            sys.modules["folder_paths"] = prior


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
    source = ast.parse((PACK / "node.py").read_text())
    node_classes = {
        item.name for item in source.body
        if isinstance(item, ast.ClassDef)
        and any(
            isinstance(base, ast.Attribute) and base.attr == "ComfyNode"
            for base in item.bases
        )
    }
    assert node_classes == {"EmbeddingPicker"}
    assert (PACK / "js" / "quickNodes.js").read_text().count("app.registerExtension({") == 1
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py") if V2 not in path.parents
    )
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"EmbeddingPicker": pack.EmbeddingPicker}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"EmbeddingPicker": "Embedding Picker"}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.embedding_picker_test")
    assert set(loaded.node_mappings) == {"EmbeddingPicker"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_upstream_contract_and_catalogue_boundary():
    node = _import_v2().EmbeddingPicker
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "EmbeddingPicker", "Embedding Picker", "utils"
    )
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("embedding", "COMBO", False),
        ("emphasis", "FLOAT", False),
        ("append", "BOOLEAN", False),
        ("text", "STRING", False),
    ]
    assert schema.inputs[0].options == []
    assert (schema.inputs[1].default, schema.inputs[1].min, schema.inputs[1].max,
            schema.inputs[1].step) == (1.0, 0.0, 3.0, 0.05)
    assert schema.inputs[2].default is False
    assert schema.inputs[3].multiline is True
    assert [(item.id, item.io_type) for item in schema.outputs] == [("text", "STRING")]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()
    declarations = (V2 / "comfy-api.d.ts").read_text()
    assert "| 'embeddings'" in declarations
    assert "list(folder: ModelFolder): Promise<string[]>" in declarations


@pytest.mark.parametrize(
    ("text", "embedding", "emphasis", "append"),
    [
        ("portrait", "EasyNegative.pt", 1.0, False),
        ("portrait", "nested/detail.safetensors", 1.0, True),
        ("", "folder/model.pt", 1.25, False),
        ("prompt", "name.with.dots.bin", 0.05, True),
        ("unchanged", "anything.pt", 0.0, False),
        ("rounded", "model", 1.23456, False),
        ("unicode", "分類/細部.pt", 3.0, True),
    ],
)
def test_python_output_is_exactly_differential_to_upstream(
    text, embedding, emphasis, append,
):
    upstream = _import_upstream_node().EmbeddingPicker.execute(
        text, embedding, emphasis, append
    ).result[0]
    secure = _import_v2().EmbeddingPicker.execute(
        text, embedding, emphasis, append
    ).result[0]
    assert secure == upstream


def test_malformed_and_oversized_inputs_fail_closed():
    pack = _import_v2()
    module = sys.modules[pack.EmbeddingPicker.__module__]
    for invalid in (-0.01, 3.01, math.nan, math.inf):
        with pytest.raises(ValueError, match="emphasis"):
            pack.EmbeddingPicker.execute("x", "model.pt", invalid, False)
    with pytest.raises(TypeError, match="emphasis"):
        pack.EmbeddingPicker.execute("x", "model.pt", True, False)
    with pytest.raises(TypeError, match="append"):
        pack.EmbeddingPicker.execute("x", "model.pt", 1.0, 0)
    with pytest.raises(ValueError, match="byte limit"):
        pack.EmbeddingPicker.execute(
            "x" * (module.MAX_TEXT_BYTES + 1), "model.pt", 1.0, False
        )
    with pytest.raises(ValueError, match="byte limit"):
        pack.EmbeddingPicker.execute(
            "x", "é" * module.MAX_MODEL_NAME_BYTES, 1.0, False
        )


def test_guest_executes_pure_formatter_in_isolated_process():
    node = _import_v2().EmbeddingPicker

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="embedding-picker-test", node_id="1",
            node_type=node.__name__, tier="sandbox", node_module=node.__module__,
            inputs={
                "text": "cinematic", "embedding": "nested/detail.safetensors",
                "emphasis": 1.25, "append": False,
            },
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "embedding-picker-pack", guest_runtime_root=V2
        ).start()
        try:
            output = await session.execute(plan, runtime, capabilities=())
            return output, session.last_guest_pid
        finally:
            await session.kill()

    output, guest_pid = asyncio.run(run())
    assert output.result == ("(embedding:detail:1.250), cinematic",)
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
    for forbidden in ("folder_paths", "unlink(", "PromptServer", "aiohttp", "subprocess"):
        assert forbidden not in python_source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "LiteGraph", "app.graph", "app.canvas", "document.",
        "window.", "localStorage", "indexedDB", "fetch(", "comfy.backend",
        "FileReader", "innerHTML",
    ):
        assert forbidden not in frontend
    assert 'comfy.models.list("embeddings")' in frontend
    assert "node.inputs.add" in frontend
    assert "connectTo" in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_catalogue_prepend_workflow_and_failure_cleanup():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "embedding_picker_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure Embedding Picker" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-embedding-picker" / "x609a63c"
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
