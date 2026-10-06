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
import warnings

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
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = PACK_DB / "patches/image-tiled-nodes/x04481c4/image-tiled-nodes-x04481c4"
IDS = ("TiledImageSplitter", "TiledImageMerger")
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


def _import(name, root):
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _secure():
    return _import("_image_tiled_secure_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import("_image_tiled_pristine_test", root)


def _manifest(pack):
    nodes = {}
    for name, node in pack.NODE_CLASS_MAPPINGS.items():
        nodes[name] = {
            "class": name,
            "module": "nodes",
            "permissions": ["raw"],
            "sdk_refs": False,
            "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            "methods": {
                key: key in node.__dict__
                for key in (
                    "check_lazy_status",
                    "fingerprint_inputs",
                    "validate_inputs",
                )
            },
        }
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}


def _inputs(shape=(1, 97, 151, 3), dtype=torch.float32, **overrides):
    count = 1
    for size in shape:
        count *= size
    values = {
        "image": torch.linspace(-0.1, 1.1, count, dtype=dtype).reshape(shape),
        "tile_width": 64,
        "tile_height": 80,
        "overlap": 16,
        "feather_ratio": 0.5,
    }
    values.update(overrides)
    return values


def _split(values):
    return _secure().TiledImageSplitter.execute(**values).result


def _merge(images, tile_info):
    return _secure().TiledImageMerger.execute(images, tile_info).result


def _equal(actual, expected):
    assert len(actual) == len(expected)
    for a, b in zip(actual, expected):
        if isinstance(a, torch.Tensor):
            assert a.shape == b.shape and a.dtype == b.dtype and a.device == b.device
            torch.testing.assert_close(a, b, rtol=0, atol=0, equal_nan=True)
        else:
            assert a == b


