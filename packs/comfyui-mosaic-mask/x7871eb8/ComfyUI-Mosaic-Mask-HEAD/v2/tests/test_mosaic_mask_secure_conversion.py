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

import cv2
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
COMMIT = "7871eb8cc512c63e6c6afaf465483b08f062ef52"
TREE = "48037c0b9acca679c85acc10259f2c7b6416c2fd"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
NODE_ID = "MosaicMask"
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    ".gitignore",
    "README.md",
    "__init__.py",
    "example.json",
    "example/example.png",
    *(f"grids/pattern{size}x{size}.png" for size in range(5, 21)),
    "mosaic_masking.py",
    "pyproject.toml",
    "requirements.txt",
    "test_mosaic_masking.py",
}
PAIR = PACK_DB / "patches/comfyui-mosaic-mask/x7871eb8/comfyui-mosaic-mask-x7871eb8"

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
    return _import_package("_secure_mosaic_mask_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_mosaic_mask_test", root)


def _manifest(pack) -> dict:
    node = pack.NODE_CLASS_MAPPINGS[NODE_ID]
    return {
        "format": FORMAT,
        "nodes": {
            NODE_ID: {
                "class": node.__name__,
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
            },
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


def _image(path: pathlib.Path) -> torch.Tensor:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert bgr is not None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return torch.from_numpy(rgb.astype(np.float32) / 255.0).unsqueeze(0)


def _inputs(image: torch.Tensor, **overrides):
    values = {
        "image": image,
        "top_n": 1,
        "kernel_size": 3,
        "threshold": 0.3,
        "min_grid_size": 10,
        "max_grid_size": 20,
    }
    values.update(overrides)
    return values


def test_actual_loader_census_schema_manifest_resources_and_contract_are_exact(
    tmp_path,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert TREE == "48037c0b9acca679c85acc10259f2c7b6416c2fd"
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    old = pristine.NODE_CLASS_MAPPINGS[NODE_ID]
    node = secure.NODE_CLASS_MAPPINGS[NODE_ID]
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "MosaicMask"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == {NODE_ID: "MosaicMask"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not hasattr(secure, "WEB_DIRECTORY")

    schema = node.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        NODE_ID,
        "MosaicMask",
        old.CATEGORY,
    )
    old_inputs = old.INPUT_TYPES()
    declarations = {
        **old_inputs["required"],
        **old_inputs["optional"],
    }
    assert [item.id for item in schema.inputs] == list(declarations)
    for item in schema.inputs:
        declaration = declarations[item.id]
        metadata = declaration[1] if len(declaration) > 1 else {}
        assert item.io_type == declaration[0]
        assert item.optional is (item.id in old_inputs["optional"])
        for field in ("default", "min", "max", "step"):
            if field in metadata:
                assert getattr(item, field) == metadata[field]
    assert [(item.id, item.io_type, item.display_name) for item in schema.outputs] == [
        ("mosaic_mask", "MASK", "mosaic_mask"),
    ]
    assert old.RETURN_TYPES == ("MASK",)
    assert old.RETURN_NAMES == ("mosaic_mask",)
    assert getattr(old, "OUTPUT_NODE", False) is False
    assert schema.is_output_node is False
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.mosaic_mask_secure_test"
    )
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.frontend_permissions == frozenset()
    assert loaded.web_directory is None
    assert not loaded.routes

    pristine_grids = PACK / "grids"
    secure_grids = V2 / "grids"
    assert len(secure.TEMPLATES) == 16
    for size in range(5, 21):
        name = f"pattern{size}x{size}.png"
        assert (secure_grids / name).read_bytes() == (
            pristine_grids / name
        ).read_bytes()


@pytest.mark.parametrize(
    "filename,overrides",
    [
        ("pattern5x5.png", {"min_grid_size": 5, "max_grid_size": 5}),
        ("pattern10x10.png", {}),
        (
            "pattern20x20.png",
            {
                "top_n": 10,
                "kernel_size": 0,
                "threshold": 0.1,
                "min_grid_size": 5,
                "max_grid_size": 20,
            },
        ),
        (
            "pattern12x12.png",
            {"kernel_size": 100, "threshold": 0.8, "min_grid_size": 12},
        ),
    ],
)
def test_bundled_templates_and_parameter_edges_match_pristine(
    tmp_path, filename, overrides
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    image = _image(PACK / "grids" / filename)
    values = _inputs(image, **overrides)
    expected = pristine.NODE_CLASS_MAPPINGS[NODE_ID]().get_mask(**values)[0]
    actual = secure.MosaicMask.execute(**values).result[0]
    assert torch.equal(actual, expected)
    assert actual.shape == image.shape[:3]
    assert actual.dtype == torch.float32
    assert actual.device == image.device


def test_example_batch_and_seeded_images_are_differential(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    example = _image(PACK / "example" / "example.png")
    values = _inputs(
        example,
        top_n=3,
        kernel_size=7,
        threshold=0.3,
        min_grid_size=5,
        max_grid_size=20,
    )
    expected = pristine.NODE_CLASS_MAPPINGS[NODE_ID]().get_mask(**values)[0]
    actual = secure.MosaicMask.execute(**values).result[0]
    assert torch.equal(actual, expected)
    assert int(actual.sum()) > 0

    generator = torch.Generator().manual_seed(0xC0FFEE)
    batch = torch.rand((4, 64, 73, 4), generator=generator, dtype=torch.float64)
    for overrides in (
        {},
        {"top_n": 10, "kernel_size": 1, "threshold": 0.0},
        {"top_n": 2, "kernel_size": 4, "threshold": 1.0},
        {"min_grid_size": 7, "max_grid_size": 14},
    ):
        values = _inputs(batch, **overrides)
        expected = pristine.NODE_CLASS_MAPPINGS[NODE_ID]().get_mask(**values)[0]
        actual = secure.MosaicMask.execute(**values).result[0]
        assert torch.equal(actual, expected)
        assert actual.dtype == torch.float32


def test_connected_component_top_n_and_noop_branches_match_pristine(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    old = pristine.NODE_CLASS_MAPPINGS[NODE_ID]
    mask = np.zeros((32, 40), dtype=np.uint8)
    mask[1:3, 1:3] = 1
    mask[7:12, 5:9] = 1
    mask[18:30, 20:38] = 1
    for top_n in (1, 2, 3, 10):
        expected = old.keep_largest_component(mask.copy(), top_n)
        actual = secure.keep_largest_components(mask.copy(), top_n)
        assert np.array_equal(actual, expected)


@pytest.mark.parametrize(
    "image,match",
    [
        (None, "IMAGE tensor"),
        (torch.zeros((16, 16, 3)), "shape"),
        (torch.zeros((1, 16, 16, 2)), "shape"),
        (torch.empty((0, 16, 16, 3), device="meta"), "batch"),
        (torch.empty((65, 1, 1, 3), device="meta"), "batch"),
        (torch.empty((1, 8_193, 1, 3), device="meta"), "dimensions"),
        (torch.empty((1, 1, 1, 17), device="meta"), "channels"),
        (torch.empty((1, 8_192, 8_192, 3), device="meta"), "pixel"),
        (torch.zeros((1, 4, 4, 3), dtype=torch.int64), "floating"),
    ],
)
def test_malformed_and_excessive_images_fail_closed(image, match):
    with pytest.raises((TypeError, ValueError), match=match):
        _secure().MosaicMask.execute(**_inputs(image))


@pytest.mark.parametrize(
    "name,value,match",
    [
        ("top_n", 0, "top_n"),
        ("top_n", True, "integer"),
        ("kernel_size", 101, "kernel_size"),
        ("threshold", float("nan"), "finite"),
        ("threshold", 1.1, "finite"),
        ("min_grid_size", 4, "min_grid_size"),
        ("max_grid_size", 21, "max_grid_size"),
    ],
)
def test_invalid_numeric_inputs_fail_closed(name, value, match):
    values = _inputs(torch.zeros((1, 8, 8, 3)))
    values[name] = value
    with pytest.raises((TypeError, ValueError), match=match):
        _secure().MosaicMask.execute(**values)


def test_inverted_grid_bounds_fail_closed():
    with pytest.raises(ValueError, match="cannot exceed"):
        _secure().MosaicMask.execute(
            **_inputs(
                torch.zeros((1, 8, 8, 3)),
                min_grid_size=20,
                max_grid_size=5,
            )
        )


def test_real_guest_value_mode_mask_shape_raw_denial_and_isolation():
    secure = _secure()
    image = _image(V2 / "grids" / "pattern10x10.png")
    inputs = _inputs(image, min_grid_size=5)
    expected = secure.MosaicMask.execute(**inputs).result[0]

    async def run():
        refs = _sdk.InProcessRefResolver()
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        plan_inputs = dict(inputs)
        plan_inputs["image"] = image_ref
        plan = _sdk.ExecutionPlan(
            prompt_id="mosaic-mask",
            node_id="1",
            node_type=secure.MosaicMask.__name__,
            tier="sandbox",
            node_module=secure.MosaicMask.__module__,
            inputs=plan_inputs,
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        session = await GuestSession(
            "mosaic-mask-conversion", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=("raw",)
            )
            value = await refs.resolve(result.result[0])
            assert torch.equal(value, expected)
            assert value.dtype == torch.float32
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, _runtime(plan, refs), capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_real_outer_executor_preserves_declared_mask_type():
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.mosaic_mask_outer_test"
    )
    node = loaded.node_mappings[NODE_ID]
    assert node.RETURN_TYPES == ["MASK"]
    image = _image(V2 / "grids" / "pattern11x11.png")
    inputs = _inputs(image, min_grid_size=5)

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "mosaic-mask-outer", guest_runtime_root=V2
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
                prompt_id="mosaic-mask-outer",
                unique_id="1",
                obj=node,
                input_data_all={key: [value] for key, value in inputs.items()},
                func=node.FUNCTION,
                v3_data=None,
            )
            output = returns[0]
            assert isinstance(output.result[0], torch.Tensor)
            assert output.result[0].shape == image.shape[:3]
            assert output.result[0].dtype == torch.float32
            assert int(output.result[0].sum()) > 0
            assert tuple(node.RETURN_TYPES) == ("MASK",)
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_docs_resource_boundary_and_stubs_are_exact():
    source = (V2 / "nodes.py").read_text()
    for required in (
        "SDK_REFS = False",
        'SDK_PERMISSIONS = ("raw",)',
        "MAX_PIXELS",
        "GRID_DIR",
        "cv2.imread",
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
        "os.",
        "sys.",
        "ctx()",
        "_from_raw",
        "from_value",
    ):
        assert forbidden not in source
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert not (PACK / "LICENSE").exists()
    assert not (V2 / "LICENSE").exists()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-mosaic-mask/x7871eb8"
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
