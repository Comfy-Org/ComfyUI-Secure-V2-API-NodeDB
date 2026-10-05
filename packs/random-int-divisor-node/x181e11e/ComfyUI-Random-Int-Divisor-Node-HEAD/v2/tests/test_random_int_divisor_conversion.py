from __future__ import annotations

import ast
import asyncio
import contextlib
import copy
import hashlib
import importlib.util
import io as stdio
import json
import os
import pathlib
import random
import shutil
import sys

import pytest


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "181e11e74a5b75bb43ca54604ddc2858e6a405d6"
DTS_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA256 = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
NODE_IDS = {
    "RandomIntegerNodeEfficient",
    "RandomIntegerNodeList",
    "RandomIntegerNodeEfficientAdvanced",
}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_package(root: pathlib.Path, name: str):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_v2(name="_secure_random_divisor_conversion_test"):
    return _import_package(V2, name)


def _import_pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package(root, "_pristine_random_divisor_conversion_test")


def _tree(root: pathlib.Path, *, omit_v2: bool = False) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _generated_manifest(pack) -> dict:
    nodes = {}
    prefix = pack.__name__ + "."
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": node_class.__module__.removeprefix(prefix),
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {"format": FORMAT, "nodes": nodes, "runtime": manifest_declaration(V2)}


def _runtime(plan):
    return _sdk.Runtime(
        refs=_sdk.InProcessRefResolver(),
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def _advanced_defaults() -> dict:
    return {
        "min_width": 256,
        "max_width": 1024,
        "width_divisors": "64",
        "min_height": 256,
        "max_height": 1024,
        "height_divisors": "64",
        "randomize_width": True,
        "randomize_height": True,
        "maintain_aspect_ratio": False,
        "aspect_ratio": 1.0,
        "aspect_ratio_basis": "width",
        "max_aspect_ratio_deviation": 10.0,
        "randomization_type": "Uniform",
        "gaussian_mean_width": 512,
        "gaussian_std_width": 128,
        "gaussian_mean_height": 512,
        "gaussian_std_height": 128,
        "exclude_widths": "",
        "exclude_heights": "",
        "max_total_megapixels": 1.0,
        "max_aspect_ratio_any_direction": 4.0,
    }


def test_actual_loader_census_manifest_contract_and_routes_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine = _import_pristine(tmp_path)
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {
        "RandomIntegerNodeEfficient": "Efficient Random Integer Generator",
        "RandomIntegerNodeList": "Random Integer Generator Using List",
        "RandomIntegerNodeEfficientAdvanced": "Advanced Random Integer Generator",
    }
    assert not hasattr(pristine, "WEB_DIRECTORY")

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == pristine.NODE_DISPLAY_NAME_MAPPINGS
    assert not hasattr(pack, "WEB_DIRECTORY")
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA256

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.random_divisor_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"
    assert not loaded.routes


def test_schemas_preserve_ids_inputs_defaults_outputs_and_stochastic_contract():
    classes = _import_v2().NODE_CLASS_MAPPINGS
    for node_id, node_class in classes.items():
        schema = node_class.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.category == "Custom/Random"
        assert schema.not_idempotent is True
        assert getattr(node_class, "SDK_REFS", False) is False
        assert getattr(node_class, "SDK_PERMISSIONS", ()) == ()
    for node_id in ("RandomIntegerNodeEfficient", "RandomIntegerNodeList"):
        schema = classes[node_id].GET_SCHEMA()
        assert [(item.id, item.io_type, item.default) for item in schema.inputs] == [
            ("min_value", "INT", 0),
            ("max_value", "INT", 100),
            ("divisor", "INT", 1),
        ]
        assert [(item.id, item.io_type) for item in schema.outputs] == [("INT", "INT")]
    advanced = classes["RandomIntegerNodeEfficientAdvanced"].GET_SCHEMA()
    assert [item.id for item in advanced.inputs] == list(_advanced_defaults())
    assert [item.default for item in advanced.inputs] == list(_advanced_defaults().values())
    assert advanced.inputs[10].options == ["width", "height"]
    assert advanced.inputs[12].options == ["Uniform", "Gaussian"]
    assert [(item.id, item.io_type) for item in advanced.outputs] == [
        ("Width", "INT"), ("Height", "INT"),
    ]


@pytest.mark.parametrize("node_id", ["RandomIntegerNodeEfficient", "RandomIntegerNodeList"])
def test_simple_nodes_match_pristine_across_seeds_ranges_and_errors(tmp_path, node_id):
    pristine = _import_pristine(tmp_path).NODE_CLASS_MAPPINGS[node_id]()
    secure = _import_v2().NODE_CLASS_MAPPINGS[node_id]
    cases = [
        (0, 100, 1), (2, 19, 4), (-19, -2, 4), (-17, 23, 7),
        (12, 12, 3), (999_999, 1_000_099, 32),
    ]
    for seed in range(100):
        for values in cases:
            random.seed(seed)
            expected = pristine.generate_random_integer(*values)
            random.seed(seed)
            actual = secure.execute(*values).result
            assert actual == expected
            assert values[0] <= actual[0] <= values[1]
            assert actual[0] % values[2] == 0
    for values in ((3, 2, 1), (0, 10, 0), (5, 6, 4)):
        with pytest.raises(ValueError) as expected:
            pristine.generate_random_integer(*values)
        with pytest.raises(ValueError) as actual:
            secure.execute(*values)
        assert str(actual.value) == str(expected.value)


def test_advanced_node_matches_pristine_for_all_feature_branches(tmp_path):
    pristine = _import_pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "RandomIntegerNodeEfficientAdvanced"
    ]()
    secure = _import_v2().NODE_CLASS_MAPPINGS[
        "RandomIntegerNodeEfficientAdvanced"
    ]
    variants = [
        {},
        {"randomization_type": "Gaussian"},
        {"randomize_width": False, "randomize_height": False},
        {"width_divisors": "32, 96", "height_divisors": "64,128",
         "exclude_widths": "256,512", "exclude_heights": "384"},
        {"maintain_aspect_ratio": True, "aspect_ratio": 16 / 9,
         "aspect_ratio_basis": "width", "max_aspect_ratio_deviation": 1.0},
        {"maintain_aspect_ratio": True, "aspect_ratio": 9 / 16,
         "aspect_ratio_basis": "height", "max_aspect_ratio_deviation": 1.0},
        {"max_total_megapixels": 0.25},
        {"min_width": 256, "max_width": 2048, "min_height": 256,
         "max_height": 512, "max_aspect_ratio_any_direction": 2.0},
        {"randomization_type": "unsupported"},
    ]
    for seed in range(80):
        for variant in variants:
            values = _advanced_defaults() | variant
            random.seed(seed)
            pristine_log = stdio.StringIO()
            with contextlib.redirect_stdout(pristine_log):
                expected = pristine.generate_random_dimensions(**values)
            random.seed(seed)
            secure_log = stdio.StringIO()
            with contextlib.redirect_stdout(secure_log):
                actual = secure.execute(**values).result
            assert actual == expected
            assert secure_log.getvalue() == pristine_log.getvalue()

    for variant in (
        {"min_width": 1024, "max_width": 256},
        {"min_height": 1024, "max_height": 256},
        {"aspect_ratio": 0},
        {"max_aspect_ratio_any_direction": 0},
        {"width_divisors": ""},
        {"height_divisors": "64,nope"},
        {"width_divisors": "0"},
        {"exclude_widths": "bad"},
    ):
        values = _advanced_defaults() | variant
        with pytest.raises(ValueError) as expected:
            pristine.generate_random_dimensions(**values)
        with pytest.raises(ValueError) as actual:
            secure.execute(**values)
        assert str(actual.value) == str(expected.value)


