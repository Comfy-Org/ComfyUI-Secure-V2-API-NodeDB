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

IDS = ("int", "float", "string", "string_multiline")
LIMIT = 1_125_899_906_842_624
PAIR = PACK_DB / "patches/primitive-types/x1b2d984/primitive-types-x1b2d984"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"


def _load(name, root):
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


def _secure(root=V2):
    return _load("_primitive_types_secure", root)


def _old():
    return _load("_primitive_types_pristine", PACK)


def _manifest(module):
    return {
        "format": FORMAT,
        "runtime": manifest_declaration(V2),
        "nodes": {
            key: {
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
            for key, cls in sorted(module.NODE_CLASS_MAPPINGS.items())
        },
    }


def test_actual_registration_entrypoint_and_exact_schemas():
    old, new = _old(), _secure()
    assert tuple(old.NODE_CLASS_MAPPINGS) == tuple(new.NODE_CLASS_MAPPINGS) == IDS
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS

    async def entrypoint():
        extension = await new.comfy_entrypoint()
        assert await extension.get_node_list() == list(new.NODE_CLASS_MAPPINGS.values())

    asyncio.run(entrypoint())
    for key in IDS:
        legacy, cls = old.NODE_CLASS_MAPPINGS[key], new.NODE_CLASS_MAPPINGS[key]
        schema = cls.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == key
        assert schema.display_name == old.NODE_DISPLAY_NAME_MAPPINGS[key]
        assert schema.category == legacy.CATEGORY and not schema.is_output_node
        assert [x.io_type for x in schema.outputs] == list(legacy.RETURN_TYPES)
        assert len(schema.inputs) == 1 and not schema.inputs[0].optional
        name, (kind, options) = next(iter(legacy.INPUT_TYPES()["required"].items()))
        projected = cls.INPUT_TYPES()["required"][name]
        assert projected[0] == kind
        for option, value in options.items():
            assert projected[1][option] == value
        assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.primitive_types_census"
    )
    assert set(loaded.node_mappings) == set(IDS)
    assert (
        not loaded.routes
        and loaded.web_directory is None
        and not loaded.frontend_permissions
    )
    assert not list(PACK.rglob("*.js")) and not hasattr(old, "WEB_DIRECTORY")


INTS = [-LIMIT, -(2**32), -1, 0, 1, 2**32, LIMIT]
FLOATS = [-LIMIT, -123.25, -0.0, 0, 0.5, 1e-12, LIMIT]
TEXTS = [
    "",
    " ",
    "line1\nline2\r\n\t",
    "\x00<script>evil</script>",
    "🙂é漢e\u0301",
    "a" * 65536,
]
CASES = [("int", x) for x in INTS] + [("float", x) for x in FLOATS]
CASES += [(key, text) for key in IDS[2:] for text in TEXTS]


@pytest.mark.parametrize("key,value", CASES)
def test_exact_passthrough_value_type_and_identity(key, value):
    arg = "value" if key in IDS[:2] else "text"
    expected = _old().NODE_CLASS_MAPPINGS[key]().execute(**{arg: value})
    actual = _secure().NODE_CLASS_MAPPINGS[key].execute(**{arg: value}).result
    assert actual == expected and type(actual[0]) is type(expected[0])
    assert actual[0] is value


def test_randomized_repeat_calls_preserve_rng_and_output():
    rng = random.Random(713)
    old, new = _old(), _secure()
    state = random.getstate()
    for _ in range(500):
        value = rng.randrange(-LIMIT, LIMIT)
        assert new.NODE_CLASS_MAPPINGS["int"].execute(
            value
        ).result == old.NODE_CLASS_MAPPINGS["int"]().execute(value=value)
        text = "".join(rng.choice(" a漢🙂\n\t") for _ in range(rng.randrange(80)))
        for key in IDS[2:]:
            assert new.NODE_CLASS_MAPPINGS[key].execute(
                text
            ).result == old.NODE_CLASS_MAPPINGS[key]().execute(text=text)
    assert random.getstate() == state


@pytest.mark.parametrize(
    "key,value",
    [
        ("int", True),
        ("int", 1.0),
        ("int", None),
        ("int", LIMIT + 1),
        ("int", -LIMIT - 1),
        ("float", False),
        ("float", "1"),
        ("float", float("inf")),
        ("float", float("nan")),
        ("float", -LIMIT - 1),
        ("string", None),
        ("string_multiline", []),
        ("string", "a" * 65537),
        ("string_multiline", "🙂" * 16385),
    ],
)
def test_direct_malformed_or_oversized_values_fail_closed(key, value):
    with pytest.raises((TypeError, ValueError)):
        _secure().NODE_CLASS_MAPPINGS[key].execute(value)


def test_real_zero_capability_guests_fresh_filesystem_and_raw_substitution_denial(
    tmp_path,
):
    fresh = tmp_path / "fresh-render"
    shutil.copytree(V2, fresh)

    async def run():
        pids = []
        refs = _sdk.InProcessRefResolver()
        for root in (V2, fresh):
            nodes = _secure(root).NODE_CLASS_MAPPINGS
            session = await GuestSession(
                "primitive-types", guest_runtime_root=root
            ).start()
            try:
                for i, (key, value) in enumerate(CASES):
                    cls = nodes[key]
                    arg = "value" if key in IDS[:2] else "text"
                    plan = _sdk.ExecutionPlan(
                        prompt_id=f"{key}-{i}",
                        node_id=str(i),
                        node_type=cls.__name__,
                        tier="sandbox",
                        node_module=cls.__module__,
                        inputs={arg: value},
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
                    assert tuple(result.result) == (value,)
                    assert type(result.result[0]) is type(value)
                import torch

                cls = nodes["string"]
                raw = _sdk.ImageRef._wrap(
                    await refs.create("IMAGE", torch.zeros(1, 1, 1, 3))
                )
                plan = _sdk.ExecutionPlan(
                    prompt_id="denied",
                    node_id="denied",
                    node_type=cls.__name__,
                    tier="sandbox",
                    node_module=cls.__module__,
                    inputs={"text": raw},
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
                await refs.release(raw)
                assert not refs._table
                assert session.last_guest_pid not in (None, os.getpid())
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert pids[0] != pids[1]

    asyncio.run(run())


def test_manifest_current_contracts_pristine_resources_and_authority_boundary():
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    assert (
        "1b2d984818b26a0ea7f1394004e81f9286684b71"
        in (V2 / "SECURE_CONVERSION.md").read_text()
    )
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import os",
        "import sys",
        "folder_paths",
        "PromptServer",
        "open(",
        "_from_raw",
        "requests",
        "subprocess",
        "eval(",
        "exec(",
    ):
        assert forbidden not in source


def test_byte_exact_patch_roundtrip_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes() == diff.encode()
    fresh = tmp_path / "primitive-types/x1b2d984"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("*.pyc")) and not list(PACK.rglob("__pycache__"))
