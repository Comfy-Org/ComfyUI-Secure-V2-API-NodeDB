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
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = (
    pathlib.Path(
        os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes")
    )
    .expanduser()
    .resolve()
)
COMMIT = "ede1f33f5889f9f6d5bcb3cc54a5904869f31a41"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-in-context-lora-utils"
    / "xede1f33"
    / ("comfyui-in-context-lora-utils-xede1f33")
)

for root in (BACKEND, CORE):
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
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_in_context_lora_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_in_context_lora_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": (
                "InContextLoraUtils"
                if node_id == "AddMaskForICLora"
                else "InContextUtils"
            ),
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs",
                    "fingerprint_inputs",
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
            part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _image(height: int, width: int, *, flip: bool = False) -> torch.Tensor:
    value = torch.linspace(0.0, 1.0, height * width * 3, dtype=torch.float32).reshape(
        1, height, width, 3
    )
    return value.flip(2) if flip else value


def _mask(height: int, width: int, box: tuple[int, int, int, int]) -> torch.Tensor:
    top, left, bottom, right = box
    value = torch.zeros((1, height, width), dtype=torch.float32)
    value[:, top:bottom, left:right] = 1.0
    return value


def _assert_value(actual, expected):
    if torch.is_tensor(expected):
        assert torch.is_tensor(actual)
        assert tuple(actual.shape) == tuple(expected.shape)
        assert actual.dtype == expected.dtype
        assert torch.equal(actual, expected)
        assert torch.isfinite(actual).all()
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected)
    else:
        assert actual == expected


def _assert_result(actual, expected):
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected, strict=True):
        _assert_value(got, want)


def test_pinned_actual_loader_census_entrypoint_and_schemas_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    expected_ids = [
        "AddMaskForICLora",
        "CreateContextWindow",
        "ConcatContextWindow",
        "AutoPatch",
    ]
    assert list(pristine.NODE_CLASS_MAPPINGS) == expected_ids
    assert list(secure.NODE_CLASS_MAPPINGS) == expected_ids
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()

    for node_id in expected_ids:
        legacy = pristine.NODE_CLASS_MAPPINGS[node_id]
        converted = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = converted.GET_SCHEMA()
        schema.validate()
        inputs = legacy.INPUT_TYPES()
        ordered = list(inputs["required"]) + list(inputs.get("optional", {}))
        assert [item.id for item in schema.inputs] == ordered
        assert [item.io_type for item in schema.outputs] == list(legacy.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(
            getattr(legacy, "RETURN_NAMES", legacy.RETURN_TYPES)
        )
        assert schema.category == legacy.CATEGORY
        assert schema.is_output_node is bool(getattr(legacy, "OUTPUT_NODE", False))
        assert converted.SDK_REFS is False
        assert converted.SDK_PERMISSIONS == ("raw",)
        for item in schema.inputs:
            group = "optional" if item.id in inputs.get("optional", {}) else "required"
            legacy_type, *rest = inputs[group][item.id]
            assert item.io_type == (
                "COMBO" if isinstance(legacy_type, list) else legacy_type
            )
            assert item.optional is (group == "optional")
            options = rest[0] if rest else {}
            for key in ("default", "min", "max", "step"):
                if key in options:
                    assert getattr(item, key) == options[key]
            if isinstance(legacy_type, list):
                assert item.options == legacy_type

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [
        secure.AddMaskForICLora,
        secure.CreateContextWindow,
        secure.ConcatContextWindow,
        secure.AutoPatch,
    ]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.in_context_lora_census_test"
    )
    assert set(loaded.node_mappings) == set(expected_ids)
    assert len(loaded.node_mappings) == len(expected_ids)
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize(
    "image,mask",
    (
        (_image(160, 240), None),
        (_image(160, 240), _mask(160, 240, (30, 50, 120, 190))),
        (_image(240, 160), _mask(240, 160, (50, 30, 190, 130))),
        (_image(96, 192), torch.zeros((1, 96, 192))),
        (_image(120, 180), torch.ones((1, 64, 64))),
    ),
)
def test_auto_patch_orientation_and_ratio_selection_are_exact(tmp_path, image, mask):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["AutoPatch"]()
    secure = _secure()
    expected = pristine.auto_path(image.clone(), None if mask is None else mask.clone())
    actual = secure.AutoPatch.execute(
        image.clone(), None if mask is None else mask.clone()
    ).result
    _assert_result(actual, expected)


