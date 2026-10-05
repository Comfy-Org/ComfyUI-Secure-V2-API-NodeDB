from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import io as stdlib_io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import types

import numpy as np
from PIL import Image, PngImagePlugin
import pytest
import torch


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes-pack2-output-formats"
)).resolve()
COMMIT = "fda1775b8e182f7409a1ee392919b5f86356a141"
TREE = "f2f2b485d89c97b2917fc12181f5cbf49af392f4"
COMFY_API_DTS_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
COMFY_API_PYI_SHA256 = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
NODE_IDS = {
    "ViewImagePropertiesSG", "LoadImageandviewPropertiesSG",
    "PreviewImageandviewPropertiesSG", "SaveImageFormatQualityPropertiesSG",
}
PRISTINE_FILES = {
    ".github/workflows/publish_comfy_registry_action.yml", "LICENSE",
    "Load_Image_and_view_Properties_SG.py",
    "Preview_Image_and_view_Properties_SG.py", "README.md",
    "Save_Image_Format_Quality_Properties_SG.py",
    "View_Image_Properties_SG.py", "__init__.py",
    "js/Load_Image_and_view_Properties_SG.js",
    "js/Preview_Image_and_view_Properties_SG.js",
    "js/Save_Image_Format_Quality_Properties_SG.js",
    "js/View_Image_Properties_SG.js", "pyproject.toml",
}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ["COMFY_CORE_ROOT"] = str(CORE)

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_v2(name="_secure_image_properties_sg_conversion_test"):
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
        if not path.is_file() or (omit_v2 and relative.parts[0] == "v2"):
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


class _Assets:
    def __init__(self, refs, files):
        self.refs = refs
        self.files = dict(files)

    async def resolve(self, folder, name):
        assert folder == "input"
        if name not in self.files:
            raise FileNotFoundError(name)
        value = self.files[name]
        logical = str(value) if isinstance(value, pathlib.Path) else name
        return _sdk.AssetRef._wrap(await self.refs.create("ASSET", logical))

    async def _value(self, ref):
        logical = await self.refs.resolve(ref)
        if logical in self.files:
            return self.files[logical]
        candidate = pathlib.Path(logical)
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(logical)

    async def size(self, ref):
        value = await self._value(ref)
        return pathlib.Path(value).stat().st_size if isinstance(value, pathlib.Path) else len(value)

    async def read_bytes(self, ref):
        value = await self._value(ref)
        return value.read_bytes() if isinstance(value, pathlib.Path) else value

    async def digest(self, ref):
        return hashlib.sha256(await self.read_bytes(ref)).hexdigest()


class _Output:
    def __init__(self):
        self.calls = []

    async def save_images(self, images, **kwargs):
        self.calls.append((images, copy.deepcopy(kwargs)))
        return {"images": [{"filename": "saved." + kwargs["image_format"], "type": "output", "subfolder": ""}]}


class _UI:
    def __init__(self):
        self.calls = []

    async def preview_images(self, images, animated=False):
        self.calls.append((images, animated))
        return {"images": [{"filename": "preview.png", "type": "temp", "subfolder": "secure"}]}


def _png_bytes(*, metadata=True, alpha=True):
    image = Image.new("RGBA" if alpha else "RGB", (4, 2), (64, 128, 192, 128) if alpha else (64, 128, 192))
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("prompt", json.dumps({
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "demo.safetensors"}},
            "7": {"class_type": "KSampler", "inputs": {
                "seed": 123, "steps": 20, "cfg": 7.5,
                "sampler_name": "euler", "scheduler": "normal",
            }},
        }))
    buffer = stdlib_io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=info)
    return buffer.getvalue()


def _plan(node_class, inputs, node_number):
    return _sdk.ExecutionPlan(
        prompt_id=f"image-properties-{node_number}", node_id=str(node_number),
        node_type=node_class.__name__, tier="sandbox", node_module=node_class.__module__,
        inputs=inputs, permissions=tuple(node_class.SDK_PERMISSIONS), method="execute",
    )


def _runtime(plan, refs, assets, output, ui):
    context = _sdk.InProcessCtxProvider().build(plan)
    context.assets = assets
    context.output = output
    context.ui = ui
    return _sdk.Runtime(refs=refs, ctx=context, ops=_sdk.InProcessOps())


