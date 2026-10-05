from __future__ import annotations

import asyncio
import contextlib
import copy
import hashlib
import importlib.util
import io as stdio
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
COMMIT = "f7f14462ff06a50cac6c14b668b822f6e2640a54"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
PAIR = PACK_DB / "patches" / "comfyui-simple-prompt-batcher" / "xf7f1446" / (
    "comfyui-simple-prompt-batcher-xf7f1446"
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
    return _import_package("_secure_simple_prompt_batcher_test", V2)


def _upstream():
    return _import_package("_upstream_simple_prompt_batcher_test", PACK)


def _manifest(pack) -> dict:
    nodes = {}
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "class": node_class.__name__,
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "check_lazy_status", "fingerprint_inputs", "validate_inputs",
                )
            },
            "module": "nodes",
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
    }


def _tree(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts)
    }


def test_exact_census_schema_manifest_and_contract():
    upstream = _upstream()
    secure = _secure()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"SimplePromptBatcher"}
    assert set(secure.NODE_CLASS_MAPPINGS) == set(upstream.NODE_CLASS_MAPPINGS)
    assert not list(PACK.rglob("*.js"))
    assert "PromptServer" not in (PACK / "prompt_batcher.py").read_text()
    assert "routes." not in (PACK / "prompt_batcher.py").read_text()
    extension = asyncio.run(secure.comfy_entrypoint())
    assert [item.GET_SCHEMA().node_id for item in asyncio.run(
        extension.get_node_list())] == ["SimplePromptBatcher"]

    old_class = upstream.NODE_CLASS_MAPPINGS["SimplePromptBatcher"]
    old_inputs = old_class.INPUT_TYPES()["required"]
    schema = secure.SimplePromptBatcher.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "SimplePromptBatcher", "📝 Simple Prompt Batcher", old_class.CATEGORY,
    )
    assert schema.description == old_class.__doc__.strip()
    assert [item.id for item in schema.inputs] == list(old_inputs)
    for item in schema.inputs:
        old_type, old_meta = old_inputs[item.id]
        assert item.io_type == old_type
        for old_name, new_name in (
            ("default", "default"), ("multiline", "multiline"),
            ("placeholder", "placeholder"), ("tooltip", "tooltip"),
        ):
            assert getattr(item, new_name) == old_meta[old_name]
    assert [(item.io_type, item.display_name, item.is_output_list)
            for item in schema.outputs] == [("STRING", "prompt", True)]
    assert secure.SimplePromptBatcher.SDK_REFS is False
    assert secure.SimplePromptBatcher.SDK_PERMISSIONS == ()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.simple_prompt_batcher_secure_test")
    assert set(loaded.node_mappings) == {"SimplePromptBatcher"}
    assert loaded.web_directory is None
    assert loaded.frontend_permissions == frozenset()
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()


CASES = (
    ("", "", ""),
    ("", "  \n\t\n", ""),
    ("pre", "one", ""),
    ("", "one", "post"),
    ("pre", "one", "post"),
    (" style ", " first \n\n second\t\n三番 ", " tail "),
    ("🔥", "alpha\r\nbeta\r\ngamma", "終"),
    ("x" * 61, "y" * 100, "z"),
)


@pytest.mark.parametrize(("prepend", "prompts", "append"), CASES)
def test_string_behavior_and_console_output_match_upstream(prepend, prompts, append):
    upstream_node = _upstream().NODE_CLASS_MAPPINGS["SimplePromptBatcher"]()
    secure_node = _secure().SimplePromptBatcher
    old_stdout = stdio.StringIO()
    new_stdout = stdio.StringIO()
    with contextlib.redirect_stdout(old_stdout):
        expected = upstream_node.batch_prompts(prepend, prompts, append)
    with contextlib.redirect_stdout(new_stdout):
        actual = secure_node.execute(prepend, prompts, append).result
    assert actual == expected
    assert new_stdout.getvalue() == old_stdout.getvalue()


def test_bounds_fail_closed_without_changing_valid_behavior():
    node = _secure().SimplePromptBatcher
    for args in ((None, "a", ""), ("", object(), ""), ("", "a", [])):
        with pytest.raises(TypeError, match="must be a string"):
            node.execute(*args)
    with pytest.raises(ValueError, match="too large"):
        node.execute("x" * (4 * 1024 * 1024 + 1), "a", "")
    with pytest.raises(ValueError, match="more than 4096"):
        node.execute("", "\n".join("x" for _ in range(4097)), "")


def test_real_guest_executes_without_capabilities_and_keeps_list_output():
    node = _secure().SimplePromptBatcher

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="simple-prompt-batcher", node_id="1",
            node_type="SimplePromptBatcher", tier="sandbox",
            node_module=node.__module__,
            inputs={
                "prepend": "portrait", "prompts": "one\n\ntwo ",
                "append": "cinematic",
            },
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps())
        session = await GuestSession(
            "simple-prompt-batcher-pack", guest_runtime_root=V2).start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            return result.result, session.last_guest_pid
        finally:
            await session.kill()

    result, pid = asyncio.run(run())
    assert result == ([
        "portrait, one, cinematic", "portrait, two, cinematic",
    ],)
    assert pid not in (None, os.getpid())


def test_backend_has_no_ambient_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests", "aiohttp",
        "subprocess", "open(", "os.", "sys.", "ctx()", "torch", "numpy",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-simple-prompt-batcher" / "xf7f1446"
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
