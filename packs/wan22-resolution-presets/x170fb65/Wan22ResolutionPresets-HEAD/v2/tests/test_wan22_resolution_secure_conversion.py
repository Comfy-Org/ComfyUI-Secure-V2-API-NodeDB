from __future__ import annotations

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
COMMIT = "170fb65d484ee5e4292e05d98ac543e0df49a86d"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "wan22-resolution-presets" / "x170fb65" / (
    "wan22-resolution-presets-x170fb65"
)
NODE_IDS = {"Wan22ResolutionPresets", "VideoResolutionSelector"}

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
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
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_wan22_resolution_test", V2)


def _upstream():
    return _import_package("_upstream_wan22_resolution_test", PACK)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "class": node_class.__name__,
            "methods": {
                method: method in node_class.__dict__
                for method in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")
            },
            "module": "nodes",
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
        }
    return {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts)
    }


def test_exact_actual_loader_census_schema_manifest_and_contract():
    upstream = _upstream()
    secure = _secure()
    assert set(upstream.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert upstream.NODE_DISPLAY_NAME_MAPPINGS == {
        "Wan22ResolutionPresets": "Wan2.2 Resolution Presets 🎬✨",
        "VideoResolutionSelector": "Resolution Selector (Legacy)",
    }
    assert pathlib.Path(upstream.WEB_DIRECTORY).name == "web"
    frontend = (PACK / "web" / "resolution_selector.js").read_text()
    assert frontend.count("app.registerExtension({") == 1
    assert "registerNodeType" not in frontend
    pristine_python = (PACK / "__init__.py").read_text()
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.wan22_resolution_secure_test")
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)

    for node_id in NODE_IDS:
        old = upstream.NODE_CLASS_MAPPINGS[node_id]
        new = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = new.GET_SCHEMA()
        old_inputs = old.INPUT_TYPES()
        required = old_inputs["required"]
        optional = old_inputs.get("optional", {})
        assert schema.node_id == node_id
        assert schema.display_name == upstream.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == old.CATEGORY
        assert [item.id for item in schema.inputs] == [*required, *optional]
        assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(old.RETURN_NAMES)
        for item in schema.inputs:
            old_type, *metadata = (required | optional)[item.id]
            old_meta = metadata[0] if metadata else {}
            assert item.optional is (item.id in optional)
            if isinstance(old_type, list):
                assert item.io_type == "COMBO"
                if item.id == "resolution" and node_id == "Wan22ResolutionPresets":
                    # Upstream sorts a set by area only. Preserve the same values
                    # and area ordering while making equal-area ties deterministic.
                    assert set(item.options) == set(old_type)
                    assert [
                        int(value.split("x")[0]) * int(value.split("x")[1])
                        for value in item.options
                    ] == sorted(
                        int(value.split("x")[0]) * int(value.split("x")[1])
                        for value in old_type
                    )
                else:
                    assert list(item.options) == old_type
            else:
                assert item.io_type == old_type
            for key in ("default", "tooltip"):
                if key in old_meta:
                    assert getattr(item, key) == old_meta[key]
        assert new.SDK_REFS is False
        assert new.SDK_PERMISSIONS == ()


@pytest.mark.parametrize(
    "resolution",
    [
        "1280x720", "288x512", "2048x880", "0x0", "-16x32",
        " 512x288 ", "bad", "1280×720", "1x2x3", "", None,
    ],
)
def test_master_resolution_parser_is_differential_to_upstream(resolution):
    old = _upstream().Wan22ResolutionPresets()
    new = _secure().Wan22ResolutionPresets
    expected = old.get_resolution("ignored", "ignored", resolution)
    assert new.execute("ignored", "ignored", resolution).result == expected


def test_every_legacy_resolution_and_fallback_is_differential_to_upstream():
    upstream = _upstream()
    secure = _secure()
    old = upstream.VideoResolutionSelector()
    new = secure.VideoResolutionSelector
    for mode, aspects in upstream.VideoResolutionSelector.RESOLUTIONS.items():
        for aspect, qualities in aspects.items():
            for quality in qualities:
                assert new.execute(mode, aspect, quality).result == old.get_resolution(
                    mode, aspect, quality
                )
    for mode, aspect, quality in (
        ("IMG", "Square", "HQ"),
        ("QWEN", "Horizontal", "MQ"),
        ("KONTEXT", "UltraWide", "LQ"),
        ("missing", "Horizontal", "HQ"),
        ("I2V720p", "Horizontal", "missing"),
    ):
        assert new.execute(mode, aspect, quality).result == old.get_resolution(
            mode, aspect, quality
        )


