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
COMMIT = "3fbc963edc0eda54b9076a1d754610c9f322fd1b"
COMFY_API_SHA256 = "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
COMFY_API_PYI_SHA256 = "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
PAIR = PACK_DB / "patches" / "comfyui-image-compare" / "x3fbc963" / (
    "comfyui-image-compare-x3fbc963"
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
    name = "_secure_image_compare_conversion_test"
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
    source = ast.parse((PACK / "__init__.py").read_text())
    classes = {item.name for item in source.body if isinstance(item, ast.ClassDef)}
    assert classes == {"ImageCompareNode"}
    assert (PACK / "image_compare_node.js").read_text().count("app.registerExtension({") == 1
    assert not list(PACK.rglob("*_routes.py"))

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"ImageCompareNode": pack.ImageCompareNode}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"ImageCompareNode": "Image Compare"}
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.image_compare_secure_test")
    assert set(loaded.node_mappings) == {"ImageCompareNode"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_upstream_contract_without_raw_authority():
    node = _import_v2().ImageCompareNode
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category, schema.is_output_node) == (
        "ImageCompareNode", "Image Compare", "SBCODE", True
    )
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("image_a", "IMAGE", False), ("image_b", "IMAGE", False)
    ]
    assert schema.outputs == []
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ("ui",)


class _ShapeOnlyImage:
    def __init__(self, batch, shape):
        self.batch = batch
        self.shape = shape
        self.selected = False

    async def batch_size(self):
        return self.batch

    async def spatial_shape(self):
        return self.shape

    async def select_batch(self, _indices):
        self.selected = True
        return self


def test_malformed_oversized_and_malformed_preview_results_fail_closed():
    pack = _import_v2()
    module = sys.modules[pack.ImageCompareNode.__module__]
    with pytest.raises(ValueError, match="at least one"):
        asyncio.run(module._validate_image(_ShapeOnlyImage(0, (1, 1)), "image_a"))
    with pytest.raises(ValueError, match="dimensions"):
        asyncio.run(module._validate_image(
            _ShapeOnlyImage(1, (1, module.MAX_DIMENSION + 1)), "image_a"
        ))
    with pytest.raises(ValueError, match="dimensions"):
        asyncio.run(module._validate_image(
            _ShapeOnlyImage(1, (8192, 8192)), "image_b"
        ))
    for malformed in ({}, {"images": []}, {"images": ["not metadata"]},
                      {"images": [{}, {}]}):
        with pytest.raises(RuntimeError, match="preview"):
            module._first_preview(malformed, "image_a")


class _PreviewUi:
    def __init__(self, refs):
        self.refs = refs
        self.calls = []

    async def preview_images(self, images, animated=False):
        pixels = await self.refs.resolve(images)
        self.calls.append(pixels.clone())
        label = "a" if len(self.calls) % 2 else "b"
        return {"images": [{
            "filename": f"compare-{label}.png", "subfolder": "", "type": "temp",
        }]}


def test_guest_selects_first_images_preserves_ab_order_and_denies_missing_ui():
    pack = _import_v2()
    node = pack.ImageCompareNode

    async def run():
        refs = _sdk.InProcessRefResolver()
        ui = _PreviewUi(refs)
        image_a = torch.stack((torch.full((3, 5, 3), 0.1), torch.full((3, 5, 3), 0.9)))
        image_b = torch.stack((torch.full((4, 2, 3), 0.2), torch.full((4, 2, 3), 0.8)))
        ref_a = _sdk.ImageRef._wrap(await refs.create("IMAGE", image_a))
        ref_b = _sdk.ImageRef._wrap(await refs.create("IMAGE", image_b))
        plan = _sdk.ExecutionPlan(
            prompt_id="image-compare-test", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__,
            inputs={"image_a": ref_a, "image_b": ref_b}, permissions=node.SDK_PERMISSIONS,
        )
        context = _sdk.InProcessCtxProvider().build(plan)
        context.ui = ui
        runtime = _sdk.Runtime(refs=refs, ctx=context, ops=_sdk.InProcessOps())
        session = await GuestSession("image-compare-pack", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, runtime, capabilities=node.SDK_PERMISSIONS)
            assert [item["filename"] for item in result.ui["images"]] == [
                "compare-a.png", "compare-b.png"
            ]
            assert len(ui.calls) == 2
            assert tuple(ui.calls[0].shape) == (1, 3, 5, 3)
            assert tuple(ui.calls[1].shape) == (1, 4, 2, 3)
            assert torch.allclose(ui.calls[0], torch.full_like(ui.calls[0], 0.1))
            assert torch.allclose(ui.calls[1], torch.full_like(ui.calls[1], 0.2))
            before = len(ui.calls)
            with pytest.raises(Exception, match="capability 'ui'"):
                await session.execute(plan, runtime, capabilities=())
            assert len(ui.calls) == before
            return session.last_guest_pid
        finally:
            await session.kill()

    assert asyncio.run(run()) not in (None, os.getpid())


def test_manifest_frontend_security_contract_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256
    source = "\n".join(item.read_text(errors="replace") for item in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "app.graph", "FileReader", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "document.", "window.", "data:image", "innerHTML",
    ):
        assert forbidden not in source
    assert "node.getOutputImages()" in source
    assert "node.widgets.mount(" in source
    assert ".raw()" not in (V2 / "nodes.py").read_text()
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_order_geometry_replacement_races_resize_and_teardown():
    completed = subprocess.run(
        ["node", "--experimental-vm-modules",
         str(V2 / "tests" / "image_compare_frontend_harness.mjs"),
         str(V2 / "web" / "main.js")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure image comparer" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest = json.loads(PAIR.with_suffix(".json").read_text())
    # Preserve upstream's CRLF lines exactly. Path.read_text() performs
    # universal-newline translation and would corrupt the review diff before
    # the byte-exact applier sees it; production also decodes read_bytes().
    diff_text = PAIR.with_suffix(".diff").read_bytes().decode("utf-8")
    fresh = tmp_path / "comfyui-image-compare" / "x3fbc963"
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
