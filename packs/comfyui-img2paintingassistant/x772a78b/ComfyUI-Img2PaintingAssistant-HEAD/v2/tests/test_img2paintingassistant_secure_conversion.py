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
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "772a78bb92bd8e8adfdec8af28ce1ac6203e77e5"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-img2paintingassistant"
    / "x772a78b"
    / ("comfyui-img2paintingassistant-x772a78b")
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

import execution  # noqa: E402
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
    return _import_package("_secure_img2paintingassistant_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_img2paintingassistant_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(
                getattr(
                    node_class,
                    "SDK_PERMISSIONS",
                    (),
                )
                or ()
            ),
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


def _image(batch=2, height=32, width=40, channels=3):
    count = batch * height * width * channels
    return torch.linspace(0.0, 1.0, count, dtype=torch.float32).reshape(
        batch,
        height,
        width,
        channels,
    )


def _painting_args(**overrides):
    values = {
        "painting_details": 26.0,
        "painting_blur": 1,
        "sharpness": 7,
        "brightness": 1.0,
        "hue": 0.0,
        "saturation": 1.1,
        "lightness": 1.4,
        "contrast": 1.0,
        "correct_black_Img": False,
        "lineArt": None,
    }
    values.update(overrides)
    return values


def _assert_tensors_exact(actual, expected):
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        assert tuple(got.shape) == tuple(want.shape)
        assert got.dtype == want.dtype
        assert torch.equal(got, want)


def test_pinned_loader_census_entrypoint_and_schema_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "2 supported, 0 rejected, 0 pending" in report
    assert set(pristine.NODE_CLASS_MAPPINGS) == {
        "Painting",
        "ProcessInspyrenetRembg",
    }
    assert set(secure.NODE_CLASS_MAPPINGS) == set(pristine.NODE_CLASS_MAPPINGS)
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]

    painting = secure.Painting.GET_SCHEMA()
    painting.validate()
    assert (painting.node_id, painting.display_name, painting.category) == (
        "Painting",
        "Image Painting Assistant",
        "image",
    )
    pristine_inputs = pristine.NODE_CLASS_MAPPINGS["Painting"].INPUT_TYPES()
    required = pristine_inputs["required"]
    assert [(item.id, item.io_type) for item in painting.inputs] == [
        ("image", "IMAGE"),
        ("painting_details", "FLOAT"),
        ("painting_blur", "INT"),
        ("sharpness", "INT"),
        ("brightness", "FLOAT"),
        ("hue", "FLOAT"),
        ("saturation", "FLOAT"),
        ("lightness", "FLOAT"),
        ("contrast", "FLOAT"),
        ("correct_black_Img", "BOOLEAN"),
        ("lineArt", "IMAGE"),
    ]
    for item in painting.inputs[1:9]:
        expected = required[item.id][1]
        assert (item.default, item.min, item.max, item.step) == (
            expected["default"],
            expected.get("min"),
            expected.get("max"),
            expected.get("step"),
        )
    assert painting.inputs[9].default is required["correct_black_Img"][1]["default"]
    assert painting.inputs[10].optional is True
    assert [(item.io_type, item.display_name) for item in painting.outputs] == [
        ("IMAGE", "painting"),
        ("IMAGE", "sharpImage"),
    ]

    rembg = secure.ProcessInspyrenetRembg.GET_SCHEMA()
    rembg.validate()
    assert (rembg.node_id, rembg.display_name, rembg.category) == (
        "ProcessInspyrenetRembg",
        "Inspyrenet Rembg Assistant",
        "image",
    )
    assert [(item.id, item.io_type) for item in rembg.inputs] == [
        ("image", "IMAGE"),
        ("mask", "MASK"),
        ("use_bg_color", "BOOLEAN"),
        ("bg_color", "COMBO"),
    ]
    pristine_rembg = pristine.NODE_CLASS_MAPPINGS[
        "ProcessInspyrenetRembg"
    ].INPUT_TYPES()["required"]
    assert rembg.inputs[2].default is pristine_rembg["use_bg_color"][1]["default"]
    assert rembg.inputs[3].options == pristine_rembg["bg_color"][0]
    assert [(item.io_type, item.display_name) for item in rembg.outputs] == [
        ("IMAGE", None),
        ("MASK", None),
    ]
    assert secure.Painting.SDK_REFS is False
    assert secure.ProcessInspyrenetRembg.SDK_REFS is False
    assert secure.Painting.SDK_PERMISSIONS == ("raw",)
    assert secure.ProcessInspyrenetRembg.SDK_PERMISSIONS == ("raw",)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [
        secure.Painting,
        secure.ProcessInspyrenetRembg,
    ]
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.img2paintingassistant_census_test",
    )
    assert set(loaded.node_mappings) == set(pristine.NODE_CLASS_MAPPINGS)
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize(
    "overrides",
    (
        {},
        {"sharpness": 9, "painting_blur": 3, "hue": 17.0},
        {"sharpness": 11, "contrast": 1.7, "brightness": 0.8},
        {"correct_black_Img": True, "saturation": 0.7, "lightness": 1.9},
    ),
)
def test_painting_rgb_batch_pipeline_is_pixel_exact(tmp_path, overrides):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["Painting"]()
    secure = _secure()
    image = _image()
    args = _painting_args(**overrides)
    expected = pristine.process(image.clone(), **args)
    actual = secure.Painting.execute(image.clone(), **args).result
    _assert_tensors_exact(actual, expected)


