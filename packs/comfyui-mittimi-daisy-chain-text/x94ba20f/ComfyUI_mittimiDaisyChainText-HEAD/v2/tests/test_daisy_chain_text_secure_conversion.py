from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import sys
import types

import pytest

sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = Path(os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"))
for root in (BACKEND, CORE):
    sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))
from comfy_api.latest import _sdk
from comfy_secure_nodes import packdb, packpatch
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema
from comfy_secure_nodes.packruntime import manifest_declaration
from comfy_secure_nodes.transport.host import GuestSession

COMMIT = "94ba20fda8dc35cd5adfe3fb01715d55149b0bf4"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "50848a56eaf4f798de1a4f11faa7e3bd9b6254c2c61a94b5a9907aaa2b0cac78"
PAIR = (
    PACK_DB
    / "patches/comfyui-mittimi-daisy-chain-text/x94ba20f/comfyui-mittimi-daisy-chain-text-x94ba20f"
)
CASES = [
    {"text": ""},
    {"text": "middle"},
    {"text": "", "text_that_comes_first": "first", "text_that_comes_last": "last"},
    {
        "text": " body ",
        "text_that_comes_first": "  pre ",
        "text_that_comes_last": " post  ",
    },
    {"text": "\n\t", "text_that_comes_first": "\r\n", "text_that_comes_last": "\t"},
    {"text": "雪🙂", "text_that_comes_first": "猫", "text_that_comes_last": "é"},
    {
        "text": "<script>alert(1)</script>",
        "text_that_comes_first": "<svg>",
        "text_that_comes_last": "</svg>",
    },
    {
        "text": "// hello /* world */",
        "text_that_comes_first": "BREAK",
        "text_that_comes_last": "BREAK",
    },
    {"text": "\x00", "text_that_comes_first": "a\x00", "text_that_comes_last": "\x00b"},
    {"text": "e\u0301\u00a0", "text_that_comes_first": "\u200b"},
    {"text": ["b"], "text_that_comes_first": ["a"], "text_that_comes_last": ["c"]},
    {"text": 2, "text_that_comes_first": 1, "text_that_comes_last": 3},
]
INVALID = [
    {"text": None},
    {"text": False},
    {"text": 1},
    {"text": []},
    {"text": {}},
    {"text": "a", "text_that_comes_first": None},
    {"text": "a", "text_that_comes_last": 7},
    {"text": ["a"], "text_that_comes_first": ["b"], "text_that_comes_last": ""},
]


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


def _secure():
    return _load("_daisy_chain_secure_test", V2)


def _old(tmp_path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    # Actual CPU registration import was run at screening. This unused import
    # alone is stubbed for repeatable differentials without device initialization.
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "comfy.sd", types.ModuleType("comfy.sd"))
        return _load("_daisy_chain_upstream_test", root)


def _node(module):
    return module.NODE_CLASS_MAPPINGS["DaisyChainTextMittimi"]


def _manifest(module):
    cls = _node(module)
    return {
        "format": FORMAT,
        "nodes": {
            "DaisyChainTextMittimi": {
                "class": cls.__name__,
                "module": "nodes",
                "sdk_refs": False,
                "permissions": [],
                "methods": {
                    key: False
                    for key in (
                        "validate_inputs",
                        "fingerprint_inputs",
                        "check_lazy_status",
                    )
                },
                "schema": encode_schema(copy.deepcopy(cls.GET_SCHEMA())),
            }
        },
        "runtime": manifest_declaration(V2),
    }


def _generated():
    rng = random.Random(941204)
    alphabet = [
        "a",
        " ",
        "\t",
        "\r\n",
        "雪",
        "🙂",
        "<svg>",
        "BREAK",
        ",",
        "\x00",
        "\u00a0",
        "é",
    ]
    return [
        {
            key: "".join(rng.choices(alphabet, k=rng.randrange(40)))
            for key in ("text", "text_that_comes_first", "text_that_comes_last")
        }
        for _ in range(128)
    ]


def test_actual_registration_schema_and_inert_web_directory(tmp_path):
    old, new = _old(tmp_path), _secure()
    assert (
        list(old.NODE_CLASS_MAPPINGS)
        == list(new.NODE_CLASS_MAPPINGS)
        == ["DaisyChainTextMittimi"]
    )
    assert (
        old.NODE_DISPLAY_NAME_MAPPINGS
        == new.NODE_DISPLAY_NAME_MAPPINGS
        == {"DaisyChainTextMittimi": "DaisyChainText"}
    )
    assert old.WEB_DIRECTORY == "./js" and not (PACK / "js").exists()
    assert not list(PACK.rglob("*.js")) and not hasattr(new, "WEB_DIRECTORY")
    cls = _node(new)
    schema = cls.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "DaisyChainTextMittimi",
        "DaisyChainText",
        _node(old).CATEGORY,
    )
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("text_that_comes_first", "STRING", False),
        ("text", "STRING", False),
        ("text_that_comes_last", "STRING", True),
    ]
    assert schema.inputs[1].multiline is True
    assert [(item.io_type, item.display_name) for item in schema.outputs] == [
        ("STRING", "text")
    ]
    assert not schema.is_output_node and not schema.is_input_list
    assert cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.daisy_chain_census")
    assert set(loaded.node_mappings) == {"DaisyChainTextMittimi"}
    assert (
        not loaded.routes
        and not loaded.frontend_permissions
        and loaded.web_directory is None
    )


