from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import types
from contextlib import contextmanager

import pytest
import torch


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "47d29099fbe96f9fd5a9a5a97ea68877c66199a9"
DTS_SHA256 = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA256 = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
NODE_IDS = {
    "CLIPTextEncodeFormatter",
    "TextOnlyFormatter",
    "TextAppendFormatter",
}
DISPLAY_NAMES = {
    "CLIPTextEncodeFormatter": "CLIP Text Encode (Prompt Formatter)",
    "TextOnlyFormatter": "Prompt Formatter (Only Text)",
    "TextAppendFormatter": "Append String",
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


def _import_v2(name="_secure_prompt_formatter_conversion_test"):
    return _import_package(V2, name)


@contextmanager
def _pristine_host_stubs():
    names = ("comfy", "comfy.comfy_types", "server", "aiohttp", "aiohttp.web")
    saved = {name: sys.modules.get(name) for name in names}
    routes = []

    io_values = types.SimpleNamespace(
        STRING="STRING", CLIP="CLIP", CONDITIONING="CONDITIONING",
    )
    comfy = types.ModuleType("comfy")
    comfy_types = types.ModuleType("comfy.comfy_types")
    comfy_types.IO = io_values
    comfy_types.ComfyNodeABC = object
    comfy_types.InputTypeDict = dict
    comfy.comfy_types = comfy_types

    class _Routes:
        def post(self, path):
            def decorate(function):
                routes.append(("post", path, function.__name__))
                return function
            return decorate

    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=_Routes()),
    )
    web = types.ModuleType("aiohttp.web")
    web.json_response = lambda value: value
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.web = web

    sys.modules.update({
        "comfy": comfy,
        "comfy.comfy_types": comfy_types,
        "server": server,
        "aiohttp": aiohttp,
        "aiohttp.web": web,
    })
    try:
        yield routes
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _import_pristine(tmp_path: pathlib.Path):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    with _pristine_host_stubs() as routes:
        package = _import_package(root, "_pristine_prompt_formatter_test")
    package._observed_routes = tuple(routes)
    return package


def _tree(root: pathlib.Path, *, omit_v2: bool = False) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if omit_v2 and relative.parts[0] == "v2":
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"}
               for part in relative.parts):
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
                for method in (
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "runtime": manifest_declaration(V2),
        "nodes": nodes,
        "web_directory": "web",
    }


def _plan(node_class, inputs, suffix):
    return _sdk.ExecutionPlan(
        prompt_id=f"prompt-formatter-{suffix}",
        node_id=suffix,
        node_type=node_class.GET_SCHEMA().node_id,
        tier="sandbox",
        node_module=node_class.__module__,
        inputs=inputs,
        permissions=(),
        method="execute",
    )


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_actual_loader_census_routes_manifest_and_contract_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine = _import_pristine(tmp_path)
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.NODE_DISPLAY_NAME_MAPPINGS == DISPLAY_NAMES
    assert pristine.WEB_DIRECTORY == "js"
    assert pristine._observed_routes == (
        ("post", "/prompt_formatter/format_prompt", "route_format_prompt"),
        ("post", "/prompt_formatter/convert_tags", "route_convert_tags"),
    )
    assert len(list((PACK / "js").glob("*.js"))) == 1
    assert (PACK / "js" / "button.js").read_text().count(
        "app.registerExtension") == 1

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == DISPLAY_NAMES
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(pack))
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA256

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.prompt_formatter_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"
    assert not loaded.routes


