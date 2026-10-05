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
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "d631a03dea2397db27042f5e9ec34fce34b2cfb6"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-inpainteasy"
    / "xd631a03"
    / "comfyui-inpainteasy-xd631a03"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
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
    return _import_package("_secure_inpainteasy_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_inpainteasy_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
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


def _image(batch=2, height=31, width=47):
    count = batch * height * width * 3
    return torch.linspace(0.0, 1.0, count).reshape(batch, height, width, 3)


def _mask(batch=2, height=31, width=47):
    result = torch.zeros((batch, height, width), dtype=torch.float32)
    result[:, 4 : height - 5, 7 : width - 9] = 1.0
    return result


def _exact(actual, expected):
    assert actual.dtype == expected.dtype
    assert tuple(actual.shape) == tuple(expected.shape)
    assert torch.equal(actual, expected)


def test_pinned_actual_loader_census_schemas_and_manifest_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    expected_ids = {
        "InpaintEasyModel",
        "ImageAndMaskResizeNode",
        "CropByMask",
        "ImageCropMerge",
    }
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert set(pristine.NODE_CLASS_MAPPINGS) == expected_ids
    assert set(secure.NODE_CLASS_MAPPINGS) == expected_ids
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]

    for node_id in expected_ids:
        legacy = pristine.NODE_CLASS_MAPPINGS[node_id]
        node = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = node.GET_SCHEMA()
        schema.validate()
        legacy_inputs = legacy.INPUT_TYPES()
        ordered = list(legacy_inputs["required"]) + list(
            legacy_inputs.get("optional", {})
        )
        assert [item.id for item in schema.inputs] == ordered
        assert [item.io_type for item in schema.outputs] == list(legacy.RETURN_TYPES)
        assert schema.category == legacy.CATEGORY
        assert schema.description == (getattr(legacy, "DESCRIPTION", None) or "")
        for item in schema.inputs:
            group = (
                "optional"
                if item.id in legacy_inputs.get("optional", {})
                else "required"
            )
            legacy_type, *rest = legacy_inputs[group][item.id]
            assert item.io_type == (
                "COMBO" if isinstance(legacy_type, list) else legacy_type
            )
            assert item.optional is (group == "optional")
            options = rest[0] if rest else {}
            for key in ("default", "min", "max", "step"):
                if key in options:
                    assert getattr(item, key) == options[key]
            if "forceInput" in options:
                assert item.force_input is options["forceInput"]
            if "display" in options:
                assert item.display_mode == options["display"]
            if isinstance(legacy_type, list):
                assert item.options == legacy_type

    assert secure.InpaintEasyModel.SDK_REFS is True
    assert secure.InpaintEasyModel.SDK_PERMISSIONS == ()
    for node in (
        secure.ImageAndMaskResizeNode,
        secure.CropByMask,
        secure.ImageCropMerge,
    ):
        assert node.SDK_REFS is False
        assert node.SDK_PERMISSIONS == ("raw",)
    extension = asyncio.run(secure.comfy_entrypoint())
    assert {
        node.GET_SCHEMA().node_id for node in asyncio.run(extension.get_node_list())
    } == expected_ids
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.inpainteasy_secure_census_test"
    )
    assert set(loaded.node_mappings) == expected_ids
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize(
    "resize_method", ("nearest-exact", "bilinear", "area", "bicubic", "lanczos")
)
@pytest.mark.parametrize(
    "crop",
    ("disabled", "center", "top_left", "top_right", "bottom_left", "bottom_right"),
)
def test_every_resize_and_crop_mode_is_pixel_exact(tmp_path, resize_method, crop):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageAndMaskResizeNode"]()
    secure = _secure()
    image = _image(batch=2)
    mask = _mask(batch=2)
    args = (40, 24, resize_method, crop, 0)
    expected = pristine.resize_image_and_mask(image.clone(), mask.clone(), *args)
    actual = secure.ImageAndMaskResizeNode.execute(
        image.clone(), mask.clone(), *args
    ).result
    _exact(actual[0], expected[0])
    _exact(actual[1], expected[1])


