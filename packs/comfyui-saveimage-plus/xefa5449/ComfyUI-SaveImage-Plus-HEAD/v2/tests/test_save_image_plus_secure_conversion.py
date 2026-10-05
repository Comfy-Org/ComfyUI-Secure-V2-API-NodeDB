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

from PIL import Image
import pytest
import torch


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "efa54493216e47126e022a6a38cdaf0c0480256d"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/comfyui-saveimage-plus/xefa5449/comfyui-saveimage-plus-xefa5449"

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
    return _import_package("_secure_save_image_plus_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_save_image_plus_test", root)


def _plan(node, inputs, *, prompt=None, extra_pnginfo=None):
    return _sdk.ExecutionPlan(
        prompt_id="save-image-plus", node_id="1", node_type=node.__name__,
        tier="sandbox", node_module=node.__module__, inputs=inputs,
        permissions=("output",), prompt=prompt, extra_pnginfo=extra_pnginfo,
        method="execute",
    )


def _manifest(pack) -> dict:
    node = pack.NODE_CLASS_MAPPINGS["SaveImagePlus"]
    return {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": {
            "SaveImagePlus": {
                "class": node.__name__,
                "methods": {
                    name: name in node.__dict__
                    for name in ("check_lazy_status", "fingerprint_inputs", "validate_inputs")
                },
                "module": "nodes",
                "permissions": ["output"],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": True,
            },
        },
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


class _Output:
    def __init__(self):
        self.calls = []

    async def save_images(self, images, **options):
        self.calls.append((images, copy.deepcopy(options)))
        suffix = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[options["image_format"]]
        return {"images": [{"filename": "saved" + suffix, "subfolder": "", "type": "output"}]}


