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
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "54e799b354a465ca9f7ade0421f069b6ff4a6804"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
NODE_IDS = {"MosaicCreator", "MosaicDetector"}
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    "LICENSE",
    "README.md",
    "__init__.py",
    "mosaic.py",
    "pyproject.toml",
    "requirements.txt",
}
PAIR = PACK_DB / "patches/comfyui-mosaic/x54e799b/comfyui-mosaic-x54e799b"

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

import execution
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession


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
    return _import_package("_secure_comfyui_mosaic_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_comfyui_mosaic_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "class": node_class.__name__,
            "methods": {
                name: name in node_class.__dict__
                for name in (
                    "check_lazy_status",
                    "fingerprint_inputs",
                    "validate_inputs",
                )
            },
            "module": "nodes",
            "permissions": ["raw"],
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
            "sdk_refs": False,
        }
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file()
        and not any(
            part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in item.relative_to(root).parts
        )
    }


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _image(batch: int = 1, height: int = 24, width: int = 28) -> torch.Tensor:
    values = torch.linspace(0.0, 1.0, batch * height * width * 3)
    return values.reshape(batch, height, width, 3)


def _mask(batch: int = 1, height: int = 24, width: int = 28) -> torch.Tensor:
    mask = torch.zeros((batch, height, width), dtype=torch.float32)
    mask[:, 3:-4, 5:-6] = torch.linspace(0.0, 1.0, (height - 7) * (width - 11)).reshape(
        height - 7, width - 11
    )
    return mask


def _creator_inputs(image=None, **overrides):
    values = {
        "image": _image() if image is None else image,
        "mosaic_type": "pixelation",
        "block_size": 6,
        "intensity": 1.0,
        "mask": None,
        "preserve_edges": False,
    }
    values.update(overrides)
    return values


def _detector_inputs(image=None, **overrides):
    values = {
        "image": _image() if image is None else image,
        "top_n": 2,
        "mask_expand": 2,
        "mask_blur": 4,
        "invert_mask": False,
        "overlay_color": "magenta",
        "overlay_opacity": 0.6,
    }
    values.update(overrides)
    return values


def _assert_tensors_equal(actual, expected):
    assert len(actual) == len(expected)
    for got, wanted in zip(actual, expected, strict=True):
        assert got.dtype == wanted.dtype
        assert got.shape == wanted.shape
        assert torch.equal(got, wanted)


def test_actual_loader_census_stale_web_schema_manifest_and_contract_are_exact(
    tmp_path,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert pristine.WEB_DIRECTORY == "./web"
    assert not (PACK / "web").exists()
    assert not hasattr(secure, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))

    for node_id in NODE_IDS:
        old = pristine.NODE_CLASS_MAPPINGS[node_id]
        node = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = node.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.display_name == pristine.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == old.CATEGORY
        assert tuple(output.io_type for output in schema.outputs) == old.RETURN_TYPES
        assert (
            tuple(output.display_name for output in schema.outputs) == old.RETURN_NAMES
        )
        assert node.SDK_REFS is False
        assert node.SDK_PERMISSIONS == ("raw",)

    assert _manifest(secure) == json.loads((V2 / "secure-nodes.json").read_text())
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.comfyui_mosaic_test")
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory is None


def test_creator_schema_preserves_names_options_defaults_bounds_and_optional_inputs():
    schema = _secure().MosaicCreator.GET_SCHEMA()
    assert [item.id for item in schema.inputs] == [
        "image",
        "mosaic_type",
        "block_size",
        "intensity",
        "mask",
        "preserve_edges",
    ]
    assert list(schema.inputs[1].options) == _secure().MOSAIC_TYPES
    assert (schema.inputs[2].default, schema.inputs[2].min, schema.inputs[2].max) == (
        20,
        2,
        100,
    )
    assert (
        schema.inputs[3].default,
        schema.inputs[3].min,
        schema.inputs[3].max,
        schema.inputs[3].step,
    ) == (1.0, 0.0, 1.0, 0.1)
    assert schema.inputs[4].optional is True
    assert schema.inputs[5].optional is True
    assert schema.inputs[5].default is False


def test_detector_schema_preserves_names_options_defaults_and_bounds():
    schema = _secure().MosaicDetector.GET_SCHEMA()
    assert [item.id for item in schema.inputs] == [
        "image",
        "top_n",
        "mask_expand",
        "mask_blur",
        "invert_mask",
        "overlay_color",
        "overlay_opacity",
    ]
    assert list(schema.inputs[5].options) == _secure().OVERLAY_COLORS
    assert (schema.inputs[1].default, schema.inputs[1].min, schema.inputs[1].max) == (
        1,
        1,
        20,
    )
    assert (schema.inputs[2].default, schema.inputs[2].min, schema.inputs[2].max) == (
        0,
        0,
        64,
    )
    assert (
        schema.inputs[3].default,
        schema.inputs[3].min,
        schema.inputs[3].max,
        schema.inputs[3].step,
    ) == (0, 0, 64, 2)
    assert schema.inputs[4].default is False
    assert (
        schema.inputs[6].default,
        schema.inputs[6].min,
        schema.inputs[6].max,
    ) == (0.5, 0.0, 1.0)