def test_pinned_pristine_census_manifest_and_contract_are_exact():
    assert set(_tree(PACK, omit_v2=True)) == PRISTINE_FILES
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert TREE in (V2 / "SECURE_CONVERSION.md").read_text()
    root = (PACK / "__init__.py").read_text()
    assert set(re.findall(r'"([A-Za-z]+SG)"\s*:', root)) == NODE_IDS
    assert sum(path.read_text().count("app.registerExtension({") for path in (PACK / "js").glob("*.js")) == 4
    assert not re.findall(r"PromptServer|routes\.(?:get|post)", "\n".join(path.read_text() for path in PACK.glob("*.py")))

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.image_properties_sg_test")
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schemas_preserve_ids_order_options_bounds_and_authority():
    pack = _import_v2()
    expected = {
        "ViewImagePropertiesSG": (("image",), ("IMAGE", "INT", "INT", "INT", "FLOAT", "FLOAT", "FLOAT"), ("raw",)),
        "LoadImageandviewPropertiesSG": (("image",), ("IMAGE", "MASK", "INT", "INT", "FLOAT", "FLOAT", "FLOAT"), ("assets", "raw")),
        "PreviewImageandviewPropertiesSG": (("images",), ("IMAGE", "INT", "INT", "INT", "FLOAT", "FLOAT", "FLOAT"), ("raw", "ui")),
        "SaveImageFormatQualityPropertiesSG": ((
            "images", "filename_prefix", "Properties", "format", "png_compress_level",
            "jpeg_quality", "jpeg_optimize", "jpeg_subsampling", "webp_quality",
            "webp_method", "webp_lossless", "tiff_compression", "tiff_jpeg_quality",
        ), (), ("raw", "output", "ui")),
    }
    for node_id, (inputs, outputs, permissions) in expected.items():
        node = pack.NODE_CLASS_MAPPINGS[node_id]
        schema = node.GET_SCHEMA()
        schema.validate()
        assert tuple(item.id for item in schema.inputs) == inputs
        assert tuple(item.io_type for item in schema.outputs) == outputs
        assert schema.is_output_node is True
        assert node.SDK_REFS is True
        assert node.SDK_PERMISSIONS == permissions
    save = pack.NODE_CLASS_MAPPINGS["SaveImageFormatQualityPropertiesSG"].GET_SCHEMA()
    by_id = {item.id: item for item in save.inputs}
    assert by_id["Properties"].options == ["None", "Basic", "Metadata", "Both"]
    assert len(by_id["format"].options) == 5
    assert (by_id["png_compress_level"].min, by_id["png_compress_level"].max, by_id["png_compress_level"].default) == (0, 9, 9)
    assert (by_id["webp_method"].min, by_id["webp_method"].max, by_id["webp_method"].default) == (0, 6, 4)
    assert [item.value for item in save.hidden] == ["PROMPT", "EXTRA_PNGINFO"]


def test_properties_metadata_filename_and_bounds_match_published_behavior():
    pack = _import_v2()
    module = sys.modules[f"{pack.__name__}.nodes"]
    tensor = torch.zeros((2, 9, 16, 3), dtype=torch.float32)
    values = module._properties(tensor)
    assert values[:6] == (2, 16, 9, 16.0, 9.0, 0.000144)
    assert values[6] == [
        "16x9 | 0.00MP ", "Ratio: 16:9 or 1.78:1",
        "Batch: 2 images | Total Tensor: 0.01MB",
    ]
    assert module._properties(torch.zeros((1, 100, 239, 3)))[6][1].endswith("or ~2.39:1")
    prompt = {"1": {"class_type": "KSampler", "inputs": {
        "seed": 9, "steps": 12, "cfg": 6.5, "sampler_name": "dpmpp_2m", "scheduler": "karras",
    }}, "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux.safetensors"}}}
    assert module._metadata_lines(prompt)[0] == "flux.safetensors (UNET)"
    assert module._metadata_lines(parameters="x\nModel: forge.ckpt, Seed: 42, Steps: 30, CFG scale: 8, Sampler: Euler, Schedule type: Normal")[2] == {
        "seed": 42, "steps": 30, "cfg": 8.0, "sampler": "Euler", "scheduler": "Normal",
    }
    fixed = module.datetime(2026, 10, 5, 13, 2, 3)
    assert module._parse_filename("x/%date:yyyyMMdd%/%time:HHmmss%/%timestamp%", fixed) == "x/20261005/130203/1791230523"
    for invalid in (torch.zeros((3, 4)), torch.zeros((1, 2, 3, 2)), torch.zeros((0, 2, 3, 3))):
        with pytest.raises((TypeError, ValueError)):
            module._checked_image(invalid)


