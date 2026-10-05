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

import numpy as np
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
COMMIT = "f83a94b5d696e53f20a3a9d853f8e594981e438b"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
NODE_ID = "ImageAutotone"
PAIR = REPO / "pack-db" / "patches" / "comfyui-imageautotone" / "xf83a94b" / (
    "comfyui-imageautotone-xf83a94b"
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


def _import_package(root: pathlib.Path, name: str):
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
    return _import_package(V2, "_secure_imageautotone_test")


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package(root, "_pristine_imageautotone_test")


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
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
    }


def _plan(node_class, inputs, suffix="case"):
    return _sdk.ExecutionPlan(
        prompt_id=f"imageautotone-{suffix}",
        node_id="1",
        node_type=node_class.__name__,
        tier="sandbox",
        node_module=node_class.__module__,
        inputs=inputs,
        permissions=node_class.SDK_PERMISSIONS,
        method="execute",
    )


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "Image Autotone"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "Image Autotone"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not hasattr(secure, "WEB_DIRECTORY")
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()

    node = secure.NODE_CLASS_MAPPINGS[NODE_ID]
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == NODE_ID
    assert schema.display_name == "Image Autotone"
    assert schema.category == "image"
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("image", "IMAGE"),
        ("shadows", "STRING"),
        ("highlights", "STRING"),
        ("shadow_clip", "FLOAT"),
        ("highlight_clip", "FLOAT"),
    ]
    assert [item.default for item in schema.inputs[1:]] == [
        "0,0,0", "255,255,255", 0.001, 0.001
    ]
    for item in schema.inputs[3:]:
        assert (item.min, item.max, item.step) == (0.0, 1.0, 0.001)
    assert [(item.io_type, item.is_output_list) for item in schema.outputs] == [
        ("IMAGE", False)
    ]
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ("raw",)

    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(secure)
    )
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.imageautotone_secure_test"
    )
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


@pytest.mark.parametrize(
    "image,shadows,highlights,shadow_clip,highlight_clip",
    [
        (
            torch.linspace(0, 1, 1 * 8 * 7 * 3).reshape(1, 8, 7, 3),
            "0,0,0", "255,255,255", 0.001, 0.001,
        ),
        (
            torch.linspace(1, 0, 2 * 5 * 9 * 4).reshape(2, 5, 9, 4),
            "16,32,48", "240,224,208", 0.05, 0.1,
        ),
        (
            torch.full((1, 4, 6, 3), 0.25),
            "10,20,30", "220,230,240", 0.0, 0.0,
        ),
    ],
)
def test_valid_pixels_match_pinned_upstream_exactly(
    tmp_path, image, shadows, highlights, shadow_clip, highlight_clip
):
    upstream = _pristine(tmp_path).NODE_CLASS_MAPPINGS[NODE_ID]()
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS[NODE_ID].__module__]
    expected = upstream.op(
        image.clone(), highlights, shadows, shadow_clip, highlight_clip
    )[0]
    actual = module._autotone(
        image.clone(), highlights, shadows, shadow_clip, highlight_clip
    )
    assert torch.equal(actual, expected)


def test_validation_is_bounded_and_fails_closed():
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS[NODE_ID].__module__]
    assert module._parse_rgb("#00aAFF", "test").tolist() == [0, 170, 255]
    assert module._parse_rgb("1,2,3", "test").tolist() == [1, 2, 3]
    for value in ("", "#fff", "1,2", "1,2,999", "../x"):
        with pytest.raises((TypeError, ValueError)):
            module._parse_rgb(value, "test")
    with pytest.raises(ValueError, match="BHWC"):
        module._validate_image(torch.zeros((1, 3, 8, 8)))
    with pytest.raises(ValueError, match="dimension|element"):
        module._validate_image(torch.empty((1, 8193, 1, 3), device="meta"))
    with pytest.raises(ValueError, match="clip"):
        module._autotone(torch.zeros((1, 2, 2, 3)), "255,255,255", "0,0,0", -0.1, 0)


def test_documented_hex_colors_work_instead_of_upstream_scalar_bytes_crash():
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS[NODE_ID].__module__]
    image = torch.linspace(0, 1, 4 * 5 * 3).reshape(1, 4, 5, 3)
    from_hex = module._autotone(image, "#f0e0d0", "#102030", 0.01, 0.02)
    from_rgb = module._autotone(
        image, "240,224,208", "16,32,48", 0.01, 0.02
    )
    assert torch.equal(from_hex, from_rgb)


def test_real_guest_matches_pixels_and_requires_raw_capability():
    node = _secure().NODE_CLASS_MAPPINGS[NODE_ID]

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = torch.linspace(0, 1, 2 * 6 * 5 * 4).reshape(2, 6, 5, 4)
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        inputs = {
            "image": image_ref,
            "shadows": "#102030",
            "highlights": "240,230,220",
            "shadow_clip": 0.02,
            "highlight_clip": 0.04,
        }
        plan = _plan(node, inputs)
        session = await GuestSession("imageautotone-conversion", guest_runtime_root=V2).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=("raw",)
            )
            actual = await refs.resolve(result.result[0])
            module = sys.modules[node.__module__]
            expected = module._autotone(
                image, "240,230,220", "#102030", 0.02, 0.04
            )
            assert torch.equal(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, _runtime(plan, refs), capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_source_has_only_declared_raw_compute_authority():
    source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "folder_paths", "PromptServer", "open(", "eval(",
        "exec(", "sdk.ctx(",
    ):
        assert forbidden not in source
    assert 'SDK_PERMISSIONS = ("raw",)' in source
    assert "await image.raw()" in source
    assert "sdk.ImageRef._from_raw(output)" in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-imageautotone" / "xf83a94b"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)


def test_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
