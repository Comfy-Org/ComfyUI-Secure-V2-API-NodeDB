from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import random
import shutil
import sys

sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMMIT = "07a7185aba4a52629a05f986d06651d42b6293d2"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-mittimi-recalculate-size"
    / "x07a7185"
    / "comfyui-mittimi-recalculate-size-x07a7185"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

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
    return _import_package("_secure_mittimi_size_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    sys.modules.setdefault("comfy", type(sys)("comfy"))
    sys.modules.setdefault("comfy.sd", type(sys)("comfy.sd"))
    return _import_package("_pristine_mittimi_size_test", root)


def _manifest(pack) -> dict:
    node = pack.RecalculateSizeMittimi01
    return {
        "format": FORMAT,
        "nodes": {
            "RecalculateSizeMittimi01": {
                "module": "nodes",
                "class": "RecalculateSizeMittimi01",
                "sdk_refs": False,
                "permissions": [],
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
            part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in relative.parts
        ):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _runtime(plan):
    return _sdk.Runtime(
        refs=_sdk.InProcessRefResolver(),
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_census_schema_manifest_and_no_frontend_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"RecalculateSizeMittimi01"}
    assert set(secure.NODE_CLASS_MAPPINGS) == set(pristine.NODE_CLASS_MAPPINGS)
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == secure.NODE_DISPLAY_NAME_MAPPINGS
    assert pristine.WEB_DIRECTORY == "./js"
    assert not (PACK / "js").exists()
    assert not hasattr(secure, "WEB_DIRECTORY")

    legacy = pristine.NODE_CLASS_MAPPINGS["RecalculateSizeMittimi01"]
    node = secure.RecalculateSizeMittimi01
    schema = node.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "RecalculateSizeMittimi01"
    assert schema.display_name == "RecalculateSize01"
    assert schema.category == legacy.CATEGORY == "mittimiTools"
    assert [item.id for item in schema.inputs] == ["Width", "Height", "Magnification"]
    assert [item.io_type for item in schema.inputs] == ["INT", "INT", "FLOAT"]
    assert [(item.default, item.min, item.max) for item in schema.inputs] == [
        (512, 1, 2_147_483_647),
        (512, 1, 2_147_483_647),
        (1.0, 0.01, 9999.99),
    ]
    assert schema.inputs[2].step == 0.01
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("width", "INT"),
        ("height", "INT"),
    ]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()
    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.mittimi_size_test")
    assert set(loaded.node_mappings) == {"RecalculateSizeMittimi01"}
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


def test_two_hundred_scalar_cases_match_upstream(tmp_path):
    pristine = _pristine(tmp_path).NODE_CLASS_MAPPINGS["RecalculateSizeMittimi01"]()
    secure = _secure()
    cases = [(1, 1, 0.01), (512, 512, 1.0), (2_147_483_647, 1, 9999.99)]
    generator = random.Random(44771)
    for _ in range(197):
        cases.append(
            (
                generator.randint(1, 2_147_483_647),
                generator.randint(1, 2_147_483_647),
                generator.uniform(0.01, 9999.99),
            )
        )
    for width, height, magnification in cases:
        expected = pristine.runRecalculateSize(width, height, magnification)
        actual = secure.RecalculateSizeMittimi01.execute(
            width, height, magnification
        ).result
        assert actual == expected


def test_real_isolated_guest_executes_without_capabilities():
    secure = _secure()

    async def run():
        node = secure.RecalculateSizeMittimi01
        inputs = {"Width": 1234, "Height": 987, "Magnification": 2.75}
        plan = _sdk.ExecutionPlan(
            prompt_id="mittimi-size",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs=inputs,
            input_mode="values",
            permissions=(),
            method="execute",
        )
        session = await GuestSession(
            "mittimi-size-secure-conversion", guest_runtime_root=V2
        ).start()
        try:
            result = await session.execute(plan, _runtime(plan), capabilities=())
            assert result.result == (3393, 2714)
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_stubs_license_authority_patch_and_cache_are_exact(tmp_path):
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy",
        "torch",
        "numpy",
        "folder_paths",
        "PromptServer",
        "requests",
        "subprocess",
        "open(",
        "ctx()",
    ):
        assert forbidden not in source

    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-mittimi-recalculate-size" / "x07a7185"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)
    for name in ("__pycache__", ".pytest_cache", ".ruff_cache"):
        assert not list(PACK.rglob(name))
    assert not list(PACK.rglob("*.pyc"))
