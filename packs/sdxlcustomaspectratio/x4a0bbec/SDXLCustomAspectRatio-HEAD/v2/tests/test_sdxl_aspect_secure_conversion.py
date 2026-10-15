from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import random
import shutil
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
CORE = Path("/Users/ben/comfy/ComfyUI-secure-nodes")
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

PAIR = PACK_DB / "patches/sdxlcustomaspectratio/x4a0bbec/sdxlcustomaspectratio-x4a0bbec"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
NODE = "SDXLAspectRatio"


def _secure(root=V2):
    name = "_sdxl_aspect_secure"
    for key in tuple(sys.modules):
        if key == name or key.startswith(name + "."):
            sys.modules.pop(key)
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _old():
    spec = importlib.util.spec_from_file_location(
        "_sdxl_aspect_pristine", PACK / "SDXLAspectRatio.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(module):
    cls = module.NODE_CLASS_MAPPINGS[NODE]
    return {
        "format": FORMAT,
        "runtime": manifest_declaration(V2),
        "nodes": {
            NODE: {
                "module": "nodes",
                "class": cls.__name__,
                "sdk_refs": False,
                "permissions": [],
                "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
                "methods": {
                    m: False
                    for m in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
            }
        },
    }


def test_actual_standalone_loader_census_schema_and_entrypoint():
    old, new = _old(), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {NODE}
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    cls = new.NODE_CLASS_MAPPINGS[NODE]
    legacy = old.NODE_CLASS_MAPPINGS[NODE]
    schema = cls.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == NODE and schema.display_name == "SDXL Aspect Ratio"
    assert schema.category == legacy.CATEGORY and not schema.is_output_node
    assert [x.io_type for x in schema.outputs] == list(legacy.RETURN_TYPES)
    assert tuple(x.display_name for x in schema.outputs) == legacy.RETURN_NAMES
    assert schema.inputs[0].id == "aspectRatio" and not schema.inputs[0].optional
    assert (
        schema.inputs[0].options == legacy.INPUT_TYPES()["required"]["aspectRatio"][0]
    )
    assert len(schema.inputs[0].options) == 28
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()

    async def entry():
        extension = await new.comfy_entrypoint()
        assert await extension.get_node_list() == [cls]

    asyncio.run(entry())
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.sdxl_aspect_census")
    assert set(loaded.node_mappings) == {NODE}
    assert (
        not loaded.routes
        and not loaded.frontend_permissions
        and loaded.web_directory is None
    )
    assert not list(PACK.rglob("*.js"))


PRESETS = _old().SDXLAspectRatio.INPUT_TYPES()["required"]["aspectRatio"][0]
DIRECT = [
    "",
    "unknown",
    "512 X 768",
    "before 0x0 after",
    "12 x 34 then 99x88",
    "١٢X٣٤",
    "１x２",
    "1×2",
    "-12x-34",
    "34x0",
    "1:2 - 123x456 portrait",
    "\x00\n9x21\n🙂",
    "a" * 65536,
]


@pytest.mark.parametrize(
    "value", PRESETS + DIRECT, ids=[f"case-{i}" for i in range(len(PRESETS + DIRECT))]
)
def test_all_ordered_presets_and_direct_parsing_are_exact(value):
    expected = _old().SDXLAspectRatio().SDXL_AspectRatio(value)
    actual = _secure().SDXLAspectRatio.execute(value).result
    assert actual == expected and all(type(x) is int for x in actual)


def test_randomized_differential_bounds_native_errors_and_rng_isolation():
    rng = random.Random(977)
    state = random.getstate()
    old = _old().SDXLAspectRatio()
    new = _secure().SDXLAspectRatio
    for _ in range(500):
        w, h = rng.randrange(100000), rng.randrange(100000)
        text = f"{rng.choice(['a', '🙂', '', 'junk '])}{w}{rng.choice(['x', 'X', ' x ', '×'])}{h} trailing"
        assert new.execute(text).result == old.SDXL_AspectRatio(text)
    assert random.getstate() == state
    for text in ("9" * 5000 + "x2",):
        with pytest.raises(ValueError) as expected:
            old.SDXL_AspectRatio(text)
        with pytest.raises(ValueError) as actual:
            new.execute(text)
        assert str(expected.value) == str(actual.value)
    for text in ("x" * 65537, "🙂" * 16385, "9223372036854775808x1"):
        with pytest.raises(ValueError):
            new.execute(text)
    for value in (None, True, 2, [], {}):
        with pytest.raises(TypeError):
            new.execute(value)


def test_real_guest_zero_authority_and_fresh_filesystem_continuity(tmp_path):
    fresh = tmp_path / "fresh-render"
    shutil.copytree(V2, fresh)

    async def run():
        refs = _sdk.InProcessRefResolver()
        pids = []
        for root in (V2, fresh):
            node = _secure(root).SDXLAspectRatio
            session = await GuestSession("sdxl-aspect", guest_runtime_root=root).start()
            try:
                for index, text in enumerate(PRESETS + DIRECT):
                    plan = _sdk.ExecutionPlan(
                        prompt_id="sdxl-aspect",
                        node_id=str(index),
                        node_type=node.__name__,
                        tier="sandbox",
                        node_module=node.__module__,
                        inputs={"aspectRatio": text},
                        input_mode="values",
                        permissions=(),
                        method="execute",
                    )
                    runtime = _sdk.Runtime(
                        refs=refs,
                        ctx=_sdk.InProcessCtxProvider().build(plan),
                        ops=_sdk.InProcessOps(),
                    )
                    result = await session.execute(plan, runtime, capabilities=())
                    assert tuple(
                        result.result
                    ) == _old().SDXLAspectRatio().SDXL_AspectRatio(text)
                    assert all(type(x) is int for x in result.result)
                import torch

                image = _sdk.ImageRef._wrap(
                    await refs.create("IMAGE", torch.zeros(1, 1, 1, 3))
                )
                plan = _sdk.ExecutionPlan(
                    prompt_id="denied",
                    node_id="1",
                    node_type=node.__name__,
                    tier="sandbox",
                    node_module=node.__module__,
                    inputs={"aspectRatio": image},
                    input_mode="values",
                    permissions=(),
                    method="execute",
                )
                runtime = _sdk.Runtime(
                    refs=refs,
                    ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=_sdk.InProcessOps(),
                )
                with pytest.raises(Exception, match="raw"):
                    await session.execute(plan, runtime, capabilities=())
                await refs.release(image)
                pids.append(session.last_guest_pid)
                assert pids[-1] not in (None, os.getpid())
                assert not refs._table
            finally:
                await session.kill()
        assert pids[0] != pids[1]

    asyncio.run(run())


def test_manifest_contracts_algorithm_byte_identity_and_authority():
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "algorithm.py").read_bytes() == (
        PACK / "SDXLAspectRatio.py"
    ).read_bytes()
    assert not (PACK / "LICENSE").exists()
    assert (
        "4a0bbec07134768324b49f14b2fa7f3bee66f0ba"
        in (V2 / "SECURE_CONVERSION.md").read_text()
    )
    for path in (V2 / "nodes.py", V2 / "algorithm.py"):
        for forbidden in (
            "import os",
            "folder_paths",
            "PromptServer",
            "open(",
            "_from_raw",
            "requests",
            "subprocess",
        ):
            assert forbidden not in path.read_text()


def test_byte_exact_crlf_patch_roundtrip_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes() == diff.encode()
    fresh = tmp_path / "sdxlcustomaspectratio/x4a0bbec"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("*.pyc")) and not list(PACK.rglob("__pycache__"))
