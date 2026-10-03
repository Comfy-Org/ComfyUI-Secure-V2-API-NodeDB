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
COMMIT = "2a440145a3b858a24192d6f7b2f0d48015928dee"
COMFY_API_SHA256 = "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
COMFY_API_PYI_SHA256 = "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
PAIR = PACK_DB / "patches" / "comfyui-preview360panorama" / "x2a44014" / (
    "comfyui-preview360panorama-x2a44014"
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
    name = "_secure_preview360_conversion_test"
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
    source = ast.parse((PACK / "nodes.py").read_text())
    classes = {item.name for item in source.body if isinstance(item, ast.ClassDef)}
    assert classes == {"PanoramaViewerNode", "PanoramaVideoViewerNode"}
    assert (PACK / "js" / "pano_viewer.js").read_text().count("app.registerExtension({") == 1
    assert not list(PACK.rglob("*_routes.py"))

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == {
        "PanoramaViewerNode", "PanoramaVideoViewerNode"
    }
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {
        "PanoramaViewerNode": "Preview 360 Panorama",
        "PanoramaVideoViewerNode": "Preview 360 Video Panorama",
    }
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.preview360_secure_test")
    assert set(loaded.node_mappings) == set(pack.NODE_CLASS_MAPPINGS)
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schemas_preserve_both_upstream_nodes():
    pack = _import_v2()
    still = pack.PanoramaViewerNode.GET_SCHEMA()
    assert (still.node_id, still.display_name, still.category, still.is_output_node) == (
        "PanoramaViewerNode", "Preview 360 Panorama", "pytorch360convert", True
    )
    assert [(item.id, item.io_type) for item in still.inputs] == [
        ("images", "IMAGE"), ("max_width", "INT")
    ]
    assert still.inputs[1].default == 4096
    assert still.outputs == []

    video = pack.PanoramaVideoViewerNode.GET_SCHEMA()
    assert (video.node_id, video.display_name, video.category, video.is_output_node) == (
        "PanoramaVideoViewerNode", "Preview 360 Video Panorama",
        "pytorch360convert", True,
    )
    assert [(item.id, item.io_type) for item in video.inputs] == [
        ("video_frames", "IMAGE"), ("fps", "INT"), ("max_width", "INT")
    ]
    assert (video.inputs[1].default, video.inputs[1].min,
            video.inputs[1].max, video.inputs[1].step) == (30, 1, 120, 1)
    assert video.inputs[2].default == 2048
    assert video.outputs == []
    for node in (pack.PanoramaViewerNode, pack.PanoramaVideoViewerNode):
        assert node.SDK_REFS is True
        assert node.SDK_PERMISSIONS == ("raw", "ui")


def _legacy_frame(frame: torch.Tensor, max_width: int) -> torch.Tensor:
    value = (frame.numpy() * 255).astype(np.uint8)
    image = Image.fromarray(value)
    if max_width > 0 and max(image.size) > max_width:
        target = tuple(int(max_width * value / max(image.size)) for value in image.size)
        image = image.resize(target, resample=Image.Resampling.LANCZOS)
    return torch.from_numpy(np.asarray(image, dtype=np.float32).copy() / 255)


def test_still_and_video_preserve_lanczos_dimensions_order_and_values():
    pack = _import_v2()
    module = sys.modules[pack.PanoramaViewerNode.__module__]
    width, height = 17, 9
    x = torch.linspace(0, 1, width).reshape(1, 1, width, 1)
    y = torch.linspace(0, 1, height).reshape(1, height, 1, 1)
    first = torch.cat((x.expand(1, height, width, 1), y.expand(1, height, width, 1),
                       torch.zeros(1, height, width, 1)), dim=-1)
    second = torch.flip(first, dims=(2,))
    third = torch.full_like(first, 0.25)
    batch = torch.cat((first, second, third))

    still = module.prepare_preview(batch, 8, video=False)
    assert tuple(still.shape) == (1, 4, 8, 3)
    assert torch.equal(still[0], _legacy_frame(first[0], 8))

    video = module.prepare_preview(batch, 8, video=True)
    assert tuple(video.shape) == (3, 4, 8, 3)
    for index in range(3):
        assert torch.equal(video[index], _legacy_frame(batch[index], 8))
    assert float(video[0, 0, 0, 0]) < float(video[1, 0, 0, 0])
    assert torch.allclose(video[2], torch.full_like(video[2], 63 / 255))


def test_malformed_shapes_and_resource_bounds_fail_closed():
    pack = _import_v2()
    module = sys.modules[pack.PanoramaViewerNode.__module__]
    for malformed in (
        torch.zeros(4, 4, 3), torch.zeros(0, 4, 4, 3), torch.zeros(1, 4, 4, 2),
    ):
        with pytest.raises(ValueError):
            module.prepare_preview(malformed, 16, video=True)
    with pytest.raises(ValueError, match="max_width"):
        module.prepare_preview(torch.zeros(1, 4, 4, 3), 0, video=False)
    with pytest.raises(ValueError, match="max_width"):
        module.prepare_preview(torch.zeros(1, 4, 4, 3), -2, video=False)
    with pytest.raises(ValueError, match="max_width"):
        module.prepare_preview(
            torch.zeros(1, 4, 4, 3), module.MAX_DIMENSION + 1, video=False
        )
    with pytest.raises(ValueError, match="frame count"):
        module.prepare_preview(
            torch.zeros(module.MAX_VIDEO_FRAMES + 1, 1, 1, 3), 1, video=True
        )
    with pytest.raises(ValueError, match="video pixels"):
        module.prepare_preview(
            torch.empty(129, 1024, 1024, 3, device="meta"), 512, video=True
        )
    with pytest.raises(ValueError, match="dimensions"):
        module.prepare_preview(
            torch.empty(1, 1, module.MAX_DIMENSION + 1, 3, device="meta"),
            512, video=False,
        )
    with pytest.raises(ValueError, match="fps"):
        asyncio.run(pack.PanoramaVideoViewerNode.execute(None, fps=0, max_width=16))


class _PreviewUi:
    def __init__(self, refs):
        self.refs = refs
        self.calls = []

    async def preview_images(self, images, animated=False):
        pixels = await self.refs.resolve(images)
        self.calls.append(pixels.clone())
        return {
            "images": [
                {"filename": f"frame-{index}.png", "subfolder": "", "type": "temp"}
                for index in range(len(pixels))
            ]
        }


def test_both_nodes_execute_in_isolated_guest_with_managed_preview_outputs():
    pack = _import_v2()

    async def run():
        refs = _sdk.InProcessRefResolver()
        ui = _PreviewUi(refs)
        session = await GuestSession("preview360-pack", guest_runtime_root=V2).start()
        try:
            source = torch.stack((torch.full((6, 10, 3), 0.2),
                                  torch.full((6, 10, 3), 0.8)))
            image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", source))
            results = []
            first_plan = None
            for number, (node_id, inputs) in enumerate((
                ("PanoramaViewerNode", {"images": image_ref, "max_width": 5}),
                ("PanoramaVideoViewerNode", {
                    "video_frames": image_ref, "fps": 24, "max_width": 5,
                }),
            ), 1):
                node = pack.NODE_CLASS_MAPPINGS[node_id]
                plan = _sdk.ExecutionPlan(
                    prompt_id="preview360-test", node_id=str(number),
                    node_type=node.__name__, tier="sandbox", node_module=node.__module__,
                    inputs=inputs, permissions=node.SDK_PERMISSIONS,
                )
                if first_plan is None:
                    first_plan = plan
                context = _sdk.InProcessCtxProvider().build(plan)
                context.ui = ui
                runtime = _sdk.Runtime(refs=refs, ctx=context, ops=_sdk.InProcessOps())
                results.append(await session.execute(
                    plan, runtime, capabilities=node.SDK_PERMISSIONS
                ))
            assert first_plan is not None
            denied_context = _sdk.InProcessCtxProvider().build(first_plan)
            denied_context.ui = ui
            denied_runtime = _sdk.Runtime(
                refs=refs, ctx=denied_context, ops=_sdk.InProcessOps()
            )
            before = len(ui.calls)
            with pytest.raises(Exception, match="capability 'ui'"):
                await session.execute(first_plan, denied_runtime, capabilities=("raw",))
            assert len(ui.calls) == before
            return results, ui.calls, session.last_guest_pid
        finally:
            await session.kill()

    results, calls, guest_pid = asyncio.run(run())
    assert guest_pid not in (None, os.getpid())
    assert [tuple(value.shape) for value in calls] == [(1, 3, 5, 3), (2, 3, 5, 3)]
    assert [len(result.ui["images"]) for result in results] == [1, 2]
    assert all(item["type"] == "temp" for result in results for item in result.ui["images"])


def test_manifest_frontend_security_contract_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256
    assert not (V2 / "install.py").exists()
    assert not (V2 / "js").exists()
    source = "\n".join(item.read_text(errors="replace") for item in (V2 / "web").glob("*.js"))
    for forbidden in (
        "../../../scripts/", "app.graph", "FileReader", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "document.", "window.", "data:image", "cdnjs",
        "jsdelivr", "innerHTML",
    ):
        assert forbidden not in source
    assert "node.getOutputImages()" in source
    assert "node.widgets.mount(" in source
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_projection_controls_playback_resize_and_teardown():
    completed = subprocess.run(
        ["node", "--experimental-vm-modules",
         str(V2 / "tests" / "panorama_frontend_harness.mjs"), str(V2 / "web" / "main.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure panorama mount" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest = json.loads(PAIR.with_suffix(".json").read_text())
    diff_text = PAIR.with_suffix(".diff").read_text()
    fresh = tmp_path / "comfyui-preview360panorama" / "x2a44014"
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
