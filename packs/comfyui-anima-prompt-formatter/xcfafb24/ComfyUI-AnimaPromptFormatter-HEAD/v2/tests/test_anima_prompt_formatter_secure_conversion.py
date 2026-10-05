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
import string
import sys

import pytest

sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path("/Users/ben/comfy/ComfyUI-secure-nodes")
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "cfafb2498eccd7b860fe0ffecd382ec468a13aea"
TREE = "269f963aa38dd420a18a2b4796e7a0ff17cca79b"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
NODE_ID = "AnimaPromptFormatter"
PRISTINE_FILES = {
    ".github/workflows/publish.yml",
    ".gitignore",
    "LICENSE",
    "README.es-ES.md",
    "README.md",
    "README_zh.md",
    "__init__.py",
    "nodes.py",
    "pyproject.toml",
    "test_formatter.py",
    "utils.py",
}
PAIR = (
    PACK_DB / "patches/comfyui-anima-prompt-formatter/xcfafb24/"
    "comfyui-anima-prompt-formatter-xcfafb24"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
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
    return _import_package("_secure_anima_prompt_formatter_test", V2)


def _pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    return _import_package("_pristine_anima_prompt_formatter_test", root)


def _manifest(pack) -> dict:
    node = pack.NODE_CLASS_MAPPINGS[NODE_ID]
    return {
        "format": FORMAT,
        "nodes": {
            NODE_ID: {
                "class": node.__name__,
                "methods": {
                    name: name in node.__dict__
                    for name in (
                        "check_lazy_status",
                        "fingerprint_inputs",
                        "validate_inputs",
                    )
                },
                "module": "nodes",
                "permissions": [],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": False,
            },
        },
        "runtime": manifest_declaration(V2),
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        item.relative_to(root).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(root.rglob("*"))
        if item.is_file()
        and not any(
            part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
            for part in item.relative_to(root).parts
        )
    }


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_actual_loader_census_schema_manifest_and_contract_are_exact(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    assert TREE == "269f963aa38dd420a18a2b4796e7a0ff17cca79b"
    assert {
        path.relative_to(PACK).as_posix()
        for path in PACK.rglob("*")
        if path.is_file() and "v2" not in path.relative_to(PACK).parts
    } == PRISTINE_FILES
    assert pristine.NODE_CLASS_MAPPINGS == {
        NODE_ID: pristine.AnimaPromptFormatter,
    }
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == {
        NODE_ID: "Anima Prompt Formatter",
    }
    assert not hasattr(pristine, "WEB_DIRECTORY")
    assert set(secure.NODE_CLASS_MAPPINGS) == {NODE_ID}
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == {
        NODE_ID: "Anima Prompt Formatter",
    }
    assert not hasattr(secure, "WEB_DIRECTORY")

    old = pristine.AnimaPromptFormatter
    node = secure.AnimaPromptFormatter
    schema = node.GET_SCHEMA()
    schema.validate()
    assert (schema.node_id, schema.display_name, schema.category) == (
        NODE_ID,
        "Anima Prompt Formatter",
        old.CATEGORY,
    )
    old_text = old.INPUT_TYPES()["required"]["text"]
    text_input = schema.inputs[0]
    assert (text_input.id, text_input.io_type) == ("text", old_text[0])
    assert text_input.default == old_text[1]["default"]
    assert text_input.multiline == old_text[1]["multiline"]
    assert text_input.extra_dict == {"display": old_text[1]["display"]}
    assert [(item.id, item.io_type, item.display_name) for item in schema.outputs] == [
        ("formatted_text", "STRING", "formatted_text"),
    ]
    assert old.RETURN_TYPES == ("STRING",)
    assert old.RETURN_NAMES == ("formatted_text",)
    assert old.OUTPUT_NODE is False
    assert schema.is_output_node is False
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [node]
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.anima_prompt_formatter_secure_test",
    )
    assert set(loaded.node_mappings) == {NODE_ID}
    assert loaded.frontend_permissions == frozenset()
    assert loaded.web_directory is None
    assert not loaded.routes


@pytest.mark.parametrize(
    "text",
    [
        "",
        "tag1",
        "tag1,tag2",
        "tag1, tag2",
        "tag1 , tag2",
        "tag1,  tag2",
        "tag1,,tag2",
        "tag1,,,tag2",
        "tag1\ntag2",
        "tag1\r\ntag2",
        "tag1\rtag2",
        "tag1,tag2\ntag3,tag4",
        "  tag1  ,  tag2  ",
        ",tag1,tag2,",
        "   ",
        ",,,",
        "a beautiful landscape, sunset, mountains, peaceful",
        "🌌 光,  ユニコード, café\r\n, 🎨",
        "a\t b,\t c , d",
        "\x00tag, control\x01value",
    ],
)
def test_documented_unicode_and_control_cases_match_pristine(tmp_path, text):
    pristine = _pristine(tmp_path)
    secure = _secure()
    expected = pristine.AnimaPromptFormatter().format(text)[0]
    assert secure.format_prompt(text) == expected
    assert secure.AnimaPromptFormatter.execute(text).result == (expected,)


def test_seeded_adversarial_string_matrix_is_differential(tmp_path):
    pristine = _pristine(tmp_path)
    secure = _secure()
    rng = random.Random(0xA11A)
    alphabet = string.ascii_letters + string.digits + " ,\t\r\né光🌌"
    for _ in range(500):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 500)))
        expected = pristine.AnimaPromptFormatter().format(text)[0]
        assert secure.format_prompt(text) == expected


def test_payload_bound_and_direct_type_validation_fail_closed():
    secure = _secure()
    maximum = "x" * secure.MAX_TEXT_CHARACTERS
    assert secure.format_prompt(maximum) == maximum
    with pytest.raises(ValueError, match="character limit"):
        secure.format_prompt(maximum + "x")
    with pytest.raises(TypeError, match="string"):
        secure.format_prompt(["tag"])
    assert secure.format_prompt(None) == ""


def test_real_zero_capability_guest_matches_behavior_and_is_isolated():
    secure = _secure()
    text = "  🌌 first,, second\r\nthird,  光  ,"
    expected = secure.format_prompt(text)

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="anima-prompt",
            node_id="1",
            node_type=secure.AnimaPromptFormatter.__name__,
            tier="sandbox",
            node_module=secure.AnimaPromptFormatter.__module__,
            inputs={"text": text},
            permissions=(),
            method="execute",
        )
        session = await GuestSession(
            "anima-prompt-formatter",
            guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(
                plan,
                _runtime(plan, refs),
                capabilities=(),
            )
            assert result.result == (expected,)
            assert refs._table == {}
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_authority_license_docs_and_stubs_are_exact():
    secure = _secure()
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    source = (V2 / "nodes.py").read_text()
    assert "MAX_TEXT_CHARACTERS" in source
    for forbidden in (
        "import torch",
        "import comfy",
        "folder_paths",
        "PromptServer",
        "requests",
        "aiohttp",
        "subprocess",
        "open(",
        "os.",
        "sys.",
        "ctx()",
        "_from_raw",
        "from_value",
    ):
        assert forbidden not in source
    assert secure.AnimaPromptFormatter.SDK_PERMISSIONS == ()


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-anima-prompt-formatter/xcfafb24"
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
    assert not list(PACK.rglob(".ruff_cache"))
