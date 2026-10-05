from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "a139b606c61a5e71e24ad2ca382e4de361df2db8"
DTS_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA256 = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
NODE_IDS = {"VisualAreaPrompt", "VisualAreaPromptAdvanced"}
EXPANSION_PERMISSIONS = (
    "graph.expand",
    "graph.expand.external:ConditioningCombine",
    "graph.expand.external:ConditioningConcat",
    "graph.expand.external:ConditioningSetAreaPercentage",
)

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_execution.graph import DynamicPrompt  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_package(root: pathlib.Path, name: str):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_v2(name="_secure_visual_area_conversion_test"):
    return _import_package(V2, name)


def _import_pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package(root, "_pristine_visual_area_conversion_test")


def _tree(root: pathlib.Path, *, omit_v2: bool = False) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
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


class CaptureGraph:
    def __init__(self):
        self.calls = []

    async def expand_nodes(self, nodes, outputs, **policy):
        if policy:
            assert policy == {"_external_node_types": frozenset({
                "ConditioningCombine", "ConditioningConcat",
                "ConditioningSetAreaPercentage",
            })}
        self.calls.append((copy.deepcopy(nodes), copy.deepcopy(outputs)))
        return {"result": outputs, "expand": {"nodes": nodes}}


def _runtime(refs, graph):
    return _sdk.Runtime(
        refs=refs,
        ctx=SimpleNamespace(graph=graph),
        ops=_sdk.InProcessOps(),
    )


async def _cond(refs, label):
    return _sdk.CondRef._wrap(await refs.create("CONDITIONING", {"label": label}))


def _workflow(node_id, areas):
    return {"workflow": {"nodes": [{
        "id": node_id,
        "properties": {"area_values": areas},
    }]}}


def test_actual_loader_census_manifest_contract_and_routes_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine = _import_pristine(tmp_path)
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {
        "VisualAreaPrompt": "Visual Area Prompt",
        "VisualAreaPromptAdvanced": 'Visual Area Prompt "Advanced"',
    }
    assert pristine.WEB_DIRECTORY == "./web"
    assert sum(
        path.read_text(errors="replace").count("app.registerExtension({")
        for path in (PACK / "web").rglob("*.js")
    ) == 2

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == pristine.NODE_DISPLAY_NAME_MAPPINGS
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA256

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.visual_area_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"
    assert not loaded.routes


def test_schemas_preserve_static_contract_and_declare_dynamic_expansion():
    classes = _import_v2().NODE_CLASS_MAPPINGS
    simple = classes["VisualAreaPrompt"]
    advanced = classes["VisualAreaPromptAdvanced"]
    for node_class in classes.values():
        schema = node_class.GET_SCHEMA()
        schema.validate()
        assert schema.node_id in NODE_IDS
        assert schema.category == "RegionalPrompt"
        assert schema.accept_all_inputs is True
        assert schema.enable_expand is True
        assert node_class.SDK_REFS is True
        assert node_class.SDK_PERMISSIONS == EXPANSION_PERMISSIONS
        assert [(item.id, item.io_type) for item in schema.outputs] == [
            ("area_conditioning", "CONDITIONING"),
            ("combined_conditioning", "CONDITIONING"),
        ]
        assert [item.value for item in schema.hidden] == ["EXTRA_PNGINFO", "UNIQUE_ID"]

    simple_schema = simple.GET_SCHEMA()
    assert [item.id for item in simple_schema.inputs] == ["image_width", "image_height"]
    advanced_schema = advanced.GET_SCHEMA()
    assert [(item.id, item.io_type) for item in advanced_schema.inputs] == [
        ("all_area_conditioning", "CONDITIONING"),
        ("global_conditioning", "CONDITIONING"),
        ("merge_global", "BOOLEAN"),
        ("image_width", "INT"),
        ("image_height", "INT"),
    ]
    for item in simple_schema.inputs + advanced_schema.inputs[-2:]:
        assert item.default == 1024
        assert item.min == 16
        assert item.max == 16384


