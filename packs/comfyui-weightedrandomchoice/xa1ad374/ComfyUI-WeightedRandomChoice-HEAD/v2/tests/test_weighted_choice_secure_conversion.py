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

PAIR = (
    PACK_DB
    / "patches/comfyui-weightedrandomchoice/xa1ad374/comfyui-weightedrandomchoice-xa1ad374"
)
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
NODE = "WeightedRandomChoice"


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
    return _load("_weighted_choice_secure", root)


def _old():
    return _load("_weighted_choice_pristine", PACK)


def _manifest(module):
    cls = module.NODE_CLASS_MAPPINGS[NODE]
    return {
        "format": FORMAT,
        "runtime": manifest_declaration(V2),
        "nodes": {
            NODE: {
                "module": "nodes",
                "class": cls.__name__,
                "sdk_refs": True,
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


def _expected(values):
    state = random.getstate()
    try:
        result = _old().NODE_CLASS_MAPPINGS[NODE]().run(**values)
        return ("",) if result == "" else result
    finally:
        random.setstate(state)


def test_actual_census_entrypoint_and_exact_schema():
    old, new = _old(), _secure()
    assert set(old.NODE_CLASS_MAPPINGS) == set(new.NODE_CLASS_MAPPINGS) == {NODE}
    assert old.NODE_DISPLAY_NAME_MAPPINGS == new.NODE_DISPLAY_NAME_MAPPINGS
    legacy, cls = old.NODE_CLASS_MAPPINGS[NODE], new.NODE_CLASS_MAPPINGS[NODE]
    schema = cls.GET_SCHEMA()
    schema.validate()
    assert schema.category == "sd" and not hasattr(legacy, "CATEGORY")
    assert schema.display_name == "Weighted Random Choice"
    assert [x.io_type for x in schema.outputs] == ["*"]
    assert (
        not schema.is_output_node and cls.SDK_REFS is True and cls.SDK_PERMISSIONS == ()
    )
    for section, rows in legacy.INPUT_TYPES().items():
        for key, (kind, options) in rows.items():
            projected = cls.INPUT_TYPES()[section][key]
            assert str(projected[0]) == str(kind)
            for option, value in options.items():
                assert projected[1][option] == value
    assert [x.id for x in schema.inputs] == ["chance", "seed", "input_a", "input_b"]

    async def entry():
        extension = await new.comfy_entrypoint()
        assert await extension.get_node_list() == [cls]

    asyncio.run(entry())
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.weighted_choice_census"
    )
    assert set(loaded.node_mappings) == {NODE}
    assert (
        loaded.web_directory is None
        and not loaded.routes
        and not loaded.frontend_permissions
    )
    assert not list(PACK.rglob("*.js"))


VALUES = [
    ("a", "b"),
    (1, 2),
    (1.5, 2.5),
    (True, False),
    ("", None),
    (None, "b"),
    (None, 3),
    (2, None),
    (1.5, None),
    (None, None),
    ([], {"x": [1, True]}),
    ({"x": 1}, None),
]


@pytest.mark.parametrize("seed", [0, 1, 13, 0xFFFFFFFFFFFFFFFF])
@pytest.mark.parametrize("chance", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_seeded_choice_defaults_type_identity_and_rng(seed, chance):
    cls = _secure().NODE_CLASS_MAPPINGS[NODE]
    state = random.getstate()
    for a, b in VALUES:
        values = {"chance": chance, "seed": seed, "input_a": a, "input_b": b}
        actual = cls.execute(**values).result
        expected = _expected(values)
        assert actual == expected and type(actual[0]) is type(expected[0])
        chosen = a if chance >= random.Random(seed).random() else b
        if chosen is not None:
            assert actual[0] is chosen
    assert random.getstate() == state


def test_randomized_differential_and_structured_identity():
    rng = random.Random(919)
    cls = _secure().NODE_CLASS_MAPPINGS[NODE]
    for _ in range(1000):
        values = {
            "chance": rng.random(),
            "seed": rng.randrange(2**64),
            "input_a": rng.randrange(-999, 999),
            "input_b": "🙂漢" + str(rng.randrange(999)),
        }
        assert cls.execute(**values).result == _expected(values)
    value = {"a": [1, True, None, "🙂"]}
    assert cls.execute(1, 0, value, None).result[0] is value
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="structure"):
        cls.execute(1, 0, cyclic, None)


@pytest.mark.parametrize(
    "values",
    [
        {"chance": True},
        {"chance": -0.01},
        {"chance": 1.01},
        {"chance": float("nan")},
        {"seed": True},
        {"seed": -1},
        {"seed": 2**64},
        {"seed": "0"},
        {"input_a": "x" * 65537},
        {"input_a": ["x"] * 4097},
        {"input_a": {1: "x"}},
        {"input_a": object()},
        {"input_a": float("inf")},
        {"input_a": 2**64},
    ],
)
def test_malformed_resource_controls_fail_closed(values):
    with pytest.raises((TypeError, ValueError)):
        _secure().NODE_CLASS_MAPPINGS[NODE].execute(
            **({"chance": 0.5, "seed": 0} | values)
        )


def test_real_guest_fresh_filesystem_zero_authority_ref_passthrough_and_denial(
    tmp_path,
):
    fresh = tmp_path / "fresh-render"
    shutil.copytree(V2, fresh)

    async def run():
        import torch

        refs = _sdk.InProcessRefResolver()
        pids = []
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", torch.ones(1, 2, 3, 3)))
        latent = _sdk.LatentRef._wrap(
            await refs.create("LATENT", {"samples": torch.zeros(1, 4, 2, 2)})
        )
        try:
            for root in (V2, fresh):
                cls = _secure(root).NODE_CLASS_MAPPINGS[NODE]
                session = await GuestSession(
                    "weighted-choice", guest_runtime_root=root
                ).start()

                async def execute(values, node_cls=cls, guest=session):
                    plan = _sdk.ExecutionPlan(
                        prompt_id="weighted",
                        node_id="1",
                        node_type=node_cls.__name__,
                        tier="sandbox",
                        node_module=node_cls.__module__,
                        inputs=values,
                        input_mode="refs",
                        permissions=(),
                        method="execute",
                    )
                    runtime = _sdk.Runtime(
                        refs=refs,
                        ctx=_sdk.InProcessCtxProvider().build(plan),
                        ops=_sdk.InProcessOps(),
                    )
                    return await guest.execute(plan, runtime, capabilities=())

                try:
                    for seed in (0, 13):
                        for chance in (0.0, 0.5, 1.0):
                            for a, b in VALUES:
                                values = {
                                    "chance": chance,
                                    "seed": seed,
                                    "input_a": a,
                                    "input_b": b,
                                }
                                result = await execute(values)
                                assert tuple(result.result) == _expected(values)
                    for a, b, chance in (
                        (image, latent, 1),
                        (image, latent, 0),
                        (image, None, 0),
                    ):
                        result = await execute(
                            {"chance": chance, "seed": 0, "input_a": a, "input_b": b}
                        )
                        assert result.result[0] == (
                            a if chance == 1 else (b if b is not None else "")
                        )
                    # Zero permissions allow handle selection, not raw tensor access.
                    plan = _sdk.ExecutionPlan(
                        prompt_id="denied",
                        node_id="1",
                        node_type=cls.__name__,
                        tier="sandbox",
                        node_module=cls.__module__,
                        inputs={"chance": 1, "seed": 0, "input_a": image},
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
                    pids.append(session.last_guest_pid)
                    assert pids[-1] not in (None, os.getpid())
                finally:
                    await session.kill()
            assert pids[0] != pids[1]
        finally:
            await refs.release(image)
            await refs.release(latent)
        assert not refs._table

    asyncio.run(run())


def test_manifest_contracts_authority_and_missing_license():
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert not (PACK / "LICENSE.txt").exists()
    assert (
        "a1ad37491ac0d5b89793c6ca3fea7de2b4b93155"
        in (V2 / "SECURE_CONVERSION.md").read_text()
    )
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import os",
        "folder_paths",
        "PromptServer",
        "open(",
        "_from_raw",
        "_wrap(",
        "random.seed",
        "subprocess",
        "requests",
        "eval(",
        "exec(",
    ):
        assert forbidden not in source


def test_byte_exact_patch_and_cache_hygiene(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes() == diff.encode()
    fresh = tmp_path / "comfyui-weightedrandomchoice/xa1ad374"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff)
    packpatch.validate_tree(fresh / PACK.name / "v2", V2)
    assert not list(PACK.rglob("__pycache__")) and not list(PACK.rglob("*.pyc"))
