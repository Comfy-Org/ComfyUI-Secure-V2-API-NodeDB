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
CORE = (
    pathlib.Path(
        os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes")
    )
    .expanduser()
    .resolve()
)
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "b0a204d910a0025d8ba4b53b01df831861cf8241"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-advanced-photo-grain"
    / "xb0a204d"
    / ("comfyui-advanced-photo-grain-xb0a204d")
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
    return _import_package("_secure_advanced_photo_grain_test", V2)


def _pristine(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    package = _import_package("_pristine_advanced_photo_grain_test", root)
    import comfy.model_management as model_management

    monkeypatch.setattr(
        model_management, "get_torch_device", lambda: torch.device("cpu")
    )
    monkeypatch.setattr(
        model_management, "intermediate_device", lambda: torch.device("cpu")
    )
    return package


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(
                getattr(
                    node_class,
                    "SDK_PERMISSIONS",
                    (),
                )
                or ()
            ),
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


def _image(batch=2, height=40, width=64, channels=3):
    count = batch * height * width * channels
    return torch.linspace(0.0, 1.0, count, dtype=torch.float32).reshape(
        batch,
        height,
        width,
        channels,
    )


def _grain_args(**overrides):
    result = {
        "grain_type": "poisson",
        "grain_intensity": 0.022,
        "grain_size": 1.5,
        "saturation_mix": 0.22,
        "adaptive_grain": 0.30,
        "halation_strength": 0.0,
        "vignette_strength": 0.0,
        "chromatic_aberration": 0.0,
        "lens_distortion": 0.0,
    }
    result.update(overrides)
    return result


def _exact(got: torch.Tensor, expected: torch.Tensor):
    assert tuple(got.shape) == tuple(expected.shape)
    assert got.dtype == expected.dtype
    assert torch.equal(got, expected)
    assert torch.isfinite(got).all()


def test_pinned_actual_loader_census_entrypoint_and_schemas_are_exact(
    tmp_path,
    monkeypatch,
):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "2 supported, 0 rejected, 0 pending" in report
    assert set(pristine.NODE_CLASS_MAPPINGS) == {
        "PhotoFilmGrain",
        "FreqSeparationSharpen",
    }
    assert set(secure.NODE_CLASS_MAPPINGS) == set(pristine.NODE_CLASS_MAPPINGS)
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]

    for node_id in pristine.NODE_CLASS_MAPPINGS:
        legacy = pristine.NODE_CLASS_MAPPINGS[node_id]
        schema = secure.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA()
        schema.validate()
        inputs = legacy.INPUT_TYPES()
        ordered = list(inputs["required"]) + list(inputs.get("optional", {}))
        assert [item.id for item in schema.inputs] == ordered
        assert schema.category == legacy.CATEGORY
        assert schema.description == legacy.DESCRIPTION
        assert [item.io_type for item in schema.outputs] == list(legacy.RETURN_TYPES)
        assert secure.NODE_CLASS_MAPPINGS[node_id].SDK_REFS is False
        assert secure.NODE_CLASS_MAPPINGS[node_id].SDK_PERMISSIONS == ("raw",)
        for item in schema.inputs:
            group = "optional" if item.id in inputs.get("optional", {}) else "required"
            legacy_type, *rest = inputs[group][item.id]
            assert item.io_type == (
                "COMBO" if isinstance(legacy_type, list) else legacy_type
            )
            assert item.optional is (group == "optional")
            options = rest[0] if rest else {}
            for key in ("default", "min", "max", "step", "tooltip"):
                if key in options:
                    assert getattr(item, key) == options[key]
            if isinstance(legacy_type, list):
                assert item.options == legacy_type

    assert _secure().GRAIN_TYPES == ["gaussian", "poisson", "perlin"]
    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [
        secure.PhotoFilmGrain,
        secure.FreqSeparationSharpen,
    ]
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.advanced_photo_grain_census_test",
    )
    assert set(loaded.node_mappings) == set(pristine.NODE_CLASS_MAPPINGS)
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize(
    "grain_type,grain_size",
    (
        ("gaussian", 1.0),
        ("gaussian", 3.8),
        ("poisson", 1.0),
        ("poisson", 4.2),
        ("perlin", 1.0),
        ("perlin", 7.0),
    ),
)
def test_all_grain_generators_are_pixel_and_rng_consumption_exact(
    tmp_path,
    monkeypatch,
    grain_type,
    grain_size,
):
    pristine = _pristine(tmp_path, monkeypatch).NODE_CLASS_MAPPINGS["PhotoFilmGrain"]()
    secure = _secure()
    image = _image()
    args = _grain_args(
        grain_type=grain_type,
        grain_size=grain_size,
        grain_intensity=0.17,
        saturation_mix=0.61,
        adaptive_grain=1.2,
    )
    torch.manual_seed(87123)
    expected = pristine.apply_grain(image.clone(), **args)[0]
    expected_rng = torch.random.get_rng_state().clone()
    torch.manual_seed(87123)
    actual = secure.PhotoFilmGrain.execute(image.clone(), **args).result[0]
    actual_rng = torch.random.get_rng_state().clone()
    _exact(actual, expected)
    assert torch.equal(actual_rng, expected_rng)