def test_direct_load_preview_and_save_behavior_is_exact(monkeypatch):
    pack = _import_v2()
    refs = _sdk.InProcessRefResolver()
    data = _png_bytes()
    assets = _Assets(refs, {"sample.png": data})
    output = _Output()
    ui = _UI()

    async def run():
        source = torch.linspace(0, 1, 2 * 3 * 4 * 3).reshape(2, 3, 4, 3)
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", source))
        context = _sdk.InProcessCtxProvider().build(_plan(pack.NODE_CLASS_MAPPINGS["ViewImagePropertiesSG"], {"image": image}, "direct"))
        context.assets, context.output, context.ui = assets, output, ui
        with _sdk.bind_runtime(refs, context, _sdk.InProcessOps()):
            loaded = await pack.NODE_CLASS_MAPPINGS["LoadImageandviewPropertiesSG"].execute("sample.png")
            loaded_image = await refs.resolve(loaded.result[0])
            loaded_mask = await refs.resolve(loaded.result[1])
            assert tuple(loaded_image.shape) == (1, 2, 4, 3)
            assert tuple(loaded_mask.shape) == (2, 4)
            assert torch.allclose(loaded_mask, torch.full((2, 4), 127 / 255), atol=1 / 255)
            assert loaded.result[2:] == (4, 2, 2.0, 1.0, 0.000008)
            assert loaded.ui["text"][-3:] == [
                "Model: demo.safetensors", "Seed: 123 | Steps: 20 | CFG: 7.5",
                "Sampler: euler | Scheduler: normal",
            ]
            assert await pack.NODE_CLASS_MAPPINGS["LoadImageandviewPropertiesSG"].validate_inputs("sample.png") is True
            assert await pack.NODE_CLASS_MAPPINGS["LoadImageandviewPropertiesSG"].fingerprint_inputs("sample.png") == hashlib.sha256(data).hexdigest()
            assert "Invalid image file" in await pack.NODE_CLASS_MAPPINGS["LoadImageandviewPropertiesSG"].validate_inputs("missing.png")

            preview = await pack.NODE_CLASS_MAPPINGS["PreviewImageandviewPropertiesSG"].execute(image)
            assert preview.result[0] is image
            assert preview.ui["images"][0]["filename"] == "preview.png"

            prompt = {"1": {"class_type": "KSampler", "inputs": {
                "seed": 77, "steps": 25, "cfg": 5.5, "sampler_name": "euler", "scheduler": "normal",
            }}}
            save = pack.NODE_CLASS_MAPPINGS["SaveImageFormatQualityPropertiesSG"]
            await save.execute(
                image, filename_prefix="review/%date:yyyyMMdd%", Properties="Both",
                format="JPEG (lossy, smaller files)", jpeg_quality=88,
                jpeg_optimize=False, jpeg_subsampling="4:2:2 (Moderate subsampling)", prompt=prompt,
            )
            options = output.calls[-1][1]
            assert options["image_format"] == "jpeg"
            assert options["quality"] == 88
            assert options["jpeg_subsampling"] == "4:2:2"
            assert options["optimize"] is False
            assert options["save_metadata"] is False
            assert options["filename_prefix"].startswith("review/20")
            png = await save.execute(image, Properties="Metadata", prompt=prompt)
            assert png.ui["text"] == [
                "Model: N/A", "Seed: 77 | Steps: 25 | CFG: 5.5",
                "Sampler: euler | Scheduler: normal",
            ]
            assert output.calls[-1][1]["extra_metadata"]["parameters"]["seed"] == 77
            before = len(ui.calls)
            await save.execute(image, format="TIFF (flexible, lossless, limited support)", tiff_compression="lzw (lossless, good compression)")
            assert output.calls[-1][1]["tiff_compression"] == "lzw"
            assert len(ui.calls) == before + 1
            assert output.calls[-1][1]["quality"] == 90
            with pytest.raises(ValueError, match="unsupported image format"):
                await save.execute(image, format="GIF")
    asyncio.run(run())