@pytest.mark.parametrize(
    "mosaic_type",
    [
        "pixelation",
        "blur",
        "block_average",
        "squares",
        "circles",
        "hexagons",
        "gradient_horizontal",
        "gradient_vertical",
    ],
)
@pytest.mark.parametrize("with_mask", [False, True])
def test_every_creator_mode_is_bit_exact_to_pristine(tmp_path, mosaic_type, with_mask):
    pristine = _pristine(tmp_path)
    secure = _secure()
    image = _image(height=19, width=23)
    mask = _mask(height=19, width=23) if with_mask else None
    values = _creator_inputs(
        image,
        mosaic_type=mosaic_type,
        block_size=5,
        intensity=0.7,
        mask=mask,
        preserve_edges=True,
    )
    expected = pristine.MosaicCreator().create_mosaic(**values)
    actual = secure.MosaicCreator.execute(**values).result
    _assert_tensors_equal(actual, expected)


@pytest.mark.parametrize("intensity", [0.0, 0.25, 1.0])
@pytest.mark.parametrize("block_size", [2, 7, 20])
def test_creator_intensity_block_and_batch_matrix_is_exact(
    tmp_path, intensity, block_size
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    image = _image(batch=2, height=17, width=21)
    values = _creator_inputs(
        image, mosaic_type="squares", block_size=block_size, intensity=intensity
    )
    expected = pristine.MosaicCreator().create_mosaic(**values)
    actual = secure.MosaicCreator.execute(**values).result
    _assert_tensors_equal(actual, expected)
    assert torch.equal(actual[1], torch.ones(image.shape[:3]))


@pytest.mark.parametrize(
    "color", ["red", "green", "blue", "yellow", "cyan", "magenta", "white"]
)
def test_detector_every_overlay_color_is_bit_exact(tmp_path, color):
    pristine = _pristine(tmp_path)
    secure = _secure()
    values = _detector_inputs(overlay_color=color)
    expected = pristine.MosaicDetector().detect_mosaic(**values)
    actual = secure.MosaicDetector.execute(**values).result
    _assert_tensors_equal(actual, expected)


@pytest.mark.parametrize(
    "overrides",
    [
        {"top_n": 1, "mask_expand": 0, "mask_blur": 0},
        {"top_n": 20, "mask_expand": 5, "mask_blur": 3},
        {"invert_mask": True, "overlay_opacity": 0.0},
        {"invert_mask": True, "overlay_opacity": 1.0},
    ],
)
def test_detector_parameter_batch_matrix_is_exact(tmp_path, overrides):
    pristine = _pristine(tmp_path)
    secure = _secure()
    values = _detector_inputs(_image(batch=2, height=25, width=29), **overrides)
    expected = pristine.MosaicDetector().detect_mosaic(**values)
    actual = secure.MosaicDetector.execute(**values).result
    _assert_tensors_equal(actual, expected)


def test_copied_algorithm_module_is_byte_exact_and_helpers_match_pristine(tmp_path):
    pristine = _pristine(tmp_path)
    secure_algorithms = importlib.import_module(f"{_secure().__package__}.algorithms")
    assert (PACK / "mosaic.py").read_bytes() == (V2 / "algorithms.py").read_bytes()
    image = _image(height=13, width=15)[0]
    mask = _mask(height=13, width=15)[0]
    for name in (
        "create_pixelation_mosaic",
        "create_blur_mosaic",
        "create_block_mosaic",
    ):
        old_fn = getattr(
            importlib.import_module(f"{pristine.__package__}.mosaic"), name
        )
        new_fn = getattr(secure_algorithms, name)
        assert torch.equal(old_fn(image, 4, mask), new_fn(image, 4, mask))
    old_detector = pristine.MosaicDetector()
    new_detector = secure_algorithms.MosaicDetector()
    for size in (10, 15, 20):
        assert np.array_equal(
            old_detector.create_grid_pattern(size),
            new_detector.create_grid_pattern(size),
        )


@pytest.mark.parametrize(
    ("name", "value", "match"),
    [
        ("mosaic_type", "missing", "mosaic_type"),
        ("block_size", 1, "block_size"),
        ("block_size", True, "block_size"),
        ("intensity", float("nan"), "intensity"),
        ("intensity", 1.1, "intensity"),
        ("preserve_edges", 1, "preserve_edges"),
    ],
)
def test_creator_invalid_controls_fail_closed(name, value, match):
    values = _creator_inputs()
    values[name] = value
    with pytest.raises((TypeError, ValueError), match=match):
        _secure().MosaicCreator.execute(**values)


@pytest.mark.parametrize(
    ("name", "value", "match"),
    [
        ("top_n", 0, "top_n"),
        ("mask_expand", 65, "mask_expand"),
        ("mask_blur", True, "mask_blur"),
        ("invert_mask", 0, "invert_mask"),
        ("overlay_color", "orange", "overlay_color"),
        ("overlay_opacity", float("inf"), "overlay_opacity"),
    ],
)
def test_detector_invalid_controls_fail_closed(name, value, match):
    values = _detector_inputs()
    values[name] = value
    with pytest.raises((TypeError, ValueError), match=match):
        _secure().MosaicDetector.execute(**values)


@pytest.mark.parametrize(
    "image",
    [
        torch.zeros((8, 8, 3)),
        torch.zeros((1, 8, 8, 4)),
        torch.zeros((1, 8, 8, 3), dtype=torch.int32),
        torch.full((1, 8, 8, 3), float("nan")),
        torch.zeros((65, 1, 1, 3)),
    ],
)
def test_malformed_images_fail_closed(image):
    with pytest.raises((TypeError, ValueError)):
        _secure().MosaicCreator.execute(**_creator_inputs(image))


@pytest.mark.parametrize(
    "mask",
    [
        torch.zeros((8, 8)),
        torch.zeros((2, 8, 8)),
        torch.zeros((1, 7, 8)),
        torch.zeros((1, 8, 8), dtype=torch.int32),
        torch.full((1, 8, 8), float("nan")),
    ],
)
def test_malformed_masks_fail_closed(mask):
    image = torch.zeros((1, 8, 8, 3))
    with pytest.raises((TypeError, ValueError)):
        _secure().MosaicCreator.execute(**_creator_inputs(image, mask=mask))


def test_repeated_execution_is_isolated_and_does_not_mutate_rng():
    secure = _secure()
    values = _creator_inputs(mask=_mask())
    state = torch.random.get_rng_state().clone()
    first = secure.MosaicCreator.execute(**values).result
    second = secure.MosaicCreator.execute(**values).result
    _assert_tensors_equal(first, second)
    assert torch.equal(torch.random.get_rng_state(), state)
    assert torch.equal(values["image"], _image())


def test_real_guest_value_mode_creator_detector_raw_denial_and_isolation():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "comfyui-mosaic-conversion", guest_runtime_root=V2
        ).start()
        try:
            cases = [
                (secure.MosaicCreator, _creator_inputs(mosaic_type="circles")),
                (secure.MosaicDetector, _detector_inputs(invert_mask=True)),
            ]
            for index, (node, values) in enumerate(cases):
                expected = node.execute(**values).result
                plan_inputs = dict(values)
                plan_inputs["image"] = _sdk.ImageRef._wrap(
                    await refs.create("IMAGE", values["image"])
                )
                if plan_inputs.get("mask") is not None:
                    plan_inputs["mask"] = _sdk.MaskRef._wrap(
                        await refs.create("MASK", values["mask"])
                    )
                plan = _sdk.ExecutionPlan(
                    prompt_id="comfyui-mosaic",
                    node_id=str(index),
                    node_type=node.__name__,
                    tier="sandbox",
                    node_module=node.__module__,
                    inputs=plan_inputs,
                    input_mode="values",
                    permissions=("raw",),
                    method="execute",
                )
                result = await session.execute(
                    plan, _runtime(plan, refs), capabilities=("raw",)
                )
                actual = []
                for item in result.result:
                    actual.append(await refs.resolve(item))
                actual = tuple(actual)
                _assert_tensors_equal(actual, expected)
                with pytest.raises(Exception, match="raw"):
                    await session.execute(plan, _runtime(plan, refs), capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("node_id", "values", "return_types"),
    [
        ("MosaicCreator", _creator_inputs(mosaic_type="hexagons"), ("IMAGE", "MASK")),
        (
            "MosaicDetector",
            _detector_inputs(overlay_color="cyan"),
            ("IMAGE", "IMAGE", "MASK"),
        ),
    ],
)
def test_real_outer_executor_preserves_declared_types(node_id, values, return_types):
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name=f"custom_nodes.mosaic_outer_{node_id}"
    )
    node = loaded.node_mappings[node_id]
    assert tuple(node.RETURN_TYPES) == return_types

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    f"comfyui-mosaic-outer-{node_id}", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

            async def shutdown(self):
                if self.session is not None:
                    await self.session.kill()

        backend = OuterGuestBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            returns = await execution._async_map_node_over_list(
                prompt_id="comfyui-mosaic-outer",
                unique_id="1",
                obj=node,
                input_data_all={key: [value] for key, value in values.items()},
                func=node.FUNCTION,
                v3_data=None,
            )
            output = returns[0]
            assert len(output.result) == len(return_types)
            for value, declared in zip(output.result, return_types, strict=True):
                assert isinstance(value, torch.Tensor)
                if declared == "IMAGE":
                    assert value.ndim == 4 and value.shape[-1] == 3
                else:
                    assert value.ndim == 3
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_docs_license_and_stub_surface_are_exact():
    source = (V2 / "nodes.py").read_text()
    algorithms = (V2 / "algorithms.py").read_text()
    for required in (
        "SDK_REFS = False",
        'SDK_PERMISSIONS = ("raw",)',
        "MAX_PIXELS",
        "_LegacyMosaicCreator",
        "_LegacyMosaicDetector",
        "io.NodeOutput(",
    ):
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
    ):
        assert forbidden not in source
        assert forbidden not in algorithms
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-mosaic/x54e799b"
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
    assert not list(PACK.rglob(".ruff_cache"))
