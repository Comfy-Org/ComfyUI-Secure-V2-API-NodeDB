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
import torch


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "79a3b1cdb044ba1f6fc973a81e0afb64de9c2957"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "comfyui-wanresolutions" / "x79a3b1c" / (
    "comfyui-wanresolutions-x79a3b1c"
)
NODE_IDS = {
    "WanResolutions", "MiniMaxH3Resolutions", "LTXResolutions", "LTXUpscalerPower",
}

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
    return _import_package("_secure_wanresolutions_test", V2)


def _upstream():
    return _import_package("_upstream_wanresolutions_test", PACK)


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


def _unpack(result):
    if isinstance(result, dict):
        return result["result"], result["ui"]
    return result, None


class _Shape:
    def __init__(self, height: int, width: int):
        self.shape = (1, height, width, 3)


def test_exact_census_schema_manifest_and_contract():
    upstream = _upstream()
    secure = _secure()
    assert set(upstream.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert (PACK / "js" / "wanresolutions.js").read_text().count("app.registerExtension({") == 1
    assert "PromptServer" not in (PACK / "wanresolutions.py").read_text()
    assert not list(PACK.rglob("*routes*.py"))

    extension = asyncio.run(secure.comfy_entrypoint())
    assert {item.GET_SCHEMA().node_id for item in asyncio.run(extension.get_node_list())} == NODE_IDS
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.wanresolutions_secure_test")
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)

    for node_id in NODE_IDS:
        old = upstream.NODE_CLASS_MAPPINGS[node_id]
        schema = secure.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA()
        required = old.INPUT_TYPES()["required"]
        optional = old.INPUT_TYPES().get("optional", {})
        assert [item.id for item in schema.inputs] == [*required, *optional]
        assert schema.category == old.CATEGORY
        assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(old.RETURN_NAMES)
        for item in schema.inputs:
            old_type, *metadata = (required | optional)[item.id]
            old_meta = metadata[0] if metadata else {}
            if isinstance(old_type, list):
                assert item.io_type == "COMBO"
                assert list(item.options) == old_type
            else:
                assert item.io_type == old_type
                if old_type == "COMBO":
                    assert list(item.options) == old_meta["options"]
            for key in ("default", "min", "max", "step"):
                if key in old_meta:
                    assert getattr(item, key) == old_meta[key]
        assert secure.NODE_CLASS_MAPPINGS[node_id].SDK_PERMISSIONS == ()


@pytest.mark.parametrize("node_id", ["WanResolutions", "MiniMaxH3Resolutions", "LTXResolutions"])
def test_all_presets_and_legacy_labels_match_upstream(node_id):
    old_cls = _upstream().NODE_CLASS_MAPPINGS[node_id]
    new_cls = _secure().NODE_CLASS_MAPPINGS[node_id]
    old_node, new_node = old_cls(), new_cls()
    for aspect, rows in old_cls.PRESETS.items():
        for index, (width, height, note) in enumerate(rows, 1):
            current = f"{note} — {width}×{height}"
            legacy = old_cls._legacy_labels_for(aspect)[index - 1]
            assert _unpack(new_node.pick(aspect, current)) == _unpack(old_node.pick(aspect, current))
            assert _unpack(new_node.pick(aspect, legacy)) == _unpack(old_node.pick(aspect, legacy))
    for unknown in ("literal unknown", "3. 999×777 — old", "480x480"):
        assert _unpack(new_node.pick(old_cls.FALLBACK_ASPECT, unknown)) == _unpack(
            old_node.pick(old_cls.FALLBACK_ASPECT, unknown)
        )


@pytest.mark.parametrize("height,width", [(480, 832), (641, 1000), (1000, 641), (1024, 1024)])
def test_image_driven_behavior_matches_upstream(height, width):
    old = _upstream()
    secure = _secure()
    image = _Shape(height, width)
    cases = (
        ("WanResolutions", "1:1", "High Detail — 832×832", {"official_only": False}),
        ("WanResolutions", "1:1", "High Detail — 832×832", {"official_only": True}),
        ("MiniMaxH3Resolutions", "16:9", "1080P Class (2.00 MP) — 1920×1088", {}),
        ("LTXResolutions", "1:1", "Full HD Output — 1440×1440", {"upscaler_power": "x1.5"}),
    )
    for node_id, aspect, resolution, kwargs in cases:
        expected = old.NODE_CLASS_MAPPINGS[node_id]().pick(aspect, resolution, image=image, **kwargs)
        actual = secure.NODE_CLASS_MAPPINGS[node_id]().pick(aspect, resolution, image=image, **kwargs)
        assert _unpack(actual) == _unpack(expected)