@pytest.mark.parametrize("radius", (0, 1, 4, 10))
def test_mask_blur_batches_and_aspect_inference_are_exact(tmp_path, radius):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageAndMaskResizeNode"]()
    secure = _secure()
    image = _image(batch=3, height=24, width=40)
    mask = _mask(batch=3, height=24, width=40)
    expected = pristine.resize_image_and_mask(
        image.clone(), mask.clone(), 0, 32, "bilinear", "disabled", radius
    )
    actual = secure.ImageAndMaskResizeNode.execute(
        image.clone(), mask.clone(), 0, 32, "bilinear", "disabled", radius
    ).result
    _exact(actual[0], expected[0])
    _exact(actual[1], expected[1])


@pytest.mark.parametrize("padding", (0, 7, 64, 512))
def test_crop_coordinates_values_and_empty_mask_failure_are_exact(tmp_path, padding):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["CropByMask"]()
    secure = _secure()
    image = _image(batch=1, height=41, width=57)
    mask = torch.zeros((1, 41, 57))
    mask[:, 3:19, 32:52] = 0.75
    expected = pristine.process(image, mask, padding)
    actual = secure.CropByMask.execute(image, mask, padding).result
    _exact(actual[0], expected[0])
    _exact(actual[1], expected[1])
    assert actual[2:] == expected[2:]
    for call in (
        lambda: pristine.process(image, torch.zeros_like(mask), padding),
        lambda: secure.CropByMask.execute(image, torch.zeros_like(mask), padding),
    ):
        with pytest.raises(ValueError, match="Mask is empty"):
            call()


@pytest.mark.parametrize(
    "resize_method", ("nearest-exact", "bilinear", "area", "bicubic", "lanczos")
)
def test_merge_is_pixel_exact_and_does_not_mutate_original(tmp_path, resize_method):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ImageCropMerge"]()
    secure = _secure()
    original = _image(batch=2, height=48, width=64)
    cropped = _image(batch=2, height=13, width=17).flip(2)
    before = original.clone()
    args = (24, 16, 11, 7, resize_method)
    expected = pristine.merge_images(cropped, original, *args)[0]
    actual = secure.ImageCropMerge.execute(cropped, original, *args).result[0]
    _exact(actual, expected)
    _exact(original, before)


def test_inpaint_typed_calls_preserve_order_defaults_and_optional_control():
    secure = _secure()
    events = []
    inputs = [object() for _ in range(7)]
    positive, negative, image, mask, _vae, _control, control_image = inputs
    conditioned = [object(), object(), object()]
    controlled = [object(), object()]

    class Vae:
        async def encode_inpaint_conditioning(self, *args, **kwargs):
            events.append(("inpaint", args, kwargs))
            return tuple(conditioned)

    class Control:
        async def apply(self, *args):
            events.append(("control", args))
            return tuple(controlled)

    vae_ref = Vae()
    control_ref = Control()
    result = asyncio.run(
        secure.InpaintEasyModel.execute(
            positive,
            negative,
            image,
            mask,
            vae_ref,
            0.75,
            0.2,
            0.8,
            control_ref,
            control_image,
        )
    ).result
    assert result == (controlled[0], controlled[1], conditioned[2])
    assert events[0] == (
        "inpaint",
        (image, mask, positive, negative),
        {"noise_mask": True},
    )
    assert events[1] == (
        "control",
        (
            conditioned[0],
            conditioned[1],
            control_image,
            0.75,
            0.2,
            0.8,
            vae_ref,
        ),
    )


def test_inpaint_no_control_branches_do_not_apply_control():
    secure = _secure()

    class Vae:
        async def encode_inpaint_conditioning(self, *_args, **_kwargs):
            return "p", "n", "latent"

    class Control:
        async def apply(self, *_args):
            raise AssertionError("ControlNet must not be called")

    for strength, control, image in (
        (0.0, Control(), object()),
        (1.0, None, object()),
        (1.0, Control(), None),
    ):
        result = asyncio.run(
            secure.InpaintEasyModel.execute(
                object(),
                object(),
                object(),
                object(),
                Vae(),
                strength,
                0.0,
                1.0,
                control,
                image,
            )
        ).result
        assert result == ("p", "n", "latent")


def test_malformed_and_oversized_raw_inputs_fail_closed():
    secure = _secure()
    image = _image(batch=1, height=8, width=8)
    mask = _mask(batch=1, height=8, width=8)
    with pytest.raises(TypeError, match="4D"):
        secure.ImageCropMerge.execute(image[0], image, 4, 4, 0, 0, "bilinear")
    with pytest.raises(TypeError, match="3D"):
        secure.CropByMask.execute(image, mask[0], 0)
    too_large = torch.empty((1, 1, secure.nodes.MAX_TENSOR_ELEMENTS + 1), device="meta")
    with pytest.raises(ValueError, match="tensor-size"):
        secure.CropByMask.execute(image, too_large, 0)


