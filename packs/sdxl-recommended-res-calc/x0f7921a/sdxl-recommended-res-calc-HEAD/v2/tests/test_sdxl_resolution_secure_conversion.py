from __future__ import annotations

import ast
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


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "0f7921a4e70e8288c027302472dc9a5d70804c12"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "82dea265a0ae3918ece66547a6e413558c419fbcb0a4cc19d52b3fd74057cc49"
PAIR = PACK_DB / "patches" / "sdxl-recommended-res-calc" / "x0f7921a" / (
    "sdxl-recommended-res-calc-x0f7921a"
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
    return _import_package("_secure_sdxl_resolution_test", V2)


def _upstream():
    return _import_package("_upstream_sdxl_resolution_test", PACK)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(
                node_class, "SDK_PERMISSIONS", ()) or ()),
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


def test_pinned_census_entrypoint_and_license_inventory_are_exact():
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "1 supported, 0 rejected, 0 pending" in report
    assert "does not invent or substitute license text" in report
    assert not (PACK / "LICENSE").exists()

    source = ast.parse((PACK / "customnode_sdxl_recommended_res_calc.py").read_text())
    classes = {item.name for item in source.body if isinstance(item, ast.ClassDef)}
    assert classes == {"RecommendedResCalc"}
    upstream = _upstream()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"RecommendedResCalc"}
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py") if V2 not in path.parents
    )
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    secure = _secure()
    assert secure.NODE_CLASS_MAPPINGS == {
        "RecommendedResCalc": secure.RecommendedResCalc,
    }
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == {
        "RecommendedResCalc": "Recommended Resolution Calculator",
    }
    extension = asyncio.run(secure.comfy_entrypoint())
    assert [item.GET_SCHEMA().node_id for item in asyncio.run(
        extension.get_node_list()
    )] == ["RecommendedResCalc"]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.sdxl_resolution_secure_test"
    )
    assert set(loaded.node_mappings) == {"RecommendedResCalc"}
    assert loaded.frontend_permissions == frozenset()


def test_schema_preserves_names_types_defaults_bounds_and_permissions():
    node = _secure().RecommendedResCalc
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "RecommendedResCalc", "Recommended Resolution Calculator", "utils",
    )
    assert [item.id for item in schema.inputs] == [
        "desiredXSIZE", "desiredYSIZE",
    ]
    assert [item.io_type for item in schema.inputs] == ["INT", "INT"]
    for item in schema.inputs:
        assert (item.default, item.min, item.max, item.step) == (
            1024, 0, 8192, 2,
        )
    assert [item.io_type for item in schema.outputs] == [
        "INT", "INT", "FLOAT", "FLOAT", "FLOAT",
    ]
    assert [item.display_name for item in schema.outputs] == [
        "recomm width", "recomm height", "upscale factor",
        "reverse upscale for 4x", "reverse upscale for 2x",
    ]
    assert schema.is_output_node is False
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()


def test_all_41_resolution_rows_and_traversal_order_match_upstream():
    upstream = sys.modules[
        f"{_upstream().__name__}.customnode_sdxl_recommended_res_calc"
    ]
    expected = tuple(upstream.accepted_ratios_horizontal.values()) + tuple(
        upstream.accepted_ratios_vertical.values()
    ) + tuple(upstream.accepted_ratios_square.values())
    secure = _secure()
    module = sys.modules[secure.RecommendedResCalc.__module__]
    assert len(expected) == 41
    assert module.ACCEPTED_RESOLUTIONS == expected


WIDTHS = (0, 2, 64, 320, 511, 512, 639, 704, 768, 960, 1024, 1216,
          1536, 1920, 2048, 4096, 8192)
HEIGHTS = (2, 64, 320, 511, 512, 576, 704, 832, 960, 1024, 1080, 1472,
           2048, 4096, 8192)


@pytest.mark.parametrize(
    ("width", "height"),
    [(width, height) for width in WIDTHS for height in HEIGHTS],
)
def test_scalar_behavior_is_exactly_differential(width, height):
    upstream = _upstream().NODE_CLASS_MAPPINGS["RecommendedResCalc"]().calc(
        width, height,
    )
    secure = _secure().RecommendedResCalc.execute(width, height).result
    assert secure == upstream


def test_upstream_zero_height_failure_and_zero_width_behavior_are_preserved():
    upstream_node = _upstream().NODE_CLASS_MAPPINGS["RecommendedResCalc"]()
    secure_node = _secure().RecommendedResCalc
    with pytest.raises(ZeroDivisionError, match="division by zero"):
        upstream_node.calc(1024, 0)
    with pytest.raises(ZeroDivisionError, match="division by zero"):
        secure_node.execute(1024, 0)
    assert secure_node.execute(0, 1024).result == upstream_node.calc(0, 1024)


def test_real_guest_executes_without_any_capabilities():
    node = _secure().RecommendedResCalc

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="sdxl-resolution-test", node_id="1",
            node_type=node.__name__, tier="sandbox",
            node_module=node.__module__,
            inputs={"desiredXSIZE": 1920, "desiredYSIZE": 1080},
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "sdxl-resolution-pack", guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            return result.result, session.last_guest_pid
        finally:
            await session.kill()

    result, guest_pid = asyncio.run(run())
    expected = _upstream().NODE_CLASS_MAPPINGS["RecommendedResCalc"]().calc(
        1920, 1080,
    )
    assert result == expected
    assert guest_pid not in (None, os.getpid())


def test_manifest_contract_and_ambient_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests",
        "aiohttp", "subprocess", "open(", "os.", "sys.", "ctx()",
        "torch", "numpy",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "sdxl-recommended-res-calc" / "x0f7921a"
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