def test_real_isolated_guest_executes_all_four_nodes(monkeypatch, tmp_path):
    import server

    monkeypatch.setattr(server.PromptServer, "instance", types.SimpleNamespace(client_id="image-properties-test"), raising=False)
    pack = _import_v2()

    async def run():
        refs = _sdk.InProcessRefResolver()
        source = torch.arange(1 * 2 * 4 * 3, dtype=torch.float32).reshape(1, 2, 4, 3) / 24
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", source))
        sample = tmp_path / "sample.png"
        sample.write_bytes(_png_bytes())
        assets = _Assets(refs, {"sample.png": sample})
        output, ui = _Output(), _UI()
        session = await GuestSession("image-properties-sg-conversion").start()
        try:
            executions = (
                ("ViewImagePropertiesSG", {"image": image}),
                ("LoadImageandviewPropertiesSG", {"image": "sample.png"}),
                ("PreviewImageandviewPropertiesSG", {"images": image}),
                ("SaveImageFormatQualityPropertiesSG", {
                    "images": image, "filename_prefix": "guest", "Properties": "Basic",
                    "format": "WEBP (modern, good compression)", "webp_quality": 81,
                    "webp_method": 5, "webp_lossless": False,
                }),
            )
            results = []
            for number, (node_id, inputs) in enumerate(executions, 1):
                node = pack.NODE_CLASS_MAPPINGS[node_id]
                plan = _plan(node, inputs, number)
                results.append(await session.execute(
                    plan, _runtime(plan, refs, assets, output, ui), capabilities=plan.permissions,
                ))
            assert session.last_guest_pid not in (None, os.getpid())
            assert results[0].result[1:4] == (1, 4, 2)
            assert torch.equal(await refs.resolve(results[1].result[0]), torch.tensor([[[[64, 128, 192]] * 4] * 2], dtype=torch.float32) / 255)
            assert results[2].ui["images"][0]["filename"] == "preview.png"
            assert results[3].ui["images"][0]["filename"] == "saved.webp"
            assert output.calls[-1][1]["webp_method"] == 5
            with pytest.raises(Exception):
                plan = _plan(pack.NODE_CLASS_MAPPINGS["SaveImageFormatQualityPropertiesSG"], executions[-1][1], "denied")
                await session.execute(plan, _runtime(plan, refs, assets, output, ui), capabilities=("raw",))
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_is_node_scoped_safe_and_tears_down_cleanly():
    paths = sorted((V2 / "web").glob("*.js"))
    sources = [path.read_text() for path in paths]
    combined = "\n".join(sources)
    assert combined.count("comfy.defs.extend(") == 1
    assert sum(path.read_text().count("extendPropertiesNode(") for path in paths if path.name != "common.js") == 4
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage", "MutationObserver",
        "app.registerExtension", "addDOMWidget", "app.graph", "setInterval(", "globalThis.fetch",
    ):
        assert forbidden not in combined
    for required in (
        "node.widgets.mount", "builder.onExecuted", "builder.onConfigured",
        "builder.onRemoved", "textContent", "comfy.backend.assetUrl", "setHidden",
    ):
        assert required in combined
    completed = subprocess.run(
        ["node", "--experimental-vm-modules", str(V2 / "tests" / "image_properties_frontend_harness.mjs"), str(V2 / "web")],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: Image Properties SG" in completed.stdout


def test_python_surface_has_only_declared_brokered_authority():
    source = "\n".join(path.read_text(errors="replace") for path in sorted(V2.glob("*.py")))
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests", "socket",
        "builtins.open(", "pathlib.Path(", "os.", "shutil", "tempfile", "urllib",
    ):
        assert forbidden not in source
    for required in (
        "sdk.ctx().assets", "sdk.ctx().output.save_images", "sdk.ctx().ui.preview_images",
        "sdk.ImageRef", "sdk.MaskRef",
    ):
        assert required in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = REPO / "pack-db" / "patches" / "comfyui-image-properties-sg" / "xfda1775" / "comfyui-image-properties-sg-xfda1775"
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-image-properties-sg" / "xfda1775"
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
