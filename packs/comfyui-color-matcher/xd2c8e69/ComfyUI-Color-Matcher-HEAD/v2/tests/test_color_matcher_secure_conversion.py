from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.metadata
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
COMMIT = "d2c8e69387c01fb93c63028fe16d52554eeba1e4"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-color-matcher"
    / "xd2c8e69"
    / "comfyui-color-matcher-xd2c8e69"
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
    return _import_package("_secure_color_matcher_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_color_matcher_test", root)


def _manifest(pack) -> dict:
    node = pack.ColorMatch
    return {
        "format": FORMAT,
        "nodes": {
            "ColorMatch": {
                "module": "nodes",
                "class": "ColorMatch",
                "sdk_refs": False,
                "permissions": ["raw"],
                "methods": {
                    method: method in node.__dict__
                    for method in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
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


def _images(batch: int, height=18, width=22, offset=0.0):
    generator = torch.Generator().manual_seed(4200 + batch + int(offset * 100))
    value = torch.rand((batch, height, width, 3), generator=generator)
    return (value * 0.8 + offset).clamp(0.0, 1.0)


def _exact(actual, expected):
    assert actual.dtype == expected.dtype == torch.float32
    assert tuple(actual.shape) == tuple(expected.shape)
    assert torch.equal(actual, expected)
    assert torch.isfinite(actual).all()


def test_pinned_actual_loader_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"ColorMatch"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"ColorMatch"}
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]

    legacy = pristine.NODE_CLASS_MAPPINGS["ColorMatch"]
    node = secure.ColorMatch
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "ColorMatch"
    assert schema.display_name == "Color Match"
    assert schema.category == legacy.CATEGORY == "image/color"
    assert [item.id for item in schema.inputs] == [
        "image_ref",
        "image_target",
        "method",
    ]
    assert [item.io_type for item in schema.inputs] == ["IMAGE", "IMAGE", "COMBO"]
    assert schema.inputs[2].options == legacy.METHODS == secure.METHODS
    assert schema.inputs[2].default == "mkl"
    assert [(item.id, item.io_type) for item in schema.outputs] == [("image", "IMAGE")]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ("raw",)
    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.color_matcher_secure_census_test"
    )
    assert set(loaded.node_mappings) == {"ColorMatch"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes
    assert importlib.metadata.version("color-matcher") == "0.6.0"


@pytest.mark.parametrize(
    "method", ("mkl", "hm", "reinhard", "mvgd", "hm-mvgd-hm", "hm-mkl-hm")
)
def test_all_six_methods_are_pixel_exact_to_upstream(tmp_path, method):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ColorMatch"]()
    secure = _secure()
    reference = _images(2, offset=0.12)
    target = _images(3, offset=0.03)
    expected = pristine.match_color(reference, target, method)[0]
    actual = secure.ColorMatch.execute(reference, target, method).result[0]
    _exact(actual, expected)


def test_reference_uses_only_first_frame_and_target_order_is_preserved(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ColorMatch"]()
    secure = _secure()
    first = _images(1, offset=0.08)
    reference_a = torch.cat((first, _images(1, offset=0.20)), dim=0)
    reference_b = torch.cat((first, _images(1, offset=0.01)), dim=0)
    target = _images(4, offset=0.02)
    forward = secure.ColorMatch.execute(reference_a, target, "reinhard").result[0]
    same_first = secure.ColorMatch.execute(reference_b, target, "reinhard").result[0]
    reverse = secure.ColorMatch.execute(reference_a, target.flip(0), "reinhard").result[
        0
    ]
    _exact(forward, pristine.match_color(reference_a, target, "reinhard")[0])
    _exact(forward, same_first)
    _exact(forward, reverse.flip(0))


def test_uint8_truncation_and_output_bounds_match_upstream(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ColorMatch"]()
    secure = _secure()
    reference = torch.tensor(
        [[[[0.0, 0.25, 1.0], [0.999, 0.501, 0.003]]] * 8],
        dtype=torch.float32,
    ).repeat(1, 8, 1, 1)
    target = _images(2, height=8, width=16)
    expected = pristine.match_color(reference, target, "hm")[0]
    actual = secure.ColorMatch.execute(reference, target, "hm").result[0]
    _exact(actual, expected)
    assert actual.min() >= 0.0 and actual.max() <= 1.0
    quantized = actual * 255.0
    torch.testing.assert_close(quantized, quantized.round(), rtol=0, atol=1e-5)


def test_malformed_method_channels_batch_and_size_fail_closed():
    secure = _secure()
    image = _images(1, height=8, width=8)
    with pytest.raises(ValueError, match="unsupported"):
        secure.ColorMatch.execute(image, image, "not-a-method")
    with pytest.raises(TypeError, match="BHWC"):
        secure.ColorMatch.execute(image[0], image, "mkl")
    with pytest.raises(ValueError, match="three RGB"):
        secure.ColorMatch.execute(image, image[..., :2], "mkl")
    with pytest.raises(ValueError, match="batch"):
        secure.ColorMatch.execute(image, image[:0], "mkl")
    too_large = torch.empty(
        (1, 1, secure.nodes.MAX_TENSOR_ELEMENTS // 3 + 1, 3), device="meta"
    )
    with pytest.raises(ValueError, match="tensor-size"):
        secure.ColorMatch.execute(too_large, image, "mkl")


def test_real_isolated_guest_matches_upstream_and_denies_raw(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["ColorMatch"]()
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        reference = _images(1, height=12, width=16, offset=0.11)
        target = _images(2, height=12, width=16, offset=0.04)
        reference_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", reference))
        target_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", target))
        node = secure.ColorMatch
        plan = _sdk.ExecutionPlan(
            prompt_id="color-matcher",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={
                "image_ref": reference_ref,
                "image_target": target_ref,
                "method": "hm-mkl-hm",
            },
            input_mode="values",
            permissions=("raw",),
            method="execute",
        )
        runtime = _runtime(plan, refs)
        session = await GuestSession(
            "color-matcher-secure-conversion", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=("raw",))
            actual = await refs.resolve(result.result[0])
            expected = pristine.match_color(reference, target, "hm-mkl-hm")[0]
            _exact(actual, expected)
            with pytest.raises(Exception, match="raw"):
                await session.execute(plan, runtime, capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_stubs_license_and_authority_boundary_are_exact():
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    assert source.count('SDK_PERMISSIONS = ("raw",)') == 1
    for forbidden in (
        "import comfy",
        "ProgressBar",
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
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-color-matcher" / "xd2c8e69"
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