def test_painting_rgba_lineart_zip_alpha_and_output_order_are_exact(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["Painting"]()
    secure = _secure()
    image = _image(batch=2, channels=4)
    lineart = torch.ones((1, 28, 36, 3), dtype=torch.float32)
    lineart[:, 4:17, 7:22, :] = 0.25
    args = _painting_args(
        lineArt=lineart,
        sharpness=11,
        painting_blur=3,
        contrast=0.65,
        brightness=1.2,
        lightness=1.6,
    )
    expected = pristine.process(image.clone(), **args)
    actual = secure.Painting.execute(image.clone(), **args).result
    _assert_tensors_exact(actual, expected)
    assert actual[0].shape == (1, 32, 40, 4)
    assert actual[1].shape == (1, 32, 40, 4)
    assert torch.equal(actual[0][..., 3], expected[0][..., 3])
    assert torch.equal(actual[1][..., 3], expected[1][..., 3])


@pytest.mark.parametrize("use_bg_color", (False, True))
def test_rembg_all_colors_mask_passthrough_and_pixels_are_exact(
    tmp_path,
    use_bg_color,
):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ProcessInspyrenetRembg"]()
    secure = _secure()
    secure_module = sys.modules[f"{secure.__name__}.nodes"]
    image = _image(batch=2, height=7, width=9, channels=4)
    mask = torch.linspace(0, 1, 126, dtype=torch.float32).reshape(2, 7, 9)
    for color in secure_module.BACKGROUND_COLORS:
        expected = pristine.remove_background(
            image.clone(),
            mask,
            use_bg_color,
            color,
        )
        actual = secure.ProcessInspyrenetRembg.execute(
            image.clone(),
            mask,
            use_bg_color,
            color,
        ).result
        _assert_tensors_exact(actual, expected)
        assert actual[1] is mask


def test_direct_malformed_inputs_and_unknown_color_match_upstream(tmp_path):
    pristine_module = sys.modules[
        f"{_pristine(tmp_path).__name__}.image_to_painting_node"
    ]
    secure = _secure()
    secure_module = sys.modules[f"{secure.__name__}.nodes"]
    for image, mask in (
        (_image(batch=1, channels=3), torch.ones((1, 32, 40))),
        (_image(batch=1, channels=4), torch.ones((1, 1, 32, 40))),
    ):
        for fn in (
            pristine_module.create_transparent_images,
            secure_module.create_transparent_images,
        ):
            with pytest.raises(ValueError):
                fn(image, mask, False, "white")
    image = _image(batch=1, height=2, width=3, channels=4)
    mask = torch.zeros((1, 2, 3), dtype=torch.float32)
    expected = pristine_module.create_transparent_images(
        image,
        mask,
        True,
        "not-a-color",
    )
    actual = secure_module.create_transparent_images(
        image,
        mask,
        True,
        "not-a-color",
    )
    assert torch.equal(actual, expected)
    assert torch.equal(actual[..., :3], torch.zeros_like(actual[..., :3]))


def test_real_guest_value_mode_matches_pixel_behavior_and_denies_raw_without_cap(
    tmp_path,
):
    pristine = _pristine(tmp_path)
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "img2paintingassistant-guest",
            guest_runtime_root=V2,
        ).start()
        try:
            image = _image(batch=1, height=8, width=10, channels=4)
            mask = torch.linspace(0, 1, 80, dtype=torch.float32).reshape(1, 8, 10)
            image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
            mask_ref = _sdk.MaskRef._wrap(await refs.create("MASK", mask))
            inputs = {
                "image": image_ref,
                "mask": mask_ref,
                "use_bg_color": True,
                "bg_color": "teal",
            }
            plan = _sdk.ExecutionPlan(
                prompt_id="img2painting-guest",
                node_id="1",
                node_type=secure.ProcessInspyrenetRembg.__name__,
                tier="sandbox",
                node_module=secure.ProcessInspyrenetRembg.__module__,
                inputs=inputs,
                input_mode="values",
                permissions=("raw",),
                method="execute",
            )
            expected = pristine.NODE_CLASS_MAPPINGS[
                "ProcessInspyrenetRembg"
            ]().remove_background(
                image,
                mask,
                True,
                "teal",
            )
            result = await session.execute(
                plan,
                _runtime(plan, refs),
                capabilities=("raw",),
            )
            resolved = tuple([await refs.resolve(item) for item in result.result])
            _assert_tensors_exact(resolved, expected)
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    plan,
                    _runtime(plan, refs),
                    capabilities=(),
                )
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_real_outer_executor_returns_declared_image_and_mask_tensors(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ProcessInspyrenetRembg"]()
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.img2paintingassistant_outer_test",
    )
    node = loaded.node_mappings["ProcessInspyrenetRembg"]
    assert node.RETURN_TYPES == ["IMAGE", "MASK"]
    image = _image(batch=1, height=8, width=10, channels=4)
    mask = torch.linspace(0, 1, 80, dtype=torch.float32).reshape(1, 8, 10)
    expected = pristine.remove_background(image, mask, False, "white")

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "img2paintingassistant-outer",
                    guest_runtime_root=V2,
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(
                    plan,
                    runtime,
                    capabilities=("raw",),
                )

            async def shutdown(self):
                if self.session is not None:
                    await self.session.kill()

        backend = OuterGuestBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            returns = await execution._async_map_node_over_list(
                prompt_id="img2painting-outer",
                unique_id="1",
                obj=node,
                input_data_all={
                    "image": [image],
                    "mask": [mask],
                    "use_bg_color": [False],
                    "bg_color": ["white"],
                },
                func=node.FUNCTION,
                v3_data=None,
            )
            assert len(returns) == 1
            output = returns[0]
            assert all(isinstance(value, torch.Tensor) for value in output.result)
            _assert_tensors_exact(output.result, expected)
            assert tuple(node.RETURN_TYPES) == ("IMAGE", "MASK")
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_manifest_stubs_missing_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert not (PACK / "LICENSE").exists()
    assert not (V2 / "LICENSE").exists()
    source = (V2 / "nodes.py").read_text()
    for required in ("import cv2", "import numpy", "import torch"):
        assert required in source
    for forbidden in (
        "import comfy",
        "folder_paths",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "os.",
        "sys.",
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
    fresh = tmp_path / "comfyui-img2paintingassistant" / "x772a78b"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
