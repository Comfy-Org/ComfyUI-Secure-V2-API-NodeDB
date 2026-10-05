from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import math
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
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "d5867b6fedf58dbe4559904097b5e2eef3cacfb1"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
NODE_IDS = {"SD3LatentSelectRes", "SD3LatentSelectResV2"}
PAIR = REPO / "pack-db" / "patches" / "comfyui-sd3latentselectres" / "xd5867b6" / (
    "comfyui-sd3latentselectres-xd5867b6"
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

if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))


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
    return _import(V2, "_secure_sd3_res_test")


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import(root, "_pristine_sd3_res_test")


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


def test_actual_census_schemas_manifest_and_contract(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()

    first = secure.NODE_CLASS_MAPPINGS["SD3LatentSelectRes"].GET_SCHEMA()
    second = secure.NODE_CLASS_MAPPINGS["SD3LatentSelectResV2"].GET_SCHEMA()
    first.validate()
    second.validate()
    assert first.is_output_node is second.is_output_node is True
    assert [(item.id, item.io_type) for item in first.inputs] == [
        ("size_selected", "COMBO"), ("landscape", "BOOLEAN"),
        ("batch_size", "INT"),
    ]
    assert [(item.id, item.io_type) for item in second.inputs] == [
        ("aspect_ratio", "COMBO"), ("megapixels", "COMBO"),
        ("latent_type", "COMBO"), ("batch_size", "INT"),
    ]
    assert [(item.id, item.io_type) for item in first.outputs] == [
        ("width", "INT"), ("height", "INT"), ("samples", "LATENT")
    ]
    assert second.inputs[2].default == "SD3/Flux/Z-Image/Qwen/etc"
    assert all(
        node.SDK_REFS is True and node.SDK_PERMISSIONS == ("raw",)
        for node in secure.NODE_CLASS_MAPPINGS.values()
    )
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.sd3_res_secure")
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


def test_all_preset_data_matches_pinned_json_exactly():
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS["SD3LatentSelectRes"].__module__]
    raw = json.loads((PACK / "sizes.json").read_text())["sizes"]
    assert module.SIZE_OPTIONS == list(raw)
    assert module.SIZES == {
        name: (int(item["width"]), int(item["height"]))
        for name, item in raw.items()
    }


@pytest.mark.parametrize("landscape", (False, True))
@pytest.mark.parametrize("index", (0, 5, 10, 18, 27, 34, 42))
def test_preset_dimensions_and_latents_match_upstream(tmp_path, landscape, index):
    pristine_class = _pristine(tmp_path).NODE_CLASS_MAPPINGS["SD3LatentSelectRes"]
    pristine_class.INPUT_TYPES()
    pristine = pristine_class()
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS["SD3LatentSelectRes"].__module__]
    option = module.SIZE_OPTIONS[index]
    expected_width, expected_height, expected = pristine.return_res(option, landscape, 1)
    width, height = module.SIZES[option]
    if not landscape:
        width, height = height, width
    actual = module._latent(width, height, 1, 16, 8)
    assert (width, height) == (expected_width, expected_height)
    assert torch.equal(actual, expected["samples"])


@pytest.mark.parametrize(
    "ratio,megapixels,latent_type",
    [
        ("1:1", 1.0, "SD3/Flux/Z-Image/Qwen/etc"),
        ("16:9", 2.5, "SD3/Flux/Z-Image/Qwen/etc"),
        ("9:16", 4.0, "Flux2"),
        ("21:9", 8.0, "Flux2"),
        ("1:2", 1.5, "SD3/Flux/Z-Image/Qwen/etc"),
    ],
)
def test_calculated_dimensions_and_layout_match_upstream(
    tmp_path, ratio, megapixels, latent_type
):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["SD3LatentSelectResV2"]()
    expected_width, expected_height, expected = pristine.return_res(
        ratio, megapixels, latent_type, 1
    )
    width_ratio, height_ratio = map(int, ratio.split(":"))
    ratio_value = width_ratio / height_ratio
    height = (float(megapixels) * 1_048_576 / ratio_value) ** 0.5
    width = round(height * ratio_value / 16) * 16
    height = round(height / 16) * 16
    channels, divisor = (128, 16) if latent_type == "Flux2" else (16, 8)
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS["SD3LatentSelectResV2"].__module__]
    actual = module._latent(width, height, 1, channels, divisor)
    assert (width, height) == (expected_width, expected_height)
    assert torch.equal(actual, expected["samples"])


def test_allocation_limit_rejects_before_tensor_creation(monkeypatch):
    secure = _secure()
    module = sys.modules[secure.NODE_CLASS_MAPPINGS["SD3LatentSelectRes"].__module__]
    monkeypatch.setattr(module.torch, "ones", lambda *_args, **_kwargs: pytest.fail("allocated"))
    with pytest.raises(ValueError, match="allocation"):
        module._latent(3072, 1312, 4096, 16, 8)


def test_both_nodes_execute_in_real_guest_and_raw_is_required():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("sd3-res-conversion", guest_runtime_root=V2).start()
        try:
            cases = [
                (
                    secure.NODE_CLASS_MAPPINGS["SD3LatentSelectRes"],
                    {"size_selected": "0.3MP - 4:3 [640x480]", "landscape": False, "batch_size": 2},
                    (480, 640, (2, 16, 80, 60)),
                ),
                (
                    secure.NODE_CLASS_MAPPINGS["SD3LatentSelectResV2"],
                    {"aspect_ratio": "16:9", "megapixels": 1.0, "latent_type": "Flux2", "batch_size": 2},
                    (1360, 768, (2, 128, 48, 85)),
                ),
            ]
            for index, (node, inputs, expected) in enumerate(cases):
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"sd3-{index}", node_id=str(index), node_type=node.__name__,
                    tier="sandbox", node_module=node.__module__, inputs=inputs,
                    permissions=("raw",), method="execute",
                )
                result = await session.execute(plan, _runtime(plan, refs), capabilities=("raw",))
                width, height, latent_ref = result.result
                value = await refs.resolve(latent_ref)
                assert (width, height, tuple(value["samples"].shape)) == expected
                assert torch.all(value["samples"] == torch.tensor(0.0609))
                with pytest.raises(Exception, match="raw"):
                    await session.execute(plan, _runtime(plan, refs), capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_source_has_only_declared_raw_authority():
    source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "folder_paths", "PromptServer", "open(", "eval(",
        "exec(", "sdk.ctx(",
    ):
        assert forbidden not in source
    assert source.count('SDK_PERMISSIONS = ("raw",)') == 2
    assert "sdk.LatentRef.from_value" in source


def test_patch_roundtrip_and_cache_cleanliness(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-sd3latentselectres" / "xd5867b6"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