def test_schemas_preserve_ids_order_options_descriptions_and_outputs():
    classes = _import_v2().NODE_CLASS_MAPPINGS
    for node_id, node_class in classes.items():
        schema = node_class.GET_SCHEMA()
        schema.validate()
        assert schema.node_id == node_id
        assert schema.display_name == DISPLAY_NAMES[node_id]
        assert schema.category == "prompt_formatter"
        assert schema.description
        assert getattr(node_class, "SDK_PERMISSIONS", ()) == ()

    clip = classes["CLIPTextEncodeFormatter"]
    schema = clip.GET_SCHEMA()
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("text", "STRING"), ("clip", "CLIP"),
    ]
    assert schema.inputs[0].multiline is True
    assert schema.inputs[0].dynamic_prompts is True
    assert schema.inputs[0].tooltip == "The text to be encoded."
    assert schema.inputs[1].tooltip == "The CLIP model used for encoding the text."
    assert [(item.io_type, item.tooltip) for item in schema.outputs] == [
        ("CONDITIONING", "A conditioning containing the embedded text used to guide the diffusion model."),
    ]
    assert clip.SDK_REFS is True

    text = classes["TextOnlyFormatter"]
    schema = text.GET_SCHEMA()
    assert [(item.id, item.io_type) for item in schema.inputs] == [("text", "STRING")]
    assert schema.inputs[0].multiline is True
    assert schema.inputs[0].dynamic_prompts is True
    assert schema.outputs[0].io_type == "STRING"
    assert getattr(text, "SDK_REFS", False) is False

    append = classes["TextAppendFormatter"]
    schema = append.GET_SCHEMA()
    assert [(item.id, item.io_type, item.default) for item in schema.inputs] == [
        ("string1", "STRING", ""),
        ("string2", "STRING", ""),
        ("comma", "BOOLEAN", True),
        ("dedupe", "BOOLEAN", True),
    ]
    assert schema.inputs[0].force_input is True
    assert schema.inputs[1].force_input is True
    assert schema.outputs[0].io_type == "STRING"
    assert getattr(append, "SDK_REFS", False) is False


def test_text_nodes_match_pristine_across_whitespace_commas_and_dedupe(tmp_path):
    pristine = _import_pristine(tmp_path).NODE_CLASS_MAPPINGS
    secure = _import_v2().NODE_CLASS_MAPPINGS
    values = ["", "plain text", " one, two ", "\nline one\nline two"]
    for value in values:
        assert secure["TextOnlyFormatter"].execute(value).result == (
            pristine["TextOnlyFormatter"]().passthrough(value))

    cases = [
        ("", "", True, True),
        ("", " second ", True, True),
        ("first", "", True, True),
        ("first,", ",second", True, True),
        ("first", "second", False, False),
        ("cat, dog", "dog, bird", True, True),
        (" cat ,dog", "dog , cat, bird ", False, True),
        ("alpha", " alpha ", True, True),
        ("alpha", " alpha ", True, False),
        ("one,two", " three, two, four", False, True),
    ]
    for case in cases:
        expected = pristine["TextAppendFormatter"]().combine(*case)
        assert secure["TextAppendFormatter"].execute(*case).result == expected


