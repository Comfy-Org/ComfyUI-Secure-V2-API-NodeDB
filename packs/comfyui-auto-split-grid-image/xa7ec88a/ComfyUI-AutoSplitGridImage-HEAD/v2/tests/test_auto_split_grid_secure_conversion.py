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
COMMIT = "a7ec88a33a7d861b998b87668f6e45046b172364"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
NODE_IDS = {"GridImageSplitter", "EvenImageResizer"}
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    "2024-10-23_10-59-03.png",
    "ComfyUI_temp_zbacb_00001_.png",
    "Screenshot_2024-12-13_15-30-41.png",
    "EvenImageResizer.py",
    "GridImageSplitter.py",
    "LICENSE",
    "README.md",
    "__init__.py",
    "example.json",
    "pyproject.toml",
    "requirements.txt",
}
PAIR = PACK_DB / (
    "patches/comfyui-auto-split-grid-image/xa7ec88a/"
    "comfyui-auto-split-grid-image-xa7ec88a"
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
    return _import_package("_secure_auto_split_grid_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_auto_split_grid_test", root)


def _manifest(pack):
    nodes = {}
    for node_id, node in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
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
        }
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}


def _tree(root):
    return {
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file()
        and not any(
            part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in item.relative_to(root).parts
        )
    }


def _image(batch=1, height=120, width=168, dtype=torch.float32):
    yy, xx = torch.meshgrid(torch.arange(height), torch.arange(width), indexing="ij")
    image = torch.stack(
        (
            0.3 + 0.6 * (xx % 31) / 31,
            0.25 + 0.7 * (yy % 29) / 29,
            0.3 + 0.6 * ((xx + yy) % 37) / 37,
        ),
        dim=-1,
    ).to(dtype)
    return image.unsqueeze(0).repeat(batch, 1, 1, 1)


def _grid_inputs(image=None, **overrides):
    values = {
        "image": _image() if image is None else image,
        "rows": 2,
        "cols": 3,
        "row_split_method": "uniform",
        "col_split_method": "uniform",
    }
    values.update(overrides)
    return values


def _assert_equal(actual, expected):
    assert len(actual) == len(expected)
    for got, wanted in zip(actual, expected, strict=True):
        assert got.shape == wanted.shape
        assert got.dtype == wanted.dtype
        assert got.device == wanted.device
        assert torch.equal(got, wanted)