def test_simple_and_advanced_expansions_preserve_topology_and_both_global_branches():
    classes = _import_v2().NODE_CLASS_MAPPINGS

    async def run():
        refs = _sdk.InProcessRefResolver()
        a, b, base, global_cond = [await _cond(refs, name) for name in ("a", "b", "base", "global")]
        areas = [[0.1, 0.2, 0.3, 0.4, 0.5], [0.5, 0.4, 0.3, 0.2, 2.0]]

        graph = CaptureGraph()
        with _sdk.bind_runtime(refs, _runtime(refs, graph).ctx, _sdk.InProcessOps()):
            result = await classes["VisualAreaPrompt"].execute(
                1024, 768, _workflow("42", areas), "42",
                area_conditioning_1=b, area_conditioning_0=a,
            )
        nodes, outputs = graph.calls[0]
        assert [node["class_type"] for node in nodes] == [
            "ConditioningConcat",
            "ConditioningSetAreaPercentage", "ConditioningSetAreaPercentage",
            "ConditioningCombine", "ConditioningCombine",
        ]
        assert nodes[0]["inputs"] == {"conditioning_to": a, "conditioning_from": b}
        assert nodes[1]["inputs"] == {
            "conditioning": a, "width": 0.3, "height": 0.4,
            "x": 0.1, "y": 0.2, "strength": 0.5,
        }
        assert outputs == [{"node": "output", "output": 0}, {"node": "concat_1", "output": 0}]
        assert result["result"] == outputs

        for merge_global in (False, True):
            graph = CaptureGraph()
            with _sdk.bind_runtime(refs, _runtime(refs, graph).ctx, _sdk.InProcessOps()):
                await classes["VisualAreaPromptAdvanced"].execute(
                    base, global_cond, merge_global, 1024, 1024,
                    _workflow("7", areas), "7",
                    area_conditioning_0=a, area_conditioning_1=b,
                )
            nodes, outputs = graph.calls[0]
            assert [node["class_type"] for node in nodes] == [
                "ConditioningConcat", "ConditioningConcat", "ConditioningConcat",
                "ConditioningConcat", "ConditioningConcat",
                "ConditioningSetAreaPercentage", "ConditioningSetAreaPercentage",
                "ConditioningCombine", "ConditioningCombine",
            ]
            final = nodes[-1]["inputs"]
            assert final["conditioning_2"] == (
                {"node": "all_concat_3", "output": 0}
                if merge_global else global_cond
            )
            assert outputs == [
                {"node": "output", "output": 0},
                {"node": "all_concat_3", "output": 0},
            ]

    asyncio.run(run())


def test_malformed_sparse_mismatched_and_unbounded_inputs_fail_before_expansion():
    node_class = _import_v2().NODE_CLASS_MAPPINGS["VisualAreaPrompt"]

    async def run():
        refs = _sdk.InProcessRefResolver()
        cond = await _cond(refs, "one")
        cases = [
            ({}, {"area_conditioning_0": cond}, ValueError),
            (_workflow("1", []), {"area_conditioning_0": cond}, ValueError),
            (_workflow("1", [[0, 0, 1, 1, float("nan")]]), {"area_conditioning_0": cond}, ValueError),
            (_workflow("1", [[0, 0, 2, 1, 1]]), {"area_conditioning_0": cond}, ValueError),
            (_workflow("1", [[0, 0, 1, 1, 1]]), {"area_conditioning_1": cond}, ValueError),
            (_workflow("1", [[0, 0, 1, 1, 1]]), {"unexpected": cond}, ValueError),
            (_workflow("1", [[0, 0, 1, 1, 1]]), {"area_conditioning_0": "raw"}, TypeError),
        ]
        for metadata, inputs, error in cases:
            graph = CaptureGraph()
            with _sdk.bind_runtime(refs, _runtime(refs, graph).ctx, _sdk.InProcessOps()):
                with pytest.raises(error):
                    await node_class.execute(1024, 1024, metadata, "1", **inputs)
            assert graph.calls == []

    asyncio.run(run())


