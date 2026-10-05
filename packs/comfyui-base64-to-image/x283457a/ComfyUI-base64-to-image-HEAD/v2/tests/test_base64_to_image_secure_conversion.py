from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sys

import cv2
import numpy as np
import pytest
import torch


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "283457a6779e5456e15c7865a7126931a4992419"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches" / "comfyui-base64-to-image" / "x283457a" / (
    "comfyui-base64-to-image-x283457a"
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
    return _import_package("_secure_base64_to_image_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_base64_to_image_test", root)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(
                node_class, "SDK_PERMISSIONS", (),
            ) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs",
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
            part in {".git", "__pycache__", ".pytest_cache"}
            for part in relative.parts
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


def _base64_image(array: np.ndarray, extension: str = ".png") -> str:
    ok, encoded = cv2.imencode(extension, array)
    assert ok
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _assert_tensors_exact(actual, expected):
    assert len(actual) == len(expected) == 2
    for got, want in zip(actual, expected):
        assert isinstance(got, torch.Tensor)
        assert tuple(got.shape) == tuple(want.shape)
        assert got.dtype == want.dtype == torch.float32
        assert torch.equal(got.cpu(), want.cpu())


def test_pinned_actual_loader_census_entrypoint_and_schema_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "1 supported, 0 rejected, 0 pending" in report
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"LoadImageFromBase64"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"LoadImageFromBase64"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == (
        pristine.NODE_DISPLAY_NAME_MAPPINGS
    )

    schema = secure.LoadImageFromBase64.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "LoadImageFromBase64", "Load Image From Base64", "image",
    )
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("data", "STRING"),
    ]
    assert schema.inputs[0].default == ""
    assert [item.io_type for item in schema.outputs] == ["IMAGE", "MASK"]
    assert schema.is_output_node is False
    assert secure.LoadImageFromBase64.SDK_REFS is False
    assert secure.LoadImageFromBase64.SDK_PERMISSIONS == ("raw",)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [
        secure.LoadImageFromBase64,
    ]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.base64_to_image_secure_test",
    )
    assert set(loaded.node_mappings) == {"LoadImageFromBase64"}
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


@pytest.mark.parametrize("channels", (3, 4))
def test_rgb_and_rgba_png_pixels_and_masks_match_upstream(tmp_path, channels):
    yy, xx = np.indices((7, 11), dtype=np.uint16)
    planes = [
        ((xx * 17 + yy * 3) % 251).astype(np.uint8),
        ((xx * 5 + yy * 29) % 253).astype(np.uint8),
        ((xx * 11 + yy * 7) % 255).astype(np.uint8),
        ((xx * 19 + yy * 13) % 256).astype(np.uint8),
    ]
    encoded = _base64_image(np.stack(planes[:channels], axis=-1))
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "LoadImageFromBase64"
    ]().load_image(encoded)
    actual = _secure().LoadImageFromBase64.execute(encoded).result
    _assert_tensors_exact(actual, expected)
    if channels == 3:
        assert torch.count_nonzero(actual[1] != 1).item() == 0
    else:
        assert torch.unique(actual[1]).numel() > 1


def test_jpeg_and_whitespace_tolerant_base64_match_upstream(tmp_path):
    rng = np.random.default_rng(1234)
    bgr = rng.integers(0, 256, size=(13, 9, 3), dtype=np.uint8)
    encoded = _base64_image(bgr, ".jpg")
    wrapped = "\n  " + "\n".join(
        encoded[index:index + 64] for index in range(0, len(encoded), 64)
    ) + "  \n"
    expected = _pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "LoadImageFromBase64"
    ]().load_image(wrapped)
    actual = _secure().LoadImageFromBase64.execute(wrapped).result
    _assert_tensors_exact(actual, expected)


@pytest.mark.parametrize(
    "value,match",
    (
        ("", "empty"),
        ("%%%%", "empty"),
        (base64.b64encode(b"not an image").decode(), "supported image"),
        ("é", "ASCII"),
    ),
)
def test_malformed_inputs_fail_closed(value, match):
    with pytest.raises(ValueError, match=match):
        _secure().LoadImageFromBase64.execute(value)


