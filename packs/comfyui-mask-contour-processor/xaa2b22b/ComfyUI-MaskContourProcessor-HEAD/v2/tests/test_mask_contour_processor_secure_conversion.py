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
from PIL import Image, ImageFilter

sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "aa2b22b3f4fd2c2e0f81be39e8b5077ab18126c2"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
NODE_IDS = {"MaskContourProcessor"}
PRISTINE_FILES = {
    ".gitignore",
    "LICENSE",
    "README.md",
    "__init__.py",
    "nodes/nodes.py",
    "requirements.txt",
    "tags",
    "tests/test_mask_contour_processor.py",
    "web/index.html",
    "web/js/index.js",
    "web/js/maskProcessor.js",
}
PAIR = PACK_DB / (
    "patches/comfyui-mask-contour-processor/xaa2b22b/"
    "comfyui-mask-contour-processor-xaa2b22b"
)

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
    return _import_package("_secure_mask_contour_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_mask_contour_test", root)


def _manifest(pack) -> dict:
    node = pack.MaskContourProcessor
    return {
        "format": FORMAT,
        "nodes": {
            "MaskContourProcessor": {
                "class": "MaskContourProcessor",
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "check_lazy_status",
                        "fingerprint_inputs",
                        "validate_inputs",
                    )
                },
                "module": "nodes",
                "permissions": ["raw"],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": False,
            }
        },
        "runtime": manifest_declaration(V2),
    }


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


def _rectangle(batch=1, height=48, width=56):
    mask = torch.zeros((batch, height, width), dtype=torch.float32)
    mask[:, 8:37, 11:44] = 1.0
    return mask


def _circle(batch=1, height=51, width=57):
    yy, xx = torch.meshgrid(torch.arange(height), torch.arange(width), indexing="ij")
    item = (((xx - 28) ** 2 + (yy - 25) ** 2) <= 15**2).to(torch.float32)
    return item.unsqueeze(0).repeat(batch, 1, 1)


def _disconnected():
    mask = torch.zeros((1, 48, 56), dtype=torch.float32)
    mask[:, 4:18, 5:20] = 1.0
    mask[:, 27:44, 34:52] = 1.0
    return mask


def _inputs(mask=None, **overrides):
    values = {
        "mask": _rectangle() if mask is None else mask,
        "line_length": 0.5,
        "line_count": 16,
        "line_width": 0.015,
        "blur_amount": 2.0,
    }
    values.update(overrides)
    return values


def _assert_equal(actual: torch.Tensor, expected: torch.Tensor):
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert torch.equal(actual, expected)


def test_actual_loader_census_schema_manifest_and_unexported_demo_are_exact(tmp_path):
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
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not hasattr(secure, "WEB_DIRECTORY")
    web_source = "\n".join(path.read_text() for path in (PACK / "web").rglob("*.js"))
    assert "app.registerExtension" not in web_source
    assert "LiteGraph.registerNodeType" not in web_source

    old = pristine.NODE_CLASS_MAPPINGS["MaskContourProcessor"]
    node = secure.MaskContourProcessor
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "MaskContourProcessor"
    assert schema.display_name == "Mask Contour Processor"
    assert schema.category == old.CATEGORY == "mask"
    assert tuple(output.io_type for output in schema.outputs) == old.RETURN_TYPES
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)
    assert _manifest(secure) == json.loads((V2 / "secure-nodes.json").read_text())

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.mask_contour_test")
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory is None


def test_schema_preserves_input_order_defaults_bounds_and_steps():
    inputs = _secure().MaskContourProcessor.GET_SCHEMA().inputs
    assert [item.id for item in inputs] == [
        "mask",
        "line_length",
        "line_count",
        "line_width",
        "blur_amount",
    ]
    assert (inputs[1].default, inputs[1].min, inputs[1].max, inputs[1].step) == (
        0.5,
        0.0,
        3.0,
        0.01,
    )
    assert (inputs[2].default, inputs[2].min, inputs[2].max, inputs[2].step) == (
        16,
        1,
        40,
        1,
    )
    assert (inputs[3].default, inputs[3].min, inputs[3].max, inputs[3].step) == (
        0.015,
        0.0,
        0.1,
        0.001,
    )
    assert (inputs[4].default, inputs[4].min, inputs[4].max, inputs[4].step) == (
        2.0,
        0.0,
        50.0,
        0.1,
    )


