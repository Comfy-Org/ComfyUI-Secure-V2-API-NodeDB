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
CORE = pathlib.Path(
    os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes")
).expanduser().resolve()
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "ee9d798ec7c8a95c5f8d6b96c4eef90927762870"
TREE = "ba0fe31ad380baee6f612bb2119e55aed0a59609"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
NODE_ID = "ColorCorrectGPU"
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    "README.md",
    "__init__.py",
    "color_correct_gpu.py",
    "pyproject.toml",
}
PAIR = PACK_DB / "patches" / "color-correct-gpu" / "xee9d798" / (
    "color-correct-gpu-xee9d798"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

import execution  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_package(name: str, root: pathlib.Path):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
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
    return _import_package("_secure_color_correct_gpu_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    pack = _import_package("_pristine_color_correct_gpu_test", root)
    module = sys.modules[pack.ColorCorrectGPU.__module__]
    module._work_device = lambda image: image.device
    module._comfy_intermediate_device = lambda fallback: fallback
    return pack


def _tree(root: pathlib.Path) -> dict[str, str]:
    result = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root)
        if not item.is_file() or any(
            part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _manifest(pack) -> dict:
    prefix = pack.__name__ + "."
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": node_class.__module__.removeprefix(prefix),
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
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


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _inputs(image: torch.Tensor, **overrides):
    values = {
        "image": image,
        "temperature": 0,
        "hue": 0,
        "brightness": 0,
        "contrast": 0,
        "saturation": 0,
        "gamma": 1,
    }
    values.update(overrides)
    return values


def _expected(pristine, inputs):
    return pristine.ColorCorrectGPU().color_correct(**inputs)[0]


def test_actual_loader_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert TREE == "ba0fe31ad380baee6f612bb2119e55aed0a59609"
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert pristine.NODE_CLASS_MAPPINGS == {NODE_ID: pristine.ColorCorrectGPU}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {
        NODE_ID: "Color Correct GPU"
    }
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert set(secure.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == {
        NODE_ID: "Color Correct GPU"
    }
    assert not hasattr(secure, "WEB_DIRECTORY")
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()

    node = secure.ColorCorrectGPU
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == NODE_ID
    assert schema.display_name == "Color Correct GPU"
    assert schema.category == "ArtVenture/Post Processing"
    assert schema.description == pristine.ColorCorrectGPU.DESCRIPTION
    assert schema.search_aliases == pristine.ColorCorrectGPU.SEARCH_ALIASES
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("image", "IMAGE"),
        ("temperature", "FLOAT"),
        ("hue", "FLOAT"),
        ("brightness", "FLOAT"),
        ("contrast", "FLOAT"),
        ("saturation", "FLOAT"),
        ("gamma", "FLOAT"),
    ]
    assert [
        (item.default, item.min, item.max, item.step)
        for item in schema.inputs[1:]
    ] == [
        (0, -100, 100, 5),
        (0, -90, 90, 5),
        (0, -100, 100, 5),
        (0, -100, 100, 5),
        (0, -100, 100, 5),
        (1, 0.2, 2.2, 0.1),
    ]
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("image", "IMAGE")
    ]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.color_correct_gpu_secure_test"
    )
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"temperature": 55},
        {"temperature": -70},
        {"hue": 65},
        {"hue": -45},
        {"brightness": 35},
        {"contrast": -40},
        {"saturation": 75},
        {"saturation": -100},
        {"gamma": 1.8},
        {
            "temperature": 35,
            "hue": -30,
            "brightness": 15,
            "contrast": 25,
            "saturation": 40,
            "gamma": 0.7,
        },
    ],
)
def test_each_adjustment_and_combined_order_match_pinned_upstream(
    tmp_path, overrides
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    image = torch.linspace(0, 1, 2 * 7 * 9 * 3).reshape(2, 7, 9, 3)
    inputs = _inputs(image.clone(), **overrides)
    expected = _expected(pristine, _inputs(image.clone(), **overrides))
    actual = secure.ColorCorrectGPU.execute(**inputs).result[0]
    assert torch.equal(actual, expected)


def test_grayscale_hue_alpha_dtype_and_chunking_match_upstream(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    module = sys.modules[secure.ColorCorrectGPU.__module__]
    image = torch.full((5, 3, 4, 4), 0.42, dtype=torch.float64)
    image[..., 3] = torch.linspace(0, 1, 5 * 3 * 4).reshape(5, 3, 4)
    inputs = _inputs(
        image.clone(),
        temperature=-25,
        hue=90,
        brightness=-15,
        contrast=30,
        saturation=100,
        gamma=1.4,
    )
    expected = _expected(pristine, copy.deepcopy(inputs))
    old_target = module._TARGET_PIXELS_PER_CHUNK
    module._TARGET_PIXELS_PER_CHUNK = 12
    try:
        actual = secure.ColorCorrectGPU.execute(**inputs).result[0]
    finally:
        module._TARGET_PIXELS_PER_CHUNK = old_target
    assert torch.equal(actual, expected)
    assert torch.equal(actual[..., 3], image[..., 3])
    assert actual.dtype == image.dtype
    assert actual.device == image.device


def test_validation_is_bounded_and_fails_closed():
    secure = _secure()
    module = sys.modules[secure.ColorCorrectGPU.__module__]
    with pytest.raises(TypeError, match="tensor"):
        module._validate_image([])
    with pytest.raises(ValueError, match="shape"):
        module._validate_image(torch.zeros((3, 8, 8)))
    with pytest.raises(ValueError, match="channels"):
        module._validate_image(torch.zeros((1, 2, 2, 5)))
    with pytest.raises(TypeError, match="floating"):
        module._validate_image(torch.zeros((1, 2, 2, 3), dtype=torch.uint8))
    with pytest.raises(ValueError, match="batch"):
        module._validate_image(torch.empty((257, 1, 1, 3), device="meta"))
    with pytest.raises(ValueError, match="dimensions"):
        module._validate_image(torch.empty((1, 8193, 1, 3), device="meta"))
    with pytest.raises(ValueError, match="element"):
        module._validate_image(torch.empty((1, 8192, 8192, 3), device="meta"))


def test_real_guest_value_mode_matches_pixels_and_denies_raw_without_capability(
    tmp_path,
):
    pristine = _pristine(tmp_path)
    secure = _secure()
    image = torch.linspace(0, 1, 2 * 6 * 5 * 4).reshape(2, 6, 5, 4)
    inputs = _inputs(
        image,
        temperature=40,
        hue=-25,
        brightness=10,
        contrast=20,
        saturation=35,
        gamma=0.8,
    )
    expected = _expected(pristine, copy.deepcopy(inputs))

    async def run():
        refs = _sdk.InProcessRefResolver()
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        plan_inputs = dict(inputs)
        plan_inputs["image"] = image_ref
        plan = _sdk.ExecutionPlan(
            prompt_id="color-correct-gpu",
            node_id="1",
            node_type=secure.ColorCorrectGPU.__name__,
            tier="sandbox",
            node_module=secure.ColorCorrectGPU.__module__,
            inputs=plan_inputs,
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        session = await GuestSession(
            "color-correct-gpu-conversion", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=("raw",)
            )
            actual = await refs.resolve(result.result[0])
            assert torch.equal(actual, expected)
            assert session.last_guest_pid not in (None, os.getpid())
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    plan, _runtime(plan, refs), capabilities=()
                )
        finally:
            await session.kill()

    asyncio.run(run())


def test_real_outer_executor_preserves_declared_image_type(tmp_path):
    pristine = _pristine(tmp_path)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.color_correct_gpu_outer_test"
    )
    node = loaded.node_mappings[NODE_ID]
    assert node.RETURN_TYPES == ["IMAGE"]
    image = torch.linspace(0, 1, 4 * 5 * 3).reshape(1, 4, 5, 3)
    inputs = _inputs(
        image,
        temperature=-35,
        hue=45,
        brightness=20,
        contrast=-10,
        saturation=55,
        gamma=1.2,
    )
    expected = _expected(pristine, copy.deepcopy(inputs))

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "color-correct-gpu-outer", guest_runtime_root=V2
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(
                    plan, runtime, capabilities=("raw",)
                )

            async def shutdown(self):
                if self.session is not None:
                    await self.session.kill()

        backend = OuterGuestBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            returns = await execution._async_map_node_over_list(
                prompt_id="color-correct-gpu-outer",
                unique_id="1",
                obj=node,
                input_data_all={key: [value] for key, value in inputs.items()},
                func=node.FUNCTION,
                v3_data=None,
            )
            assert len(returns) == 1
            output = returns[0]
            assert isinstance(output.result[0], torch.Tensor)
            assert torch.equal(output.result[0], expected)
            assert tuple(node.RETURN_TYPES) == ("IMAGE",)
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_authority_surface_is_only_declared_value_mode_raw_compute():
    source = (V2 / "nodes.py").read_text()
    for required in (
        "SDK_REFS = False",
        'SDK_PERMISSIONS = ("raw",)',
        "MAX_BATCH",
        "MAX_DIMENSION",
        "MAX_ELEMENTS",
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
        "socket",
        "urllib",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "color-correct-gpu" / "xee9d798"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_no_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
    assert not list(PACK.rglob(".ruff_cache"))