def test_official_bypass_upscaler_and_support_node_match_upstream():
    old = _upstream()
    secure = _secure()
    for power in ("none", "x1.5", "x2", "1.5x", "2x", "invalid", None):
        expected = old.LTXResolutions().pick(
            "16:9", "Full HD Output — 1920×1088", upscaler_power=power,
        )
        actual = secure.LTXResolutions().pick(
            "16:9", "Full HD Output — 1920×1088", upscaler_power=power,
        )
        assert actual == expected
        assert secure.LTXUpscalerPower.execute(power).result == old.LTXUpscalerPower().select(power)
    bypass = _Shape(1000, 641)
    assert secure.LTXResolutions().pick(
        "1:1", "Balanced — 768×768", image=bypass, image_bypass=True,
    ) == old.LTXResolutions().pick(
        "1:1", "Balanced — 768×768", image=bypass, image_bypass=True,
    )
    for aspect in old.WanResolutions.ASPECT_ORDER:
        for label in old.WanResolutions._official_labels_for(aspect):
            assert secure.WanResolutions().pick(aspect, label, official_only=True) == (
                old.WanResolutions().pick(aspect, label, official_only=True)
            )


def test_async_refs_and_real_isolated_guest_execute_all_nodes():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", torch.zeros((1, 641, 1000, 3))))
        executions = (
            (secure.WanResolutions, {
                "aspect_ratio": "1:1", "resolution": "High Detail — 832×832",
                "official_only": True, "image": image,
            }),
            (secure.MiniMaxH3Resolutions, {
                "aspect_ratio": "16:9", "resolution": "2K (2.25 MP) — 2048×1152",
                "image": image,
            }),
            (secure.LTXResolutions, {
                "aspect_ratio": "1:1", "resolution": "Balanced — 768×768",
                "image_bypass": False, "upscaler_power": "x2", "image": image,
            }),
            (secure.LTXUpscalerPower, {"upscaler_power": "1.5x"}),
        )
        session = await GuestSession("wanresolutions-conversion", guest_runtime_root=V2).start()
        try:
            results = []
            for index, (node, inputs) in enumerate(executions, 1):
                plan = _sdk.ExecutionPlan(
                    prompt_id="wanresolutions", node_id=str(index), node_type=node.GET_SCHEMA().node_id,
                    tier="sandbox", node_module=node.__module__, inputs=inputs, permissions=(),
                )
                runtime = _sdk.Runtime(
                    refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps(),
                )
                results.append(await session.execute(plan, runtime, capabilities=()))
            return results, session.last_guest_pid
        finally:
            await session.kill()

    results, pid = asyncio.run(run())
    assert results[0].result == (1280, 720)
    assert results[0].ui["aspect_resolution_state"][0]["aspect_ratio"] == "3:2"
    assert results[1].result == (1920, 1216)
    assert results[2].result == (480, 320)
    assert results[3].result == ("x1.5",)
    assert pid not in (None, os.getpid())


def test_ltx_bypass_does_not_touch_the_optional_image_ref():
    secure = _secure()

    class FailingImage:
        async def spatial_shape(self):
            raise AssertionError("bypassed image must not be inspected")

    result = asyncio.run(secure.LTXResolutions.execute(
        "16:9", "Balanced — 1184×672", image=FailingImage(),
        image_bypass=True, upscaler_power="none",
    ))
    assert result.result == (1184, 672)


def test_frontend_dynamic_options_isolation_teardown_and_typecheck():
    source = (V2 / "web" / "main.js").read_text()
    for forbidden in (
        "/scripts/app.js", "app.registerExtension", "LiteGraph", "document.", "window.",
        "localStorage", "indexedDB", "fetch(", "innerHTML", "comfy.backend",
    ):
        assert forbidden not in source
    completed = subprocess.run(
        ["node", "--experimental-vm-modules", str(V2 / "tests" / "wanresolutions_frontend_harness.mjs"), str(V2 / "web" / "main.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: WanResolutions" in completed.stdout
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_python_has_only_the_declared_dimension_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "socket", "open(", "torch", "numpy", "sdk.ctx()",
    ):
        assert forbidden not in source
    assert "await image.spatial_shape()" in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-wanresolutions" / "x79a3b1c"
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