@pytest.mark.parametrize("factory", [_rectangle, _circle, _disconnected])
@pytest.mark.parametrize(
    "controls",
    [
        {"line_length": 0.0, "line_count": 1, "line_width": 0.0, "blur_amount": 0.0},
        {"line_length": 0.5, "line_count": 9, "line_width": 0.015, "blur_amount": 2.0},
        {"line_length": 1.75, "line_count": 16, "line_width": 0.05, "blur_amount": 7.5},
        {"line_length": 3.0, "line_count": 40, "line_width": 0.1, "blur_amount": 50.0},
    ],
)
def test_valid_mask_behavior_is_bit_exact_to_pristine(tmp_path, factory, controls):
    pristine = _pristine(tmp_path)
    values = _inputs(factory(), **controls)
    expected = pristine.NODE_CLASS_MAPPINGS["MaskContourProcessor"]().process_mask(
        **values
    )[0]
    actual = _secure().MaskContourProcessor.execute(**values).result[0]
    _assert_equal(actual, expected)


def test_batch_behavior_is_bit_exact_to_pristine(tmp_path):
    pristine = _pristine(tmp_path)
    batch = torch.cat(
        (_rectangle(), _circle(height=48, width=56), _disconnected()), dim=0
    )
    values = _inputs(batch, line_count=13, blur_amount=1.5)
    expected = pristine.NODE_CLASS_MAPPINGS["MaskContourProcessor"]().process_mask(
        **values
    )[0]
    actual = _secure().MaskContourProcessor.execute(**values).result[0]
    _assert_equal(actual, expected)


def test_copied_algorithm_is_byte_exact_and_helpers_match_pristine(tmp_path):
    pristine_package = _pristine(tmp_path)
    pristine = pristine_package.NODE_CLASS_MAPPINGS["MaskContourProcessor"]()
    algorithm = importlib.util.spec_from_file_location(
        "_mask_contour_algorithm_test", V2 / "algorithm.py"
    )
    assert algorithm is not None and algorithm.loader is not None
    module = importlib.util.module_from_spec(algorithm)
    algorithm.loader.exec_module(module)
    secure = module.MaskContourProcessor()
    assert (PACK / "nodes/nodes.py").read_bytes() == (V2 / "algorithm.py").read_bytes()
    array = _circle()[0].numpy()
    center = pristine.calculate_mask_centroid(array)
    assert secure.calculate_mask_centroid(array) == center
    old_edges = pristine.detect_edge_points(array, center)
    new_edges = secure.detect_edge_points(array, center)
    assert new_edges == old_edges
    assert secure.redistribute_points(new_edges, 17) == pristine.redistribute_points(
        old_edges, 17
    )
    assert secure.calculate_base_line_width(
        new_edges, 0.02
    ) == pristine.calculate_base_line_width(old_edges, 0.02)
    old_effect = pristine.generate_flame_ray_effect(
        old_edges[0], old_edges[1], 12.0, center, 2.5
    )
    new_effect = secure.generate_flame_ray_effect(
        new_edges[0], new_edges[1], 12.0, center, 2.5
    )
    assert new_effect == old_effect
    assert np.array_equal(
        secure.render_effect_to_mask(np.zeros_like(array), new_effect),
        pristine.render_effect_to_mask(np.zeros_like(array), old_effect),
    )


@pytest.mark.parametrize(
    "mask",
    [
        torch.zeros((1, 32, 40), dtype=torch.float32),
        torch.nn.functional.pad(torch.ones((1, 1, 1)), (19, 20, 15, 16)),
        torch.ones((1, 1, 1), dtype=torch.float32),
    ],
)
@pytest.mark.parametrize("blur_amount", [0.0, 3.0])
def test_empty_and_degenerate_masks_use_documented_blurred_original(mask, blur_amount):
    values = _inputs(mask, line_count=2, blur_amount=blur_amount)
    actual = _secure().MaskContourProcessor.execute(**values).result[0]
    expected_items = []
    for item in mask:
        image = Image.fromarray(
            (np.clip(item.numpy(), 0, 1) * 255).astype(np.uint8), mode="L"
        ).filter(ImageFilter.GaussianBlur(blur_amount))
        expected_items.append(torch.from_numpy(np.array(image) / 255.0))
    expected = torch.stack(expected_items)
    _assert_equal(actual, expected)
    assert torch.isfinite(actual).all()
    assert ((0.0 <= actual) & (actual <= 1.0)).all()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("line_length", -0.1),
        ("line_length", float("nan")),
        ("line_count", 0),
        ("line_count", True),
        ("line_width", 0.11),
        ("blur_amount", float("inf")),
        ("blur_amount", 50.1),
    ],
)
def test_invalid_controls_fail_closed(name, value):
    values = _inputs()
    values[name] = value
    with pytest.raises((TypeError, ValueError), match=name):
        _secure().MaskContourProcessor.execute(**values)


