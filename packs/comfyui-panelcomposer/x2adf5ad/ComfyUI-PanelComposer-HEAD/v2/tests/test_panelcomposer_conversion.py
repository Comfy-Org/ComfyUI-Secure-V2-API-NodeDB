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
import types

import torch


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "2adf5ad8dea4a7ad88c1f4c20d8eb8cb7616de31"
COMFY_API_DTS_SHA256 = (
    "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
)
COMFY_API_PYI_SHA256 = (
    "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
)
NODE_IDS = {
    "PanelLayoutProvider", "PanelCompositor", "ListGetItem", "TupleUnpack",
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


def _import_v2(name="_secure_panelcomposer_conversion_test"):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name,
        V2 / "__init__.py",
        submodule_search_locations=[str(V2)],
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
            "permissions": list(
                getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
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


def _runtime(refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=types.SimpleNamespace(),
        ops=_sdk.InProcessOps(),
    )


def _plan(node_class, inputs, node_id="1"):
    return _sdk.ExecutionPlan(
        prompt_id="panelcomposer-conversion",
        node_id=node_id,
        node_type=node_class.GET_SCHEMA().node_id,
        tier="sandbox",
        node_module=node_class.__module__,
        inputs=inputs,
        method="execute",
    )


def test_pinned_census_manifest_and_authoritative_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine_mapping = ast.parse((PACK / "__init__.py").read_text())
    mapping = next(
        node for node in pristine_mapping.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name)
                and target.id == "NODE_CLASS_MAPPINGS" for target in node.targets)
    )
    assert isinstance(mapping.value, ast.Dict)
    assert {key.value for key in mapping.value.keys} == NODE_IDS
    assert sum(
        path.read_text(errors="replace").count("app.registerExtension({")
        for path in (PACK / "web").glob("*.js")
    ) == 2

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(pack))
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256)
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256)

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.panelcomposer_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_all_four_node_schemas_preserve_the_wire_contract():
    pack = _import_v2()
    expected = {
        "PanelLayoutProvider": {
            "category": "PanelComposer/Layout",
            "inputs": [
                "layout_preset", "reading_order", "canvas_rotation",
                "aspect_ratio", "page_orientation", "canvas_size_mode",
                "fixed_preset_size", "fixed_custom_megapixels", "megapixels",
                "multiple",
            ],
            "input_types": [
                "COMBO", "COMBO", "COMBO", "COMBO", "COMBO", "COMBO",
                "COMBO", "FLOAT", "FLOAT", "INT",
            ],
            "outputs": [
                "layout_json", "panel_dimensions", "area_image", "area_colors",
            ],
            "output_types": ["STRING", "PANEL_DIMENSIONS", "IMAGE", "COLOR_LIST"],
            "input_list": False,
            "permissions": ("raw",),
        },
        "PanelCompositor": {
            "category": "PanelComposer/Compositing",
            "inputs": [
                "layout_json", "images", "canvas_mode", "aspect_ratio",
                "fixed_preset_size", "fixed_custom_megapixels",
                "page_orientation", "scale_to_input_mode", "fit_mode",
                "scale_algo", "gutter_px", "gutter_color",
            ],
            "input_types": [
                "STRING", "IMAGE", "COMBO", "COMBO", "COMBO", "FLOAT",
                "COMBO", "COMBO", "COMBO", "COMBO", "INT", "STRING",
            ],
            "outputs": ["page_image"],
            "output_types": ["IMAGE"],
            "input_list": True,
            "permissions": ("raw",),
        },
        "ListGetItem": {
            "category": "utils/list",
            "inputs": ["list_or_tuple", "index"],
            "input_types": ["*", "INT"],
            "outputs": ["item"],
            "output_types": ["*"],
            "input_list": False,
            "permissions": (),
        },
        "TupleUnpack": {
            "category": "utils/list",
            "inputs": ["tuple_or_list"],
            "input_types": ["*"],
            "outputs": ["item_0", "item_1", "item_2", "item_3"],
            "output_types": ["*", "*", "*", "*"],
            "input_list": False,
            "permissions": (),
        },
    }
    for node_id, contract in expected.items():
        node_class = pack.NODE_CLASS_MAPPINGS[node_id]
        schema = node_class.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.category == contract["category"]
        assert [item.id for item in schema.inputs] == contract["inputs"]
        assert [item.io_type for item in schema.inputs] == contract["input_types"]
        assert [item.id for item in schema.outputs] == contract["outputs"]
        assert [item.io_type for item in schema.outputs] == contract["output_types"]
        assert schema.is_input_list is contract["input_list"]
        assert node_class.SDK_REFS is True
        assert node_class.SDK_PERMISSIONS == contract["permissions"]

    provider = pack.NODE_CLASS_MAPPINGS["PanelLayoutProvider"].GET_SCHEMA()
    assert len(provider.inputs[0].options) == 45
    assert provider.inputs[7].as_dict()["default"] == 2.0
    assert provider.inputs[8].as_dict()["min"] == 0.01
    assert provider.inputs[9].as_dict()["step"] == 1
    compositor = pack.NODE_CLASS_MAPPINGS["PanelCompositor"].GET_SCHEMA()
    assert compositor.inputs[8].options == [
        "cover", "contain", "stretch", "fit_to_shape",
    ]
    assert "EXPERIMENTAL" in compositor.inputs[8].tooltip
    assert compositor.inputs[9].default == "lanczos"