def test_frontend_algorithms_match_pristine_and_lifecycle_harness(tmp_path):
    pristine = _import_pristine(tmp_path)
    formatter = sys.modules[pristine.__name__ + ".prompt_formatter"]
    format_cases = {
        "  cat   ,  dog  , cat ": "cat, dog",
        "（cat） [dog] {bird": "(cat:1.1) (dog:0.91) bird",
        "cat, cat, BREAK, dog, <lora:x:1>, dog": "cat BREAK dog <lora:x:1>",
        "((cat)), [[dog]], (((bird)))": "(cat:1.21), (dog:0.83), (bird:1.33)",
        "cat  AND   dog, [red|blue], (sharp:1.2)": "cat AND dog, [red|blue], (sharp:1.2)",
        r"\(literal\), (plain:1.0), <lora:test:0.8>": r"\(literal\), plain <lora:test:0.8>",
        "cat,\n\n dog , BREAK\n bird": "cat, dog BREAK\nbird",
        "(cat)(dog), [red][blue]": "(cat:1.1) (dog:1.1), (red:0.91) (blue:0.91)",
    }
    tag_cases = {
        "blue_hair green_eyes tagme watermark 2024": "blue hair, green eyes,",
        "speech_bubble hello_world onomatopoeia": "hello world,",
        r"character_\(solo\) detailed_artwork signature": r"character \(solo\),",
        "already, comma, text": "already, comma, text",
        "(ordinary phrase)": "(ordinary phrase)",
        "first_tag second_tag\nBREAK\nthird_tag\n": "first tag, second tag,\nBREAK\nthird tag,\n",
        "": "",
    }
    assert {value: formatter.format_prompt(value) for value in format_cases} == format_cases
    assert {value: formatter.convert_tags(value) for value in tag_cases} == tag_cases

    completed = subprocess.run(
        ["node", str(V2 / "tests" / "prompt_formatter_frontend_harness.mjs")],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "behavior/security tests passed" in completed.stdout


def test_clip_node_matches_pristine_and_runs_through_real_guest(tmp_path):
    calls = []

    class Clip:
        def tokenize(self, text, **kwargs):
            calls.append(("tokenize", text, kwargs))
            return {"g": [[f"g:{text}"]], "l": [[f"l:{text}"]]}

        def encode_from_tokens_scheduled(self, tokens, add_dict=None):
            value = [[torch.tensor([[[3.0, 7.0]]]), {
                "tokens": copy.deepcopy(tokens), "add": add_dict,
            }]]
            calls.append(("encode", copy.deepcopy(tokens), add_dict))
            return value

    pristine_node = _import_pristine(tmp_path).NODE_CLASS_MAPPINGS[
        "CLIPTextEncodeFormatter"]()
    pristine_clip = Clip()
    expected = pristine_node.encode(pristine_clip, "a silver lighthouse")[0]
    assert calls == [
        ("tokenize", "a silver lighthouse", {}),
        ("encode", {"g": [["g:a silver lighthouse"]], "l": [["l:a silver lighthouse"]]}, None),
    ]
    calls.clear()

    async def run():
        node_class = _import_v2().NODE_CLASS_MAPPINGS["CLIPTextEncodeFormatter"]
        refs = _sdk.InProcessRefResolver()
        clip_ref = _sdk.ClipRef._wrap(await refs.create("CLIP", Clip()))
        plan = _plan(node_class, {
            "text": "a silver lighthouse", "clip": clip_ref,
        }, "clip")
        session = await GuestSession("prompt-formatter-conversion").start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=(),
            )
            assert session.last_guest_pid not in (None, os.getpid())
            actual = await refs.resolve(result.result[0])
            assert torch.equal(actual[0][0], expected[0][0])
            assert actual[0][1] == expected[0][1]
            assert calls == [
                ("tokenize", "a silver lighthouse", {}),
                ("encode", {"g": [["g:a silver lighthouse"]], "l": [["l:a silver lighthouse"]]}, None),
            ]
        finally:
            await session.kill()

        with pytest.raises(RuntimeError, match="clip input is invalid: None"):
            await node_class.execute("text", None)

    asyncio.run(run())


def test_sources_have_no_routes_writes_network_or_ambient_browser_authority():
    refused = {
        "aiohttp", "app", "comfy", "comfy_execution", "execution",
        "folder_paths", "node_helpers", "nodes", "os", "pathlib", "requests",
        "server", "socket", "subprocess", "urllib",
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
    python_source = "\n".join(path.read_text() for path in sorted(V2.glob("*.py")))
    for forbidden in (
        "open(", "eval(", "exec(", "PromptServer", "SDK_PERMISSIONS",
        "sdk.ctx(",
    ):
        assert forbidden not in python_source

    frontend = (V2 / "web" / "button.js").read_text()
    for forbidden in (
        "fetch(", "XMLHttpRequest", "WebSocket", "window.", "document.",
        "localStorage", "sessionStorage", "app.registerExtension",
    ):
        assert forbidden not in frontend
    assert frontend.count('from "/comfy/api/v2.js"') == 1
    assert frontend.count("comfy.defs.extend") == 1
    assert not list(V2.glob("app_config.py"))
    assert not list(V2.glob("prompt_formatter.py"))
    assert json.loads((V2 / "settings.json").read_text()) == {
        "BRACKET2WEIGHT": True,
        "COLLAPSE_LINEBREAKS": True,
        "CONV_SPACE_UNDERSCORE": "None",
        "BLACKLIST_FILE": "blacklisted_tags.txt",
    }


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-prompt-formatter"
        / "x47d2909" / "comfyui-prompt-formatter-x47d2909"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    # Preserve the CRLF bytes embedded in the pinned upstream README diff.
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-prompt-formatter" / "x47d2909"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert _tree(PACK, omit_v2=True) == _tree(fresh / PACK.name, omit_v2=True)


def test_no_cache_artifacts_in_pristine_or_v2():
    for root in (PACK, V2):
        assert not list(root.rglob("__pycache__"))
        assert not list(root.rglob("*.pyc"))
