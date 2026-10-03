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
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "8b065f1cd57d05e949fa8925860fb349c5f94ebb"
TREE = "4affd886e453c18ef42a956463a0e61ae630e6cd"
COMFY_API_DTS_SHA256 = (
    "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
)
COMFY_API_PYI_SHA256 = (
    "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"
)
NODE_IDS = {
    "ConfigurableIntSlider", "SimpleFloatSlider", "ConfigurableFloatSlider",
}
PRISTINE_FILES = {
    ".github/workflows/publish_action.yml", ".gitignore", "LICENSE", "README.md",
    "__init__.py", "assets/icon-floatslider.svg", "js/slider.js", "nodes.py",
    "pyproject.toml", "screenshots/all-nodes-overview.png",
    "screenshots/configurable-float-slider-collapsed.png",
    "screenshots/configurable-float-slider-expanded.png",
    "screenshots/configurable-int-slider-collapsed.png",
    "screenshots/configurable-int-slider-expanded.png",
    "screenshots/simple-float-slider.png",
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


def _import_v2(name="_secure_simple_float_slider_conversion_test"):
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
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"}
               for part in relative.parts):
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
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
    }


def _attrs(item):
    return {
        "id": item.id,
        "io_type": item.io_type,
        "default": getattr(item, "default", None),
        "min": getattr(item, "min", None),
        "max": getattr(item, "max", None),
        "step": getattr(item, "step", None),
    }


