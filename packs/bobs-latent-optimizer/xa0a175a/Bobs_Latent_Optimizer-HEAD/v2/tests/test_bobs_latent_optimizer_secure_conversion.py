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
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "a0a175aed20bc9e42bdd03f99b9f6dcfd1ecbf40"
TREE = "74647bca3d873d95a7401d10ad4dfe60a5a3a399"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
NODE_IDS = ("BobsLatentNode", "BobsLatentNodeAdvanced")
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    ".github/workflows/test.yml",
    ".gitignore",
    "Bobs_Latent_Optimizer.py",
    "LICENSE",
    "README.md",
    "__init__.py",
    "pyproject.toml",
    "tests/test_latent_optimizer.py",
}
PAIR = PACK_DB / "patches/bobs-latent-optimizer/xa0a175a/bobs-latent-optimizer-xa0a175a"

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
    return _import_package("_secure_bobs_latent_optimizer_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    package = _import_package("_pristine_bobs_latent_optimizer_test", root)
    implementation = sys.modules[package.NODE_CLASS_MAPPINGS[NODE_IDS[0]].__module__]
    implementation.model_management = None
    return package, implementation


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node in pack.NODE_CLASS_MAPPINGS.items():
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
    return {
        "format": FORMAT,
        "nodes": nodes,
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


def _preset_inputs(**overrides):
    values = {
        "aspect_ratio": "1:1",
        "mp_size": "1",
        "upscale_by": 2.0,
        "model_type": "FLUX",
        "batch_size": 1,
        "max_tile_size": 2048,
        "length": 1,
    }
    values.update(overrides)
    return values


def _advanced_inputs(**overrides):
    values = _preset_inputs(**overrides)
    values.pop("mp_size", None)
    values["mp_size_float"] = overrides.get("mp_size_float", 1.0)
    return values


def _assert_result_equal(actual, expected):
    actual_values = actual.result if hasattr(actual, "result") else actual
    assert len(actual_values) == len(expected) == 6
    assert set(actual_values[0]) == set(expected[0]) == {"samples"}
    actual_samples = actual_values[0]["samples"]
    expected_samples = expected[0]["samples"]
    assert actual_samples.shape == expected_samples.shape
    assert actual_samples.dtype == expected_samples.dtype == torch.float32
    assert torch.count_nonzero(actual_samples) == 0
    assert torch.count_nonzero(expected_samples) == 0
    assert actual_values[1:] == expected[1:]


def test_actual_loader_census_schemas_manifest_license_and_contract_are_exact(tmp_path):
    pristine, _ = _pristine(tmp_path)
    secure = _secure()
    assert TREE == "74647bca3d873d95a7401d10ad4dfe60a5a3a399"
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert tuple(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert tuple(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == pristine.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not hasattr(secure, "WEB_DIRECTORY")

    for node_id in NODE_IDS:
        old = pristine.NODE_CLASS_MAPPINGS[node_id]
        node = secure.NODE_CLASS_MAPPINGS[node_id]
        schema = node.GET_SCHEMA()
        schema.validate()
        assert (schema.node_id, schema.display_name, schema.category) == (
            node_id,
            pristine.NODE_DISPLAY_NAME_MAPPINGS[node_id],
            old.CATEGORY,
        )
        assert schema.description == old.DESCRIPTION
        old_inputs = old.INPUT_TYPES()
        declarations = {**old_inputs["required"], **old_inputs["optional"]}
        assert [item.id for item in schema.inputs] == list(declarations)
        for item in schema.inputs:
            declaration = declarations[item.id]
            metadata = declaration[1] if len(declaration) > 1 else {}
            old_type = declaration[0]
            assert item.io_type == ("COMBO" if isinstance(old_type, list) else old_type)
            if isinstance(old_type, list):
                assert list(item.options) == old_type
            assert item.optional is (item.id in old_inputs["optional"])
            for field in ("default", "min", "max", "step", "tooltip"):
                if field in metadata:
                    assert getattr(item, field) == metadata[field]
            if metadata.get("display") == "number":
                assert item.display_mode.value == "number"
        assert [item.id for item in schema.outputs] == list(old.RETURN_NAMES)
        assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES)
        assert [item.tooltip for item in schema.outputs] == list(old.OUTPUT_TOOLTIPS)
        assert node.SDK_REFS is False
        assert node.SDK_PERMISSIONS == ("raw",)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [
        secure.BobsLatentNode,
        secure.BobsLatentNodeAdvanced,
    ]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.bobs_latent_optimizer_secure_test"
    )
    assert set(loaded.node_mappings) == set(NODE_IDS)
    assert loaded.frontend_permissions == frozenset()
    assert loaded.web_directory is None
    assert not loaded.routes
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()


def test_model_table_and_preset_area_tables_are_exact(tmp_path):
    _, old = _pristine(tmp_path)
    secure = _secure()
    assert secure.MODEL_SPECS == old.MODEL_SPECS
    assert secure.MODEL_TYPES == old.MODEL_TYPES
    assert secure.VIDEO_MODEL_TYPES == old.VIDEO_MODEL_TYPES
    assert secure.MP_SIZE_TO_AREA == old.MP_SIZE_TO_AREA
    assert secure.MP_SIZES == old.MP_SIZES


@pytest.mark.parametrize("model_type", list(_secure().MODEL_TYPES))
def test_every_model_family_shape_rank_and_scalars_match_pristine(tmp_path, model_type):
    pristine, _ = _pristine(tmp_path)
    secure = _secure()
    values = _preset_inputs(
        aspect_ratio="16:9",
        mp_size="0.25",
        upscale_by=3.25,
        model_type=model_type,
        batch_size=1,
        max_tile_size=768,
        length=17,
    )
    expected = pristine.NODE_CLASS_MAPPINGS["BobsLatentNode"]().generate(**values)
    actual = secure.BobsLatentNode.execute(**values)
    _assert_result_equal(actual, expected)


@pytest.mark.parametrize(
    "aspect_ratio", ["1:1", "16:9", "9/16", "3x2", "1.5:1", "0.37"]
)
@pytest.mark.parametrize("mp_size", ["0.25", "1", "2.5", "4"])
def test_preset_ratios_areas_alignment_and_tiles_match_pristine(
    tmp_path, aspect_ratio, mp_size
):
    pristine, _ = _pristine(tmp_path)
    secure = _secure()
    values = _preset_inputs(
        aspect_ratio=aspect_ratio,
        mp_size=mp_size,
        upscale_by=1.37,
        model_type="SDXL",
        batch_size=2,
        max_tile_size=1024,
    )
    expected = pristine.NODE_CLASS_MAPPINGS["BobsLatentNode"]().generate(**values)
    _assert_result_equal(secure.BobsLatentNode.execute(**values), expected)


@pytest.mark.parametrize("area", [0.01, 0.25, 1.0, 1.75, 4.0, 16.0])
@pytest.mark.parametrize("model_type", ["SD15", "QWEN", "FLUX2", "WAN", "MOCHI"])
def test_advanced_continuous_area_matches_pristine(tmp_path, area, model_type):
    pristine, _ = _pristine(tmp_path)
    secure = _secure()
    values = _advanced_inputs(
        aspect_ratio="21:9",
        mp_size_float=area,
        upscale_by=1.0,
        model_type=model_type,
        batch_size=1,
        max_tile_size=8192,
        length=49,
    )
    expected = pristine.NODE_CLASS_MAPPINGS["BobsLatentNodeAdvanced"]().generate(
        **values
    )
    _assert_result_equal(secure.BobsLatentNodeAdvanced.execute(**values), expected)


def test_pure_helpers_match_pristine_over_edge_matrix(tmp_path):
    _, old = _pristine(tmp_path)
    secure = _secure()
    for ratio in (0.001, 0.37, 1.0, 16 / 9, 1000.0):
        for area in (16, 512 * 512, 4 * 1024 * 1024, 16 * 1024 * 1024):
            for align in (8, 16, 32, 64):
                assert secure.compute_base_dimensions(
                    area, ratio, align
                ) == old.compute_base_dimensions(area, ratio, align)
    for length in (1, 2, 4, 5, 17, 4096):
        for temporal in (1, 4, 6, 8):
            assert secure.compute_latent_frames(
                length, temporal
            ) == old.compute_latent_frames(length, temporal)
    for width, height in ((16, 16), (512, 768), (1920, 1080), (16_384, 64)):
        for upscale in (1.0, 1.37, 2.0, 10.0):
            for maximum in (256, 2048, 8192):
                assert secure.compute_tile_dimensions(
                    width, height, upscale, maximum
                ) == old.compute_tile_dimensions(width, height, upscale, maximum)


@pytest.mark.parametrize(
    "value",
    ["", "1:0", "abc", "-16:9", "1:2:3", "0:1", "1,5", "nan", "inf"],
)
def test_invalid_aspect_ratios_match_pristine_failure(value, tmp_path):
    _, old = _pristine(tmp_path)
    secure = _secure()
    with pytest.raises(ValueError):
        old.parse_aspect_ratio(value)
    with pytest.raises(ValueError):
        secure.parse_aspect_ratio(value)


@pytest.mark.parametrize(
    "name,value,match",
    [
        ("upscale_by", 0.99, "upscale_by"),
        ("upscale_by", float("nan"), "finite"),
        ("batch_size", 0, "batch_size"),
        ("batch_size", True, "integer"),
        ("max_tile_size", 255, "max_tile_size"),
        ("length", 4097, "length"),
    ],
)
def test_direct_numeric_bounds_fail_closed(name, value, match):
    values = _preset_inputs()
    values[name] = value
    with pytest.raises((TypeError, ValueError), match=match):
        _secure().BobsLatentNode.execute(**values)


def test_unknown_choices_character_limit_allocation_limit_and_advanced_bounds():
    secure = _secure()
    with pytest.raises(ValueError, match="Unknown mp_size"):
        secure.BobsLatentNode.execute(**_preset_inputs(mp_size="9"))
    with pytest.raises(ValueError, match="Unknown model_type"):
        secure.BobsLatentNode.execute(**_preset_inputs(model_type="unknown"))
    with pytest.raises(ValueError, match="character limit"):
        secure.BobsLatentNode.execute(**_preset_inputs(aspect_ratio="1" * 129))
    with pytest.raises(ValueError, match="element limit"):
        secure.BobsLatentNodeAdvanced.execute(
            **_advanced_inputs(
                mp_size_float=16.0,
                model_type="CHROMA_RADIANCE",
                batch_size=64,
            )
        )
    for value in (0.0, 16.01, float("inf"), True):
        with pytest.raises((TypeError, ValueError)):
            secure.BobsLatentNodeAdvanced.execute(
                **_advanced_inputs(mp_size_float=value)
            )


def test_repeated_calls_are_zero_deterministic_and_do_not_advance_torch_rng():
    secure = _secure()
    state = torch.random.get_rng_state().clone()
    first = secure.BobsLatentNode.execute(
        **_preset_inputs(model_type="WAN22", length=33, batch_size=2)
    ).result
    second = secure.BobsLatentNode.execute(
        **_preset_inputs(model_type="WAN22", length=33, batch_size=2)
    ).result
    assert torch.equal(torch.random.get_rng_state(), state)
    assert first[1:] == second[1:]
    assert torch.equal(first[0]["samples"], second[0]["samples"])
    assert first[0]["samples"].data_ptr() != second[0]["samples"].data_ptr()


def test_real_guest_value_mode_video_latent_raw_denial_and_isolation():
    secure = _secure()
    inputs = _preset_inputs(
        aspect_ratio="16:9",
        mp_size="0.25",
        model_type="WAN",
        batch_size=2,
        length=17,
        max_tile_size=512,
    )
    expected = secure.BobsLatentNode.execute(**inputs).result

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="bobs-latent",
            node_id="1",
            node_type=secure.BobsLatentNode.__name__,
            tier="sandbox",
            node_module=secure.BobsLatentNode.__module__,
            inputs=inputs,
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        session = await GuestSession(
            "bobs-latent-optimizer", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=("raw",)
            )
            latent = await refs.resolve(result.result[0])
            assert latent["samples"].shape == expected[0]["samples"].shape
            assert torch.count_nonzero(latent["samples"]) == 0
            assert result.result[1:] == expected[1:]
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, _runtime(plan, refs), capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_real_outer_executor_preserves_declared_latent_and_scalar_types():
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.bobs_latent_optimizer_outer_test"
    )
    node = loaded.node_mappings["BobsLatentNodeAdvanced"]
    assert tuple(node.RETURN_TYPES) == ("LATENT", "INT", "INT", "FLOAT", "INT", "INT")
    inputs = _advanced_inputs(
        aspect_ratio="3:2",
        mp_size_float=0.25,
        model_type="FLUX2",
        batch_size=1,
    )

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "bobs-latent-outer", guest_runtime_root=V2
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
                prompt_id="bobs-latent-outer",
                unique_id="1",
                obj=node,
                input_data_all={key: [value] for key, value in inputs.items()},
                func=node.FUNCTION,
                v3_data=None,
            )
            output = returns[0].result
            assert isinstance(output[0], dict)
            assert isinstance(output[0]["samples"], torch.Tensor)
            assert output[0]["samples"].ndim == 4
            assert output[0]["samples"].shape[1] == 128
            assert torch.count_nonzero(output[0]["samples"]) == 0
            assert all(
                isinstance(value, int)
                for value in (output[1], output[2], output[4], output[5])
            )
            assert isinstance(output[3], float)
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_docs_and_stub_surface_are_exact():
    source = (V2 / "nodes.py").read_text()
    for required in (
        "SDK_REFS = False",
        'SDK_PERMISSIONS = ("raw",)',
        "MAX_LATENT_ELEMENTS",
        'torch.zeros(shape, device="cpu")',
        "io.NodeOutput(",
    ):
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
    ):
        assert forbidden not in source
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "bobs-latent-optimizer/xa0a175a"
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