@pytest.mark.parametrize(
    "mask",
    [
        torch.zeros((32, 40)),
        torch.zeros((1, 2, 32, 40)),
        torch.zeros((1, 32, 40), dtype=torch.int32),
        torch.full((1, 32, 40), float("nan")),
        torch.zeros((65, 1, 1)),
    ],
)
def test_malformed_masks_fail_closed(mask):
    with pytest.raises((TypeError, ValueError), match="mask"):
        _secure().MaskContourProcessor.execute(**_inputs(mask))


def test_dimension_and_total_pixel_limits_fail_closed(monkeypatch):
    secure = _secure()
    monkeypatch.setattr(secure.nodes, "MAX_DIMENSION", 16)
    with pytest.raises(ValueError, match="dimensions"):
        secure.MaskContourProcessor.execute(**_inputs(torch.zeros((1, 17, 4))))
    monkeypatch.setattr(secure.nodes, "MAX_DIMENSION", 8192)
    monkeypatch.setattr(secure.nodes, "MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="pixel"):
        secure.MaskContourProcessor.execute(**_inputs(torch.zeros((1, 11, 10))))


def test_repeated_execution_is_isolated_and_does_not_mutate_rng_or_input():
    values = _inputs(_circle(batch=2), line_count=11)
    before = values["mask"].clone()
    rng = torch.random.get_rng_state().clone()
    first = _secure().MaskContourProcessor.execute(**values).result[0]
    second = _secure().MaskContourProcessor.execute(**values).result[0]
    _assert_equal(first, second)
    assert torch.equal(values["mask"], before)
    assert torch.equal(torch.random.get_rng_state(), rng)


def test_real_guest_value_mode_raw_permission_and_denial():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "mask-contour-conversion", guest_runtime_root=V2
        ).start()
        try:
            values = _inputs(_circle(), line_count=11)
            expected = secure.MaskContourProcessor.execute(**values).result[0]
            wrapped = dict(values)
            wrapped["mask"] = _sdk.MaskRef._wrap(
                await refs.create("MASK", values["mask"])
            )
            plan = _sdk.ExecutionPlan(
                prompt_id="mask-contour",
                node_id="1",
                node_type="MaskContourProcessor",
                tier="sandbox",
                node_module=secure.MaskContourProcessor.__module__,
                inputs=wrapped,
                input_mode="values",
                permissions=("raw",),
                method="execute",
            )
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=("raw",)
            )
            actual = await refs.resolve(result.result[0])
            _assert_equal(actual, expected)
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, _runtime(plan, refs), capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_real_outer_executor_preserves_declared_mask_type():
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.mask_contour_outer")
    node = loaded.node_mappings["MaskContourProcessor"]
    assert tuple(node.RETURN_TYPES) == ("MASK",)

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "mask-contour-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

            async def shutdown(self):
                if self.session is not None:
                    await self.session.kill()

        backend = OuterGuestBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            values = _inputs(_rectangle(), line_count=11)
            returns = await execution._async_map_node_over_list(
                prompt_id="mask-contour-outer",
                unique_id="1",
                obj=node,
                input_data_all={key: [value] for key, value in values.items()},
                func=node.FUNCTION,
                v3_data=None,
            )
            output = returns[0]
            assert len(output.result) == 1
            assert isinstance(output.result[0], torch.Tensor)
            assert output.result[0].ndim == 3
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_docs_license_and_canonical_stubs_are_exact():
    source = (V2 / "nodes.py").read_text()
    algorithm = (V2 / "algorithm.py").read_text()
    for required in (
        "SDK_REFS = False",
        'SDK_PERMISSIONS = ("raw",)',
        "MAX_PIXELS",
        "_supports_legacy_geometry",
        "_blur_original",
        "_LegacyMaskContourProcessor",
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
        assert forbidden not in algorithm
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert "degenerate" in (V2 / "SECURE_CONVERSION.md").read_text()
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-mask-contour-processor/xaa2b22b"
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