def test_pinned_pristine_census_manifest_resources_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert TREE == "4affd886e453c18ef42a956463a0e61ae630e6cd"
    assert set(_tree(PACK, omit_v2=True)) == PRISTINE_FILES
    assert (PACK / "assets" / "icon-floatslider.svg").read_bytes() == (
        V2 / "assets" / "icon-floatslider.svg"
    ).read_bytes()
    for filename in sorted((PACK / "screenshots").iterdir()):
        assert filename.read_bytes() == (V2 / "screenshots" / filename.name).read_bytes()

    pristine = ast.parse((PACK / "__init__.py").read_text())
    mapping = next(
        item for item in pristine.body
        if isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Name)
                and target.id == "NODE_CLASS_MAPPINGS" for target in item.targets)
    )
    assert isinstance(mapping.value, ast.Dict)
    assert {key.value for key in mapping.value.keys} == NODE_IDS
    pristine_frontend = (PACK / "js" / "slider.js").read_text()
    assert pristine_frontend.count("app.registerExtension({") == 1
    pristine_python = "\n".join(path.read_text() for path in PACK.glob("*.py"))
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.simple_float_slider_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schemas_preserve_ids_names_bounds_defaults_and_steps():
    pack = _import_v2()
    schemas = {key: value.GET_SCHEMA() for key, value in pack.NODE_CLASS_MAPPINGS.items()}
    for schema in schemas.values():
        schema.validate()
        assert schema.category == "utils/sliders"
        assert schema.is_output_node is False

    integer = schemas["ConfigurableIntSlider"]
    assert integer.display_name == "Configurable Int Slider"
    assert [_attrs(item) for item in integer.inputs] == [
        {"id": "value", "io_type": "INT", "default": 50, "min": -1_000_000, "max": 1_000_000, "step": 1},
        {"id": "min_value", "io_type": "INT", "default": 0, "min": -1_000_000, "max": 1_000_000, "step": 1},
        {"id": "max_value", "io_type": "INT", "default": 100, "min": -1_000_000, "max": 1_000_000, "step": 1},
        {"id": "step", "io_type": "INT", "default": 1, "min": 1, "max": 1_000_000, "step": 1},
    ]
    simple = schemas["SimpleFloatSlider"]
    assert simple.display_name == "Simple Float Slider"
    assert [_attrs(item) for item in simple.inputs] == [
        {"id": "value", "io_type": "FLOAT", "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01},
    ]
    configurable = schemas["ConfigurableFloatSlider"]
    assert configurable.display_name == "Configurable Float Slider"
    assert [_attrs(item) for item in configurable.inputs] == [
        {"id": "value", "io_type": "FLOAT", "default": 0.5, "min": -10_000.0, "max": 10_000.0, "step": 0.0001},
        {"id": "min_value", "io_type": "FLOAT", "default": 0.0, "min": -10_000.0, "max": 10_000.0, "step": 0.01},
        {"id": "max_value", "io_type": "FLOAT", "default": 1.0, "min": -10_000.0, "max": 10_000.0, "step": 0.01},
        {"id": "precision", "io_type": "INT", "default": 2, "min": 0, "max": 4, "step": 1},
        {"id": "step", "io_type": "FLOAT", "default": 0.01, "min": 0.0001, "max": 1_000.0, "step": 0.01},
    ]
    assert [(item.id, item.io_type) for item in integer.outputs] == [("int", "INT")]
    assert [(item.id, item.io_type) for item in simple.outputs] == [("float", "FLOAT")]
    assert [(item.id, item.io_type) for item in configurable.outputs] == [("float", "FLOAT")]
    for node_class in pack.NODE_CLASS_MAPPINGS.values():
        assert getattr(node_class, "SDK_REFS", False) is False
        assert getattr(node_class, "SDK_PERMISSIONS", ()) == ()


def test_real_isolated_guest_matches_upstream_scalar_behavior():
    pack = _import_v2()
    cases = [
        ("ConfigurableIntSlider", {"value": 150.9, "min_value": -10, "max_value": 100, "step": 7}, 100),
        ("ConfigurableIntSlider", {"value": -50, "min_value": -10, "max_value": 100, "step": 1}, -10),
        ("ConfigurableIntSlider", {"value": 5, "min_value": 10, "max_value": 0, "step": 1}, 10),
        ("SimpleFloatSlider", {"value": 0.335}, round(float(0.335), 2)),
        ("SimpleFloatSlider", {"value": -1.234}, round(float(-1.234), 2)),
        ("ConfigurableFloatSlider", {"value": 7.555, "min_value": 0, "max_value": 5, "precision": 2, "step": 0.25}, 5.0),
        ("ConfigurableFloatSlider", {"value": -2.3456, "min_value": -10, "max_value": 10, "precision": 3, "step": 0.1}, round(-2.3456, 3)),
        ("ConfigurableFloatSlider", {"value": 5, "min_value": 10, "max_value": 0, "precision": 4, "step": 1}, 10.0),
    ]

    async def run():
        session = await GuestSession("simple-float-slider-conversion").start()
        refs = _sdk.InProcessRefResolver()
        try:
            for index, (node_id, inputs, expected) in enumerate(cases):
                node_class = pack.NODE_CLASS_MAPPINGS[node_id]
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"slider-{index}",
                    node_id=str(index),
                    node_type=node_id,
                    tier="sandbox",
                    node_module=node_class.__module__,
                    inputs=inputs,
                    permissions=(),
                    method="execute",
                )
                context = _sdk.InProcessCtxProvider().build(plan)
                runtime = _sdk.Runtime(refs=refs, ctx=context, ops=_sdk.InProcessOps())
                result = await session.execute(plan, runtime, capabilities=())
                assert session.last_guest_pid not in (None, os.getpid())
                assert result.result == (expected,)
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_preserves_restoration_regrid_scoping_and_lifecycle():
    source = (V2 / "web" / "slider.js").read_text()
    assert source.count("comfy.defs.extend(nodeType") == 1
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage", "fetch(",
        "app.registerExtension", "addDOMWidget", ".prototype", "requestAnimationFrame",
        "comfy.keyboard", "setInterval(", "setTimeout(",
    ):
        assert forbidden not in source
    for required in (
        "node.widgets.mount", "node.widgets.remove(\"value\")",
        "node.widgets.move(\"value\", 0)", "mountedValue.onChange",
        "widget.on(\"change\"", "setHidden", "builder.onConfigured",
        "builder.onRemoved", "snapToGrid", "state.dragAnchor",
        "editor.addEventListener(\"keydown\"",
    ):
        assert required in source

    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "simple_float_slider_frontend_harness.mjs"),
            str(V2 / "web" / "slider.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: SimpleFloatSlider" in completed.stdout


def test_python_surface_has_no_ambient_authority():
    source = "\n".join(path.read_text(errors="replace") for path in sorted(V2.glob("*.py")))
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "import server", "from server", "folder_paths",
        "PromptServer", "open(", "eval(", "exec(", "sdk.ctx(", "SDK_PERMISSIONS",
    ):
        assert forbidden not in source
    assert "from comfy_api.latest import io" in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-simple-float-slider"
        / "x8b065f1" / "comfyui-simple-float-slider-x8b065f1"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-simple-float-slider" / "x8b065f1"
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
