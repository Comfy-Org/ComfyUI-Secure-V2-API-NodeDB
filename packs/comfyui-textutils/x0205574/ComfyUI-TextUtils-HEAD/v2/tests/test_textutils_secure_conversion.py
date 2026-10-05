from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
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
COMMIT = "0205574631195bc2a00dcc96ae7598eaef0ce592"
DTS_SHA = "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches" / "comfyui-textutils" / "x0205574" / (
    "comfyui-textutils-x0205574"
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


NODE_IDS = (
    "Text Utils - Join Strings",
    "Text Utils - Split String to List",
    "Text Utils - Join String List",
    "Text Utils - Join N-Elements of String List",
)


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
    return _import_package("_secure_textutils_test", V2)


def _upstream():
    return _import_package("_upstream_textutils_test", PACK)


def _manifest(pack) -> dict:
    return {
        "format": FORMAT,
        "nodes": {
            node_id: {
                "class": node.__name__,
                "methods": {
                    method: method in node.__dict__
                    for method in (
                        "check_lazy_status", "fingerprint_inputs", "validate_inputs"
                    )
                },
                "module": "nodes",
                "permissions": [],
                "schema": encode_schema(copy.deepcopy(node.GET_SCHEMA())),
                "sdk_refs": False,
            }
            for node_id, node in pack.NODE_CLASS_MAPPINGS.items()
        },
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
    assert tuple(upstream.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert tuple(secure.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == upstream.NODE_DISPLAY_NAME_MAPPINGS
    assert not list(PACK.rglob("*.js"))

    for node_id in NODE_IDS:
        old = upstream.NODE_CLASS_MAPPINGS[node_id]
        schema = secure.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA()
        old_inputs = old.INPUT_TYPES()["required"]
        assert schema.node_id == node_id
        assert schema.display_name == upstream.NODE_DISPLAY_NAME_MAPPINGS[node_id]
        assert schema.category == old.CATEGORY
        assert [item.id for item in schema.inputs] == list(old_inputs)
        assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES)
        assert [item.display_name for item in schema.outputs] == list(old.RETURN_NAMES)
        assert schema.is_input_list is bool(getattr(old, "INPUT_IS_LIST", False))
        assert [item.is_output_list for item in schema.outputs] == list(
            getattr(old, "OUTPUT_IS_LIST", (False,) * len(old.RETURN_TYPES))
        )

    extension = asyncio.run(secure.comfy_entrypoint())
    assert [node.GET_SCHEMA().node_id for node in asyncio.run(extension.get_node_list())] == list(NODE_IDS)
    loaded = packdb.load_pack(SNAPSHOT, mount_name="custom_nodes.textutils_test")
    assert set(loaded.node_mappings) == set(NODE_IDS)
    assert loaded.web_directory is None
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)


@pytest.mark.parametrize(
    ("class_name", "args"),
    [
        ("JoinStringsNode", ("alpha", "beta")),
        ("JoinStringsNode", ("🙂", "\ntext")),
        ("SplitStringNode", ("a/b//c", "/")),
        ("SplitStringNode", ("no match", "::")),
        ("JoinStringListNode", (["a", "", "c"], ["/"])),
        ("JoinStringListNElementNode", (["a", "b", "c", "d"], ["-"], [2], ["front"])),
        ("JoinStringListNElementNode", (["a", "b", "c", "d"], ["-"], [2], ["back"])),
        ("JoinStringListNElementNode", (["a", "b"], [""], [5], ["back"])),
        ("JoinStringListNElementNode", (["a", "b"], [","], [0], ["front"])),
    ],
)
def test_behavior_matches_upstream(class_name, args):
    upstream_node = getattr(_upstream(), class_name)()
    secure_node = getattr(_secure(), class_name)
    method = getattr(upstream_node, upstream_node.FUNCTION)
    assert secure_node.execute(*args).result == method(*args)


def test_split_empty_separator_matches_upstream_error():
    with pytest.raises(ValueError, match="empty separator"):
        _upstream().SplitStringNode().perform_split_string("abc", "")
    with pytest.raises(ValueError, match="empty separator"):
        _secure().SplitStringNode.execute("abc", "")


def test_bounds_fail_before_large_results():
    secure = _secure()
    oversized = "x" * (secure.nodes.MAX_TEXT_BYTES + 1)
    with pytest.raises(ValueError, match="byte limit"):
        secure.JoinStringsNode.execute(oversized, "")
    with pytest.raises(ValueError, match="item limit"):
        secure.JoinStringListNode.execute(
            [""] * (secure.nodes.MAX_LIST_ITEMS + 1), [","]
        )


def test_all_nodes_execute_in_real_isolated_guest():
    secure = _secure()

    cases = [
        (secure.JoinStringsNode, {"text1": "a", "text2": "b"}, ("ab",)),
        (secure.SplitStringNode, {"text": "a/b", "separator": "/"}, (["a", "b"],)),
        (secure.JoinStringListNode, {"texts": ["a", "b"], "separator": ["|"]}, ("a|b",)),
        (
            secure.JoinStringListNElementNode,
            {"texts": ["a", "b", "c"], "separator": ["-"], "n": [2], "start_from": ["back"]},
            ("b-c",),
        ),
    ]

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession("textutils-conversion", guest_runtime_root=V2).start()
        try:
            outputs = []
            for index, (node, inputs, expected) in enumerate(cases):
                plan = _sdk.ExecutionPlan(
                    prompt_id="textutils",
                    node_id=str(index),
                    node_type=node.__name__,
                    tier="sandbox",
                    node_module=node.__module__,
                    inputs=inputs,
                    permissions=(),
                )
                runtime = _sdk.Runtime(
                    refs=refs,
                    ctx=_sdk.InProcessCtxProvider().build(plan),
                    ops=_sdk.InProcessOps(),
                )
                result = await session.execute(plan, runtime, capabilities=())
                assert result.result == expected
                outputs.append(result.result)
            return outputs, session.last_guest_pid
        finally:
            await session.kill()

    outputs, pid = asyncio.run(run())
    assert len(outputs) == 4
    assert pid not in (None, os.getpid())


def test_python_has_no_ambient_authority():
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "folder_paths", "PromptServer", "aiohttp", "subprocess", "requests",
        "socket", "open(", "torch", "numpy", "sdk.ctx()",
    ):
        assert forbidden not in source
    assert source.count("SDK_PERMISSIONS = ()") == 4


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-textutils" / "x0205574"
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
