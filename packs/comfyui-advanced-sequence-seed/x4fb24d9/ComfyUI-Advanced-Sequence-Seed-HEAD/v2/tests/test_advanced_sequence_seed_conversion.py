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
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes",
)).expanduser().resolve()
COMMIT = "4fb24d9b3c96a781d4f391cba1e73b86dc2911f3"
TREE = "c493c22ceea8ad8ff9fca61f567e9fb64b584419"
COMFY_API_DTS_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
COMFY_API_PYI_SHA256 = "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
SEQUENCES = {
    "Fibonacci": [0, 1, 1, 2, 3, 5, 8, 13],
    "Prime": [2, 3, 5, 7, 11, 13, 17, 19],
    "Padovan": [1, 1, 1, 2, 2, 3, 4, 5],
    "Triangular": [1, 3, 6, 10, 15, 21, 28, 36],
    "Catalan": [1, 1, 2, 5, 14, 42, 132, 429],
    "Pell": [0, 1, 2, 5, 12, 29, 70, 169],
    "Lucas": [2, 1, 3, 4, 7, 11, 18, 29],
}
PRISTINE_FILES = {
    ".github/workflows/publish.yml", "LICENSE", "README.md",
    "__init__.py", "advanced_sequence_seed_node.py", "assets/screenshot.png",
    "js/advanced_sequence_seed.js", "pyproject.toml",
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


def _import_v2(name="_secure_advanced_sequence_seed_test"):
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
        if not path.is_file() or (omit_v2 and relative.parts[0] == "v2"):
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
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
                for method in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")
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

    pristine = ast.parse((PACK / "__init__.py").read_text())
    mappings = [
        item for item in pristine.body if isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "NODE_CLASS_MAPPINGS"
                for target in item.targets)
    ]
    assert len(mappings) == 1 and len(mappings[0].value.keys) == 1
    assert (PACK / "js" / "advanced_sequence_seed.js").read_text().count(
        "app.registerExtension({",
    ) == 1
    pristine_source = "\n".join(path.read_text() for path in PACK.glob("*.py"))
    assert "@PromptServer.instance.routes" not in pristine_source

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == {"AdvancedSequenceSeedNode"}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {
        "AdvancedSequenceSeedNode": "Advanced Sequence Seed Generator",
    }
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.advanced_sequence_seed_test")
    assert set(loaded.node_mappings) == {"AdvancedSequenceSeedNode"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schema_preserves_ids_types_defaults_and_bounds():
    node_class = _import_v2().NODE_CLASS_MAPPINGS["AdvancedSequenceSeedNode"]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "AdvancedSequenceSeedNode"
    assert schema.display_name == "Advanced Sequence Seed Generator"
    assert schema.category == "AI WizArt"
    assert schema.is_output_node is True
    assert [item.id for item in schema.inputs] == [
        "sequence_type", "max_sequence_length", "seed_range_start",
        "seed_range_end", "force_recalculation", "current_seed", "noise_factor",
    ]
    assert [item.io_type for item in schema.inputs] == [
        "COMBO", "INT", "INT", "INT", "BOOLEAN", "INT", "FLOAT",
    ]
    assert list(schema.inputs[0].options) == list(SEQUENCES)
    assert [(item.default, item.min, item.max) for item in schema.inputs[1:4]] == [
        (20, 2, 1000), (0, 0, 999), (19, 1, 1000),
    ]
    assert schema.inputs[4].default is True
    assert (schema.inputs[5].default, schema.inputs[5].min, schema.inputs[5].max, schema.inputs[5].step) == (
        0, 0, 9_999_999_999, 1,
    )
    assert (schema.inputs[6].default, schema.inputs[6].min, schema.inputs[6].max, schema.inputs[6].step, schema.inputs[6].optional) == (
        0.0, 0.0, 1.0, 0.01, True,
    )
    assert [(item.id, item.io_type) for item in schema.outputs] == [("INT", "INT")]
    assert node_class.SDK_REFS is False
    assert node_class.SDK_PERMISSIONS == ()


def test_all_sequences_primality_ranges_noise_reuse_and_fingerprint(monkeypatch):
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["AdvancedSequenceSeedNode"]
    module = sys.modules[f"{pack.__name__}.advanced_sequence_seed_node"]
    for name, expected in SEQUENCES.items():
        assert node_class.generate_sequence(name, 8) == expected
    assert node_class.generate_sequence("Padovan", 2) == [1, 1, 1]
    assert [node_class.is_prime(value) for value in (-2, 0, 1, 2, 17, 21)] == [
        False, False, False, True, True, False,
    ]
    with pytest.raises(ValueError, match="Unsupported sequence"):
        node_class.generate_sequence("Other", 8)

    monkeypatch.setattr(module.random, "randint", lambda start, end: end)
    result = node_class.execute("Fibonacci", 8, 2, 5, True, 999, 0.0)
    assert result.result == (5,)
    assert result.ui == {"seed": [5]}
    with pytest.raises(ValueError, match="Invalid range"):
        node_class.execute("Prime", 8, 9, 10, True, 0, 0.0)

    monkeypatch.setattr(module.random, "randint", lambda *_args: pytest.fail("fixed seed rerolled"))
    monkeypatch.setattr(module.random, "uniform", lambda low, high: high)
    assert node_class.execute("Lucas", 8, 0, 7, False, 100, 0.25).result == (125,)
    assert node_class.execute("Lucas", 8, 0, 7, False, 100, 0.0).result == (100,)
    assert math.isnan(node_class.fingerprint_inputs(True, 9))
    assert math.isnan(node_class.fingerprint_inputs(False, 0))
    assert node_class.fingerprint_inputs(False, 9) == ""


def test_real_isolated_guest_executes_without_host_authority():
    node_class = _import_v2().NODE_CLASS_MAPPINGS["AdvancedSequenceSeedNode"]

    async def run():
        plan = _sdk.ExecutionPlan(
            prompt_id="advanced-sequence-seed",
            node_id="17",
            node_type="AdvancedSequenceSeedNode",
            tier="sandbox",
            node_module=node_class.__module__,
            inputs={
                "sequence_type": "Prime", "max_sequence_length": 8,
                "seed_range_start": 0, "seed_range_end": 7,
                "force_recalculation": False, "current_seed": 31337,
                "noise_factor": 0.0,
            },
            permissions=(), method="execute",
        )
        runtime = _sdk.Runtime(
            refs=_sdk.InProcessRefResolver(),
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession("advanced-sequence-seed-conversion").start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
            assert result.result == (31337,)
            assert result.ui == {"seed": [31337]}
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_is_node_scoped_graph_safe_and_tears_down():
    source = (V2 / "web" / "advanced_sequence_seed.js").read_text()
    assert source.count("comfy.defs.extend(NODE_TYPE") == 1
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage", "fetch(",
        "app.registerExtension", "PromptServer", "addEventListener", "api.",
        ".prototype", "setTimeout", "setInterval", "MutationObserver",
    ):
        assert forbidden not in source
    for required in (
        "builder.onCreated", "builder.onConfigured", "builder.onExecuted",
        "builder.onRemoved", 'force.on("change"', "state.unsubscribe?.()",
        "result?.raw?.seed", "state.current.setValue",
    ):
        assert required in source

    completed = subprocess.run(
        ["node", str(V2 / "tests" / "advanced_sequence_seed_frontend_harness.mjs")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "advanced sequence seed frontend behavior/security tests passed" in completed.stdout


def test_python_surface_has_no_ambient_host_authority():
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
        REPO / "pack-db" / "patches" / "comfyui-advanced-sequence-seed"
        / "x4fb24d9" / "comfyui-advanced-sequence-seed-x4fb24d9"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-advanced-sequence-seed" / "x4fb24d9"
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
