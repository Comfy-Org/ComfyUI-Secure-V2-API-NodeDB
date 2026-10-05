from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sys

import pytest
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
COMMIT = "a5c09c8a893032dc4a3a3d5ff32fbd195883fbda"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
NODE_ID = "AD_image-concat-advanced"
PAIR = REPO / "pack-db" / "patches" / "ad-image-concatenation-advanced" / "xa5c09c8" / (
    "ad-image-concatenation-advanced-xa5c09c8"
)

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import(root: pathlib.Path, name: str):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
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
    return _import(V2, "_secure_image_concat_test")


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import(root, "_pristine_image_concat_test")


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


def _generated_manifest(pack) -> dict:
    prefix = pack.__name__ + "."
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": node_class.__module__.removeprefix(prefix),
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status"
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps()
    )


def test_census_schema_manifest_and_contract(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert set(secure.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()

    node = secure.NODE_CLASS_MAPPINGS[NODE_ID]
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == NODE_ID
    assert schema.display_name == "AD Image Concatenation Advanced"
    assert schema.category == "🌻 Addoor/image"
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("image1", "IMAGE", False),
        ("direction", "COMBO", False),
        ("match_size", "BOOLEAN", False),
        ("method", "COMBO", False),
        ("output_all_concatenations", "BOOLEAN", False),
        ("image2", "IMAGE", True),
        ("image3", "IMAGE", True),
        ("image4", "IMAGE", True),
        ("image5", "IMAGE", True),
    ]
    assert schema.inputs[1].options == ["horizontal", "vertical"]
    assert schema.inputs[3].options == ["lanczos", "bicubic", "bilinear", "nearest"]
    assert schema.outputs[0].io_type == "IMAGE"
    assert schema.outputs[0].is_output_list is True
    assert node.SDK_REFS is True and node.SDK_PERMISSIONS == ("raw",)
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.image_concat_secure")
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


@pytest.mark.parametrize("direction", ("horizontal", "vertical"))
@pytest.mark.parametrize("match_size", (False, True))
@pytest.mark.parametrize("method", ("lanczos", "bicubic", "bilinear", "nearest"))
def test_pixels_match_upstream(direction, match_size, method, tmp_path):
    upstream = _pristine(tmp_path).NODE_CLASS_MAPPINGS[NODE_ID]()
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS[NODE_ID].__module__]
    images = [
        torch.linspace(0, 1, 1 * 5 * 7 * 3).reshape(1, 5, 7, 3),
        torch.linspace(1, 0, 1 * 8 * 4 * 3).reshape(1, 8, 4, 3),
        torch.full((1, 3, 6, 3), 0.4),
    ]
    expected = upstream._concatenate_multiple(images, direction, match_size, method)
    actual = module._concatenate(images, direction, match_size, method)
    assert torch.equal(actual, expected)


def test_alpha_centering_and_cumulative_outputs_match_upstream(tmp_path):
    upstream = _pristine(tmp_path).NODE_CLASS_MAPPINGS[NODE_ID]()
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS[NODE_ID].__module__]
    images = [
        torch.linspace(0, 1, 1 * 4 * 7 * 4).reshape(1, 4, 7, 4),
        torch.linspace(1, 0, 1 * 8 * 3 * 4).reshape(1, 8, 3, 4),
        torch.full((1, 5, 5, 4), 0.25),
    ]
    for count in range(1, 4):
        expected = upstream._concatenate_multiple(
            images[:count], "horizontal", False, "nearest"
        )
        actual = module._concatenate(
            images[:count], "horizontal", False, "nearest"
        )
        assert torch.equal(actual, expected)


def test_real_guest_outputs_are_ordered_and_raw_is_required():
    node = _secure().NODE_CLASS_MAPPINGS[NODE_ID]

    async def run():
        refs = _sdk.InProcessRefResolver()
        images = [
            torch.full((2, 4, 3, 3), 0.1),
            torch.full((1, 6, 5, 3), 0.7),
            torch.full((1, 2, 4, 3), 0.4),
        ]
        image_refs = [
            _sdk.ImageRef._wrap(await refs.create("IMAGE", value)) for value in images
        ]
        inputs = {
            "image1": image_refs[0], "image2": image_refs[1], "image3": image_refs[2],
            "direction": "vertical", "match_size": True,
            "method": "bilinear", "output_all_concatenations": True,
        }
        plan = _sdk.ExecutionPlan(
            prompt_id="image-concat", node_id="1", node_type=node.__name__,
            tier="sandbox", node_module=node.__module__, inputs=inputs,
            permissions=("raw",), method="execute",
        )
        session = await GuestSession("image-concat-conversion", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, _runtime(plan, refs), capabilities=("raw",))
            output_refs = result.result[0]
            assert len(output_refs) == 3
            assert output_refs[0].id == image_refs[0].id
            values = [await refs.resolve(item) for item in output_refs]
            assert values[0] is images[0]
            assert tuple(values[1].shape) == (1, 12, 5, 3)
            assert tuple(values[2].shape) == (1, 11, 4, 3)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, _runtime(plan, refs), capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_failure_falls_back_to_original_first_ref():
    node = _secure().NODE_CLASS_MAPPINGS[NODE_ID]

    async def run():
        refs = _sdk.InProcessRefResolver()
        value = torch.zeros((1, 2, 2, 3))
        ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", value))
        plan = _sdk.ExecutionPlan(
            prompt_id="fallback", node_id="1", node_type=node.__name__, tier="sandbox",
            node_module=node.__module__, inputs={}, permissions=("raw",), method="execute",
        )
        with _sdk.bind_runtime(refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()):
            result = await node.execute(ref, direction="diagonal")
        assert result[0][0].id == ref.id

    asyncio.run(run())


def test_source_has_only_declared_raw_authority():
    source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "folder_paths", "PromptServer", "open(", "eval(",
        "exec(", "sdk.ctx(",
    ):
        assert forbidden not in source
    assert 'SDK_PERMISSIONS = ("raw",)' in source
    assert "await item.raw()" in source


def test_patch_roundtrip_and_cache_cleanliness(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "ad-image-concatenation-advanced" / "xa5c09c8"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
