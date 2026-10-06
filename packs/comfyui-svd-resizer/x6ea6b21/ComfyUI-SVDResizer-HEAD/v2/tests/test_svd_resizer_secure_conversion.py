from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import inspect
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
PAIR = PACK_DB / "patches/comfyui-svd-resizer/x6ea6b21/comfyui-svd-resizer-x6ea6b21"
MODES = ("nearest", "bilinear", "bicubic", "area", "nearest-exact", "lanczos")
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    ".gitignore",
    "LICENSE",
    "README.md",
    "SVD_demo.json",
    "SVDResizer.py",
    "__init__.py",
    "pyproject.toml",
}
for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

import comfy.utils
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
    return _import("_svd_resizer_secure_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    filters = list(warnings.filters)
    try:
        return _import("_svd_resizer_pristine_test", root)
    finally:
        warnings.filters[:] = filters


def _manifest(pack):
    node = pack.SVDRsizer
    return {
        "format": FORMAT,
        "nodes": {
            "SVDRsizer": {
                "class": "SVDRsizer",
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


def _inputs(channels=3, dtype=torch.float32, batch=1, **overrides):
    image = torch.linspace(-0.1, 1.1, batch * 7 * 11 * channels, dtype=dtype).reshape(
        batch, 7, 11, channels
    )
    values = {
        "image": image,
        "width": 600,
        "height": 576,
        "keep_proportion": False,
        "interpolation": "nearest",
    }
    values.update(overrides)
    return values


def _execute(values):
    return _secure().SVDRsizer.execute(**values).result


def _equal(actual, expected):
    assert len(actual) == len(expected) == 3
    a, b = actual[0], expected[0]
    assert a.shape == b.shape and a.dtype == b.dtype and a.device == b.device
    assert torch.equal(a, b)
    assert tuple(actual[1:]) == tuple(expected[1:])
    assert all(type(x) is int for x in actual[1:])


def test_exact_actual_loader_schema_display_typo_and_manifest(tmp_path):
    old, new = _pristine(tmp_path), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {"SVDRsizer"}
    assert (
        old.NODE_DISPLAY_NAME_MAPPINGS
        == new.NODE_DISPLAY_NAME_MAPPINGS
        == {"SVDResizer": "SVDResizer"}
    )
    assert {
        p.relative_to(PACK).as_posix()
        for p in PACK.rglob("*")
        if p.is_file() and "v2" not in p.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert not hasattr(old, "WEB_DIRECTORY") and not hasattr(new, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    node = new.SVDRsizer
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == schema.display_name == "SVDRsizer"
    assert schema.category == old.NODE_CLASS_MAPPINGS["SVDRsizer"].CATEGORY
    required = old.NODE_CLASS_MAPPINGS["SVDRsizer"].INPUT_TYPES()["required"]
    assert [x.id for x in schema.inputs] == list(required)
    for item in schema.inputs[1:3]:
        opts = required[item.id][1]
        assert (item.default, item.min, item.max, item.step) == (
            opts["default"],
            opts["min"],
            opts["max"],
            opts["step"],
        )
    assert list(schema.inputs[3].options) == list(MODES) == required["interpolation"][0]
    assert schema.inputs[4].default is False
    legacy = old.NODE_CLASS_MAPPINGS["SVDRsizer"]
    assert tuple(x.io_type for x in schema.outputs) == legacy.RETURN_TYPES
    assert tuple(x.display_name for x in schema.outputs) == legacy.RETURN_NAMES
    assert not schema.is_output_node
    assert node.SDK_REFS is False and node.SDK_PERMISSIONS == ("raw",)
    assert _manifest(new) == json.loads((V2 / "secure-nodes.json").read_text())
    extension = asyncio.run(new.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.svd_resizer_census")
    assert set(loaded.node_mappings) == {"SVDRsizer"} and loaded.web_directory is None


@pytest.mark.parametrize("method", MODES)
@pytest.mark.parametrize("keep", [False, True])
@pytest.mark.parametrize("channels", [3, 4])
def test_all_six_modes_and_proportional_rgb_rgba_are_bit_exact(
    tmp_path, method, keep, channels
):
    values = _inputs(channels, keep_proportion=keep, interpolation=method)
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS["SVDRsizer"]().execute(**values)
    actual = _execute(values)
    _equal(actual, expected)
    assert actual[1:] == ((600, 382) if keep else (600, 576))


@pytest.mark.parametrize("method", MODES)
@pytest.mark.parametrize("dtype", [torch.float16, torch.float64])
def test_noncontiguous_batches_dtype_and_device_are_preserved(tmp_path, method, dtype):
    values = _inputs(4, dtype, batch=2, interpolation=method, keep_proportion=True)
    values["image"] = values["image"].transpose(1, 2)
    assert not values["image"].is_contiguous()
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS["SVDRsizer"]().execute(**values)
    actual = _execute(values)
    _equal(actual, expected)
    assert actual[0].shape[0] == 2 and actual[0].dtype == dtype


@pytest.mark.parametrize("shape", [(11, 7), (1, 5), (5, 1)])
def test_portrait_and_singleton_proportional_geometry_matches_pristine(tmp_path, shape):
    values = _inputs(
        image=torch.linspace(0, 1, shape[0] * shape[1] * 3).reshape(1, *shape, 3),
        keep_proportion=True,
    )
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS["SVDRsizer"]().execute(**values)
    _equal(_execute(values), expected)


def test_nearest_is_distinct_and_lanczos_is_not_bicubic():
    values = _inputs()
    nearest = _execute(values)[0]
    values["interpolation"] = "nearest-exact"
    exact = _execute(values)[0]
    assert not torch.equal(nearest, exact)
    values["interpolation"] = "lanczos"
    lanczos = _execute(values)[0]
    values["interpolation"] = "bicubic"
    bicubic = _execute(values)[0]
    assert not torch.equal(lanczos, bicubic)
    assert lanczos.min() >= 0 and lanczos.max() <= 1


def test_migrated_lanczos_helper_has_exact_canonical_ast_and_pixels():
    import ast

    old = ast.parse(inspect.getsource(comfy.utils.lanczos)).body[0]
    new = ast.parse(inspect.getsource(_secure().nodes.algorithm.lanczos)).body[0]
    assert ast.dump(old, include_attributes=False) == ast.dump(
        new, include_attributes=False
    )
    image = _inputs(4, torch.float64, batch=2)["image"].permute(0, 3, 1, 2)
    _equal(
        (comfy.utils.lanczos(image, 600, 576).permute(0, 2, 3, 1), 600, 576),
        (
            _secure().nodes.algorithm.lanczos(image, 600, 576).permute(0, 2, 3, 1),
            600,
            576,
        ),
    )


@pytest.mark.parametrize(
    "override",
    [
        {"width": True},
        {"height": 600.0},
        {"width": 575},
        {"height": 1025},
        {"width": 0},
        {"interpolation": "bilanczos"},
        {"keep_proportion": 1},
        {"image": "not a tensor"},
        {"image": torch.zeros(1, 2, 3, 2)},
        {"image": torch.zeros(0, 7, 11, 3)},
        {"image": torch.zeros(65, 7, 11, 3)},
        {"image": torch.zeros(1, 0, 11, 3)},
        {"image": torch.ones(1, 7, 11, 3, dtype=torch.int64)},
        {"image": torch.full((1, 7, 11, 3), float("nan"))},
        {"image": torch.full((1, 7, 11, 3), float("inf"))},
    ],
)
def test_malformed_and_out_of_schema_requests_fail(override):
    with pytest.raises((TypeError, ValueError)):
        _execute(_inputs(**override))


def test_bounds_and_aspect_collapse_fail_before_compute(monkeypatch):
    pack = _secure()

    def forbidden(*args, **kwargs):
        pytest.fail("pixel compute entered before validation")

    monkeypatch.setattr(pack.nodes.algorithm, "resize", forbidden)
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 100)
    with pytest.raises(ValueError, match="input"):
        pack.SVDRsizer.execute(**_inputs())
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 2000)
    with pytest.raises(ValueError, match="output"):
        pack.SVDRsizer.execute(**_inputs())
    monkeypatch.setattr(pack.nodes, "MAX_ELEMENTS", 16_777_216)
    with pytest.raises(ValueError, match="collapse"):
        pack.SVDRsizer.execute(
            **_inputs(image=torch.zeros(1, 1, 8192, 3), keep_proportion=True)
        )
    monkeypatch.setattr(pack.nodes, "MAX_DIMENSION", 10)
    with pytest.raises(ValueError, match="dimensions"):
        pack.SVDRsizer.execute(**_inputs())


def test_repeated_inputs_rng_and_warning_policy_are_isolated():
    values = _inputs(interpolation="lanczos", keep_proportion=True)
    image = values["image"].clone()
    rng = torch.random.get_rng_state().clone()
    filters = list(warnings.filters)
    first = _execute(values)
    _equal(_execute(values), first)
    assert torch.equal(image, values["image"]) and torch.equal(
        rng, torch.random.get_rng_state()
    )
    assert warnings.filters == filters


async def _guest(root, values, label="svd-resizer-render", deny=False):
    pack = _import("_svd_resizer_guest_source", root)
    refs = _sdk.InProcessRefResolver()
    wrapped = dict(values)
    wrapped["image"] = _sdk.ImageRef._wrap(await refs.create("IMAGE", values["image"]))
    plan = _sdk.ExecutionPlan(
        prompt_id=label,
        node_id="1",
        node_type="SVDRsizer",
        tier="sandbox",
        node_module=pack.SVDRsizer.__module__,
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
        if deny:
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
        assert session.last_guest_pid not in (None, os.getpid())
        return actual
    finally:
        await session.kill()


@pytest.mark.parametrize("method", MODES)
def test_real_guest_all_modes_raw_denial_and_outer_image_int_types(method):
    values = _inputs(interpolation=method, keep_proportion=True)
    expected = _execute(values)

    async def run():
        _equal(await _guest(V2, values, deny=True), expected)
        loaded = packdb.load_pack(
            SNAPSHOT,
            mount_name="custom_nodes.svd_resizer_outer_" + method.replace("-", "_"),
        )
        outer = loaded.node_mappings["SVDRsizer"]
        assert tuple(outer.RETURN_TYPES) == ("IMAGE", "INT", "INT")
        previous = _sdk.providers.execution_backend

        class Backend:
            session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "svd-resizer-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            result = await execution._async_map_node_over_list(
                prompt_id="svd-resizer-outer",
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


def test_fresh_filesystem_and_guest_require_no_durable_state(tmp_path):
    first, second = tmp_path / "render-one", tmp_path / "render-two"
    shutil.copytree(V2, first)
    shutil.copytree(V2, second)
    values = _inputs(interpolation="lanczos", keep_proportion=True)
    expected = _execute(values)

    async def run():
        _equal(await _guest(first, values, label="svd-user-a-first"), expected)
        _equal(await _guest(second, values, label="svd-user-a-fresh"), expected)
        _equal(
            await _guest(
                second, _inputs(interpolation="nearest"), label="svd-user-b-controls"
            ),
            _execute(_inputs(interpolation="nearest")),
        )

    asyncio.run(run())

    def tree(root):
        return {
            p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
        }

    assert tree(first) == tree(second) == tree(V2)


def test_license_stubs_authority_and_persistence_report():
    assert (PACK / "LICENSE").read_bytes() == (V2 / "LICENSE").read_bytes()
    for filename, digest in [("comfy-api.d.ts", DTS_SHA), ("comfy-api.pyi", PYI_SHA)]:
        assert hashlib.sha256((V2 / filename).read_bytes()).hexdigest() == digest
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert "6ea6b21455afc4f4c86506e2ea674cdb46fbcb4b" in report
    assert "Persistence disposition: no durable state" in report
    source = "\n".join(
        (V2 / name).read_text() for name in ("nodes.py", "algorithm.py", "__init__.py")
    )
    for forbidden in [
        "folder_paths",
        "comfy.utils",
        "warnings.filterwarnings",
        "torchvision",
        "SaveImage",
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


def test_patch_roundtrip_byte_exact(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf8") == diff
    fresh = tmp_path / "comfyui-svd-resizer/x6ea6b21"
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