@pytest.mark.parametrize(
    "first,mode,color,first_mask,second,second_mask",
    (
        (_image(160, 240), "auto", "#FF0000", None, None, None),
        (
            _image(240, 160),
            "patch_right",
            "#00FF00",
            _mask(240, 160, (40, 20, 200, 140)),
            _image(240, 160, flip=True),
            _mask(240, 160, (20, 40, 220, 120)),
        ),
        (
            _image(180, 220),
            "patch_bottom",
            "#0000FF",
            torch.zeros((1, 180, 220)),
            _image(220, 180, flip=True),
            None,
        ),
    ),
)
def test_add_mask_resize_padding_color_and_offsets_are_exact(
    tmp_path, first, mode, color, first_mask, second, second_mask
):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["AddMaskForICLora"]()
    secure = _secure()
    args = {
        "first_image": first.clone(),
        "patch_mode": mode,
        "output_length": 193,
        "patch_color": color,
        "first_mask": None if first_mask is None else first_mask.clone(),
        "second_image": None if second is None else second.clone(),
        "second_mask": None if second_mask is None else second_mask.clone(),
    }
    expected = pristine.add_mask(**copy.deepcopy(args))
    actual = secure.AddMaskForICLora.execute(**copy.deepcopy(args)).result
    _assert_result(actual, expected)


