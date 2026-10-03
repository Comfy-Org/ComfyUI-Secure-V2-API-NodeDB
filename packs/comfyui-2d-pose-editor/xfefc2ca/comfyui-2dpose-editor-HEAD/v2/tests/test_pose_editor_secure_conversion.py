from __future__ import annotations

import ast
import asyncio
import base64
import copy
import hashlib
import importlib.util
from io import BytesIO
import json
import os
import pathlib
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image
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
COMMIT = "fefc2cadf4d5239238f74d1c5fa2b01a19cd681e"
COMFY_API_SHA256 = "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
PAIR = PACK_DB / "patches" / "comfyui-2d-pose-editor" / "xfefc2ca" / (
    "comfyui-2d-pose-editor-xfefc2ca"
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
    name = "_secure_pose_editor_conversion_test"
    for module in (name, f"{name}.nodes"):
        sys.modules.pop(module, None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _data_url(image: Image.Image) -> str:
    stream = BytesIO()
    image.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()


def _tree(root: pathlib.Path) -> dict[str, str]:
    files = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if not item.is_file() or any(
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in relative.parts
        ):
            continue
        files[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return files


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


def test_pinned_pristine_and_secure_census_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    source_tree = ast.parse((PACK / "pose_editor_node.py").read_text())
    assert {node.name for node in source_tree.body if isinstance(node, ast.ClassDef)} == {
        "PoseEditor2DNode"
    }
    assert (PACK / "js" / "pose_editor.js").read_text().count(
        "app.registerExtension({"
    ) == 1
    assert not list(PACK.rglob("*_routes.py"))

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"PoseEditor2D": pack.PoseEditor2D}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"PoseEditor2D": "2D Pose Editor"}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.pose_editor_secure_test")
    assert set(loaded.node_mappings) == {"PoseEditor2D"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_and_fingerprint_preserve_upstream_contract():
    node = _import_v2().PoseEditor2D
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "PoseEditor2D", "2D Pose Editor", "2D Pose"
    )
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("image_data", "STRING", False),
        ("output_size_mode", "COMBO", False),
        ("custom_width", "INT", False),
        ("custom_height", "INT", False),
        ("background_image", "IMAGE", True),
    ]
    assert schema.inputs[0].default == ""
    assert schema.inputs[1].options == ["Standard", "Background", "Custom"]
    assert schema.inputs[1].default == "Standard"
    for item in schema.inputs[2:4]:
        assert (item.default, item.min, item.max, item.step) == (600, 64, 4096, 8)
    assert [(item.id, item.io_type, item.display_name) for item in schema.outputs] == [
        ("image", "IMAGE", "image")
    ]
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ("raw",)
    first = asyncio.run(node.fingerprint_inputs("abc", "Custom", 512, 768))
    second = asyncio.run(node.fingerprint_inputs("abc", "Custom", 512, 768))
    assert first == second == hashlib.md5(b"abc|Custom|512|768").hexdigest()


def test_standard_background_custom_lanczos_and_alpha_compositing():
    module = sys.modules[_import_v2().PoseEditor2D.__module__]
    pose = Image.new("RGBA", (4, 2), (255, 0, 0, 128))
    standard = module.compose_pose(_data_url(pose), "Standard", 600, 600, None)
    assert tuple(standard.shape) == (1, 2, 4, 3)
    # Alpha over the legacy #e0e0e0 canvas.
    assert torch.allclose(standard[0, 0, 0], torch.tensor([240 / 255, 112 / 255, 112 / 255]), atol=1 / 255)

    background = torch.zeros(1, 6, 6, 3)
    background[..., 1] = 1
    composed = module.compose_pose(_data_url(pose), "Background", 600, 600, background)
    assert tuple(composed.shape) == (1, 6, 6, 3)
    assert composed[0, 0, 0, 1] > 0.99
    assert composed[0, 3, 2, 0] > 0.45

    custom = module.compose_pose(_data_url(pose), "Custom", 8 * 8, 8 * 12, background)
    assert tuple(custom.shape) == (1, 96, 64, 3)
    expected_bg = Image.fromarray(
        (background[0].numpy() * 255).round().astype(np.uint8)
    ).convert("RGBA").resize((64, 96), Image.Resampling.LANCZOS)
    expected = expected_bg.copy()
    expected_pose = pose.resize((64, 32), Image.Resampling.LANCZOS)
    expected.paste(expected_pose, (0, 32), expected_pose)
    expected_tensor = torch.from_numpy(
        np.asarray(expected.convert("RGB"), dtype=np.float32).copy() / 255
    )
    assert torch.equal(custom[0], expected_tensor)


def test_malformed_and_resource_bounded_inputs_fail_closed():
    module = sys.modules[_import_v2().PoseEditor2D.__module__]
    blank = module.compose_pose("not base64!", "Standard", 600, 600, None)
    assert tuple(blank.shape) == (1, 600, 600, 3)
    assert torch.allclose(blank[0, 0, 0], torch.tensor([224 / 255] * 3))
    with pytest.raises(ValueError, match="16 MiB"):
        module.compose_pose("x" * (module.MAX_DATA_URL_BYTES + 1), "Standard", 600, 600, None)
    with pytest.raises(ValueError, match="custom dimensions"):
        module.compose_pose("", "Custom", 63, 600, None)
    with pytest.raises(ValueError, match="unknown output"):
        module.compose_pose("", "Arbitrary", 600, 600, None)

    huge = Image.new("1", (4097, 4097), 0)
    encoded = _data_url(huge)
    assert module._decode_pose(encoded) is None


def test_node_executes_in_isolated_guest_and_returns_bounded_image_ref():
    pack = _import_v2()
    node = pack.PoseEditor2D

    async def run():
        refs = _sdk.InProcessRefResolver()
        background = torch.zeros(1, 20, 30, 3)
        background[..., 2] = 1
        background_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", background))
        pose = _data_url(Image.new("RGBA", (10, 10), (255, 0, 0, 255)))
        plan = _sdk.ExecutionPlan(
            prompt_id="pose-editor-test", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={"image_data": pose, "output_size_mode": "Background",
                    "custom_width": 600, "custom_height": 600,
                    "background_image": background_ref},
            permissions=node.SDK_PERMISSIONS,
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps()
        )
        session = await GuestSession("pose-editor-pack", guest_runtime_root=V2).start()
        try:
            output = await session.execute(plan, runtime, capabilities=node.SDK_PERMISSIONS)
            returned = await refs.resolve(output.result[0])
            return returned, session.last_guest_pid
        finally:
            await session.kill()

    image, guest_pid = asyncio.run(run())
    assert guest_pid not in (None, os.getpid())
    assert tuple(image.shape) == (1, 20, 30, 3)
    assert image[0, 10, 15, 0] > 0.9


def test_manifest_frontend_security_contract_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_SHA256
    source = "\n".join(item.read_text(errors="replace") for item in (V2 / "web").glob("*.js"))
    for forbidden in (
        "app.graph", "graph.serialize", "FileReader", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "document.", "window.", "innerHTML",
    ):
        assert forbidden not in source
    assert "comfy.files.pick" in source
    assert "beforeSerialize" in source
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_behavior_lifecycle_files_history_and_serialization():
    completed = subprocess.run(
        ["node", "--experimental-vm-modules", str(V2 / "tests" / "pose_frontend_harness.mjs"),
         str(V2 / "web" / "main.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure mounted pose editor" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest = json.loads(PAIR.with_suffix(".json").read_text())
    diff_text = PAIR.with_suffix(".diff").read_text()
    fresh = tmp_path / "comfyui-2d-pose-editor" / "xfefc2ca"
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