def test_radial_attention_math_is_differential_across_tables_modes_and_edges():
    upstream = _upstream()
    secure = _secure()
    sizes = {
        (1, 1), (7, 7), (8, 8), (15, 31), (624, 624), (1280, 720),
        (1088, 832), (1024, 440), (1792, 768), (2048, 880),
    }
    for aspects in upstream.VideoResolutionSelector.RESOLUTIONS.values():
        for qualities in aspects.values():
            sizes.update(qualities.values())
    for block_size in (64, 128):
        for mode in ("upscale", "downscale", "closest"):
            for width, height in sorted(sizes):
                expected = upstream.calculate_radial_compatible_resolution(
                    width, height, mode, block_size
                )
                assert secure.nodes.calculate_radial_compatible_resolution(
                    width, height, mode, block_size
                ) == expected
            assert secure.nodes.get_radial_resolutions(mode, block_size) == (
                upstream.get_radial_resolutions(mode, block_size)
            )
    old = upstream.VideoResolutionSelector()
    for block_size in (64, 128):
        for radial_mode in ("upscale", "downscale", "closest"):
            for mode, aspect, quality in (
                ("I2V720p", "Squarish", "HQ"),
                ("T2V14B", "Horizontal", "MQ"),
                ("IMG", "Cinematic", "LQ"),
                ("QWEN", "UltraTall", "HQ"),
            ):
                assert _secure().VideoResolutionSelector.execute(
                    mode, aspect, quality, True, radial_mode, block_size
                ).result == old.get_resolution(
                    mode, aspect, quality, True, radial_mode, block_size
                )


def test_real_isolated_guest_executes_both_nodes_without_capabilities():
    secure = _secure()

    async def run():
        executions = (
            (secure.Wan22ResolutionPresets, {
                "mode": "Wan2.2 - 5B Model (TI2V)",
                "aspect_ratio": "16:9 Landscape", "resolution": "1280x704",
            }),
            (secure.VideoResolutionSelector, {
                "mode": "T2V14B", "aspect_ratio": "Squarish", "quality": "HQ",
                "enable_radial_attention": True, "radial_mode": "closest", "block_size": 128,
            }),
        )
        session = await GuestSession("wan22-resolution-conversion", guest_runtime_root=V2).start()
        try:
            results = []
            for index, (node, inputs) in enumerate(executions, 1):
                plan = _sdk.ExecutionPlan(
                    prompt_id="wan22-resolution", node_id=str(index),
                    node_type=node.GET_SCHEMA().node_id, tier="sandbox",
                    node_module=node.__module__, inputs=inputs, permissions=(),
                )
                runtime = _sdk.Runtime(
                    refs=_sdk.InProcessRefResolver(),
                    ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=_sdk.InProcessOps(),
                )
                results.append(await session.execute(plan, runtime, capabilities=()))
            return results, session.last_guest_pid
        finally:
            await session.kill()

    results, pid = asyncio.run(run())
    assert results[0].result == (1280, 704)
    assert results[1].result == _secure().VideoResolutionSelector.execute(
        "T2V14B", "Squarish", "HQ", True, "closest", 128
    ).result
    assert pid not in (None, os.getpid())


def test_frontend_filter_defaults_lifecycle_security_and_typecheck():
    source = (V2 / "web" / "main.js").read_text()
    for forbidden in (
        "/scripts/app.js", "app.registerExtension", "LiteGraph", "document.", "window.",
        "localStorage", "indexedDB", "fetch(", "innerHTML", "comfy.backend",
        "setTimeout", "setInterval", ".prototype", ".callback",
    ):
        assert forbidden not in source
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "wan22_resolution_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: Wan2.2 resolution" in completed.stdout
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_python_is_authority_free_and_uses_only_declared_math():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "socket", "open(", "pathlib", "import os", "torch", "numpy", "sdk.ctx()",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "wan22-resolution-presets" / "x170fb65"
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
