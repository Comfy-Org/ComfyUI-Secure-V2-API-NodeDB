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
import sys

import pytest


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes",
)).expanduser().resolve()
COMMIT = "43b21384353cc94f23cdfde65f586d779f91ba47"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = PACK_DB / "patches" / "comfyui-better-strings" / "x43b2138" / (
    "comfyui-better-strings-x43b2138"
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
        name, root / "__init__.py", submodule_search_locations=[str(root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _secure():
    return _import_package("_secure_better_strings_test", V2)


def _upstream():
    return _import_package("_upstream_better_strings_test", PACK)


def _manifest(pack) -> dict:
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
                    "validate_inputs", "fingerprint_inputs", "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
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


def test_pinned_actual_loader_census_and_entrypoint_are_exact():
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "1 supported, 0 rejected, 0 pending" in report

    pristine_python = [
        path for path in PACK.rglob("*.py") if V2 not in path.parents
    ]
    classes = set()
    source = []
    for path in pristine_python:
        text = path.read_text(errors="replace")
        source.append(text)
        tree = ast.parse(text)
        classes.update(
            item.name for item in tree.body if isinstance(item, ast.ClassDef)
        )
    assert classes == {"BetterString"}
    upstream = _upstream()
    assert set(upstream.NODE_CLASS_MAPPINGS) == {"BetterString"}
    assert upstream.NODE_DISPLAY_NAME_MAPPINGS == {
        "BetterString": "Better Multiline String 💡",
    }
    assert not [path for path in PACK.rglob("*.js") if V2 not in path.parents]
    assert not [path for path in PACK.rglob("*.ts") if V2 not in path.parents]
    combined = "\n".join(source)
    assert "PromptServer" not in combined
    assert "routes." not in combined

    secure = _secure()
    assert set(secure.NODE_CLASS_MAPPINGS) == {"BetterString"}
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == upstream.NODE_DISPLAY_NAME_MAPPINGS
    extension = asyncio.run(secure.comfy_entrypoint())
    assert [node.GET_SCHEMA().node_id for node in asyncio.run(
        extension.get_node_list()
    )] == ["BetterString"]
    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.better_strings_secure_test",
    )
    assert set(loaded.node_mappings) == {"BetterString"}
    assert loaded.frontend_permissions == frozenset()


def test_schema_and_v1_projection_preserve_socket_contract():
    secure = _secure()
    node = secure.BetterString
    schema = node.GET_SCHEMA()
    assert (schema.node_id, schema.display_name, schema.category) == (
        "BetterString", "Better Multiline String 💡", "Better Things 💡",
    )
    assert [item.id for item in schema.inputs] == ["chain", "string"]
    assert [item.get_io_type() for item in schema.inputs] == ["STRING", "STRING"]
    chain, string = schema.inputs
    assert chain.optional is True
    assert chain.force_input is True
    assert chain.multiline is False
    assert chain.default is None
    assert string.optional is False
    assert string.force_input is None
    assert string.multiline is True
    assert string.default is None
    assert [item.get_io_type() for item in schema.outputs] == ["STRING"]
    assert node.SDK_REFS is False
    assert node.SDK_PERMISSIONS == ()

    legacy = schema.get_v1_info(node)
    assert legacy.input == {
        "required": {"string": ("STRING", {"multiline": True})},
        "optional": {
            "chain": ("STRING", {"forceInput": True, "multiline": False}),
        },
    }
    assert legacy.output == ["STRING"]


@pytest.mark.parametrize(
    ("chain", "string"),
    [
        ("", "body"),
        ("   \t\n", "body"),
        ("head", "body"),
        ("head,", "body"),
        ("head,   \n", "body"),
        ("alpha\nbeta", "line one\nline two"),
        ("素晴らしい 💡", "café\n🚀"),
        ("<script>alert(1)</script>", "${globalThis.constructor}"),
        ("x" * 4096, "y" * 4096),
    ],
)
def test_string_composition_is_differential(chain: str, string: str):
    upstream = _upstream().BetterString()
    secure = _secure().BetterString
    assert secure.execute(string=string, chain=chain).result == upstream.action(
        string=string, chain=chain,
    )


def test_repeated_calls_are_independent_and_do_not_mutate_inputs():
    node = _secure().BetterString
    chain = "first  \n"
    string = "second"
    before = (chain, string)
    assert node.execute(string, chain).result == ("first,\n\nsecond",)
    assert node.execute("other", "").result == ("other",)
    assert node.execute(string, chain).result == ("first,\n\nsecond",)
    assert (chain, string) == before


def test_real_guest_executes_without_any_capabilities():
    secure = _secure()

    async def run(inputs):
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="better-strings-test",
            node_id="better-string",
            node_type=secure.BetterString.__name__,
            tier="sandbox",
            node_module=secure.BetterString.__module__,
            inputs=inputs,
            permissions=(),
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "better-strings-pack", guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(plan, runtime, capabilities=())
            return result.result, session.last_guest_pid
        finally:
            await session.kill()

    result, guest_pid = asyncio.run(run({
        "string": "payload\nline two",
        "chain": "prefix,  \n",
    }))
    assert result == ("prefix,\n\npayload\nline two",)
    assert guest_pid not in (None, os.getpid())


def test_manifest_stubs_license_and_ambient_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    source = (V2 / "nodes.py").read_text()
    for forbidden in (
        "import comfy", "folder_paths", "PromptServer", "requests",
        "aiohttp", "subprocess", "open(", "os.", "sys.", "ctx()",
        "torch", "numpy", "eval(", "exec(", "localStorage", "fetch(",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-better-strings" / "x43b2138"
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