def test_real_guest_runs_without_capabilities_and_rejects_invalid_input():
    classes = _import_v2().NODE_CLASS_MAPPINGS

    async def run():
        session = await GuestSession("random-divisor-conversion").start()
        try:
            for node_id, inputs in (
                ("RandomIntegerNodeEfficient", {"min_value": -20, "max_value": 20, "divisor": 5}),
                ("RandomIntegerNodeList", {"min_value": 11, "max_value": 99, "divisor": 11}),
                ("RandomIntegerNodeEfficientAdvanced", _advanced_defaults()),
            ):
                node_class = classes[node_id]
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"random-divisor-{node_id}", node_id=node_id,
                    node_type=node_id, tier="sandbox", node_module=node_class.__module__,
                    inputs=inputs, permissions=(), method="execute",
                )
                result = await session.execute(plan, _runtime(plan), capabilities=())
                assert session.last_guest_pid not in (None, os.getpid())
                if node_id == "RandomIntegerNodeEfficientAdvanced":
                    width, height = result.result
                    assert width % 64 == height % 64 == 0
                    assert 256 <= width <= 1024 and 256 <= height <= 1024
                else:
                    value = result.result[0]
                    assert inputs["min_value"] <= value <= inputs["max_value"]
                    assert value % inputs["divisor"] == 0

            node_class = classes["RandomIntegerNodeEfficient"]
            bad = _sdk.ExecutionPlan(
                prompt_id="random-divisor-bad", node_id="bad",
                node_type="RandomIntegerNodeEfficient", tier="sandbox",
                node_module=node_class.__module__,
                inputs={"min_value": 5, "max_value": 6, "divisor": 4},
                permissions=(), method="execute",
            )
            with pytest.raises(Exception, match="No multiples"):
                await session.execute(bad, _runtime(bad), capabilities=())
        finally:
            await session.kill()

    asyncio.run(run())


def test_sources_are_pure_and_have_no_undeclared_authority():
    refused = {
        "app", "comfy", "comfy_execution", "comfy_extras", "execution",
        "folder_paths", "latent_preview", "main", "node_helpers", "nodes", "server",
        "os", "pathlib", "requests", "socket", "subprocess", "urllib",
    }
    for source in [V2 / "__init__.py", *sorted(V2.glob("*.py"))]:
        tree = ast.parse(source.read_text(), filename=str(source))
        for item in ast.walk(tree):
            names = []
            if isinstance(item, ast.Import):
                names = [alias.name for alias in item.names]
            elif isinstance(item, ast.ImportFrom) and item.module and item.level == 0:
                names = [item.module]
            assert not [name for name in names if name.split(".", 1)[0] in refused]
    joined = "\n".join(path.read_text() for path in sorted(V2.glob("*.py")))
    for forbidden in ("open(", "eval(", "exec(", "sdk.ctx(", "SDK_PERMISSIONS"):
        assert forbidden not in joined


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "random-int-divisor-node"
        / "x181e11e" / "random-int-divisor-node-x181e11e"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    # Preserve the CRLF bytes embedded in diffs of the pinned upstream files.
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "random-int-divisor-node" / "x181e11e"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert _tree(PACK, omit_v2=True) == _tree(fresh / PACK.name, omit_v2=True)


def test_no_cache_artifacts_in_pristine_or_v2():
    for root in (PACK, V2):
        assert not list(root.rglob("__pycache__"))
        assert not list(root.rglob("*.pyc"))
