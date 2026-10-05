from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import random
import shutil
import subprocess
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
COMMIT = "9808d4315d0c88ecb448bc6c1ad1774470dfb172"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "comfyui-text-randomizer" / "x9808d43" / (
    "comfyui-text-randomizer-x9808d43"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402


def _import_v2():
    name = "_secure_text_randomizer_test"
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_upstream():
    name = "_upstream_text_randomizer_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, PACK / "nodes.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generated_manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "nodes",
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status"
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "frontend_permissions": [],
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "web",
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


def test_pinned_pristine_and_secure_census_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    source = ast.parse((PACK / "nodes.py").read_text())
    classes = {item.name for item in source.body if isinstance(item, ast.ClassDef)}
    assert classes == {
        "RandomizeText", "RandomizeTextWithCheck", "ConcatText",
        "RandomTextChoice", "ShowText",
    }
    pristine_frontend = (PACK / "ui" / "extension.js").read_text()
    assert pristine_frontend.count("app.registerExtension({") == 1
    pristine_python = "\n".join(
        path.read_text(errors="replace")
        for path in PACK.rglob("*.py") if V2 not in path.parents
    )
    assert "PromptServer" not in pristine_python
    assert "routes." not in pristine_python

    pack = _import_v2()
    expected = {
        "RandomizeText", "RandomizeTextWithCheck", "RandomTextChoice",
        "ConcatText", "ShowText",
    }
    assert set(pack.NODE_CLASS_MAPPINGS) == expected
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == expected
    assert pack.WEB_DIRECTORY == "web"
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.text_randomizer_test")
    assert set(loaded.node_mappings) == expected
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()


def test_all_schemas_preserve_the_legacy_contract():
    pack = _import_v2()
    schemas = {key: value.GET_SCHEMA() for key, value in pack.NODE_CLASS_MAPPINGS.items()}
    assert all(schema.category == "randomizer" for schema in schemas.values())
    assert all(value.SDK_REFS is False for value in pack.NODE_CLASS_MAPPINGS.values())
    assert all(value.SDK_PERMISSIONS == () for value in pack.NODE_CLASS_MAPPINGS.values())

    randomize = schemas["RandomizeText"]
    assert [(item.id, item.io_type, item.optional) for item in randomize.inputs] == [
        ("text", "STRING", False), ("seed", "INT", False),
    ]
    assert randomize.inputs[0].multiline is True
    assert (randomize.inputs[1].default, randomize.inputs[1].min,
            randomize.inputs[1].max) == (0, 0, 0xFFFFFFFFFFFFFFFF)
    assert [(item.id, item.io_type) for item in randomize.outputs] == [
        ("text", "STRING")
    ]

    checked = schemas["RandomizeTextWithCheck"]
    assert [
        (item.id, item.optional, getattr(item, "multiline", None))
        for item in checked.inputs
    ] == [
        ("text", False, True), ("seed", False, None), ("info_text", True, True),
    ]
    for node_id in ("ConcatText", "RandomTextChoice"):
        strings = [item for item in schemas[node_id].inputs if item.io_type == "STRING"]
        assert all(item.multiline is True and item.force_input is True for item in strings)

    show = schemas["ShowText"]
    assert show.is_output_node is True and show.outputs == []
    assert [(item.id, item.optional) for item in show.inputs] == [
        ("text", False), ("preview", True),
    ]
    assert show.inputs[0].force_input is True
    assert show.inputs[0].dynamic_prompts is True
    assert show.inputs[1].multiline is True


@pytest.mark.parametrize("seed", [0, 1, 2, 17, 2**32, 0xFFFFFFFFFFFFFFFF])
@pytest.mark.parametrize(
    "text",
    [
        "plain text",
        "[red|green|blue]",
        "[man|girl], sitting on [bench|grass]",
        "nested [outer [one|two]|other] result",
        "empty [apple|] or [x||]",
        "Unicode [雪|火] and punctuation",
    ],
)
def test_randomizers_are_differential_to_upstream(text, seed):
    upstream = _import_upstream()
    secure = _import_v2()
    expected = upstream.RandomizeText().randomize(text, seed)
    assert secure.RandomizeText.execute(text, seed).result == expected
    assert secure.RandomizeTextWithCheck.execute(text, seed, "ignored").result == expected


@pytest.mark.parametrize("seed", [0, 1, 2, 99, 2**63, 0xFFFFFFFFFFFFFFFF])
@pytest.mark.parametrize("values", [("a", "b"), ("", "text"), ("雪", "火")])
def test_choice_is_differential_to_upstream(values, seed):
    upstream = _import_upstream()
    secure = _import_v2()
    expected = upstream.RandomTextChoice().choice(*values, seed)
    assert secure.RandomTextChoice.execute(*values, seed).result == expected


@pytest.mark.parametrize("values", [("a", "b"), ("", ""), ("雪", "line\ntwo")])
def test_concat_and_show_text_are_differential_to_upstream(values):
    upstream = _import_upstream()
    secure = _import_v2()
    assert secure.ConcatText.execute(*values).result == upstream.ConcatText().concat(*values)
    text = values[0]
    result = secure.ShowText.execute(text, "old")
    assert result.result is None
    assert result.ui == upstream.ShowText().showText(text)["ui"]


def test_secure_randomizers_do_not_mutate_process_random_state():
    secure = _import_v2()
    random.seed(12345)
    before = random.getstate()
    secure.RandomizeText.execute("[a|b] [c|d]", 9)
    secure.RandomTextChoice.execute("a", "b", 9)
    assert random.getstate() == before


def test_malformed_and_oversized_values_fail_closed():
    secure = _import_v2()
    with pytest.raises(ValueError, match="unmatched opening bracket"):
        secure.RandomizeText.execute("broken [choice", 0)
    for seed in (-1, 2**64):
        with pytest.raises(ValueError, match="seed"):
            secure.RandomizeText.execute("text", seed)
    with pytest.raises(TypeError, match="seed"):
        secure.RandomTextChoice.execute("a", "b", True)
    with pytest.raises(ValueError, match="byte limit"):
        secure.ShowText.execute("x" * 1_048_577)
    with pytest.raises(ValueError, match="concatenated text"):
        secure.ConcatText.execute("x" * 600_000, "y" * 600_000)


def test_real_isolated_guest_executes_every_node_without_capabilities():
    pack = _import_v2()
    cases = [
        (pack.RandomizeText, {"text": "[a|b]", "seed": 4}),
        (pack.RandomizeTextWithCheck, {"text": "[a|b]", "seed": 4,
                                       "info_text": "ok"}),
        (pack.RandomTextChoice, {"text1": "a", "text2": "b", "seed": 4}),
        (pack.ConcatText, {"text1": "a", "text2": "b"}),
        (pack.ShowText, {"text": "shown", "preview": "old"}),
    ]

    async def run():
        outputs = []
        session = await GuestSession("text-randomizer-pack", guest_runtime_root=V2).start()
        try:
            for index, (node, inputs) in enumerate(cases):
                plan = _sdk.ExecutionPlan(
                    prompt_id="text-randomizer-test", node_id=str(index),
                    node_type=node.__name__, tier="sandbox",
                    node_module=node.__module__, inputs=inputs, permissions=(),
                )
                runtime = _sdk.Runtime(
                    refs=_sdk.InProcessRefResolver(),
                    ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=_sdk.InProcessOps(),
                )
                outputs.append(await session.execute(plan, runtime, capabilities=()))
            return outputs, session.last_guest_pid
        finally:
            await session.kill()

    outputs, guest_pid = asyncio.run(run())
    assert outputs[0].result == pack.RandomizeText.execute("[a|b]", 4).result
    assert outputs[1].result == outputs[0].result
    assert outputs[2].result in {("a",), ("b",)}
    assert outputs[3].result == ("a, b",)
    assert outputs[4].result is None and outputs[4].ui == {"text": "shown"}
    assert guest_pid not in (None, os.getpid())


def test_manifest_security_contract_frontend_and_typecheck():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    python_source = "\n".join(path.read_text() for path in V2.glob("*.py"))
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "socket", "open(", "pathlib", "torch", "numpy",
    ):
        assert forbidden not in python_source
    frontend = "\n".join(path.read_text() for path in (V2 / "web").glob("*.js"))
    for forbidden in (
        "/scripts/app.js", "/scripts/widgets.js", "LiteGraph", "app.graph",
        "app.canvas", "document.", "window.", "localStorage", "indexedDB",
        "fetch(", "comfy.backend", "innerHTML",
    ):
        assert forbidden not in frontend
    completed = subprocess.run(
        ["tsc", "--noEmit", "-p", str(V2 / "tsconfig.json")],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_frontend_validation_results_isolation_and_teardown():
    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "text_randomizer_frontend_harness.mjs"),
            str(V2 / "web" / "main.js"),
        ],
        cwd=V2, text=True, capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: secure Text Randomizer" in completed.stdout


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-text-randomizer" / "x9808d43"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_leave_no_bytecode_or_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
