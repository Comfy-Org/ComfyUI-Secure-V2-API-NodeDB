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
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "c385f389ee53cc15cd7f92edb76c1b35f45e0ba7"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "constrainresolution" / "xc385f38" / (
    "constrainresolution-xc385f38"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
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
    return _import_package("_secure_constrainresolution_test", V2)


def _upstream():
    name = "_upstream_constrainresolution_test"
    package = _import_package(name, PACK)
    package.ConstrainResolution = sys.modules[f"{name}.nodes"].ConstrainResolution
    return package


def _manifest(pack) -> dict:
    node = pack.ConstrainResolution
    return {
        "format": FORMAT,
        "nodes": {
            "ConstrainResolution": {
                "class": "ConstrainResolution",
                "methods": {
                    method: method in node.__dict__
                    for method in (
                        "check_lazy_status", "fingerprint_inputs", "validate_inputs"
                    )
                },
                "module": "nodes",
                "permissions": ["raw"],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": True,
            }
        },
        "runtime": manifest_declaration(V2),
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts)
    }


def _schema_signature(schema):
    return {
        "node_id": schema.node_id,
        "display_name": schema.display_name,
        "category": schema.category,
        "inputs": [
            (
                item.id,
                item.io_type,
                tuple(item.options) if getattr(item, "options", None) else None,
                getattr(item, "default", None),
                getattr(item, "min", None),
                getattr(item, "max", None),
            )
            for item in schema.inputs
        ],
        "outputs": [(item.io_type, item.display_name) for item in schema.outputs],
    }


def test_exact_census_schema_manifest_and_contract():
    upstream = _upstream()
    secure = _secure()
    old_extension = asyncio.run(upstream.comfy_entrypoint())
    new_extension = asyncio.run(secure.comfy_entrypoint())
    old_nodes = asyncio.run(old_extension.get_node_list())
    new_nodes = asyncio.run(new_extension.get_node_list())
    assert [item.GET_SCHEMA().node_id for item in old_nodes] == ["ConstrainResolution"]
    assert [item.GET_SCHEMA().node_id for item in new_nodes] == ["ConstrainResolution"]
    assert _schema_signature(old_nodes[0].GET_SCHEMA()) == _schema_signature(
        new_nodes[0].GET_SCHEMA()
    )
    assert not list(PACK.rglob("*.js"))
    assert "PromptServer" not in (PACK / "nodes.py").read_text()
    assert not list(PACK.rglob("*routes*.py"))

    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.constrainresolution_test")
    assert set(loaded.node_mappings) == {"ConstrainResolution"}
    assert loaded.web_directory is None
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)


@pytest.mark.parametrize(
    "width,height,min_res,max_res,multiple,mode",
    [
        (1920, 1080, 704, 1280, 2, "Prioritize Min Resolution"),
        (1080, 1920, 704, 1280, 8, "Prioritize Max Resolution (Strict)"),
        (1001, 641, 512, 1536, 32, "Prioritize Min Resolution"),
        (4096, 512, 256, 1024, 64, "Prioritize Max Resolution (Strict)"),
        (777, 777, 704, 1280, 256, "Prioritize Min Resolution"),
    ],
)
def test_dimension_math_matches_upstream(width, height, min_res, max_res, multiple, mode):
    old = _upstream().ConstrainResolution
    new = _secure().ConstrainResolution
    assert new.calculate_optimal_dimensions(
        width, height, min_res, max_res, multiple, mode
    ) == old.calculate_optimal_dimensions(
        width, height, min_res, max_res, multiple, mode
    )


@pytest.mark.parametrize("method", ["bilinear", "bicubic", "nearest-exact", "area", "lanczos"])
def test_all_resize_methods_are_pixel_equivalent(method):
    old = _upstream().ConstrainResolution
    new = _secure().ConstrainResolution
    source = torch.linspace(0, 1, 2 * 9 * 13 * 3, dtype=torch.float32).reshape(2, 9, 13, 3)
    expected = old.resize_image(source, 17, 11, method)
    actual = new.resize_image(source, 17, 11, method)
    assert torch.equal(actual, expected)


@pytest.mark.parametrize("position", ["center", "top", "bottom", "left", "right"])
def test_all_crop_positions_are_pixel_equivalent(position):
    old = _upstream().ConstrainResolution
    new = _secure().ConstrainResolution
    source = torch.arange(2 * 17 * 19 * 3, dtype=torch.float32).reshape(2, 17, 19, 3)
    assert torch.equal(
        new.crop_image(source, 11, 9, position),
        old.crop_image(source, 11, 9, position),
    )


def test_real_isolated_guest_matches_upstream_and_preserves_original_ref():
    upstream = _upstream()
    secure = _secure()
    source = torch.linspace(0, 1, 1 * 17 * 29 * 3, dtype=torch.float32).reshape(1, 17, 29, 3)
    inputs = {
        "min_res": 24,
        "max_res": 40,
        "multiple_of": 8,
        "resize_method": "lanczos",
        "constraint_mode": "Prioritize Max Resolution (Strict)",
        "crop_as_required": True,
        "crop_position": "right",
    }
    expected = upstream.ConstrainResolution.execute(source, **inputs).result

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", source))
        session = await GuestSession(
            "constrainresolution-conversion", guest_runtime_root=V2
        ).start()
        try:
            plan = _sdk.ExecutionPlan(
                prompt_id="constrainresolution",
                node_id="1",
                node_type="ConstrainResolution",
                tier="compute",
                node_module=secure.ConstrainResolution.__module__,
                inputs={"image": image, **inputs},
                permissions=("raw",),
            )
            runtime = _sdk.Runtime(
                refs=refs,
                ctx=_sdk.InProcessCtxProvider().build(plan),
                ops=_sdk.InProcessOps(),
            )
            result = await session.execute(plan, runtime, capabilities=("raw",))
            resized = await refs.resolve(result.result[0])
            return result, resized, image, session.last_guest_pid
        finally:
            await session.kill()

    result, resized, image, pid = asyncio.run(run())
    assert torch.equal(resized, expected[0])
    assert result.result[1].id == image.id
    assert result.result[2:] == expected[2:]
    assert pid not in (None, os.getpid())


def test_validation_and_resource_bounds_fail_closed():
    node = _secure().ConstrainResolution
    assert node.validate_inputs(704, 1280, 2, "Prioritize Min Resolution") is True
    assert "multiple_of" in node.validate_inputs(
        1, 8, 16, "Prioritize Max Resolution (Strict)"
    )
    with pytest.raises(ValueError, match="safety limit"):
        node.calculate_optimal_dimensions(
            1, 690, 704, 1280, 2, "Prioritize Min Resolution"
        )

    class Oversized:
        async def raw(self):
            return torch.empty((257, 1, 1, 3))

    with pytest.raises(ValueError, match="batch"):
        asyncio.run(node.execute(
            Oversized(), 1, 2, 1, "nearest-exact",
            "Prioritize Max Resolution (Strict)", False, "center",
        ))


def test_python_authority_is_only_bounded_raw_image_compute():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "socket", "open(", "comfy.utils", "sdk.ctx()",
    ):
        assert forbidden not in source
    assert 'SDK_PERMISSIONS = ("raw",)' in source
    assert "await image.raw()" in source
    assert "await sdk.ImageRef._from_raw(resized_image)" in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "constrainresolution" / "xc385f38"
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