def test_grayscale_and_resource_limits_fail_before_open_cv_allocation(monkeypatch):
    secure = _secure()
    module = sys.modules[f"{secure.__name__}.nodes"]
    gray = np.arange(16, dtype=np.uint8).reshape(4, 4)
    gray_data = _base64_image(gray)
    with pytest.raises(ValueError, match="RGB or RGBA"):
        secure.LoadImageFromBase64.execute(gray_data)

    color_data = _base64_image(np.zeros((4, 4, 3), dtype=np.uint8))
    monkeypatch.setattr(module, "MAX_ENCODED_BYTES", 3)
    with pytest.raises(ValueError, match="base64 input exceeds"):
        secure.LoadImageFromBase64.execute(color_data)
    monkeypatch.setattr(module, "MAX_ENCODED_BYTES", 1024 * 1024)
    monkeypatch.setattr(module, "MAX_DECODED_BYTES", 3)
    with pytest.raises(ValueError, match="decoded image exceeds"):
        secure.LoadImageFromBase64.execute(color_data)
    monkeypatch.setattr(module, "MAX_DECODED_BYTES", 1024 * 1024)
    monkeypatch.setattr(module, "MAX_DIMENSION", 3)
    with pytest.raises(ValueError, match="dimensions exceed"):
        secure.LoadImageFromBase64.execute(color_data)
    monkeypatch.setattr(module, "MAX_DIMENSION", 8192)
    monkeypatch.setattr(module, "MAX_PIXELS", 15)
    with pytest.raises(ValueError, match="pixel limit"):
        secure.LoadImageFromBase64.execute(color_data)


def test_real_guest_matches_pixels_and_denies_raw_without_capability(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    bgra = np.zeros((6, 8, 4), dtype=np.uint8)
    bgra[:, :, :3] = np.arange(8, dtype=np.uint8)[None, :, None] * 23
    bgra[:, :, 3] = np.arange(6, dtype=np.uint8)[:, None] * 41
    encoded = _base64_image(bgra)
    expected = pristine.NODE_CLASS_MAPPINGS[
        "LoadImageFromBase64"
    ]().load_image(encoded)

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "base64-to-image-conversion", guest_runtime_root=V2,
        ).start()
        try:
            plan = _sdk.ExecutionPlan(
                prompt_id="base64-to-image",
                node_id="1",
                node_type=secure.LoadImageFromBase64.__name__,
                tier="sandbox",
                node_module=secure.LoadImageFromBase64.__module__,
                inputs={"data": encoded},
                input_mode="values",
                permissions=("raw",),
                method="execute",
            )
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=("raw",),
            )
            resolved = tuple([await refs.resolve(item) for item in result.result])
            _assert_tensors_exact(resolved, expected)
            with pytest.raises(Exception, match="raw"):
                await session.execute(
                    plan, _runtime(plan, refs), capabilities=(),
                )
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_real_outer_executor_preserves_declared_image_and_mask_types(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "LoadImageFromBase64"
    ]()
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.base64_to_image_outer_test",
    )
    node = loaded.node_mappings["LoadImageFromBase64"]
    assert node.RETURN_TYPES == ["IMAGE", "MASK"]
    bgra = np.zeros((5, 7, 4), dtype=np.uint8)
    bgra[:, :, 0] = 10
    bgra[:, :, 1] = 80
    bgra[:, :, 2] = 240
    bgra[:, :, 3] = np.arange(5, dtype=np.uint8)[:, None] * 50
    encoded = _base64_image(bgra)
    expected = pristine.load_image(encoded)

    async def run():
        previous = _sdk.providers.execution_backend

        class OuterGuestBackend:
            def __init__(self):
                self.session = None

            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession(
                    "base64-to-image-outer", guest_runtime_root=V2,
                ).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(
                    plan, runtime, capabilities=("raw",),
                )

            async def shutdown(self):
                if self.session is not None:
                    await self.session.kill()

        backend = OuterGuestBackend()
        _sdk.providers.register_execution_backend(backend)
        try:
            returns = await execution._async_map_node_over_list(
                prompt_id="base64-to-image-outer",
                unique_id="1",
                obj=node,
                input_data_all={"data": [encoded]},
                func=node.FUNCTION,
                v3_data=None,
            )
            assert len(returns) == 1
            output = returns[0]
            assert all(isinstance(value, torch.Tensor) for value in output.result)
            _assert_tensors_exact(output.result, expected)
            assert tuple(node.RETURN_TYPES) == ("IMAGE", "MASK")
        finally:
            _sdk.providers.register_execution_backend(previous)
            await backend.shutdown()

    asyncio.run(run())


def test_manifest_stubs_license_gap_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert not (PACK / "LICENSE").exists()
    assert not (V2 / "LICENSE").exists()
    source = (V2 / "nodes.py").read_text()
    for required in (
        "MAX_ENCODED_BYTES", "MAX_DECODED_BYTES", "MAX_DIMENSION",
        "MAX_PIXELS", "BytesIO", "cv2.imdecode",
    ):
        assert required in source
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests",
        "aiohttp", "subprocess", "pathlib", "socket", "urllib",
        "ctx()", "_from_raw", "from_value", "localStorage",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-base64-to-image" / "x283457a"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
