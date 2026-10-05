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


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "1a2c5db1768dc0c1260082a5e5653dca9274786c"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "videoresolutions" / "x1a2c5db" / (
    "videoresolutions-x1a2c5db"
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
    return _import_package("_secure_videoresolutions_test", V2)


def _upstream(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "_upstream_videoresolutions_nodes_test", PACK / "nodes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, "nodes", module)
    return _import_package("_upstream_videoresolutions_test", PACK)


def _manifest(pack) -> dict:
    node = pack.HunyuanResolutions
    return {
        "format": FORMAT,
        "nodes": {
            "HunyuanResolutions": {
                "class": "HunyuanResolutions",
                "methods": {
                    method: method in node.__dict__
                    for method in (
                        "check_lazy_status", "fingerprint_inputs", "validate_inputs"
                    )
                },
                "module": "nodes",
                "permissions": [],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": False,
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


def test_exact_census_schema_manifest_and_contract(monkeypatch):
    upstream = _upstream(monkeypatch)
    secure = _secure()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"HunyuanResolutions"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"HunyuanResolutions"}
    assert not list(PACK.rglob("*.js"))
    assert "PromptServer" not in (PACK / "nodes.py").read_text()

    old = upstream.NODE_CLASS_MAPPINGS["HunyuanResolutions"]
    schema = secure.HunyuanResolutions.GET_SCHEMA()
    old_required = old.INPUT_TYPES()["required"]
    assert (schema.node_id, schema.display_name, schema.category) == (
        "HunyuanResolutions", "HunyuanResolutions", old.CATEGORY
    )
    assert [item.id for item in schema.inputs] == list(old_required)
    assert list(schema.inputs[0].options) == old_required["resolution"][0]
    assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES)
    assert [item.display_name for item in schema.outputs] == list(old.RETURN_NAMES)

    extension = asyncio.run(secure.comfy_entrypoint())
    assert [item.GET_SCHEMA().node_id for item in asyncio.run(extension.get_node_list())] == [
        "HunyuanResolutions"
    ]
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.videoresolutions_test")
    assert set(loaded.node_mappings) == {"HunyuanResolutions"}
    assert loaded.web_directory is None
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)


def test_every_preset_and_heading_matches_upstream(monkeypatch):
    old = _upstream(monkeypatch).NODE_CLASS_MAPPINGS["HunyuanResolutions"]()
    new = _secure().HunyuanResolutions
    options = old.INPUT_TYPES()["required"]["resolution"][0]
    assert len(options) == 46
    for option in options:
        assert new.execute(option).result == old.generate(option)


@pytest.mark.parametrize("value", ["", "not a size", "1x", "1x2x3", "abcx12"])
def test_malformed_values_preserve_legacy_errors(monkeypatch, value):
    old = _upstream(monkeypatch).NODE_CLASS_MAPPINGS["HunyuanResolutions"]()
    new = _secure().HunyuanResolutions
    with pytest.raises(Exception) as old_error:
        old.generate(value)
    with pytest.raises(type(old_error.value)):
        new.execute(value)


def test_real_isolated_guest_has_zero_authority():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "videoresolutions-conversion", guest_runtime_root=V2
        ).start()
        try:
            plan = _sdk.ExecutionPlan(
                prompt_id="videoresolutions",
                node_id="1",
                node_type="HunyuanResolutions",
                tier="sandbox",
                node_module=secure.HunyuanResolutions.__module__,
                inputs={"resolution": "1728x576 (3:1)"},
                permissions=(),
            )
            runtime = _sdk.Runtime(
                refs=refs,
                ctx=_sdk.InProcessCtxProvider().build(plan),
                ops=_sdk.InProcessOps(),
            )
            result = await session.execute(plan, runtime, capabilities=())
            return result, session.last_guest_pid
        finally:
            await session.kill()

    result, pid = asyncio.run(run())
    assert result.result == (1728, 576)
    assert pid not in (None, os.getpid())


def test_python_has_no_ambient_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "socket", "open(", "torch", "numpy", "sdk.ctx()", "comfy.model",
    ):
        assert forbidden not in source
    assert "SDK_PERMISSIONS = ()" in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "videoresolutions" / "x1a2c5db"
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