@pytest.mark.parametrize("inputs", CASES)
def test_exact_concat_defaults_whitespace_unicode_and_native_addition(tmp_path, inputs):
    expected = _node(_old(tmp_path))().daisyChainTextMittimi(**inputs)
    assert _node(_secure()).execute(**inputs).result == expected


@pytest.mark.parametrize("inputs", INVALID)
def test_native_malformed_input_errors_are_not_coerced(tmp_path, inputs):
    with pytest.raises(Exception) as expected:
        _node(_old(tmp_path))().daisyChainTextMittimi(**inputs)
    with pytest.raises(type(expected.value)) as actual:
        _node(_secure()).execute(**inputs)
    assert str(actual.value) == str(expected.value)


def test_generated_differential_no_globals_or_instance_state(tmp_path):
    old, new = _node(_old(tmp_path))(), _node(_secure())
    state = random.getstate()
    for inputs in _generated():
        assert new.execute(**inputs).result == old.daisyChainTextMittimi(**inputs)
    assert random.getstate() == state
    assert new.execute("userA", "graphA:", ":A").result == ("graphA:userA:A",)
    assert new.execute("userB").result == ("userB",)
    assert new.execute("").result == ("",)


def test_bounds_preserve_accepted_values_and_native_types(tmp_path):
    new, old = _node(_secure()), _node(_old(tmp_path))()
    for value in ("x" * 65536, "🙂" * 16384, "\ud800"):
        inputs = dict(
            text=value, text_that_comes_first=value, text_that_comes_last=value
        )
        assert new.execute(**inputs).result == old.daisyChainTextMittimi(**inputs)
    for key in ("text", "text_that_comes_first", "text_that_comes_last"):
        for value in ("x" * 65537, "🙂" * 16385):
            with pytest.raises(ValueError, match="input limit"):
                new.execute(**dict({"text": ""}, **{key: value}))
        with pytest.raises(ValueError, match="sequence input limit"):
            new.execute(**dict({"text": ""}, **{key: ["a"] * 4097}))
    args = dict(
        text=["b"] * 4096,
        text_that_comes_first=["a"] * 4096,
        text_that_comes_last=["c"] * 4096,
    )
    assert new.execute(**args).result == old.daisyChainTextMittimi(**args)


def test_real_zero_capability_guests_fresh_render_and_cross_graph_state(tmp_path):
    old = _node(_old(tmp_path))()
    fresh = tmp_path / "fresh-render"
    shutil.copytree(V2, fresh)

    async def run():
        for index, root in enumerate((V2, fresh)):
            cls = _node(_load(f"_daisy_chain_guest_{index}", root))
            refs = _sdk.InProcessRefResolver()
            session = await GuestSession(
                "mittimi-daisy-chain", guest_runtime_root=root
            ).start()
            try:

                async def execute(inputs, prompt="userA-graphA"):
                    plan = _sdk.ExecutionPlan(
                        prompt_id=prompt,
                        node_id="1",
                        node_type=cls.__name__,
                        tier="sandbox",
                        node_module=cls.__module__,
                        inputs=inputs,
                        input_mode="values",
                        permissions=(),
                        method="execute",
                    )
                    runtime = _sdk.Runtime(
                        refs=refs,
                        ctx=_sdk.InProcessCtxProvider().build(plan),
                        ops=_sdk.InProcessOps(),
                    )
                    return await session.execute(plan, runtime, capabilities=())

                for inputs in CASES + _generated():
                    assert (await execute(inputs)).result == old.daisyChainTextMittimi(
                        **inputs
                    )
                for inputs in INVALID:
                    with pytest.raises(Exception):
                        await execute(inputs)
                assert (await execute({"text": "other"}, "userB-graphB")).result == (
                    "other",
                )
                assert (await execute({"text": "first"}, "userA-graphA")).result == (
                    "first",
                )
                for key in ("text", "text_that_comes_first", "text_that_comes_last"):
                    with pytest.raises(Exception, match="input limit"):
                        await execute(dict({"text": ""}, **{key: "🙂" * 16385}))
                    with pytest.raises(Exception, match="sequence input limit"):
                        await execute(dict({"text": ""}, **{key: ["a"] * 4097}))
                with pytest.raises(TypeError, match="cannot cross the guest wire"):
                    await execute({"text": b"a"})
                text = "🙂" * 16384
                assert (
                    await execute(
                        {
                            "text": text,
                            "text_that_comes_first": text,
                            "text_that_comes_last": text,
                        }
                    )
                ).result == (text * 3,)
                assert session.last_guest_pid not in (None, os.getpid())
                assert not refs._table
            finally:
                await session.kill()

    asyncio.run(run())


def test_manifest_contract_license_and_no_authority():
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(_secure())
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    assert b"GNU GENERAL PUBLIC LICENSE" in (V2 / "LICENSE").read_bytes()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report and "no durable pack state" in report
    allowed = {"comfy_api.latest", "nodes"}
    for filename in ("__init__.py", "nodes.py"):
        tree = ast.parse((V2 / filename).read_text())
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                assert False, "ambient import"
            if isinstance(item, ast.ImportFrom):
                assert item.module in allowed
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
                assert item.func.id not in {"open", "eval", "exec", "__import__"}


def test_byte_exact_pristine_to_v2_roundtrip_and_no_cache_artifacts(tmp_path):
    manifest, diff = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff
    root = tmp_path / "comfyui-mittimi-daisy-chain-text/x94ba20f"
    root.mkdir(parents=True)
    shutil.copytree(PACK, root / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(root, manifest, diff)
    packpatch.validate_tree(root / PACK.name / "v2", V2)
    assert not list(PACK.rglob("*.pyc")) and not list(PACK.rglob("__pycache__"))
