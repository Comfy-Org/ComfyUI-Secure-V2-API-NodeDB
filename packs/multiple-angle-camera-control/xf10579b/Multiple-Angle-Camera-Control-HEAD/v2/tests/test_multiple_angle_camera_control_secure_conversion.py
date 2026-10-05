from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import itertools
import json
import os
import pathlib
import shutil
import sys


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "f10579b4846ff3ff9701d88b37ea0a838ba30025"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "multiple-angle-camera-control" / "xf10579b" / (
    "multiple-angle-camera-control-xf10579b"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk, io  # noqa: E402
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
    return _import_package("_secure_multiple_angle_camera_test", V2)


def _upstream():
    return _import_package("_upstream_multiple_angle_camera_test", PACK)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(
                node_class, "SDK_PERMISSIONS", (),
            ) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs",
                    "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
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


def test_pinned_actual_loader_census_and_entrypoint_are_exact():
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "2 supported, 0 rejected, 0 pending" in report

    pristine_python = [
        path for path in PACK.rglob("*.py") if V2 not in path.parents
    ]
    classes = set()
    pristine_text = []
    for path in pristine_python:
        text = path.read_text(errors="replace")
        pristine_text.append(text)
        tree = ast.parse(text)
        classes.update(
            item.name for item in tree.body if isinstance(item, ast.ClassDef)
        )
    assert classes == {"CameraControlPromptNode", "RelightingPromptNode"}
    upstream = _upstream()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {
        "CameraControlPromptNode", "RelightingPromptNode",
    }
    assert upstream.NODE_DISPLAY_NAME_MAPPINGS == {
        "CameraControlPromptNode": "Camera Control Prompt Generator",
        "RelightingPromptNode": "Relighting Prompt Generator",
    }
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]
    source = "\n".join(pristine_text)
    assert "PromptServer" not in source
    assert "routes." not in source

    secure = _secure()
    assert set(secure.NODE_CLASS_MAPPINGS) == set(upstream.NODE_CLASS_MAPPINGS)
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == upstream.NODE_DISPLAY_NAME_MAPPINGS
    extension = asyncio.run(secure.comfy_entrypoint())
    assert [node.GET_SCHEMA().node_id for node in asyncio.run(
        extension.get_node_list()
    )] == ["CameraControlPromptNode", "RelightingPromptNode"]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.multiple_angle_camera_secure_test",
    )
    assert set(loaded.node_mappings) == set(upstream.NODE_CLASS_MAPPINGS)
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_all_names_types_options_defaults_and_bounds():
    secure = _secure()
    camera = secure.CameraControlPromptNode
    schema = camera.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "CameraControlPromptNode",
        "Camera Control Prompt Generator",
        "prompt/camera",
    )
    assert [item.id for item in schema.inputs] == [
        "move_horizontal", "move_vertical", "move_forward", "rotate",
        "view_top_down", "view_wide_angle", "view_close_up",
        "view_bottom_up",
    ]
    assert [item.io_type for item in schema.inputs] == [
        "COMBO", "COMBO", "COMBO", "INT", "BOOLEAN", "BOOLEAN",
        "BOOLEAN", "BOOLEAN",
    ]
    assert schema.inputs[0].options == ["none", "left", "right"]
    assert schema.inputs[0].default == "none"
    assert schema.inputs[1].options == ["none", "up", "down"]
    assert schema.inputs[1].default == "none"
    assert schema.inputs[2].options == ["no", "yes"]
    assert schema.inputs[2].default == "no"
    rotate = schema.inputs[3]
    assert (rotate.default, rotate.min, rotate.max, rotate.step) == (0, -90, 90, 45)
    assert rotate.display_mode == io.NumberDisplay.slider
    assert [item.default for item in schema.inputs[4:]] == [False] * 4
    assert [item.io_type for item in schema.outputs] == ["STRING"]
    assert [item.display_name for item in schema.outputs] == ["prompt"]
    assert camera.SDK_REFS is False
    assert camera.SDK_PERMISSIONS == ()

    relighting = secure.RelightingPromptNode
    schema = relighting.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "RelightingPromptNode", "Relighting Prompt Generator", "relighting",
    )
    assert [item.id for item in schema.inputs] == [
        "light_direction", "use_chinese",
    ]
    assert schema.inputs[0].options == [
        "front", "front_left", "left", "back_left", "back", "back_right",
        "right", "front_right", "above", "below",
    ]
    assert schema.inputs[0].default == "front"
    assert schema.inputs[1].default is True
    assert [item.io_type for item in schema.outputs] == ["STRING"]
    assert [item.display_name for item in schema.outputs] == ["prompt"]
    assert relighting.SDK_REFS is False
    assert relighting.SDK_PERMISSIONS == ()


def test_camera_prompt_is_exhaustively_differential():
    upstream = _upstream().NODE_CLASS_MAPPINGS["CameraControlPromptNode"]()
    secure = _secure().CameraControlPromptNode
    for values in itertools.product(
        ("none", "left", "right"),
        ("none", "up", "down"),
        ("no", "yes"),
        (-90, -45, 0, 45, 90),
        (False, True),
        (False, True),
        (False, True),
        (False, True),
    ):
        assert secure.execute(*values).result == upstream.generate_prompt(*values)

    for rotation in (-137, -1, 1, 137):
        values = ("unexpected", "unexpected", "unexpected", rotation,
                  False, False, False, False)
        assert secure.execute(*values).result == upstream.generate_prompt(*values)


def test_relighting_prompt_is_differential_for_every_mode_and_fallback():
    upstream = _upstream().NODE_CLASS_MAPPINGS["RelightingPromptNode"]()
    secure = _secure().RelightingPromptNode
    for direction, use_chinese in itertools.product(
        (*secure.LIGHT_DIRECTIONS, "unexpected"), (False, True),
    ):
        assert secure.execute(direction, use_chinese).result == (
            upstream.generate_prompt(direction, use_chinese)
        )


def test_real_guest_executes_both_nodes_without_any_capabilities():
    secure = _secure()

    async def run(node_class, node_id, inputs):
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="multiple-angle-camera-test",
            node_id=node_id,
            node_type=node_class.__name__,
            tier="sandbox",
            node_module=node_class.__module__,
            inputs=inputs,
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "multiple-angle-camera-pack", guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            return result.result, session.last_guest_pid
        finally:
            await session.kill()

    camera_inputs = {
        "move_horizontal": "left",
        "move_vertical": "up",
        "move_forward": "yes",
        "rotate": -45,
        "view_top_down": True,
        "view_wide_angle": False,
        "view_close_up": True,
        "view_bottom_up": False,
    }
    camera_result, camera_pid = asyncio.run(run(
        secure.CameraControlPromptNode, "camera", camera_inputs,
    ))
    light_result, light_pid = asyncio.run(run(
        secure.RelightingPromptNode,
        "light",
        {"light_direction": "back_right", "use_chinese": False},
    ))
    upstream = _upstream().NODE_CLASS_MAPPINGS
    assert camera_result == upstream["CameraControlPromptNode"]().generate_prompt(
        **camera_inputs,
    )
    assert light_result == upstream["RelightingPromptNode"]().generate_prompt(
        "back_right", False,
    )
    assert camera_pid not in (None, os.getpid())
    assert light_pid not in (None, os.getpid())


def test_manifest_stubs_and_ambient_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests",
        "aiohttp", "subprocess", "open(", "os.", "sys.", "ctx()",
        "torch", "numpy",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "multiple-angle-camera-control" / "xf10579b"
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
