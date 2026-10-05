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
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "926d0faf98b029f1ca99c5a85bd9d8ea360e0857"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/comfyui-yaresolutionselector/x926d0fa/" \
    "comfyui-yaresolutionselector-x926d0fa"

for root in (COMFYUI, BACKEND, CORE):
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
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_yars_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_yars_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node in pack.NODE_CLASS_MAPPINGS.items():
        nodes[node_id] = {
            "class": node.__name__,
            "methods": {
                name: name in node.__dict__
                for name in (
                    "check_lazy_status", "fingerprint_inputs", "validate_inputs",
                )
            },
            "module": "nodes",
            "permissions": [],
            "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            "sdk_refs": False,
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
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file() and not any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in item.relative_to(root).parts
        )
    }


def test_actual_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"YARS", "YARSAdv"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"YARS", "YARSAdv"}
    assert pristine.WEB_DIRECTORY == "./js"
    assert secure.WEB_DIRECTORY == "web"
    assert sum(path.read_text().count("app.registerExtension(") for path in (PACK / "js").glob("*.js")) == 1

    for node_id in pristine.NODE_CLASS_MAPPINGS:
        old = pristine.NODE_CLASS_MAPPINGS[node_id]
        new = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = new.GET_SCHEMA()
        old_inputs = old.INPUT_TYPES()["required"]
        assert (schema.node_id, schema.category) == (node_id, old.CATEGORY)
        assert schema.display_name == pristine.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert [item.id for item in schema.inputs] == list(old_inputs)
        assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(old.RETURN_NAMES)
        for item in schema.inputs:
            old_type, *rest = old_inputs[item.id]
            metadata = rest[0] if rest else {}
            if isinstance(old_type, list):
                assert item.io_type == "COMBO"
                assert list(item.options) == old_type
            else:
                assert item.io_type == old_type
            for name in ("default", "min", "max", "step", "label_on", "label_off"):
                if name in metadata:
                    assert getattr(item, name) == metadata[name]
        assert new.SDK_REFS is False
        assert new.SDK_PERMISSIONS == ()

    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.yars_secure_test")
    assert set(loaded.node_mappings) == {"YARS", "YARSAdv"}
    assert loaded.web_directory == V2 / "web"
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


