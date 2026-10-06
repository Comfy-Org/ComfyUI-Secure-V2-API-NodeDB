from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys

import pytest
import torch

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"))
for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
sys.path.append("/Users/ben/comfy/ComfyUI")
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = "3e28a97d804cf9e6ab246e3bfebe69f404209827"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = (
    PACK_DB
    / "patches/comfyui-image-expand-nodes/x3e28a97/comfyui-image-expand-nodes-x3e28a97"
)
DIRECTIONS = ["top", "bottom", "left", "right"]
MODES = ["outside", "inside"]


def _load(name, root):
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
    return _load("_image_expand_secure_test", V2)


def _old(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _load("_image_expand_upstream_test", root)


def _manifest(module):
    return {
        "format": FORMAT,
        "nodes": {
            node_id: {
                "class": cls.__name__,
                "module": "nodes",
                "sdk_refs": False,
                "permissions": list(cls.SDK_PERMISSIONS),
                "methods": {
                    key: False
                    for key in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            }
            for node_id, cls in module.NODE_CLASS_MAPPINGS.items()
        },
        "runtime": manifest_declaration(V2),
    }


def _image(batch=2, height=7, width=11, channels=3, dtype=torch.float32):
    return torch.linspace(0, 1, batch * height * width * channels, dtype=dtype).reshape(
        batch, height, width, channels
    )


def _exact(actual, expected):
    assert len(actual) == len(expected)
    for left, right in zip(actual, expected):
        if isinstance(right, torch.Tensor):
            assert (
                left.shape == right.shape
                and left.dtype == right.dtype
                and left.device == right.device
            )
            assert torch.equal(left, right)
        else:
            assert left == right


def _noiser_exact(old, new, inputs):
    # Production deliberately has no seed/global RNG mutation. The oracle seeds
    # both calls to the same draw state and restores the process afterwards.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(139857)
        start = torch.get_rng_state()
        expected = old.expand_image(**inputs)
        consumed = torch.get_rng_state()
        torch.set_rng_state(start)
        actual = new.execute(**inputs).result
        assert torch.equal(torch.get_rng_state(), consumed)
        _exact(actual, expected)
    return expected


def _region(height, width, direction, percentage):
    amount = math.ceil(
        (height if direction in ("top", "bottom") else width) * percentage
    )
    region = torch.zeros(height, width, dtype=torch.bool)
    if direction == "top":
        region[:amount] = True
    elif direction == "bottom":
        region[-amount:] = True
    elif direction == "left":
        region[:, :amount] = True
    else:
        region[:, -amount:] = True
    return region


def test_exact_actual_census_schema_and_algorithm_body_preservation(tmp_path):
    old, new = _old(tmp_path), _secure()
    assert (
        list(old.NODE_CLASS_MAPPINGS)
        == list(new.NODE_CLASS_MAPPINGS)
        == ["ImageExpandNoiser", "ImageExpandMerger", "ImageExpandOption"]
    )
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(old, "WEB_DIRECTORY") and not list(PACK.rglob("*.js"))
    for node_id, cls in new.NODE_CLASS_MAPPINGS.items():
        upstream = old.NODE_CLASS_MAPPINGS[node_id]
        schema = cls.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == upstream.CATEGORY and not schema.is_output_node
        expected = {
            **upstream.INPUT_TYPES()["required"],
            **upstream.INPUT_TYPES().get("optional", {}),
        }
        assert [item.id for item in schema.inputs] == list(expected)
        for item in schema.inputs:
            type_info = expected[item.id]
            if isinstance(type_info[0], list):
                assert item.options == type_info[0]
            else:
                assert item.io_type == type_info[0]
            assert item.optional == (
                item.id in upstream.INPUT_TYPES().get("optional", {})
            )
            if len(type_info) > 1:
                for key, value in type_info[1].items():
                    assert getattr(item, key) == value
        assert [item.io_type for item in schema.outputs] == list(upstream.RETURN_TYPES)
        if hasattr(upstream, "RETURN_NAMES"):
            assert [item.display_name for item in schema.outputs] == list(
                upstream.RETURN_NAMES
            )
        assert cls.SDK_REFS is False
        assert cls.SDK_PERMISSIONS == (
            () if node_id == "ImageExpandOption" else ("raw",)
        )
    source = ast.parse((PACK / "nodes.py").read_text())
    algorithms = ast.parse((V2 / "algorithms.py").read_text())
    for original, converted, method in [
        ("ImageExpandNoiser", "NoiserAlgorithm", "expand_image"),
        ("ImageExpandMerger", "MergerAlgorithm", "merge_images"),
    ]:
        left = next(
            item
            for c in source.body
            if isinstance(c, ast.ClassDef) and c.name == original
            for item in c.body
            if isinstance(item, ast.FunctionDef) and item.name == method
        )
        right = next(
            item
            for c in algorithms.body
            if isinstance(c, ast.ClassDef) and c.name == converted
            for item in c.body
            if isinstance(item, ast.FunctionDef) and item.name == method
        )
        assert ast.dump(left, include_attributes=False) == ast.dump(
            right, include_attributes=False
        )
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.image_expand_census")
    assert set(loaded.node_mappings) == set(old.NODE_CLASS_MAPPINGS)
    assert (
        not loaded.routes
        and not loaded.frontend_permissions
        and loaded.web_directory is None
    )


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    "dtype", [torch.float16, torch.bfloat16, torch.float32, torch.float64]
)
def test_noiser_pixel_exact_draws_shifts_masks_and_no_mutation(
    tmp_path, direction, mode, dtype
):
    old, new = _old(tmp_path).NODE_CLASS_MAPPINGS, _secure().NODE_CLASS_MAPPINGS
    image = _image(dtype=dtype)
    saved = image.clone()
    inputs = dict(
        image=image,
        expand_options={"direction": direction, "mode": mode},
        percentage=0.2,
    )
    expected = _noiser_exact(
        old["ImageExpandNoiser"](), new["ImageExpandNoiser"], inputs
    )
    assert torch.equal(image, saved)
    assert expected[0].data_ptr() != image.data_ptr()
    assert expected[1].dtype == torch.float32


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("mask_kind", ["2d", "single", "batch", "resize"])
def test_mask_resize_broadcast_dtype_and_fractional_merge(
    tmp_path, direction, mode, mask_kind
):
    old, new = _old(tmp_path).NODE_CLASS_MAPPINGS, _secure().NODE_CLASS_MAPPINGS
    image = _image()
    shape = {
        "2d": (7, 11),
        "single": (1, 7, 11),
        "batch": (2, 7, 11),
        "resize": (1, 3, 5),
    }[mask_kind]
    mask = torch.linspace(0, 0.3, math.prod(shape), dtype=torch.float64).reshape(shape)
    saved_image, saved_mask = image.clone(), mask.clone()
    options = {"direction": direction, "mode": mode}
    images = _noiser_exact(
        old["ImageExpandNoiser"](),
        new["ImageExpandNoiser"],
        dict(image=image, mask=mask, expand_options=options, percentage=0.5),
    )
    expected = old["ImageExpandMerger"]().merge_images(image, *images, options)
    actual = new["ImageExpandMerger"].execute(image, *images, options).result
    _exact(actual, expected)
    assert torch.equal(image, saved_image) and torch.equal(mask, saved_mask)
    if mode == "inside":
        assert images[1].dtype == torch.float64


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("channels", [(3, 3), (3, 4), (4, 3), (1, 1)])
def test_merger_exact_alpha_promotion_zero_masks_and_geometry(
    tmp_path, direction, mode, channels
):
    old, new = _old(tmp_path).NODE_CLASS_MAPPINGS, _secure().NODE_CLASS_MAPPINGS
    image1 = _image(channels=channels[0])
    image2 = _image(channels=channels[1]) * 0.7
    options = {"direction": direction, "mode": mode}
    for mask in (
        torch.zeros(7, 11),
        _region(7, 11, direction, 0.3).float().unsqueeze(0).expand(2, -1, -1),
    ):
        inputs = dict(image1=image1, image2=image2, mask=mask, expand_options=options)
        saved = [x.clone() for x in (image1, image2, mask)]
        _exact(
            new["ImageExpandMerger"].execute(**inputs).result,
            old["ImageExpandMerger"]().merge_images(**inputs),
        )
        for original, before in zip((image1, image2, mask), saved):
            assert torch.equal(original, before)


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("mode", MODES)
def test_option_passthrough_and_direct_zero_expansion(tmp_path, direction, mode):
    old, new = _old(tmp_path).NODE_CLASS_MAPPINGS, _secure().NODE_CLASS_MAPPINGS
    options = {"direction": direction, "mode": mode}
    assert new["ImageExpandOption"].execute(direction, mode).result == old[
        "ImageExpandOption"
    ]().get_option(direction, mode)
    inputs = dict(image=_image(), expand_options=options, percentage=0)
    if mode == "inside" and direction in ("bottom", "right"):
        with pytest.raises(RuntimeError) as expected:
            old["ImageExpandNoiser"]().expand_image(**inputs)
        with pytest.raises(RuntimeError) as actual:
            new["ImageExpandNoiser"].execute(**inputs)
        assert str(actual.value) == str(expected.value)
    else:
        _noiser_exact(old["ImageExpandNoiser"](), new["ImageExpandNoiser"], inputs)


def test_native_malformed_errors_unknown_options_and_out_of_schema_fallback(tmp_path):
    old, new = _old(tmp_path).NODE_CLASS_MAPPINGS, _secure().NODE_CLASS_MAPPINGS
    image = _image()
    options = {"direction": "top", "mode": "inside"}
    invalid = [
        dict(image=image, expand_options={}, percentage=0.2),
        dict(image=image, expand_options=None, percentage=0.2),
        dict(image=image[0], expand_options=options, percentage=0.2),
        dict(image=image, expand_options=options, percentage=float("nan")),
        dict(image=image, expand_options=options, percentage=float("inf")),
        dict(image=image, expand_options=options, percentage="bad"),
        dict(
            image=image,
            expand_options=options,
            percentage=0.2,
            mask=torch.zeros(3, 7, 11),
        ),
        dict(image=image.to(torch.int32), expand_options=options, percentage=0.2),
    ]
    for inputs in invalid:
        with pytest.raises(Exception) as expected:
            old["ImageExpandNoiser"]().expand_image(**inputs)
        with pytest.raises(type(expected.value)) as actual:
            new["ImageExpandNoiser"].execute(**inputs)
        assert str(actual.value) == str(expected.value)
    for options in (
        {"direction": "unknown", "mode": "inside"},
        {"direction": "unknown", "mode": "outside"},
        {"direction": "top", "mode": "unknown"},
    ):
        _noiser_exact(
            old["ImageExpandNoiser"](),
            new["ImageExpandNoiser"],
            dict(image=image, expand_options=options, percentage=0.2),
        )
        inputs = dict(
            image1=image,
            image2=image,
            mask=torch.zeros(2, 7, 11),
            expand_options=options,
        )
        _exact(
            new["ImageExpandMerger"].execute(**inputs).result,
            old["ImageExpandMerger"]().merge_images(**inputs),
        )
    assert new["ImageExpandOption"].execute("unknown", "other").result == (
        {"direction": "unknown", "mode": "other"},
    )


def test_projected_bounds_reject_before_rand_clone_interpolate_cat(monkeypatch):
    module = _secure()
    new = module.NODE_CLASS_MAPPINGS
    options = {"direction": "top", "mode": "inside"}
    image = torch.ones(1, 1, 1, 3)
    huge = torch.zeros(1).expand(1, 4096, 4096, 3)
    # Each below uses cheap expanded/meta tensors, never allocates the huge data.
    cases = [
        (
            "ImageExpandNoiser",
            dict(image=huge, expand_options=options, percentage=0.2),
            "input tensor",
        ),
        (
            "ImageExpandNoiser",
            dict(
                image=image.expand(65, 1, 1, 3), expand_options=options, percentage=0.2
            ),
            "dimensions",
        ),
        (
            "ImageExpandNoiser",
            dict(image=image, expand_options=options, percentage=10000),
            "projected noise",
        ),
        (
            "ImageExpandNoiser",
            dict(
                image=image.expand(1, 2048, 2048, 3),
                mask=torch.zeros(1).expand(64, 1, 1),
                expand_options=options,
                percentage=0.2,
            ),
            "projected noiser",
        ),
        (
            "ImageExpandMerger",
            dict(
                image1=torch.empty((1, 2048, 2048, 3), device="meta"),
                image2=torch.empty((1, 2048, 2048, 3), device="meta"),
                mask=torch.empty((1, 2048, 2048), device="meta"),
                expand_options={"direction": "top", "mode": "outside"},
            ),
            "projected merged",
        ),
        (
            "ImageExpandMerger",
            dict(
                image1=torch.empty((1, 1536, 1536, 4), device="meta"),
                image2=torch.empty((1, 1536, 1536, 4), device="meta"),
                mask=torch.empty((1, 1536, 1536), device="meta"),
                expand_options=options,
            ),
            "projected merger",
        ),
    ]

    def forbidden(*args, **kwargs):
        raise AssertionError("allocation occurred before guard")

    monkeypatch.setattr(torch, "rand", forbidden)
    monkeypatch.setattr(torch, "cat", forbidden)
    monkeypatch.setattr(torch.nn.functional, "interpolate", forbidden)
    monkeypatch.setattr(torch.Tensor, "clone", forbidden)
    for node_id, inputs, match in cases:
        with pytest.raises(ValueError, match=match):
            new[node_id].execute(**inputs)
    with pytest.raises(ValueError, match="mask rank"):
        new["ImageExpandMerger"].execute(image, image, torch.zeros(1, 1, 1, 1), options)


def test_bound_thresholds_and_aggregate_inputs_without_materialization():
    package = _secure()
    module = sys.modules[package.NODE_CLASS_MAPPINGS["ImageExpandNoiser"].__module__]
    at_limit = torch.empty((1, 2048, 2048, 4), device="meta")
    assert module._bounded_inputs(at_limit) == 16_777_216
    assert module._bounded_inputs(at_limit, at_limit) == 33_554_432
    with pytest.raises(ValueError, match="aggregate"):
        module._bounded_inputs(
            at_limit, at_limit, torch.empty((1, 1, 1), device="meta")
        )
    for value in (
        torch.empty((1, 4097, 1, 1), device="meta"),
        torch.empty((1, 1, 1, 5), device="meta"),
        torch.empty((0, 1, 1, 3), device="meta"),
    ):
        with pytest.raises(ValueError, match="resource bounds"):
            module._bounded_inputs(value)


def test_real_raw_guests_all_modes_chaining_denial_and_fresh_filesystem(tmp_path):
    old = _old(tmp_path).NODE_CLASS_MAPPINGS
    fresh = tmp_path / "fresh-render"
    shutil.copytree(V2, fresh)

    async def run():
        host_rng = torch.get_rng_state().clone()
        for index, root in enumerate((V2, fresh)):
            classes = _load(f"_image_expand_guest_{index}", root).NODE_CLASS_MAPPINGS
            refs = _sdk.InProcessRefResolver()
            session = await GuestSession(
                "image-expand", guest_runtime_root=root
            ).start()

            async def execute(node_id, inputs, capabilities=None):
                cls = classes[node_id]
                plan = _sdk.ExecutionPlan(
                    prompt_id="image-expand-guest",
                    node_id=node_id,
                    node_type=cls.__name__,
                    tier="sandbox",
                    node_module=cls.__module__,
                    inputs=inputs,
                    input_mode="values",
                    permissions=cls.SDK_PERMISSIONS,
                    method="execute",
                )
                runtime = _sdk.Runtime(
                    refs=refs,
                    ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=_sdk.InProcessOps(),
                )
                return await session.execute(
                    plan,
                    runtime,
                    capabilities=cls.SDK_PERMISSIONS
                    if capabilities is None
                    else capabilities,
                )

            try:
                for direction in DIRECTIONS:
                    for mode in MODES:
                        option_out = await execute(
                            "ImageExpandOption", dict(direction=direction, mode=mode)
                        )
                        options = option_out.result[0]
                        assert options == {"direction": direction, "mode": mode}
                        image = _image()
                        saved = image.clone()
                        image_ref = _sdk.ImageRef._wrap(
                            await refs.create("IMAGE", image)
                        )
                        mask = torch.linspace(0, 0.2, 15).reshape(1, 3, 5)
                        mask_ref = _sdk.MaskRef._wrap(await refs.create("MASK", mask))
                        owned = [image_ref, mask_ref]
                        try:
                            inputs = dict(
                                image=image_ref,
                                expand_options=options,
                                percentage=0.2,
                                mask=mask_ref,
                            )
                            with pytest.raises(Exception, match="raw"):
                                await execute("ImageExpandNoiser", inputs, ())
                            output = await execute("ImageExpandNoiser", inputs)
                            owned.extend(output.result)
                            actual = tuple(
                                [await refs.resolve(ref) for ref in output.result]
                            )
                            with torch.random.fork_rng(devices=[]):
                                expected = old["ImageExpandNoiser"]().expand_image(
                                    image, options, 0.2, mask
                                )
                            region = _region(7, 11, direction, 0.2)
                            assert torch.equal(
                                actual[0][:, ~region, :], expected[0][:, ~region, :]
                            )
                            assert torch.equal(actual[1], expected[1])
                            noise = actual[0][:, region, :]
                            assert (
                                torch.all((noise >= 0) & (noise < 1))
                                and noise.std() > 0.1
                            )
                            again = await execute("ImageExpandNoiser", inputs)
                            owned.extend(again.result)
                            again_image = await refs.resolve(again.result[0])
                            assert not torch.equal(again_image[:, region, :], noise)
                            merged = await execute(
                                "ImageExpandMerger",
                                dict(
                                    image1=image_ref,
                                    image2=output.result[0],
                                    mask=output.result[1],
                                    expand_options=options,
                                ),
                            )
                            owned.extend(merged.result)
                            _exact(
                                (await refs.resolve(merged.result[0]),),
                                old["ImageExpandMerger"]().merge_images(
                                    image, *actual, options
                                ),
                            )
                            with pytest.raises(Exception, match="raw"):
                                await execute(
                                    "ImageExpandMerger",
                                    dict(
                                        image1=image_ref,
                                        image2=output.result[0],
                                        mask=output.result[1],
                                        expand_options=options,
                                    ),
                                    (),
                                )
                            assert torch.equal(await refs.resolve(image_ref), saved)
                        finally:
                            for ref in owned:
                                await refs.release(ref)
                bad = _sdk.ImageRef._wrap(
                    await refs.create("IMAGE", _image(batch=65, height=1, width=1))
                )
                try:
                    with pytest.raises(Exception, match="resource bounds"):
                        await execute(
                            "ImageExpandNoiser",
                            dict(
                                image=bad,
                                expand_options={"direction": "top", "mode": "inside"},
                                percentage=0.2,
                            ),
                        )
                finally:
                    await refs.release(bad)
                assert (
                    session.last_guest_pid not in (None, os.getpid())
                    and not refs._table
                )
            finally:
                await session.kill()
        assert torch.equal(torch.get_rng_state(), host_rng)

    asyncio.run(run())


def test_outer_executor_preserves_declared_image_mask_and_tensor_values(tmp_path):
    import execution

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.image_expand_outer")
    node = loaded.node_mappings["ImageExpandNoiser"]
    assert tuple(node.RETURN_TYPES) == ("IMAGE", "MASK")
    image = _image(batch=1)
    mask = torch.linspace(0, 0.2, 77).reshape(1, 7, 11)
    options = {"direction": "left", "mode": "inside"}
    old = _old(tmp_path).NODE_CLASS_MAPPINGS["ImageExpandNoiser"]()
    with torch.random.fork_rng(devices=[]):
        expected = old.expand_image(image, options, 0.2, mask)

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "image-expand-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=("raw",))

        backend = OuterGuestBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            values = await execution._async_map_node_over_list(
                prompt_id="image-expand-outer",
                unique_id="1",
                obj=node,
                input_data_all={
                    "image": [image],
                    "expand_options": [options],
                    "percentage": [0.2],
                    "mask": [mask],
                },
                func=node.FUNCTION,
                v3_data=None,
            )
            output = values[0].result
            assert len(output) == 2 and all(isinstance(x, torch.Tensor) for x in output)
            region = _region(7, 11, "left", 0.2)
            assert torch.equal(output[0][:, ~region, :], expected[0][:, ~region, :])
            assert torch.equal(output[1], expected[1]) and output[1].shape == (1, 7, 11)
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session is not None:
                await backend.session.kill()

    asyncio.run(run())


def test_manifest_stubs_license_and_no_ambient_authority():
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report and "no durable pack state" in report
    for file in ("nodes.py", "algorithms.py", "__init__.py"):
        tree = ast.parse((V2 / file).read_text())
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                assert all(x.name in ("torch", "math") for x in item.names)
            if isinstance(item, ast.ImportFrom):
                assert item.module in ("comfy_api.latest", "nodes", "algorithms")
            if isinstance(item, ast.Call):
                if isinstance(item.func, ast.Name):
                    assert item.func.id not in ("open", "eval", "exec", "__import__")
                if isinstance(item.func, ast.Attribute):
                    assert item.func.attr not in (
                        "_from_raw",
                        "manual_seed",
                        "set_rng_state",
                        "load",
                        "save",
                    )


def test_exact_patch_roundtrip_no_generated_cache_artifacts(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff
    root = tmp_path / "comfyui-image-expand-nodes/x3e28a97"
    root.mkdir(parents=True)
    shutil.copytree(PACK, root / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(root, manifest, diff)
    packpatch.validate_tree(root / PACK.name / "v2", V2)
    assert not list(PACK.rglob("*.pyc")) and not list(PACK.rglob("__pycache__"))