def test_legacy_first_batch_selection_is_preserved(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    image = torch.cat((_image(160, 240), _image(160, 240, flip=True)), dim=0)
    mask = torch.cat(
        (
            _mask(160, 240, (30, 50, 120, 190)),
            _mask(160, 240, (5, 5, 25, 25)),
        ),
        dim=0,
    )
    expected_auto = pristine.NODE_CLASS_MAPPINGS["AutoPatch"]().auto_path(image, mask)
    actual_auto = secure.AutoPatch.execute(image, mask).result
    _assert_result(actual_auto, expected_auto)

    expected_add = pristine.NODE_CLASS_MAPPINGS["AddMaskForICLora"]().add_mask(
        image, "auto", 192, "#FFFFFF", first_mask=mask
    )
    actual_add = secure.AddMaskForICLora.execute(
        image, "auto", 192, "#FFFFFF", first_mask=mask
    ).result
    _assert_result(actual_add, expected_add)


@pytest.mark.parametrize(
    "mode,patch_type,color,second_mask",
    (
        ("patch_right", "1:1", "#FFFFFF", None),
        ("patch_bottom", "3:4", "#0000FF", None),
        ("auto", "9:16", "#00FF00", torch.ones((1, 96, 170))),
    ),
)
def test_concat_context_window_order_masks_and_metadata_are_exact(
    tmp_path, mode, patch_type, color, second_mask
):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ConcatContextWindow"]()
    secure = _secure()
    output_length = 192
    ratio = {"1:1": (96, 96), "3:4": (128, 96), "9:16": (170, 96)}[patch_type]
    target_width, target_height = ratio
    first = _image(target_height, target_width)
    second = _image(target_height, target_width, flip=True)
    mask = second_mask
    if mask is not None and tuple(mask.shape[1:]) != (target_height, target_width):
        mask = torch.ones((1, target_height, target_width))
    args = {
        "first_image": first,
        "patch_mode": mode,
        "patch_type": patch_type,
        "output_length": output_length,
        "patch_color": color,
        "second_image": second,
        "second_mask": mask,
    }
    expected = pristine.concat_context_window(**copy.deepcopy(args))
    actual = secure.ConcatContextWindow.execute(**copy.deepcopy(args)).result
    _assert_result(actual, expected)


@pytest.mark.parametrize(
    "image,mask,mode,patch_type,pixel_buffer",
    (
        (
            _image(160, 240),
            _mask(160, 240, (30, 50, 120, 190)),
            "auto",
            "3:4",
            24,
        ),
        (
            _image(240, 160),
            _mask(240, 160, (50, 30, 190, 130)),
            "patch_right",
            "1:1",
            0,
        ),
        (
            _image(192, 256),
            _mask(192, 256, (0, 0, 90, 120)),
            "patch_bottom",
            "9:16",
            48,
        ),
        (
            _image(192, 128),
            torch.zeros((1, 192, 128)),
            "auto",
            "3:4",
            16,
        ),
    ),
)
def test_create_context_crop_scale_mask_and_metadata_are_exact(
    tmp_path, image, mask, mode, patch_type, pixel_buffer
):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["CreateContextWindow"]()
    secure = _secure()
    args = {
        "input_image": image.clone(),
        "input_mask": mask.clone(),
        "patch_mode": mode,
        "patch_type": patch_type,
        "output_length": 193,
        "pixel_buffer": pixel_buffer,
    }
    expected = pristine.create_context_window(**copy.deepcopy(args))
    actual = secure.CreateContextWindow.execute(**copy.deepcopy(args)).result
    _assert_result(actual, expected)


def test_secure_resource_bounds_and_malformed_inputs_fail_closed():
    secure = _secure()
    image = _image(64, 64)
    mask = torch.ones((1, 64, 64))
    for bad in (True, 63, 2049, 1.5):
        with pytest.raises((TypeError, ValueError)):
            secure.AddMaskForICLora.execute(image, "auto", bad, "#FF0000")
        with pytest.raises((TypeError, ValueError)):
            secure.ConcatContextWindow.execute(
                image, "patch_right", "1:1", bad, "#FF0000"
            )
        with pytest.raises((TypeError, ValueError)):
            secure.CreateContextWindow.execute(
                image, mask, "auto", "1:1", output_length=bad
            )
    for bad in (True, -1, 4097, 1.5):
        with pytest.raises((TypeError, ValueError)):
            secure.CreateContextWindow.execute(
                image, mask, "auto", "1:1", pixel_buffer=bad
            )
    malformed = torch.zeros((1, 32, 32))
    with pytest.raises((ValueError, IndexError)):
        secure.AddMaskForICLora.execute(malformed, "auto", 192, "#FF0000")


def test_real_isolated_guest_executes_all_nodes_and_denies_raw(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "in-context-lora-utils", guest_runtime_root=V2
        ).start()
        try:
            image = _image(160, 240)
            mask = _mask(160, 240, (30, 50, 120, 190))
            image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
            mask_ref = _sdk.MaskRef._wrap(await refs.create("MASK", mask))
            prepared = _image(96, 128)
            prepared_mask = torch.ones((1, 96, 128))
            prepared_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", prepared))
            prepared_mask_ref = _sdk.MaskRef._wrap(
                await refs.create("MASK", prepared_mask)
            )
            cases = (
                (
                    secure.AutoPatch,
                    {"image2": image_ref, "mask2": mask_ref},
                    pristine.NODE_CLASS_MAPPINGS["AutoPatch"]().auto_path(image, mask),
                ),
                (
                    secure.AddMaskForICLora,
                    {
                        "first_image": image_ref,
                        "patch_mode": "auto",
                        "output_length": 192,
                        "patch_color": "#FF0000",
                    },
                    pristine.NODE_CLASS_MAPPINGS["AddMaskForICLora"]().add_mask(
                        image, "auto", 192, "#FF0000"
                    ),
                ),
                (
                    secure.CreateContextWindow,
                    {
                        "input_image": image_ref,
                        "input_mask": mask_ref,
                        "patch_mode": "auto",
                        "patch_type": "3:4",
                        "output_length": 192,
                        "pixel_buffer": 24,
                    },
                    pristine.NODE_CLASS_MAPPINGS[
                        "CreateContextWindow"
                    ]().create_context_window(image, mask, "auto", "3:4", 192, 24),
                ),
                (
                    secure.ConcatContextWindow,
                    {
                        "first_image": prepared_ref,
                        "patch_mode": "patch_bottom",
                        "patch_type": "3:4",
                        "output_length": 192,
                        "patch_color": "#FFFFFF",
                        "second_image": prepared_ref,
                        "second_mask": prepared_mask_ref,
                    },
                    pristine.NODE_CLASS_MAPPINGS[
                        "ConcatContextWindow"
                    ]().concat_context_window(
                        prepared,
                        "patch_bottom",
                        "3:4",
                        192,
                        "#FFFFFF",
                        prepared,
                        prepared_mask,
                    ),
                ),
            )
            for index, (node, inputs, expected) in enumerate(cases):
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"in-context-lora-{index}",
                    node_id=str(index),
                    node_type=node.__name__,
                    tier="sandbox",
                    node_module=node.__module__,
                    inputs=inputs,
                    input_mode="values",
                    permissions=("raw",),
                    method="execute",
                )
                result = await session.execute(
                    plan, _runtime(plan, refs), capabilities=("raw",)
                )
                actual = []
                for value in result.result:
                    if isinstance(value, _sdk.Ref):
                        value = await refs.resolve(value)
                    actual.append(value)
                _assert_result(tuple(actual), expected)
                if index == 0:
                    with pytest.raises(Exception, match="raw"):
                        await session.execute(
                            plan, _runtime(plan, refs), capabilities=()
                        )
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = "\n".join(
        (V2 / name).read_text()
        for name in ("InContextUtils.py", "InContextLoraUtils.py", "nodes.py")
    )
    for required in ("import cv2", "import numpy", "import torch"):
        assert required in source
    for forbidden in (
        "import os",
        "import json",
        "import random",
        "safetensors",
        "skimage",
        "from PIL",
        "folder_paths",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "ctx()",
        "_from_raw",
        "from_value",
        "socket",
        "urllib",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-in-context-lora-utils" / "xede1f33"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