def test_ratio_catalogue_helpers_and_errors_are_differential(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    old_nodes = sys.modules[f"{pristine.__name__}.nodes"]
    assert secure.nodes.RATIOS == pristine.YARS().load_ratios()

    for width, height in ((64, 64), (153.584, 128), (1025, 769)):
        old = old_nodes.Dimensions(width, height)
        new = secure.nodes.Dimensions(width, height)
        assert (new.width, new.height) == (old.width, old.height)
    for width, height in ((63, 512), (512, 63)):
        with pytest.raises(ValueError) as old_error:
            old_nodes.Dimensions(width, height)
        with pytest.raises(type(old_error.value)) as new_error:
            secure.nodes.Dimensions(width, height)
        assert str(new_error.value) == str(old_error.value)

    for base in (512, 1024, 8192):
        for ratio in (1.0, 4 / 5, 4 / 3, 9 / 21):
            for overextend in (False, True):
                old = old_nodes.calculate_aspect_ratio(base, ratio, overextend)
                new = secure.nodes.calculate_aspect_ratio(base, ratio, overextend)
                assert (new.width, new.height) == (old.width, old.height)
            old = old_nodes.calculate_constant_constant_resolution(base, ratio)
            new = secure.nodes.calculate_constant_constant_resolution(base, ratio)
            assert (new.width, new.height) == (old.width, old.height)


@pytest.mark.parametrize("base", [512, 1024, 8192])
@pytest.mark.parametrize("overextend", [False, True])
def test_yars_outputs_and_ui_are_differential(tmp_path, base, overextend):
    pristine = _pristine(tmp_path)
    secure = _secure()
    old = pristine.YARS()
    for ratio in secure.nodes.RATIOS:
        expected = old.calculate(base, ratio, overextend)
        actual = secure.YARS.execute(base, ratio, overextend)
        assert actual.result == expected["result"]
        assert actual.ui == expected["ui"]

    for malformed in ("", "landscape", "1-1"):
        with pytest.raises(ValueError) as old_error:
            old.calculate(base, malformed, overextend)
        with pytest.raises(type(old_error.value)) as new_error:
            secure.YARS.execute(base, malformed, overextend)
        assert str(new_error.value) == str(old_error.value)


@pytest.mark.parametrize("base", [512, 1024, 8192])
@pytest.mark.parametrize("width_ratio,height_ratio", [(1, 1), (4, 3), (3, 4), (21, 9), (1024, 1)])
@pytest.mark.parametrize("overextend", [False, True])
@pytest.mark.parametrize("constant", [False, True])
def test_advanced_outputs_and_ui_are_differential(
    tmp_path, base, width_ratio, height_ratio, overextend, constant,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    try:
        expected = pristine.YARSAdv().calculate(
            base, width_ratio, height_ratio, overextend, constant,
        )
    except Exception as old_error:
        with pytest.raises(type(old_error)) as new_error:
            secure.YARSAdv.execute(
                base, width_ratio, height_ratio, overextend, constant,
            )
        assert str(new_error.value) == str(old_error)
    else:
        actual = secure.YARSAdv.execute(
            base, width_ratio, height_ratio, overextend, constant,
        )
        assert actual.result == expected["result"]
        assert actual.ui == expected["ui"]


def test_real_zero_capability_guest_executes_both_nodes():
    secure = _secure()

    async def run():
        cases = [
            (secure.YARS, {"base_resolution": 1024, "aspect_ratio": "landscape (4:3)", "overextend": False}, (1024, 768)),
            (secure.YARSAdv, {"base_resolution": 1024, "width_ratio": 16, "height_ratio": 9, "overextend": True, "constant_resolution": False}, (1820, 1024)),
        ]
        session = await GuestSession("yars", guest_runtime_root=V2).start()
        try:
            for node, inputs, expected in cases:
                plan = _sdk.ExecutionPlan(
                    prompt_id="yars", node_id="1", node_type=node.__name__,
                    tier="sandbox", node_module=node.__module__, inputs=inputs,
                    permissions=(), method="execute",
                )
                runtime = _sdk.Runtime(
                    refs=_sdk.InProcessRefResolver(),
                    ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=_sdk.InProcessOps(),
                )
                output = await session.execute(plan, runtime, capabilities=())
                assert output.result == expected
                assert output.ui["width"] == [expected[0]]
                assert output.ui["height"] == [expected[1]]
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_typecheck():
    source = (V2 / "web/main.js").read_text()
    for forbidden in (
        "/scripts/app.js", "/scripts/widgets.js", "app.registerExtension",
        "LiteGraph", "app.graph", "app.canvas", "document.", "window.",
        "localStorage", "indexedDB", "fetch(", "innerHTML", "setTimeout",
        "setInterval", ".prototype",
    ):
        assert forbidden not in source
    commands = [
        ["node", "--experimental-vm-modules", str(V2 / "tests/yars_frontend_harness.mjs"), str(V2 / "web/main.js")],
        ["node", "--check", str(V2 / "web/main.js")],
        [str(pathlib.Path("/Users/ben/comfy/ComfyUI_frontend-secure-nodes/node_modules/.bin/tsc")), "--project", str(V2 / "tsconfig.json")],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=V2, text=True, capture_output=True, timeout=60, check=False)
        assert completed.returncode == 0, completed.stdout + completed.stderr


def test_contract_assets_and_authority_boundary_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    for relative in ("README.md", "LICENSE", "yeetctor.PNG"):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import torch", "import comfy", "folder_paths", "PromptServer",
        "requests", "aiohttp", "subprocess", "open(", "ctx()", "_from_raw",
    ):
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-yaresolutionselector/x926d0fa"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