def test_real_isolated_guest_executes_raw_and_typed_paths_and_denies_raw(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()

    class FakeVae:
        def encode(self, pixels):
            return pixels.movedim(-1, 1).mean(dim=1, keepdim=True)

    class FakeControl:
        def copy(self):
            return FakeControl()

        def set_cond_hint(self, hint, strength, percent_range, vae=None, **_kwargs):
            self.hint = hint
            self.strength = strength
            self.percent_range = percent_range
            self.vae = vae
            return self

        def set_previous_controlnet(self, previous):
            self.previous = previous

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "inpainteasy-secure-conversion", guest_runtime_root=V2
        ).start()
        try:
            image = _image(batch=1, height=24, width=32)
            mask = _mask(batch=1, height=24, width=32)
            image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
            mask_ref = _sdk.MaskRef._wrap(await refs.create("MASK", mask))
            resize_node = secure.ImageAndMaskResizeNode
            resize_inputs = {
                "image": image_ref,
                "mask": mask_ref,
                "width": 40,
                "height": 32,
                "resize_method": "bicubic",
                "crop": "bottom_right",
                "mask_blur_radius": 2,
            }
            resize_plan = _sdk.ExecutionPlan(
                prompt_id="inpainteasy-raw",
                node_id="1",
                node_type=resize_node.__name__,
                tier="sandbox",
                node_module=resize_node.__module__,
                inputs=resize_inputs,
                input_mode="values",
                permissions=("raw",),
                method="execute",
            )
            resized = await session.execute(
                resize_plan, _runtime(resize_plan, refs), capabilities=("raw",)
            )
            expected = pristine.NODE_CLASS_MAPPINGS[
                "ImageAndMaskResizeNode"
            ]().resize_image_and_mask(image, mask, 40, 32, "bicubic", "bottom_right", 2)
            _exact(await refs.resolve(resized.result[0]), expected[0])
            _exact(await refs.resolve(resized.result[1]), expected[1])
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    resize_plan, _runtime(resize_plan, refs), capabilities=()
                )

            cond_value = [[torch.ones((1, 2, 3)), {"tag": "keep"}]]
            positive = _sdk.CondRef._wrap(
                await refs.create("CONDITIONING", copy.deepcopy(cond_value))
            )
            negative = _sdk.CondRef._wrap(
                await refs.create("CONDITIONING", copy.deepcopy(cond_value))
            )
            vae = _sdk.VaeRef._wrap(await refs.create("VAE", FakeVae()))
            control = _sdk.ControlNetRef._wrap(
                await refs.create("CONTROL_NET", FakeControl())
            )
            model_node = secure.InpaintEasyModel
            model_inputs = {
                "positive": positive,
                "negative": negative,
                "inpaint_image": image_ref,
                "mask": mask_ref,
                "vae": vae,
                "strength": 0.65,
                "start_percent": 0.2,
                "end_percent": 0.8,
                "control_net": control,
                "control_image": image_ref,
            }
            model_plan = _sdk.ExecutionPlan(
                prompt_id="inpainteasy-typed",
                node_id="2",
                node_type=model_node.__name__,
                tier="sandbox",
                node_module=model_node.__module__,
                inputs=model_inputs,
                input_mode="refs",
                permissions=(),
                method="execute",
            )
            modeled = await session.execute(
                model_plan, _runtime(model_plan, refs), capabilities=()
            )
            out_positive = await refs.resolve(modeled.result[0])
            out_negative = await refs.resolve(modeled.result[1])
            out_latent = await refs.resolve(modeled.result[2])
            for output in (out_positive, out_negative):
                assert output[0][1]["tag"] == "keep"
                assert "concat_latent_image" in output[0][1]
                assert "concat_mask" in output[0][1]
                applied = output[0][1]["control"]
                assert applied.strength == 0.65
                assert applied.percent_range == (0.2, 0.8)
                assert applied.previous is None
                assert output[0][1]["control_apply_to_uncond"] is False
            assert set(out_latent) == {"samples", "noise_mask"}
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_contract_license_and_authority_boundary_are_exact():
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    assert source.count('SDK_PERMISSIONS = ("raw",)') == 3
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
    fresh = tmp_path / "comfyui-inpainteasy" / "xd631a03"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
