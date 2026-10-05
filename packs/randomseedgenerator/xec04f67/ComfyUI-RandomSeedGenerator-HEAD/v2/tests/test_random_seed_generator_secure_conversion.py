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
import time

import pytest


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "ec04f6748e0aa57ea5165baa149188eedb5980b8"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches/randomseedgenerator/xec04f67/randomseedgenerator-xec04f67"

for root in (BACKEND, CORE, COMFYUI):
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
    return _import_package("_secure_random_seed_generator_test", V2)


def _pristine(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_random_seed_generator_test", root)


def _manifest(pack):
    node = pack.NODE_CLASS_MAPPINGS["AdvancedSeedGenerator"]
    return {
        "format": FORMAT,
        "nodes": {
            "AdvancedSeedGenerator": {
                "module": "random_seed_generator",
                "class": "AdvancedSeedGenerator",
                "sdk_refs": False,
                "permissions": [],
                "methods": {
                    name: name in node.__dict__
                    for name in ("validate_inputs", "fingerprint_inputs", "check_lazy_status")
                },
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


def test_census_schema_manifest_and_zero_authority_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"AdvancedSeedGenerator"}
    assert set(secure.NODE_CLASS_MAPPINGS) == {"AdvancedSeedGenerator"}
    assert not hasattr(pristine, "WEB_DIRECTORY")
    node = secure.AdvancedSeedGenerator
    schema = node.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "AdvancedSeedGenerator", "🎲 Advanced Seed Generator", "utils",
    )
    assert [item.id for item in schema.inputs] == ["mode", "seed"]
    assert schema.inputs[0].options == ["fixed", "increment", "decrement", "random"]
    assert (schema.inputs[1].default, schema.inputs[1].min, schema.inputs[1].max) == (
        0, 0, 0xFFFFFFFFFFFFFFFF,
    )
    assert [(item.id, item.io_type) for item in schema.outputs] == [("seed", "INT")]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.random_seed_generator_secure_test")
    assert set(loaded.node_mappings) == {"AdvancedSeedGenerator"}
    assert not loaded.routes
    assert loaded.frontend_permissions == frozenset()


@pytest.mark.parametrize("initial", [0, 1, 42, 0xFFFFFFFFFFFFFFFE, 0xFFFFFFFFFFFFFFFF])
def test_fixed_increment_and_decrement_match_pristine(tmp_path, initial):
    pristine = _pristine(tmp_path).AdvancedSeedGenerator
    secure = _secure().AdvancedSeedGenerator
    for node in (pristine, secure):
        node.reset_state()
        node._last_seed = initial

    assert secure.execute("fixed", 123).result == pristine().generate_seed("fixed", 123)
    assert secure._last_seed == pristine._last_seed == initial
    for mode in ("increment", "decrement", "increment"):
        assert secure.execute(mode, 0).result == pristine().generate_seed(mode, 0)
        assert secure._last_seed == pristine._last_seed


def test_random_mode_matches_pristine_rng_and_updates_state(tmp_path):
    pristine = _pristine(tmp_path).AdvancedSeedGenerator
    secure = _secure().AdvancedSeedGenerator
    rng_state = random.getstate()
    try:
        random.seed(73921)
        expected = [pristine().generate_seed("random", 0) for _ in range(12)]
        expected_last = pristine._last_seed
        random.seed(73921)
        actual = [secure.execute("random", 0).result for _ in range(12)]
        assert actual == expected
        assert secure._last_seed == expected_last
        assert all(0 <= value[0] <= 0xFFFFFFFFFFFFFFFF for value in actual)
    finally:
        random.setstate(rng_state)


def test_errors_and_fingerprints_match_pristine(tmp_path):
    pristine = _pristine(tmp_path).AdvancedSeedGenerator
    secure = _secure().AdvancedSeedGenerator
    with pytest.raises(ValueError, match="Unknown mode: 'teleport'"):
        pristine().generate_seed("teleport", 0)
    with pytest.raises(ValueError, match="Unknown mode: 'teleport'"):
        secure.execute("teleport", 0)
    for seed in (0, 99, 0xFFFFFFFFFFFFFFFF):
        assert secure.fingerprint_inputs("fixed", seed) == pristine.IS_CHANGED("fixed", seed)
    before = time.time()
    for mode in ("random", "increment", "decrement"):
        fingerprint = secure.fingerprint_inputs(mode, 0)
        assert before <= fingerprint <= time.time()


def test_real_guest_preserves_shared_state_wraparound_and_fixed_mode():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "random-seed-generator-conversion", guest_runtime_root=V2
        ).start()
        try:
            values = []
            for index, (mode, seed) in enumerate((
                ("decrement", 0),
                ("increment", 0),
                ("fixed", 87),
                ("increment", 0),
            )):
                plan = _sdk.ExecutionPlan(
                    prompt_id=f"seed-{index}", node_id=str(index),
                    node_type=secure.AdvancedSeedGenerator.__name__, tier="sandbox",
                    node_module=secure.AdvancedSeedGenerator.__module__,
                    inputs={"mode": mode, "seed": seed}, permissions=(), method="execute",
                )
                runtime = _sdk.Runtime(
                    refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=_sdk.InProcessOps(),
                )
                result = await session.execute(plan, runtime, capabilities=())
                values.append(result.result)
            assert values == [
                (0xFFFFFFFFFFFFFFFF,), (0,), (87,), (1,),
            ]
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_contract_assets_and_source_boundary_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    for relative in ("LICENSE", "README.md", "icon.png", "image/random-seed-generator.png"):
        assert (V2 / relative).read_bytes() == (PACK / relative).read_bytes()
    source = (V2 / "random_seed_generator.py").read_text()
    for forbidden in (
        "import torch", "import comfy", "folder_paths", "PromptServer", "requests",
        "aiohttp", "subprocess", "open(", "ctx()", "sdk.",
    ):
        assert forbidden not in source


def test_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "randomseedgenerator" / "xec04f67"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
