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
COMMIT = "e11ea12bcd88d090520c68b494635abb970f1776"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
NODE_ID = "RonLayers/TrimBg: RonLayersTrimBgUltraV2"
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    "LICENSE",
    "README.md",
    "__init__.py",
    "demo.png",
    "imagefunc.py",
    "pyproject.toml",
    "requirements.txt",
    "ron_layers_trim_bg_ultra_v2.py",
}
PAIR = PACK_DB / "patches/comfyui-auto-trim-bg/xe11ea12/comfyui-auto-trim-bg-xe11ea12"

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


def _import_package(name, root):
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
    return _import_package("_secure_auto_trim_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_auto_trim_test", root)


def _manifest(pack):
    node = pack.RonLayersTrimBgUltraV2
    return {
        "format": FORMAT,
        "nodes": {
            NODE_ID: {
                "class": "RonLayersTrimBgUltraV2",
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


def _tree(root):
    return {
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file()
        and not any(
            part in {"__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in item.relative_to(root).parts
        )
    }


def _image(channels=3, dtype=torch.float32):
    return torch.linspace(0.1, 1.0, 32 * 40 * channels, dtype=dtype).reshape(
        1, 32, 40, channels
    )


def _mask(intensity=1.0):
    mask = torch.zeros((1, 32, 40), dtype=torch.float32)
    mask[:, 7:25, 9:30] = intensity
    return mask


def _inputs(**overrides):
    values = {"image": _image(), "mask": _mask(), "padding": 0}
    values.update(overrides)
    return values


def _execute(node, **values):
    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="auto-trim-local",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs=values,
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        with _sdk.bind_runtime(
            refs, _sdk.InProcessCtxProvider().build(plan), _sdk.InProcessOps()
        ):
            result = await node.execute(**values)
            return (await _sdk.unwrap_outputs(refs, result)).result

    return asyncio.run(run())


def _assert_equal(actual, expected):
    assert len(actual) == len(expected) == 4
    for index in (0, 1, 3):
        assert actual[index].shape == expected[index].shape
        assert actual[index].dtype == expected[index].dtype
        assert torch.equal(actual[index], expected[index])
    assert actual[2] == expected[2]
    assert type(actual[2]) is type(expected[2])


def test_actual_loader_schema_census_and_manifest_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert {
        p.relative_to(PACK).as_posix()
        for p in PACK.rglob("*")
        if p.is_file() and "v2" not in p.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert (
        set(pristine.NODE_CLASS_MAPPINGS)
        == set(secure.NODE_CLASS_MAPPINGS)
        == {NODE_ID}
    )
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not hasattr(secure, "WEB_DIRECTORY")
    assert not list(PACK.rglob("*.js"))
    old = pristine.RonLayersTrimBgUltraV2
    node = secure.RonLayersTrimBgUltraV2
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == schema.display_name == NODE_ID
    assert schema.category == old.CATEGORY
    assert [item.id for item in schema.inputs] == ["image", "mask", "padding"]
    assert tuple(output.io_type for output in schema.outputs) == old.RETURN_TYPES
    assert tuple(output.display_name for output in schema.outputs) == old.RETURN_NAMES
    padding = schema.inputs[2]
    assert (padding.default, padding.min, padding.max, padding.step) == (0, 0, 1000, 1)
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)
    assert _manifest(secure) == json.loads((V2 / "secure-nodes.json").read_text())
    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.auto_trim_test")
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.web_directory is None


@pytest.mark.parametrize("channels", [3, 4])
@pytest.mark.parametrize("padding", [0, 3, 1000])
@pytest.mark.parametrize("intensity", [0.0, 0.25, 1.0])
def test_crop_mask_alpha_padding_and_empty_behavior_are_bit_exact(
    tmp_path, channels, padding, intensity
):
    values = _inputs(image=_image(channels), mask=_mask(intensity), padding=padding)
    expected = (
        _pristine(tmp_path).RonLayersTrimBgUltraV2().trim_and_crop_by_mask(**values)
    )
    actual = _execute(_secure().RonLayersTrimBgUltraV2, **values)
    _assert_equal(actual, expected)
    if intensity == 0:
        assert actual[2] is None
        assert torch.equal(actual[0], values["image"])
    else:
        assert actual[0].shape[-1] == 4
        assert actual[2] == (
            max(0, 9 - padding),
            max(0, 7 - padding),
            min(40, 30 + padding),
            min(32, 25 + padding),
        )


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_first_mask_selection_and_hw_normalization_are_preserved(tmp_path, dtype):
    old = _pristine(tmp_path).RonLayersTrimBgUltraV2()
    secure = _secure().RonLayersTrimBgUltraV2
    image = _image(dtype=dtype)
    mask = torch.cat((_mask(0.5), torch.ones_like(_mask())), dim=0).to(dtype)
    expected = old.trim_and_crop_by_mask(image, mask, 4)
    actual = _execute(secure, image=image, mask=mask, padding=4)
    _assert_equal(actual, expected)
    _assert_equal(actual, _execute(secure, image=image, mask=mask[:1], padding=4))
    _assert_equal(actual, _execute(secure, image=image, mask=mask[0], padding=4))


def test_copied_algorithm_and_helpers_are_byte_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert (PACK / "ron_layers_trim_bg_ultra_v2.py").read_bytes() == (
        V2 / "algorithm.py"
    ).read_bytes()
    assert (PACK / "imagefunc.py").read_bytes() == (V2 / "imagefunc.py").read_bytes()
    old = sys.modules[f"{pristine.__name__}.imagefunc"]
    new = sys.modules[f"{secure.__name__}.imagefunc"]
    for values in (_image(), _mask()):
        assert np.array_equal(
            np.array(old.tensor2pil(values)), np.array(new.tensor2pil(values))
        )
    image = old.tensor2pil(_image())
    for method in ("pil2tensor", "image2mask"):
        assert torch.equal(getattr(old, method)(image), getattr(new, method)(image))
    assert np.array_equal(
        np.array(old.mask2image(_mask())), np.array(new.mask2image(_mask()))
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"padding": True},
        {"padding": -1},
        {"padding": 1001},
        {"image": torch.zeros((2, 32, 40, 3))},
        {"image": torch.zeros((1, 32, 40, 2))},
        {"image": torch.ones((1, 32, 40, 3), dtype=torch.int32)},
        {"image": torch.full((1, 32, 40, 3), float("nan"))},
        {"mask": torch.zeros((1, 31, 40))},
        {"mask": torch.zeros((1, 32, 40), dtype=torch.int32)},
        {"mask": torch.full((1, 32, 40), float("inf"))},
        {"mask": torch.zeros((65, 32, 40))},
    ],
)
def test_malformed_inputs_fail_closed(overrides):
    with pytest.raises((TypeError, ValueError)):
        _execute(_secure().RonLayersTrimBgUltraV2, **_inputs(**overrides))


def test_resource_bounds_fail_before_algorithm(monkeypatch):
    secure = _secure()
    monkeypatch.setattr(secure.nodes, "MAX_DIMENSION", 20)
    with pytest.raises(ValueError, match="dimensions"):
        _execute(secure.RonLayersTrimBgUltraV2, **_inputs())
    monkeypatch.setattr(secure.nodes, "MAX_DIMENSION", 8192)
    monkeypatch.setattr(secure.nodes, "MAX_PIXELS", 1200)
    with pytest.raises(ValueError, match="image.*pixel"):
        _execute(secure.RonLayersTrimBgUltraV2, **_inputs())
    monkeypatch.setattr(secure.nodes, "MAX_PIXELS", 2000)
    with pytest.raises(ValueError, match="mask.*pixel"):
        _execute(secure.RonLayersTrimBgUltraV2, **_inputs(mask=_mask().repeat(2, 1, 1)))


def test_repeated_execution_input_and_rng_isolation():
    secure = _secure().RonLayersTrimBgUltraV2
    values = _inputs(mask=_mask(0.4), padding=2)
    image = values["image"].clone()
    mask = values["mask"].clone()
    rng = torch.random.get_rng_state().clone()
    first = _execute(secure, **values)
    second = _execute(secure, **values)
    _assert_equal(first, second)
    assert torch.equal(image, values["image"])
    assert torch.equal(mask, values["mask"])
    assert torch.equal(rng, torch.random.get_rng_state())


@pytest.mark.parametrize("empty", [False, True])
def test_real_guest_raw_denial_and_outer_image_mask_box_types(empty):
    secure = _secure()
    node = secure.RonLayersTrimBgUltraV2
    values = _inputs(mask=_mask(0.0 if empty else 0.5), padding=2)
    expected = _execute(node, **values)

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("auto-trim-bg", guest_runtime_root=V2).start()
        try:
            wrapped = dict(values)
            wrapped["image"] = _sdk.ImageRef._wrap(
                await refs.create("IMAGE", values["image"])
            )
            wrapped["mask"] = _sdk.MaskRef._wrap(
                await refs.create("MASK", values["mask"])
            )
            plan = _sdk.ExecutionPlan(
                prompt_id="auto-trim-bg",
                node_id="1",
                node_type=node.__name__,
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
            actual = list(result.result)
            for index in range(4):
                if isinstance(actual[index], _sdk.Ref):
                    actual[index] = await refs.resolve(actual[index])
            _assert_equal(actual, expected)
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

        loaded = packdb.load_pack(
            SNAPSHOT, mount_name=f"custom_nodes.auto_trim_outer_{empty}"
        )
        outer_node = loaded.node_mappings[NODE_ID]
        assert tuple(outer_node.RETURN_TYPES) == ("IMAGE", "MASK", "BOX", "IMAGE")
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "auto-trim-outer", guest_runtime_root=V2
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
                prompt_id="auto-trim-outer",
                unique_id="1",
                obj=outer_node,
                input_data_all={key: [value] for key, value in values.items()},
                func=outer_node.FUNCTION,
                v3_data=None,
            )
            _assert_equal(returns[0].result, expected)
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_license_canonical_stubs_and_documentation():
    sources = "\n".join(
        (V2 / name).read_text() for name in ("nodes.py", "algorithm.py", "imagefunc.py")
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


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-auto-trim-bg/xe11ea12"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_no_generated_cache_artifacts():
    for pattern in ("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(pattern))