def test_exact_actual_loader_schemas_census_manifest_and_algorithm(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == set(IDS)
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert (V2 / "algorithm.py").read_bytes() == (PACK / "nodes.py").read_bytes()
    assert not hasattr(old, "WEB_DIRECTORY") and not hasattr(new, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    for name in IDS:
        node, legacy = new.NODE_CLASS_MAPPINGS[name], old.NODE_CLASS_MAPPINGS[name]
        schema = node.GET_SCHEMA()
        schema.validate()
        assert (
            schema.node_id == name
            and schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[name]
        )
        assert schema.category == legacy.CATEGORY
        required = legacy.INPUT_TYPES()["required"]
        assert [x.id for x in schema.inputs] == list(required)
        for item in schema.inputs:
            declaration = required[item.id]
            assert item.io_type == declaration[0]
            if len(declaration) > 1:
                for key, value in declaration[1].items():
                    assert getattr(item, key) == value
        assert tuple(x.io_type for x in schema.outputs) == legacy.RETURN_TYPES
        assert tuple(x.display_name for x in schema.outputs) == legacy.RETURN_NAMES
        assert (
            not schema.is_output_node
            and node.SDK_REFS is False
            and node.SDK_PERMISSIONS == ("raw",)
        )
    extension = asyncio.run(new.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [
        new.NODE_CLASS_MAPPINGS[x] for x in IDS
    ]
    assert _manifest(new) == json.loads((V2 / "secure-nodes.json").read_text())
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.image_tiled_census")
    assert set(loaded.node_mappings) == set(IDS) and loaded.web_directory is None


@pytest.mark.parametrize(
    "shape,width,height,overlap",
    [
        ((1, 97, 151, 3), 64, 80, 16),
        ((2, 109, 141, 4), 80, 64, 0),
        ((1, 128, 128, 1), 64, 64, 16),
        ((1, 73, 79, 2), 128, 256, 4),
        ((1, 65, 67, 3), 64, 64, 63),
        ((1, 65, 67, 3), 64, 64, 64),
        ((1, 7, 11, 3), 64, 64, 128),
        ((2, 31, 79, 4), 64, 64, 32),
    ],
)
@pytest.mark.parametrize("ratio", [0.0, 0.1, 0.5])
def test_split_then_merge_exact_across_shapes_overlap_feather_and_fallback(
    tmp_path, shape, width, height, overlap, ratio
):
    values = _inputs(
        shape,
        tile_width=width,
        tile_height=height,
        overlap=overlap,
        feather_ratio=ratio,
    )
    old = _pristine(tmp_path)
    expected = old.NODE_CLASS_MAPPINGS[IDS[0]]().split(**values)
    actual = _split(values)
    _equal(actual, expected)
    _equal(
        _merge(actual[0], actual[2]),
        old.NODE_CLASS_MAPPINGS[IDS[1]]().merge(expected[0], expected[2]),
    )


@pytest.mark.parametrize("dtype", [torch.float16, torch.float64, torch.bfloat16])
@pytest.mark.parametrize("ratio", [0.0, 0.5])
def test_dtype_device_noncontiguous_batches_and_merger_float32(tmp_path, dtype, ratio):
    values = _inputs((2, 97, 151, 4), dtype, feather_ratio=ratio)
    values["image"] = values["image"].transpose(1, 2)
    assert not values["image"].is_contiguous()
    old = _pristine(tmp_path)
    expected = old.NODE_CLASS_MAPPINGS[IDS[0]]().split(**values)
    actual = _split(values)
    _equal(actual, expected)
    assert actual[0].dtype == dtype and actual[1].dtype == torch.float32
    merged = _merge(actual[0], actual[2])
    _equal(merged, old.NODE_CLASS_MAPPINGS[IDS[1]]().merge(expected[0], expected[2]))
    assert merged[0].dtype == torch.float32


@pytest.mark.parametrize(
    "transform",
    ["resized", "missing", "extra", "zero", "no_positions", "minimal_metadata"],
)
def test_merger_resizes_partial_extra_zero_and_optional_metadata(tmp_path, transform):
    tiles, _, info = _split(_inputs())
    if transform == "resized":
        tiles = tiles[:, ::2, ::2, :]
    elif transform == "missing":
        tiles = tiles[:1]
    elif transform == "extra":
        tiles = torch.cat([tiles, tiles[:1]], dim=0)
    elif transform == "zero":
        tiles = tiles[:0]
    elif transform == "no_positions":
        info["positions"] = []
    else:
        info.pop("batch_size")
        for pos in info["positions"]:
            pos.pop("row")
            pos.pop("col")
    expected = (
        _pristine(tmp_path)
        .NODE_CLASS_MAPPINGS[IDS[1]]()
        .merge(tiles, copy.deepcopy(info))
    )
    _equal(_merge(tiles, info), expected)
    if transform in ("zero", "no_positions"):
        assert torch.count_nonzero(expected[0]) == 0


def test_order_edge_backshift_corner_feather_and_overlap_ratio():
    tiles, masks, info = _split(_inputs((2, 97, 151, 3)))
    assert [(p["batch_index"], p["row"], p["col"]) for p in info["positions"]] == [
        (b, r, c) for b in range(2) for r in range(2) for c in range(3)
    ]
    assert [(p["x"], p["y"]) for p in info["positions"][:6]] == [
        (0, 0),
        (48, 0),
        (87, 0),
        (0, 17),
        (48, 17),
        (87, 17),
    ]
    assert masks.shape == (12, 80, 64)
    gradient = torch.linspace(0, 1, 8)
    assert torch.equal(masks[4, :8, :8], gradient[:, None] * gradient[None, :])
    assert masks[4, 8, 8] == 1
    assert tiles.shape == (12, 80, 64, 3)


def test_empty_grid_fallback_returns_original_and_2d_cpu_mask():
    values = _inputs((2, 7, 11, 4), overlap=128)
    tiles, mask, info = _split(values)
    assert tiles is values["image"] and mask.shape == (7, 11)
    assert mask.dtype == torch.float32 and mask.device.type == "cpu"
    assert info["positions"] == [] and info["batch_size"] == 2
    assert torch.count_nonzero(mask) == 0


def test_zero_tile_rgba_input_falls_back_to_rgb_in_real_guest(tmp_path):
    tiles, _, info = _split(_inputs((1, 97, 151, 4)))
    empty = tiles[:0]
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS[IDS[1]]().merge(empty, info)
    _equal(_merge(empty, info), expected)
    assert expected[0].shape == (1, 97, 151, 3)

    async def run():
        values = {"images": empty, "tile_info": info}
        _equal(await _guest(V2, IDS[1], values), expected)
        _equal(await _outer(IDS[1], values), expected)

    asyncio.run(run())


def test_nan_inf_pixels_preserve_original_arithmetic(tmp_path):
    values = _inputs()
    values["image"][0, 0, 0, :] = torch.tensor(
        [float("nan"), float("inf"), -float("inf")]
    )
    old = _pristine(tmp_path)
    expected = old.NODE_CLASS_MAPPINGS[IDS[0]]().split(**values)
    actual = _split(values)
    _equal(actual, expected)
    _equal(
        _merge(actual[0], actual[2]),
        old.NODE_CLASS_MAPPINGS[IDS[1]]().merge(expected[0], expected[2]),
    )


def test_sparse_empty_geometry_excessive_input_and_extreme_control_fail_before_compute(
    monkeypatch,
):
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("compute entered for invalid image or control")

    monkeypatch.setattr(pack.nodes.algorithm.TiledImageSplitter, "split", forbidden)
    for value in [
        torch.zeros(1, 3, 4, 3).to_sparse(),
        torch.zeros(1, 0, 4, 3),
        torch.empty(1, 8193, 1, 3, device="meta"),
        torch.empty(1, 4096, 4096, 3, device="meta"),
    ]:
        with pytest.raises((TypeError, ValueError)):
            pack.TiledImageSplitter.execute(**_inputs(image=value))
    with pytest.raises(ValueError, match="feather_ratio"):
        pack.TiledImageSplitter.execute(**_inputs(feather_ratio=10**1000))


def test_input_tile_metadata_rng_and_warning_policy_are_unchanged():
    values = _inputs()
    original = values["image"].clone()
    rng, filters = torch.random.get_rng_state().clone(), list(warnings.filters)
    split = _split(values)
    info = copy.deepcopy(split[2])
    tiles = split[0].clone()
    _equal(_split(values), split)
    _equal(_merge(split[0], split[2]), _merge(split[0], split[2]))
    assert torch.equal(values["image"], original) and torch.equal(split[0], tiles)
    assert split[2] == info
    assert (
        torch.equal(rng, torch.random.get_rng_state()) and warnings.filters == filters
    )


@pytest.mark.parametrize(
    "override",
    [
        {"tile_width": True},
        {"tile_height": 63},
        {"tile_width": 8193},
        {"overlap": -1},
        {"overlap": 513},
        {"feather_ratio": True},
        {"feather_ratio": -0.1},
        {"feather_ratio": 0.51},
        {"feather_ratio": float("nan")},
        {"feather_ratio": float("inf")},
        {"image": "image"},
        {"image": torch.zeros(1, 3, 4)},
        {"image": torch.zeros(0, 3, 4, 3)},
        {"image": torch.zeros(65, 3, 4, 3)},
        {"image": torch.ones(1, 3, 4, 5)},
        {"image": torch.ones(1, 3, 4, 3, dtype=torch.int64)},
    ],
)
def test_split_invalid_inputs(override):
    values = _inputs(**override)
    with pytest.raises((TypeError, ValueError)):
        _split(values)


@pytest.mark.parametrize(
    "change",
    [
        ("original_height", 0),
        ("original_width", 8193),
        ("batch_size", True),
        ("batch_size", 65),
        ("tile_width", 0),
        ("tile_height", 8193),
        ("overlap", 513),
        ("feather_ratio", float("nan")),
        ("positions", "list"),
        ("positions", [{}]),
        ("positions", [None]),
        ("positions", [{"batch_index": -1, "x": 0, "y": 0}]),
        ("positions", [{"batch_index": 1, "x": 0, "y": 0}]),
        ("positions", [{"batch_index": 0, "x": -1, "y": 0}]),
        ("positions", [{"batch_index": 0, "x": 150, "y": 0}]),
        ("positions", [{"batch_index": 0, "x": 0, "y": 0, "row": True}]),
        ("arbitrary_path", "/tmp/not-authority"),
    ],
)
def test_hostile_tile_metadata_fails_before_merger(change, monkeypatch):
    tiles, _, info = _split(_inputs())
    key, value = change
    info[key] = value
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("merge compute entered for hostile metadata")

    monkeypatch.setattr(pack.nodes.algorithm.TiledImageMerger, "merge", forbidden)
    with pytest.raises((TypeError, ValueError)):
        pack.TiledImageMerger.execute(tiles, info)


def test_projected_tile_storage_and_merge_work_bounds_before_compute(monkeypatch):
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("tensor algorithm entered before projected bounds")

    monkeypatch.setattr(pack.nodes.algorithm.TiledImageSplitter, "split", forbidden)
    monkeypatch.setattr(pack.nodes.algorithm.TiledImageMerger, "merge", forbidden)
    with pytest.raises(ValueError, match="tile count"):
        pack.TiledImageSplitter.execute(
            **_inputs((1, 100, 100, 3), tile_height=64, overlap=64)
        )
    with pytest.raises(ValueError, match="row loop"):
        pack.TiledImageSplitter.execute(
            **_inputs((2, 8192, 11, 1), tile_height=64, overlap=64)
        )
    monkeypatch.setattr(pack.nodes, "MAX_WORK_ELEMENTS", 100)
    with pytest.raises(ValueError, match="split output"):
        pack.TiledImageSplitter.execute(**_inputs())
    with pytest.raises(ValueError, match="merge output/work"):
        pack.TiledImageMerger.execute(
            torch.ones(1, 64, 64, 3),
            {
                "original_height": 100,
                "original_width": 100,
                "tile_width": 64,
                "tile_height": 64,
                "overlap": 16,
                "feather_ratio": 0.5,
                "positions": [{"batch_index": 0, "x": 0, "y": 0}],
            },
        )
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 10)
    with pytest.raises(ValueError, match="input element"):
        pack.TiledImageSplitter.execute(**_inputs())


def test_metadata_count_missing_fields_and_non_dict_fail_closed():
    tiles, _, info = _split(_inputs())
    for invalid in [None, {}, {**info, "positions": info["positions"] * 100}]:
        with pytest.raises((TypeError, ValueError)):
            _merge(tiles, invalid)


async def _guest(root, node_id, values, label="image-tiled", deny=False):
    pack = _import("_image_tiled_guest_source", root)
    refs = _sdk.InProcessRefResolver()
    wrapped = dict(values)
    image_key = "image" if node_id == IDS[0] else "images"
    wrapped[image_key] = _sdk.ImageRef._wrap(
        await refs.create("IMAGE", values[image_key])
    )
    node = pack.NODE_CLASS_MAPPINGS[node_id]
    plan = _sdk.ExecutionPlan(
        prompt_id=label,
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
        refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps()
    )
    session = await GuestSession(label, guest_runtime_root=root).start()
    try:
        result = await session.execute(plan, runtime, capabilities=("raw",))
        actual = [
            await refs.resolve(x) if isinstance(x, _sdk.Ref) else x
            for x in result.result
        ]
        assert session.last_guest_pid not in (None, os.getpid())
        if deny:
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
        return actual
    finally:
        await session.kill()


async def _outer(node_id, values):
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.image_tiled_outer_" + node_id
    )
    outer = loaded.node_mappings[node_id]
    expected_types = ("IMAGE", "MASK", "TILE_INFO") if node_id == IDS[0] else ("IMAGE",)
    assert tuple(outer.RETURN_TYPES) == expected_types
    previous = _sdk.providers.execution_backend

    class Backend:
        session = None

        async def dispatch(self, plan, local_call, runtime):
            self.session = await GuestSession(
                "image-tiled-outer", guest_runtime_root=V2
            ).start()
            plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
            return await self.session.execute(plan, runtime, capabilities=("raw",))

    backend = Backend()
    _sdk.providers.register_execution_backend(backend)
    try:
        result = await execution._async_map_node_over_list(
            prompt_id="image-tiled-outer",
            unique_id="1",
            obj=outer,
            input_data_all={key: [value] for key, value in values.items()},
            func=outer.FUNCTION,
            v3_data=None,
        )
        return result[0].result
    finally:
        _sdk.providers.register_execution_backend(previous)
        if backend.session is not None:
            await backend.session.kill()


@pytest.mark.parametrize("fallback", [False, True])
def test_real_guest_split_merge_raw_denial_and_outer_metadata_types(fallback):
    values = _inputs((1, 7, 11, 4), overlap=128) if fallback else _inputs()
    expected = _split(values)

    async def run():
        split = await _guest(V2, IDS[0], values, deny=True)
        _equal(split, expected)
        _equal(await _outer(IDS[0], values), expected)
        merger = {"images": split[0], "tile_info": split[2]}
        merged = _merge(**merger)
        _equal(await _guest(V2, IDS[1], merger, deny=True), merged)
        _equal(await _outer(IDS[1], merger), merged)

    asyncio.run(run())


def _tree(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_reset_to_fresh_pack_and_guest_needs_no_durable_state(tmp_path):
    first, second = tmp_path / "render-one", tmp_path / "render-two"
    shutil.copytree(V2, first)
    shutil.copytree(V2, second)
    values = _inputs()

    async def run():
        split = await _guest(first, IDS[0], values, label="tiled-user-a")
        _equal(split, _split(values))
        _equal(await _guest(second, IDS[0], values, label="tiled-user-a-fresh"), split)
        _equal(
            await _guest(
                second,
                IDS[1],
                {"images": split[0], "tile_info": split[2]},
                label="tiled-fresh-merge",
            ),
            _merge(split[0], split[2]),
        )
        other = _inputs((2, 83, 117, 4), overlap=0)
        _equal(await _guest(second, IDS[0], other, label="tiled-user-b"), _split(other))

    asyncio.run(run())
    assert _tree(first) == _tree(second) == _tree(V2)


def test_license_stubs_authority_and_persistence_ledger():
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    for filename, digest in [("comfy-api.d.ts", DTS_SHA), ("comfy-api.pyi", PYI_SHA)]:
        assert hashlib.sha256((V2 / filename).read_bytes()).hexdigest() == digest
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert "04481c4ca008dfd394d9b5b9b705218351670b9c" in report
    assert "Persistence disposition: no durable state" in report
    source = "\n".join(
        (V2 / name).read_text() for name in ("__init__.py", "nodes.py", "algorithm.py")
    )
    for forbidden in [
        "folder_paths",
        "comfy.utils",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "os.",
        "sys.",
        "_from_raw",
        "ctx()",
    ]:
        assert forbidden not in source


def test_byte_exact_patch_roundtrip(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf8") == diff
    fresh = tmp_path / "image-tiled-nodes/x04481c4"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_cache_hygiene():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))