@pytest.mark.parametrize("lens_distortion", (-0.35, 0.28))
def test_combined_optical_effects_are_pixel_exact(
    tmp_path,
    monkeypatch,
    lens_distortion,
):
    pristine = _pristine(tmp_path, monkeypatch).NODE_CLASS_MAPPINGS["PhotoFilmGrain"]()
    secure = _secure()
    image = _image(batch=1, height=48, width=80)
    args = _grain_args(
        grain_type="perlin",
        grain_intensity=0.0,
        halation_strength=1.0,
        vignette_strength=0.73,
        chromatic_aberration=2.4,
        lens_distortion=lens_distortion,
    )
    expected = pristine.apply_grain(image.clone(), **args)[0]
    actual = secure.PhotoFilmGrain.execute(image.clone(), **args).result[0]
    _exact(actual, expected)
    assert not torch.equal(actual, image)


@pytest.mark.parametrize(
    "radius,strength,threshold,halo_limit",
    (
        (2.0, 1.0, 0.0, 0.0),
        (0.7, 0.0, 0.0, 0.0),
        (2.3, 3.4, 0.0, 0.0),
        (4.1, 2.2, 0.025, 0.0),
        (1.4, 7.0, 0.006, 0.08),
    ),
)
def test_frequency_sharpen_modes_are_pixel_exact(
    tmp_path,
    monkeypatch,
    radius,
    strength,
    threshold,
    halo_limit,
):
    pristine = _pristine(tmp_path, monkeypatch).NODE_CLASS_MAPPINGS[
        "FreqSeparationSharpen"
    ]()
    secure = _secure()
    image = _image(batch=3, height=36, width=44)
    expected = pristine.process(
        image.clone(),
        radius,
        strength,
        threshold,
        halo_limit,
    )[0]
    actual = secure.FreqSeparationSharpen.execute(
        image.clone(),
        radius,
        strength,
        threshold,
        halo_limit,
    ).result[0]
    _exact(actual, expected)


def test_identity_paths_and_direct_failure_bounds_match_upstream(
    tmp_path,
    monkeypatch,
):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    image = _image(batch=1, height=8, width=8)
    upstream_sharpen = pristine.NODE_CLASS_MAPPINGS["FreqSeparationSharpen"]()
    expected = upstream_sharpen.process(image, 2.0, 1.0, 0.0, 0.0)[0]
    actual = secure.FreqSeparationSharpen.execute(
        image,
        2.0,
        1.0,
        0.0,
        0.0,
    ).result[0]
    assert expected is image
    assert actual is image

    upstream_grain = pristine.NODE_CLASS_MAPPINGS["PhotoFilmGrain"]()
    bad_args = _grain_args(grain_type="gaussian", grain_size=16.0)
    for fn in (
        lambda: upstream_grain.apply_grain(image, **bad_args),
        lambda: secure.PhotoFilmGrain.execute(image, **bad_args),
    ):
        with pytest.raises(RuntimeError):
            fn()

    for fn in (
        lambda: upstream_sharpen.process(image, 50.0, 2.0),
        lambda: secure.FreqSeparationSharpen.execute(image, 50.0, 2.0),
    ):
        with pytest.raises(RuntimeError):
            fn()


def test_real_isolated_guest_matches_deterministic_paths_and_denies_raw(
    tmp_path,
    monkeypatch,
):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "advanced-photo-grain",
            guest_runtime_root=V2,
        ).start()
        try:
            image = _image(batch=2, height=32, width=64)
            image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
            cases = (
                (
                    secure.PhotoFilmGrain,
                    {
                        "images": image_ref,
                        **_grain_args(
                            grain_intensity=0.0,
                            halation_strength=1.0,
                            vignette_strength=0.45,
                            chromatic_aberration=1.7,
                            lens_distortion=-0.2,
                        ),
                    },
                    pristine.NODE_CLASS_MAPPINGS["PhotoFilmGrain"]().apply_grain(
                        image,
                        **_grain_args(
                            grain_intensity=0.0,
                            halation_strength=1.0,
                            vignette_strength=0.45,
                            chromatic_aberration=1.7,
                            lens_distortion=-0.2,
                        ),
                    )[0],
                ),
                (
                    secure.FreqSeparationSharpen,
                    {
                        "image": image_ref,
                        "radius": 1.7,
                        "strength": 3.1,
                        "threshold": 0.013,
                        "halo_limit": 0.09,
                    },
                    pristine.NODE_CLASS_MAPPINGS["FreqSeparationSharpen"]().process(
                        image, 1.7, 3.1, 0.013, 0.09
                    )[0],
                ),
            )
            for index, (node, inputs, expected) in enumerate(cases):
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"advanced-photo-grain-{index}",
                    node_id=str(index),
                    node_type=node.__name__,
                    tier="sandbox",
                    node_module=node.__module__,
                    inputs=inputs,
                    input_mode="values",
                    permissions=("raw",),
                    method="execute",
                )
                result = await session.execute(
                    plan,
                    _runtime(plan, refs),
                    capabilities=("raw",),
                )
                actual = await refs.resolve(result.result[0])
                _exact(actual, expected)
                if index == 0:
                    with pytest.raises(Exception, match="raw"):
                        await session.execute(
                            plan,
                            _runtime(plan, refs),
                            capabilities=(),
                        )
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    for required in ("import torch", "import torchvision"):
        assert required in source
    for forbidden in (
        "import comfy",
        "model_management",
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
        "manual_seed",
        "set_rng_state",
        "socket",
        "urllib",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-advanced-photo-grain" / "xb0a204d"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