def test_real_guest_uses_exact_capabilities_and_is_out_of_process(monkeypatch):
    node_class = _import_v2().NODE_CLASS_MAPPINGS["VisualAreaPrompt"]

    async def run():
        import nodes as core_nodes

        saved = {name: core_nodes.NODE_CLASS_MAPPINGS.get(name) for name in (
            "ConditioningCombine", "ConditioningConcat", "ConditioningSetAreaPercentage",
        )}
        proxy = type("ConvertedProxy", (), {"SECURE_NODE_PROXY": True})
        core_nodes.NODE_CLASS_MAPPINGS.update({name: proxy for name in saved})
        refs = _sdk.InProcessRefResolver()
        cond = await _cond(refs, "guest")
        graph = CaptureGraph()
        prompt = {"1": {"class_type": "VisualAreaPrompt", "inputs": {}}}
        plan = _sdk.ExecutionPlan(
            prompt_id="visual-area-guest", node_id="1",
            node_type="VisualAreaPrompt", tier="sandbox",
            node_module=node_class.__module__,
            inputs={
                "image_width": 640, "image_height": 480,
                "area_conditioning_0": cond,
                "extra_pnginfo": _workflow("1", [[0, 0, 1, 1, 1]]),
                "unique_id": "1",
            },
            permissions=EXPANSION_PERMISSIONS,
            method="execute",
            extra_pnginfo=_workflow("1", [[0, 0, 1, 1, 1]]),
            dynamic_prompt=DynamicPrompt(prompt),
        )
        session = await GuestSession("visual-area-conversion").start()
        try:
            result = await session.execute(
                plan, _runtime(refs, graph), capabilities=EXPANSION_PERMISSIONS,
            )
            assert session.last_guest_pid not in (None, os.getpid())
            assert len(graph.calls) == 1
            assert result.result[0] == {"node": "output", "output": 0}
            with pytest.raises(Exception, match="graph.expand"):
                await session.execute(plan, _runtime(refs, CaptureGraph()), capabilities=())
        finally:
            await session.kill()
            for name, value in saved.items():
                if value is None:
                    core_nodes.NODE_CLASS_MAPPINGS.pop(name, None)
                else:
                    core_nodes.NODE_CLASS_MAPPINGS[name] = value

    asyncio.run(run())


def test_frontend_behavior_security_and_teardown():
    source = (V2 / "web" / "main.js").read_text()
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage", "fetch(",
        "app.registerExtension", "LiteGraph", "app.graph", "._nodes",
        "MutationObserver", "WebSocket", "XMLHttpRequest",
    ):
        assert forbidden not in source
    for required in (
        'comfy.defs.extend(nodeType', 'node.widgets.canvas({',
        'node.inputs.add(PREFIX, "CONDITIONING"', "node.inputs.remove(slot.id)",
        'node.setProperty("area_values"', "builder.onRemoved",
    ):
        assert required in source
    completed = subprocess.run(
        ["node", "--experimental-vm-modules", str(V2 / "tests" / "visual_area_frontend_harness.mjs"), str(V2 / "web" / "main.js")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: Visual Area" in completed.stdout


def test_guest_sources_have_only_declared_authority_and_frontend_parses():
    refused = {
        "app", "comfy", "comfy_execution", "comfy_extras", "execution",
        "folder_paths", "latent_preview", "main", "node_helpers", "nodes", "server",
        "os", "pathlib", "requests", "socket", "subprocess", "urllib",
    }
    for source in [V2 / "__init__.py", *sorted((V2 / "nodes").glob("*.py"))]:
        tree = ast.parse(source.read_text(), filename=str(source))
        for item in ast.walk(tree):
            names = []
            if isinstance(item, ast.Import):
                names = [alias.name for alias in item.names]
            elif isinstance(item, ast.ImportFrom) and item.module and item.level == 0:
                names = [item.module]
            assert not [name for name in names if name.split(".", 1)[0] in refused]
    subprocess.run(["node", "--check", str(V2 / "web" / "main.js")], check=True)


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-visualarea-nodes"
        / "xa139b60" / "comfyui-visualarea-nodes-xa139b60"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-visualarea-nodes" / "xa139b60"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert _tree(PACK, omit_v2=True) == _tree(fresh / PACK.name, omit_v2=True)


def test_no_cache_artifacts_in_pristine_or_v2():
    for root in (PACK, V2):
        assert not list(root.rglob("__pycache__"))
        assert not list(root.rglob("*.pyc"))