def test_actual_loader_census_schema_manifest_and_frontend_absence(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not hasattr(secure, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    for node_id in NODE_IDS:
        old = pristine.NODE_CLASS_MAPPINGS[node_id]
        node = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = node.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.category == old.CATEGORY
        assert tuple(output.io_type for output in schema.outputs) == old.RETURN_TYPES
        assert node.SDK_REFS is False
        assert node.SDK_PERMISSIONS == ("raw",)
        old_inputs = old.INPUT_TYPES()["required"]
        assert [item.id for item in schema.inputs] == list(old_inputs)
        for item in schema.inputs:
            old_input = old_inputs[item.id]
            if isinstance(old_input[0], list):
                assert list(item.options) == old_input[0]
            elif len(old_input) > 1:
                for attribute in ("default", "min", "max"):
                    assert getattr(item, attribute) == old_input[1][attribute]
    extension = asyncio.run(secure.comfy_entrypoint())
    assert set(asyncio.run(extension.get_node_list())) == set(
        secure.NODE_CLASS_MAPPINGS.values()
    )
    assert _manifest(secure) == json.loads((V2 / "secure-nodes.json").read_text())
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.auto_split_grid_test")
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory is None


@pytest.mark.parametrize("rows,cols", [(1, 1), (2, 3), (3, 2)])
@pytest.mark.parametrize("row_method", ["uniform", "edge_detection"])
@pytest.mark.parametrize("col_method", ["uniform", "edge_detection"])
def test_every_grid_method_and_cell_order_matches_pristine(
    tmp_path, rows, cols, row_method, col_method
):
    old = _pristine(tmp_path).GridImageSplitter()
    values = _grid_inputs(
        rows=rows, cols=cols, row_split_method=row_method, col_split_method=col_method
    )
    expected = old.split_image(**values)
    actual = _secure().GridImageSplitter.execute(**values).result
    _assert_equal(actual, expected)
    assert actual[1].shape[0] == rows * cols


def test_first_frame_cells_and_full_batch_preview_are_preserved(tmp_path):
    image = _image(batch=2, dtype=torch.float64)
    image[1] = image[1].flip(0)
    original = image.clone()
    values = _grid_inputs(image)
    expected = _pristine(tmp_path).GridImageSplitter().split_image(**values)
    actual = _secure().GridImageSplitter.execute(**values).result
    _assert_equal(actual, expected)
    single = _secure().GridImageSplitter.execute(**_grid_inputs(image[:1])).result
    assert torch.equal(actual[1], single[1])
    assert actual[0].shape[0] == 2
    assert actual[0].dtype == torch.float64
    assert actual[1].dtype == torch.float32
    assert torch.equal(
        actual[0][:, :, 56:58], torch.tensor([0.0, 1.0, 0.0]).expand(2, 120, 2, 3)
    )
    assert torch.equal(image, original)


@pytest.mark.parametrize("height,width", [(32, 40), (33, 40), (32, 41), (33, 41)])
@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_even_crop_is_bit_exact_and_preserves_dtype_batch(
    tmp_path, height, width, dtype
):
    image = _image(batch=3, height=height, width=width, dtype=dtype)
    expected = _pristine(tmp_path).EvenImageResizer().resize_to_even(image)
    actual = _secure().EvenImageResizer.execute(image).result
    _assert_equal(actual, expected)
    assert actual[0].shape == (3, height - height % 2, width - width % 2, 3)


def test_hwc_normalization_matches_pristine(tmp_path):
    old = _pristine(tmp_path)
    secure = _secure()
    image = _image()[0]
    _assert_equal(
        secure.GridImageSplitter.execute(**_grid_inputs(image)).result,
        old.GridImageSplitter().split_image(**_grid_inputs(image)),
    )
    _assert_equal(
        secure.EvenImageResizer.execute(image).result,
        old.EvenImageResizer().resize_to_even(image),
    )


def test_copied_algorithms_helpers_border_trim_and_lanczos_are_exact(tmp_path):
    old = _pristine(tmp_path).GridImageSplitter()
    new = _secure().nodes._LegacyGridImageSplitter()
    assert (PACK / "GridImageSplitter.py").read_bytes() == (
        V2 / "grid_algorithm.py"
    ).read_bytes()
    assert (PACK / "EvenImageResizer.py").read_bytes() == (
        V2 / "even_algorithm.py"
    ).read_bytes()
    array = (_image()[0].numpy() * 255).astype(np.uint8)
    bordered = np.pad(array, ((22, 22), (22, 22), (0, 0)), constant_values=0)
    assert np.array_equal(
        old.remove_external_borders(bordered), new.remove_external_borders(bordered)
    )
    for vertical in (False, True):
        assert old.detect_split_borders(array, vertical) == new.detect_split_borders(
            array, vertical
        )
        assert old.adjust_split_line(array, 60, vertical) == new.adjust_split_line(
            array, 60, vertical
        )
        for method in ("uniform", "edge_detection"):
            assert old.find_split_positions(
                array, 2, vertical, method
            ) == new.find_split_positions(array, 2, vertical, method)
    values = _grid_inputs(torch.from_numpy(bordered).float().unsqueeze(0) / 255.0)
    _assert_equal(
        _secure().GridImageSplitter.execute(**values).result, old.split_image(**values)
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("rows", 0),
        ("rows", True),
        ("rows", 11),
        ("cols", 0),
        ("cols", 2.5),
        ("row_split_method", "guess"),
        ("col_split_method", None),
    ],
)
def test_invalid_controls_fail_closed(name, value):
    with pytest.raises((TypeError, ValueError), match=name):
        _secure().GridImageSplitter.execute(**_grid_inputs(**{name: value}))


@pytest.mark.parametrize(
    "image",
    [
        torch.zeros((1, 1, 20, 3)),
        torch.zeros((1, 20, 20, 4)),
        torch.zeros((1, 20, 20, 3), dtype=torch.int32),
        torch.full((1, 20, 20, 3), float("nan")),
        torch.zeros((65, 2, 2, 3)),
    ],
)
def test_invalid_images_fail_closed_for_both_nodes(image):
    secure = _secure()
    for node_id, values in (
        ("GridImageSplitter", _grid_inputs(image)),
        ("EvenImageResizer", {"image": image}),
    ):
        with pytest.raises((TypeError, ValueError), match="image"):
            secure.NODE_CLASS_MAPPINGS[node_id].execute(**values)


def test_tiny_dense_grid_and_resource_bounds_fail_closed(monkeypatch):
    secure = _secure()
    with pytest.raises(ValueError, match="small"):
        secure.GridImageSplitter.execute(
            **_grid_inputs(_image(height=8, width=8), rows=10)
        )
    monkeypatch.setattr(secure.nodes, "MAX_OUTPUT_PIXELS", 100)
    with pytest.raises(ValueError, match="output pixel"):
        secure.GridImageSplitter.execute(**_grid_inputs())
    monkeypatch.setattr(secure.nodes, "MAX_INPUT_PIXELS", 100)
    with pytest.raises(ValueError, match="input pixel"):
        secure.EvenImageResizer.execute(_image())
    monkeypatch.setattr(secure.nodes, "MAX_DIMENSION", 10)
    with pytest.raises(ValueError, match="dimensions"):
        secure.EvenImageResizer.execute(_image())


def test_repeated_calls_do_not_mutate_inputs_or_rng():
    secure = _secure()
    values = _grid_inputs()
    original = values["image"].clone()
    rng = torch.random.get_rng_state().clone()
    numpy_rng = np.random.get_state()
    first = secure.GridImageSplitter.execute(**values).result
    second = secure.GridImageSplitter.execute(**values).result
    _assert_equal(first, second)
    assert torch.equal(original, values["image"])
    assert torch.equal(rng, torch.random.get_rng_state())
    after = np.random.get_state()
    assert numpy_rng[0] == after[0]
    assert np.array_equal(numpy_rng[1], after[1])
    assert numpy_rng[2:] == after[2:]


def test_dense_grid_that_creates_empty_cells_remains_an_error(tmp_path):
    values = _grid_inputs(_image(height=20, width=20), rows=10, cols=10)
    old = _pristine(tmp_path).GridImageSplitter()
    with pytest.raises(ZeroDivisionError):
        old.split_image(**values)
    with pytest.raises(ZeroDivisionError):
        _secure().GridImageSplitter.execute(**values)


@pytest.mark.parametrize("node_id", sorted(NODE_IDS))
def test_real_guest_value_mode_raw_denial_and_outer_image_typing(node_id):
    secure = _secure()
    node = secure.NODE_CLASS_MAPPINGS[node_id]
    values = (
        _grid_inputs()
        if node_id == "GridImageSplitter"
        else {"image": _image(height=33, width=41)}
    )
    expected = node.execute(**values).result

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("auto-split-grid", guest_runtime_root=V2).start()
        try:
            wrapped = dict(values)
            wrapped["image"] = _sdk.ImageRef._wrap(
                await refs.create("IMAGE", values["image"])
            )
            plan = _sdk.ExecutionPlan(
                prompt_id="auto-split-grid",
                node_id="1",
                node_type=node_id,
                tier="sandbox",
                node_module=node.__module__,
                inputs=wrapped,
                input_mode="values",
                permissions=("raw",),
                method="execute",
            )
            runtime = _sdk.Runtime(
                refs=refs,
                ctx=_sdk.InProcessCtxProvider().build(plan),
                ops=_sdk.InProcessOps(),
            )
            result = await session.execute(plan, runtime, capabilities=("raw",))
            actual = tuple([await refs.resolve(item) for item in result.result])
            _assert_equal(actual, expected)
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
            if node_id == "GridImageSplitter":
                plan.inputs["rows"] = 0
                with pytest.raises(Exception, match="rows"):
                    await session.execute(plan, runtime, capabilities=("raw",))
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

        loaded = packdb.load_pack(
            SNAPSHOT, mount_name=f"custom_nodes.auto_split_outer_{node_id}"
        )
        outer_node = loaded.node_mappings[node_id]
        assert tuple(outer_node.RETURN_TYPES) == tuple(node.RETURN_TYPES)
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "auto-split-outer", guest_runtime_root=V2
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
                prompt_id="auto-split-grid-outer",
                unique_id="1",
                obj=outer_node,
                input_data_all={key: [value] for key, value in values.items()},
                func=outer_node.FUNCTION,
                v3_data=None,
            )
            output = returns[0]
            _assert_equal(output.result, expected)
            for item in output.result:
                assert isinstance(item, torch.Tensor)
                assert item.ndim == 4 and item.shape[-1] == 3
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_license_canonical_stubs_and_documentation():
    sources = "\n".join(
        (V2 / name).read_text()
        for name in ("nodes.py", "grid_algorithm.py", "even_algorithm.py")
    )
    for forbidden in (
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
    ):
        assert forbidden not in sources
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert "first" in (V2 / "SECURE_CONVERSION.md").read_text()


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-auto-split-grid-image/xa7ec88a"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_no_generated_cache_artifacts():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))