def test_actual_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"SaveImagePlus"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"SaveImagePlus"}
    assert pristine.WEB_DIRECTORY == "web"
    assert secure.WEB_DIRECTORY == "web"
    assert sum(path.read_text().count("app.registerExtension(") for path in (PACK / "web").glob("*.js")) == 1

    old = pristine.NODE_CLASS_MAPPINGS["SaveImagePlus"]
    new = secure.NODE_CLASS_MAPPINGS["SaveImagePlus"]
    schema = new.GET_SCHEMA()
    old_inputs = old.INPUT_TYPES()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "SaveImagePlus", "Save Image Plus", old.CATEGORY,
    )
    assert [item.id for item in schema.inputs] == list(old_inputs["required"])
    assert [item.io_type for item in schema.inputs] == ["IMAGE", "STRING", "COMBO", "BOOLEAN"]
    assert list(schema.inputs[2].options) == old_inputs["required"]["file_type"][0]
    assert schema.inputs[1].default == "ComfyUI"
    assert schema.inputs[3].default is False
    assert [item.value for item in schema.hidden] == ["PROMPT", "EXTRA_PNGINFO"]
    assert schema.outputs == []
    assert schema.is_output_node is True
    assert new.SDK_REFS is True
    assert new.SDK_PERMISSIONS == ("output",)

    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.save_image_plus_secure_test")
    assert set(loaded.node_mappings) == {"SaveImagePlus"}
    assert loaded.web_directory == V2 / "web"
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize(
    "file_type,expected",
    [
        ("PNG", {"image_format": "png", "lossless": False}),
        ("JPEG", {"image_format": "jpeg", "lossless": False}),
        ("WEBP (lossless)", {"image_format": "webp", "lossless": True}),
        ("WEBP (lossy)", {"image_format": "webp", "lossless": False}),
    ],
)
def test_output_broker_mapping_and_validation_are_exact(file_type, expected):
    pack = _secure()
    refs = _sdk.InProcessRefResolver()
    output = _Output()

    async def run():
        tensor = torch.linspace(0, 1, 2 * 3 * 4 * 3).reshape(2, 3, 4, 3)
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", tensor))
        plan = _plan(pack.SaveImagePlus, {})
        context = _sdk.InProcessCtxProvider().build(plan)
        context.output = output
        with _sdk.bind_runtime(refs, context, _sdk.InProcessOps()):
            result = await pack.SaveImagePlus.execute(
                image, "folder/name", file_type, True,
            )
        assert result.result is None
        assert result.ui == {"images": [{"filename": "saved" + {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[expected["image_format"]], "subfolder": "", "type": "output"}]}
        passed_image, options = output.calls[-1]
        assert passed_image is image
        assert options == {
            "filename_prefix": "folder/name", "compress_level": 4,
            "save_metadata": False, "image_format": expected["image_format"],
            "quality": 90, "lossless": expected["lossless"],
            "jpeg_subsampling": "auto",
        }

    asyncio.run(run())
    with pytest.raises(ValueError, match="unsupported file type"):
        asyncio.run(pack.SaveImagePlus.execute(None, file_type="TIFF"))
    with pytest.raises(TypeError, match="filename_prefix"):
        asyncio.run(pack.SaveImagePlus.execute(None, filename_prefix=1))
    with pytest.raises(TypeError, match="remove_metadata"):
        asyncio.run(pack.SaveImagePlus.execute(None, remove_metadata=1))


def test_real_output_encoder_preserves_formats_and_canonical_metadata(monkeypatch, tmp_path):
    import folder_paths

    pack = _secure()
    monkeypatch.setattr(folder_paths, "get_output_directory", lambda: str(tmp_path))

    async def run():
        refs = _sdk.InProcessRefResolver()
        tensor = torch.tensor([[[[0.0, 0.5, 1.0], [1.0, 0.5, 0.0]]]], dtype=torch.float32)
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", tensor))
        prompt = {"1": {"class_type": "KSampler"}}
        extra = {"workflow": {"nodes": [{"id": 1}]}}
        cases = [("PNG", "PNG"), ("JPEG", "JPEG"), ("WEBP (lossless)", "WEBP")]
        paths = []
        for index, (file_type, pil_format) in enumerate(cases):
            plan = _plan(pack.SaveImagePlus, {}, prompt=prompt, extra_pnginfo=extra)
            runtime = _sdk.Runtime(
                refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
                ops=_sdk.InProcessOps(),
            )
            with _sdk.bind_runtime(runtime.refs, runtime.ctx, runtime.ops):
                result = await pack.SaveImagePlus.execute(image, f"case-{index}", file_type, False)
            item = result.ui["images"][0]
            path = tmp_path / item["subfolder"] / item["filename"]
            paths.append(path)
            with Image.open(path) as saved:
                assert saved.format == pil_format
                if pil_format == "PNG":
                    assert json.loads(saved.text["prompt"]) == prompt
                    assert json.loads(saved.text["workflow"]) == extra["workflow"]
                else:
                    values = list(saved.getexif().values())
                    assert f"prompt:{json.dumps(prompt)}" in values
                    assert f"workflow:{json.dumps(extra['workflow'])}" in values
        return paths

    paths = asyncio.run(run())
    assert all(path.is_file() for path in paths)


def test_real_guest_executes_and_output_capability_is_required():
    pack = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", torch.zeros((1, 2, 3, 3))))
        output = _Output()
        inputs = {
            "images": image, "filename_prefix": "guest", "file_type": "WEBP (lossy)",
            "remove_metadata": False,
        }
        plan = _plan(pack.SaveImagePlus, inputs)
        context = _sdk.InProcessCtxProvider().build(plan)
        context.output = output
        runtime = _sdk.Runtime(refs=refs, ctx=context, ops=_sdk.InProcessOps())
        session = await GuestSession("save-image-plus", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, runtime, capabilities=("output",))
            assert result.ui["images"][0]["filename"] == "saved.webp"
            assert output.calls[-1][1]["quality"] == 90
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="output"):
                await session.execute(plan, runtime, capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_typecheck():
    source = (V2 / "web/main.js").read_text()
    for forbidden in (
        "/scripts/app.js", "app.registerExtension", "app.handleFile",
        "loadGraphData", "loadApiJson", "document.", "window.", "FileReader",
        "fetch(", "innerHTML", "localStorage", "indexedDB",
    ):
        assert forbidden not in source
    commands = [
        ["node", "--experimental-vm-modules", str(V2 / "tests/save_image_plus_frontend_harness.mjs"), str(V2 / "web/main.js")],
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
    for relative in ("README.md", "LICENSE"):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import torch", "import comfy", "folder_paths", "PromptServer",
        "requests", "aiohttp", "subprocess", "open(", "_from_raw",
    ):
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-saveimage-plus/xefa5449"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
