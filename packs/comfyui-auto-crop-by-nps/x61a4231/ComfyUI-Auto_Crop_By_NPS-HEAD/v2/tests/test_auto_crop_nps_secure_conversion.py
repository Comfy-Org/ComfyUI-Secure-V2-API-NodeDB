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
from PIL import Image

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
PAIR = (
    PACK_DB
    / "patches/comfyui-auto-crop-by-nps/x61a4231/comfyui-auto-crop-by-nps-x61a4231"
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
    return _import("_crop_nps_secure_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    policy = Image.MAX_IMAGE_PIXELS
    try:
        return _import("_crop_nps_pristine_test", root)
    finally:
        Image.MAX_IMAGE_PIXELS = policy


def _manifest(pack):
    node = pack.AutoCropByNPS
    return {
        "format": FORMAT,
        "nodes": {
            "AutoCropByNPS": {
                "class": "AutoCropByNPS",
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
        },
        "runtime": manifest_declaration(V2),
    }


def _inputs(channels=3, dtype=torch.float32, **overrides):
    values = {
        name: 0.0
        for name in ("crop_top", "crop_bottom", "crop_left", "crop_right", "rotation")
    }
    values.update(
        image=torch.linspace(-0.1, 1.1, 2 * 8 * 11 * channels, dtype=dtype).reshape(
            2, 8, 11, channels
        ),
        mask=torch.linspace(0, 1, 3 * 6 * 9, dtype=dtype).reshape(3, 6, 9),
    )
    values.update(overrides)
    return values


def _execute(values):
    return _secure().AutoCropByNPS.execute(**values).result


def _equal(actual, expected):
    assert len(actual) == len(expected) == 2
    for a, b in zip(actual, expected):
        if b is None:
            assert a is None
        else:
            assert a.shape == b.shape
            assert a.dtype == b.dtype == torch.float32
            assert a.device == b.device
            assert torch.equal(a, b)


def test_exact_actual_loader_schema_and_manifest_census(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert (
        set(old.NODE_CLASS_MAPPINGS)
        == set(new.NODE_CLASS_MAPPINGS)
        == {"AutoCropByNPS"}
    )
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert {
        p.relative_to(PACK).as_posix()
        for p in PACK.rglob("*")
        if p.is_file() and "v2" not in p.relative_to(PACK).parts
    } == {"README.md", "__init__.py", "Auto_Crop_By_NPS.py"}
    assert not hasattr(old, "WEB_DIRECTORY") and not hasattr(new, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    schema = new.AutoCropByNPS.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "AutoCropByNPS"
    assert schema.display_name == "Auto Crop by NPS"
    assert schema.category == old.AutoCropByNPS.CATEGORY
    required = old.AutoCropByNPS.INPUT_TYPES()["required"]
    assert [x.id for x in schema.inputs] == [*required, "image", "mask"]
    for item in schema.inputs[:5]:
        assert item.io_type == "FLOAT" and not item.optional
        opts = required[item.id][1]
        assert (item.default, item.min, item.max, item.step) == (
            opts["default"],
            opts["min"],
            opts["max"],
            opts["step"],
        )
        assert item.display_mode.value == "slider"
    assert [x.io_type for x in schema.inputs[5:]] == ["IMAGE", "MASK"]
    assert all(x.optional for x in schema.inputs[5:])
    assert tuple(x.io_type for x in schema.outputs) == old.AutoCropByNPS.RETURN_TYPES
    assert (
        tuple(x.display_name for x in schema.outputs) == old.AutoCropByNPS.RETURN_NAMES
    )
    assert not schema.is_output_node
    assert (
        new.AutoCropByNPS.SDK_REFS is False
        and new.AutoCropByNPS.SDK_PERMISSIONS == ("raw",)
    )
    assert _manifest(new) == json.loads((V2 / "secure-nodes.json").read_text())
    extension = asyncio.run(new.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [new.AutoCropByNPS]
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.crop_nps_census")
    assert (
        set(loaded.node_mappings) == {"AutoCropByNPS"} and loaded.web_directory is None
    )


@pytest.mark.parametrize("channels", [3, 4])
@pytest.mark.parametrize(
    "controls",
    [
        {},
        {"crop_top": -0.25, "crop_right": -0.36},
        {"crop_top": 0.5, "crop_left": 0.36, "crop_bottom": 0.25, "crop_right": 0.18},
        {
            "crop_top": -0.25,
            "crop_bottom": 0.5,
            "crop_left": 0.3,
            "crop_right": -0.2,
            "rotation": 37,
        },
        {"rotation": 90},
        {"rotation": -90},
        {"rotation": 180},
        {"rotation": -17.25},
        {"crop_left": -1.0, "crop_right": 1.0},
    ],
)
def test_pixel_exact_crop_expand_rotate_and_rgba(tmp_path, channels, controls):
    values = _inputs(channels, **controls)
    expected = _pristine(tmp_path).AutoCropByNPS().auto_crop_images(**values)
    _equal(_execute(values), expected)


@pytest.mark.parametrize("dtype", [torch.float16, torch.float32, torch.float64])
@pytest.mark.parametrize("surface", ["both", "image", "mask", "none", "empty"])
def test_optional_independent_geometry_empty_batches_and_dtype(
    tmp_path, dtype, surface
):
    values = _inputs(dtype=dtype, crop_top=0.2, rotation=-12)
    if surface in ("mask", "none"):
        values["image"] = None
    if surface in ("image", "none"):
        values["mask"] = None
    if surface == "empty":
        values["image"] = values["image"][:0]
        values["mask"] = values["mask"][:0]
    expected = _pristine(tmp_path).AutoCropByNPS().auto_crop_images(**values)
    _equal(_execute(values), expected)


@pytest.mark.parametrize("size", [(7, 11), (8, 12), (3, 4)])
@pytest.mark.parametrize(
    "rotation", [-180, -90, -45, -17.25, 0, 0.01, 33.3, 90, 179.999]
)
def test_preallocation_rotated_geometry_matches_actual_pillow(size, rotation):
    node = _secure().nodes
    expected = Image.new("RGB", size).rotate(-rotation, expand=True).size
    assert node._rotated_size(*size, rotation) == expected


def test_fill_quantization_clockwise_orientation_and_input_policy_isolation():
    policy = Image.MAX_IMAGE_PIXELS
    values = _inputs(
        image=torch.tensor(
            [[[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], [[0.0, 0.0, 1.0], [1.0, 1.0, 0.0]]]]
        ),
        mask=None,
        rotation=90,
    )
    original = values["image"].clone()
    rng = torch.random.get_rng_state().clone()
    result = _execute(values)
    assert torch.equal(result[0], torch.rot90(original, k=-1, dims=(1, 2)))
    white = _execute(_inputs(crop_top=0.5, crop_left=0.5))
    assert torch.all(white[0][:, 0] == 1) and torch.all(white[1][:, 0] == 1)
    assert torch.equal(original, values["image"])
    assert torch.equal(rng, torch.random.get_rng_state())
    assert Image.MAX_IMAGE_PIXELS == policy


@pytest.mark.parametrize(
    "override",
    [
        {"crop_top": True},
        {"crop_left": -1.1},
        {"rotation": 181},
        {"rotation": float("nan")},
        {"crop_bottom": float("inf")},
        {"crop_right": "0"},
        {"image": "not a tensor"},
        {"image": torch.zeros(1, 8, 11, 2)},
        {"mask": torch.zeros(6, 9)},
        {"mask": torch.ones(1, 6, 9, dtype=torch.int64)},
        {"image": torch.full((1, 8, 11, 3), float("nan"))},
        {"mask": torch.full((1, 6, 9), float("inf"))},
        {"image": torch.zeros(65, 8, 11, 3)},
        {"image": torch.zeros(1, 1, 11, 3)},
        {"crop_left": -0.8, "crop_right": -0.8},
        {"crop_left": -1.0},
    ],
)
def test_invalid_controls_layouts_and_crops_fail_explicitly(override):
    values = _inputs(**override)
    with pytest.raises((ValueError, TypeError)):
        _execute(values)


def test_geometry_and_element_bounds_reject_before_algorithm_and_pillow(monkeypatch):
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("entered pixel algorithm before resource validation")

    monkeypatch.setattr(pack.nodes._Algorithm, "auto_crop_images", forbidden)
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 100)
    with pytest.raises(ValueError, match="input"):
        pack.AutoCropByNPS.execute(**_inputs())
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 2000)
    with pytest.raises(ValueError, match="output"):
        pack.AutoCropByNPS.execute(
            **_inputs(crop_top=1, crop_bottom=1, crop_left=1, crop_right=1)
        )
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 16_777_216)
    monkeypatch.setattr(pack.nodes, "MAX_DIMENSION", 12)
    with pytest.raises(ValueError, match="rotated"):
        pack.AutoCropByNPS.execute(**_inputs(rotation=45))


async def _guest(root, values, label="crop-nps-render", deny=False):
    pack = _import("_crop_nps_guest_source", root)
    node = pack.AutoCropByNPS
    refs = _sdk.InProcessRefResolver()
    wrapped = dict(values)
    for key, kind, cls in [
        ("image", "IMAGE", _sdk.ImageRef),
        ("mask", "MASK", _sdk.MaskRef),
    ]:
        if values[key] is not None:
            wrapped[key] = cls._wrap(await refs.create(kind, values[key]))
    plan = _sdk.ExecutionPlan(
        prompt_id=label,
        node_id="1",
        node_type="AutoCropByNPS",
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
            await refs.resolve(item) if isinstance(item, _sdk.Ref) else item
            for item in result.result
        ]
        if deny and any(values[key] is not None for key in ("image", "mask")):
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
        elif deny:
            empty = await session.execute(plan, runtime, capabilities=())
            assert empty.result == (None, None)
        assert session.last_guest_pid not in (None, os.getpid())
        return actual
    finally:
        await session.kill()


@pytest.mark.parametrize("surface", ["both", "image", "mask", "none"])
def test_real_guest_raw_denial_and_outer_image_mask_none_outputs(surface):
    values = _inputs(rotation=-23, crop_right=0.2)
    if surface in ("mask", "none"):
        values["image"] = None
    if surface in ("image", "none"):
        values["mask"] = None
    expected = _execute(values)

    async def run():
        _equal(await _guest(V2, values, deny=True), expected)
        loaded = packdb.load_pack(
            SNAPSHOT, mount_name="custom_nodes.crop_nps_outer_" + surface
        )
        outer = loaded.node_mappings["AutoCropByNPS"]
        assert tuple(outer.RETURN_TYPES) == ("IMAGE", "MASK")
        previous = _sdk.providers.execution_backend

        class Backend:
            session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "crop-nps-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            result = await execution._async_map_node_over_list(
                prompt_id="crop-nps-outer",
                unique_id="1",
                obj=outer,
                input_data_all={k: [v] for k, v in values.items()},
                func=outer.FUNCTION,
                v3_data=None,
            )
            _equal(result[0].result, expected)
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()

    asyncio.run(run())


def test_fresh_pack_filesystem_and_worker_need_no_durable_state(tmp_path):
    first = tmp_path / "first-render"
    second = tmp_path / "fresh-render"
    shutil.copytree(V2, first)
    shutil.copytree(V2, second)
    values = _inputs(crop_top=0.5, crop_bottom=-0.2, rotation=32)
    expected = _execute(values)

    async def run():
        _equal(await _guest(first, values, label="crop-nps-user-a-render-1"), expected)
        _equal(await _guest(second, values, label="crop-nps-user-a-render-2"), expected)
        _equal(await _guest(second, values, label="crop-nps-user-b-render"), expected)
        _equal(
            await _guest(second, _inputs(), label="crop-nps-other-controls"),
            _execute(_inputs()),
        )

    asyncio.run(run())

    def tree(root):
        return {
            p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
        }

    assert tree(first) == tree(second) == tree(V2)


def test_provenance_stubs_authority_and_only_global_policy_removal():
    old = (PACK / "Auto_Crop_By_NPS.py").read_bytes()
    removed = b"# Ensure PIL can handle large images\nImage.MAX_IMAGE_PIXELS = None\n\n"
    assert removed in old
    assert old.replace(removed, b"") == (V2 / "algorithm.py").read_bytes()
    assert not (PACK / "LICENSE").exists() and not (V2 / "LICENSE").exists()
    assert "license" not in (V2 / "pyproject.toml").read_text().lower()
    for filename, digest in [("comfy-api.d.ts", DTS_SHA), ("comfy-api.pyi", PYI_SHA)]:
        assert hashlib.sha256((V2 / filename).read_bytes()).hexdigest() == digest
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert "61a42319c40944099fcc1e8466b2bf4fbf293ccc" in report
    assert "Persistence disposition: no durable pack state" in report
    source = (V2 / "algorithm.py").read_text() + (V2 / "nodes.py").read_text()
    for forbidden in [
        "folder_paths",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "os.",
        "sys.",
        "_from_raw",
        "ctx()",
        "MAX_IMAGE_PIXELS",
    ]:
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf8") == diff
    fresh = tmp_path / "comfyui-auto-crop-by-nps/x61a4231"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert {
        p.relative_to(rebuilt): p.read_bytes()
        for p in rebuilt.rglob("*")
        if p.is_file()
    } == {p.relative_to(V2): p.read_bytes() for p in V2.rglob("*") if p.is_file()}


def test_no_generated_caches():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))