def test_builtin_parity_custom_serialization_and_list_helpers():
    pack = _import_v2()
    layouts = sys.modules[f"{pack.__name__}.presets.layouts"]
    builtin = sys.modules[f"{pack.__name__}.presets.builtin_layouts"]
    source = json.loads((PACK / "web" / "layouts.json").read_text())
    assert builtin.BUILTIN_LAYOUTS == source
    assert len(layouts.LAYOUT_CHOICES) == len(source) == 45
    for key, expected in source.items():
        choice = f"{expected['category']} / {expected['label']}"
        assert layouts.decode_layout_choice(choice)["panels"] == expected["panels"]
        assert [panel["polygon"] for panel in layouts.get_layout(choice)] == (
            expected["panels"])

    custom = {
        "category": "Personal",
        "label": "Serialized split",
        "panels": [
            [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
            [[0.5, 0], [1, 0], [1, 1], [0.5, 1]],
        ],
        "reading_groups": [[0, 1]],
    }
    choice = layouts.CUSTOM_LAYOUT_PREFIX + json.dumps(custom, separators=(",", ":"))
    decoded = layouts.decode_layout_choice(choice)
    assert decoded["panels"] == custom["panels"]
    assert layouts.get_layout(choice)[1]["polygon"] == custom["panels"][1]
    assert pack.PanelLayoutProvider.validate_inputs(choice) is True
    duplicate_groups = {
        **custom,
        "reading_groups": [[0, 0]],
    }
    duplicate_choice = layouts.CUSTOM_LAYOUT_PREFIX + json.dumps(
        duplicate_groups, separators=(",", ":"))
    assert "every panel exactly once" in pack.PanelLayoutProvider.validate_inputs(
        duplicate_choice)
    assert "unknown layout preset" in pack.PanelLayoutProvider.validate_inputs("missing")
    too_large = layouts.CUSTOM_LAYOUT_PREFIX + " " * (128 * 1024 + 1)
    assert "exceeds 128 KiB" in pack.PanelLayoutProvider.validate_inputs(too_large)

    async def helpers():
        indexed = await pack.ListGetItem.execute(["a", "b"], 20)
        unpacked = await pack.TupleUnpack.execute((7, 8))
        return indexed.result, unpacked.result

    assert asyncio.run(helpers()) == (("b",), (7, 8, None, None))


def test_provider_and_compositor_execute_in_real_isolated_guest():
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.panelcomposer_guest_test",
    )
    provider = loaded.node_mappings["PanelLayoutProvider"]
    compositor = loaded.node_mappings["PanelCompositor"]
    custom = {
        "category": "Tests",
        "label": "Half split",
        "panels": [
            [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
            [[0.5, 0], [1, 0], [1, 1], [0.5, 1]],
        ],
        "reading_groups": [[0, 1]],
    }
    custom_choice = "__panelcomposer_v2__:" + json.dumps(
        custom, separators=(",", ":"))

    async def run():
        session = await GuestSession("panelcomposer-conversion").start()
        refs = _sdk.InProcessRefResolver()
        try:
            provider_result = await session.execute(
                _plan(provider, {
                    "layout_preset": custom_choice,
                    "reading_order": "left_to_right",
                    "canvas_rotation": "0",
                    "aspect_ratio": "1:1 (Square)",
                    "page_orientation": "portrait",
                    "canvas_size_mode": "fixed_custom",
                    "fixed_preset_size": "1080p",
                    "fixed_custom_megapixels": 0.1,
                    "megapixels": 0.05,
                    "multiple": 8,
                }),
                _runtime(refs),
                capabilities={"raw"},
            )
            assert session.last_guest_pid not in (None, os.getpid())
            layout_json, dimensions, area_ref, colors = provider_result.result
            layout = json.loads(layout_json)
            assert len(layout["panels"]) == len(dimensions) == len(colors) == 2
            area = await refs.resolve(area_ref)
            assert tuple(area.shape[:1]) == (1,)
            assert tuple(area.shape[1:3]) == (
                layout["canvas_height"], layout["canvas_width"])

            red = torch.zeros((1, 24, 16, 3), dtype=torch.float32)
            red[..., 0] = 1
            green = torch.zeros((1, 24, 16, 3), dtype=torch.float32)
            green[..., 1] = 1
            red_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", red))
            green_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", green))
            composite_result = await session.execute(
                _plan(compositor, {
                    "layout_json": [layout_json],
                    "images": [red_ref, green_ref],
                    "canvas_mode": ["auto"],
                    "aspect_ratio": ["1:1 (Square)"],
                    "fixed_preset_size": ["1080p"],
                    "fixed_custom_megapixels": [0.1],
                    "page_orientation": ["auto"],
                    "scale_to_input_mode": ["largest"],
                    "fit_mode": ["stretch"],
                    "scale_algo": ["nearest"],
                    "gutter_px": [0],
                    "gutter_color": ["#000000"],
                }, node_id="2"),
                _runtime(refs),
                capabilities={"raw"},
            )
            page = await refs.resolve(composite_result.result[0])
            assert tuple(page.shape) == (
                1, layout["canvas_height"], layout["canvas_width"], 3)
            center_y = page.shape[1] // 2
            assert torch.allclose(page[0, center_y, page.shape[2] // 4],
                                  torch.tensor([1.0, 0.0, 0.0]))
            assert torch.allclose(page[0, center_y, 3 * page.shape[2] // 4],
                                  torch.tensor([0.0, 1.0, 0.0]))
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_scoped_shortcuts():
    sources = "\n".join(
        path.read_text(errors="replace")
        for path in sorted((V2 / "web").glob("*.js"))
    )
    assert sources.count('comfy.defs.extend("PanelLayoutProvider"') == 2
    for forbidden in (
        "fetch(", "window.", "document.", "localStorage", "sessionStorage",
        "app.registerExtension", "addDOMWidget", "layouts_user.json\")",
    ):
        assert forbidden not in sources
    assert "comfy.storage.get" in sources
    assert "comfy.storage.set" in sources
    assert "comfy.ui.showDialog" in sources
    assert "onKeyDown" in sources
    assert "node.widgets.mount" in sources
    assert "setPointerCapture" in sources

    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "panelcomposer_frontend_harness.mjs"),
            str(V2 / "web" / "panel_drawing_dialog.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: PanelComposer private layouts" in completed.stdout


def test_python_surface_has_no_host_or_mutable_pack_access():
    source = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(V2.rglob("*.py"))
        if "tests" not in path.parts
    )
    for forbidden in (
        "import folder_paths", "from folder_paths", "import server",
        "from server", "PromptServer", "aiohttp", "layouts_user.json",
        "open(", "Path(", "subprocess",
    ):
        assert forbidden not in source
    assert not (V2 / "nodes" / "routes.py").exists()


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-panelcomposer" / "x2adf5ad"
        / "comfyui-panelcomposer-x2adf5ad"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-panelcomposer" / "x2adf5ad"
    fresh.mkdir(parents=True)
    shutil.copytree(
        PACK,
        fresh / PACK.name,
        ignore=shutil.ignore_patterns("v2"),
    )
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_do_not_dirty_pristine_or_v2_with_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
