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
import types

import pytest


sys.dont_write_bytecode = True
V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
PACK_DB = SNAPSHOT.parents[2]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = (
    pathlib.Path(
        os.environ.get("COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes")
    )
    .expanduser()
    .resolve()
)
COMFYUI = pathlib.Path("/Users/ben/comfy/ComfyUI")
COMMIT = "ce1c3aab3dd198dcb279c45573428cf41d271843"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "string-constructor"
    / "xce1c3aa"
    / "string-constructor-xce1c3aa"
)

for root in (BACKEND, CORE):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if str(COMFYUI) not in sys.path:
    sys.path.append(str(COMFYUI))
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
    return _import_package("_secure_string_constructor_test", V2)


def _pristine(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    dependency = types.ModuleType("frozendict")
    dependency.frozendict = type("frozendict", (dict,), {})
    monkeypatch.setitem(sys.modules, "frozendict", dependency)
    return _import_package("_pristine_string_constructor_test", root)


def _nodes(pack):
    extension = asyncio.run(pack.comfy_entrypoint())
    return asyncio.run(extension.get_node_list())


def _manifest(pack) -> dict:
    nodes = {}
    for node_class in _nodes(pack):
        node_id = node_class.GET_SCHEMA().node_id
        nodes[node_id] = {
            "module": node_class.__module__.rsplit(".", 1)[-1],
            "class": node_class.__name__,
            "sdk_refs": getattr(node_class, "SDK_REFS", False) is True,
            "permissions": list(getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
            "methods": {
                method: method in node_class.__dict__
                for method in (
                    "validate_inputs",
                    "fingerprint_inputs",
                    "check_lazy_status",
                )
            },
            "schema": encode_schema(copy.deepcopy(node_class.GET_SCHEMA())),
        }
    return {
        "format": FORMAT,
        "nodes": dict(sorted(nodes.items())),
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


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_pinned_actual_entrypoint_census_and_all_schemas_are_exact(
    tmp_path,
    monkeypatch,
):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "4 supported, 0 rejected, 0 pending" in report
    pristine_nodes = _nodes(pristine)
    secure_nodes = _nodes(secure)
    expected_ids = [
        "StringFormatter [String Constructor]",
        "StringConstructorFormatter",
        "ValidateKeys [String Constructor]",
        "StringConstructorValidateKeys",
    ]
    assert [node.GET_SCHEMA().node_id for node in pristine_nodes] == expected_ids
    assert [node.GET_SCHEMA().node_id for node in secure_nodes] == expected_ids
    assert len(secure_nodes) == 4
    for old, new in zip(pristine_nodes, secure_nodes, strict=True):
        assert encode_schema(copy.deepcopy(new.GET_SCHEMA())) == encode_schema(
            copy.deepcopy(old.GET_SCHEMA())
        )
        new.GET_SCHEMA().validate()
        assert new.SDK_REFS is False
        assert new.SDK_PERMISSIONS == ()
    assert secure_nodes[1].GET_SCHEMA().is_deprecated is True
    assert secure_nodes[1].GET_SCHEMA().is_dev_only is True
    assert secure_nodes[3].GET_SCHEMA().is_deprecated is True
    assert secure_nodes[3].GET_SCHEMA().is_dev_only is True

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.string_constructor_census_test",
    )
    assert set(loaded.node_mappings) == set(expected_ids)
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes
    assert loaded.web_directory is None


@pytest.mark.parametrize(
    "template,recursive,safe,mapping",
    (
        ("plain text", False, True, None),
        ("{greeting}, {name}!", False, True, {"greeting": "Hello", "name": "Ada"}),
        ("{known} {missing}", False, True, {"known": "yes"}),
        ("{{literal}} {value:04d}", False, False, {"value": 7}),
        ("{outer}", True, True, {"outer": "{inner}", "inner": "nested"}),
        ("{item[name]}:{item[value]:.2f}", False, False,
         {"item": {"name": "score", "value": 2.5}}),
        ("{valid}", False, True, {"valid": "kept", "bad-key": "dropped"}),
    ),
)
def test_current_and_deprecated_formatters_are_differential(
    tmp_path,
    monkeypatch,
    template,
    recursive,
    safe,
    mapping,
):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    for old, new in zip(_nodes(pristine)[:2], _nodes(secure)[:2], strict=True):
        expected = old.execute(template, recursive, safe, True, mapping)
        actual = new.execute(template, recursive, safe, True, mapping)
        assert actual.result == expected.result
        assert actual.ui == expected.ui.as_dict()
        hidden = new.execute(template, recursive, safe, False, mapping)
        assert hidden.result == expected.result
        assert hidden.ui is None


def test_unsafe_errors_recursive_cycles_and_input_types_match_upstream(
    tmp_path,
    monkeypatch,
):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    for old, new in zip(_nodes(pristine)[:2], _nodes(secure)[:2], strict=True):
        for node in (old, new):
            with pytest.raises(KeyError):
                node.execute("{missing}", False, False, False, {"known": "x"})
            with pytest.raises(RecursionError):
                node.execute("{a}", True, True, False, {"a": "{b}", "b": "{a}"})
            with pytest.raises(TypeError, match="Not a string"):
                node.execute(5, False, True, False, {})


@pytest.mark.parametrize(
    "mapping",
    (
        {"valid": "x", "also_valid_2": 3},
        {},
    ),
)
def test_current_and_deprecated_validators_preserve_identity(
    tmp_path,
    monkeypatch,
    mapping,
):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    for old, new in zip(_nodes(pristine)[2:], _nodes(secure)[2:], strict=True):
        assert old.execute(mapping).result[0] is mapping
        assert new.execute(mapping).result[0] is mapping


@pytest.mark.parametrize(
    "mapping,fragment",
    (
        ({1: "number"}, "(?i)not a string"),
        ({"": "empty"}, "(?i)empty string"),
        ({"1start": "digit"}, "starts with digit"),
        ({"not-valid": "punctuation"}, "(?i)wrong name"),
    ),
)
def test_validator_errors_are_differential(tmp_path, monkeypatch, mapping, fragment):
    pristine = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    for old, new in zip(_nodes(pristine)[2:], _nodes(secure)[2:], strict=True):
        for node in (old, new):
            with pytest.raises(KeyError, match=fragment):
                node.execute(mapping)


def test_pack_side_resource_bounds_fail_closed():
    secure = _secure()
    with pytest.raises(ValueError, match="template exceeds"):
        secure.StringFormatter.execute("x" * 1_048_577)
    with pytest.raises(ValueError, match="formatted string exceeds"):
        secure.StringFormatter.execute(
            "{x}", dict={"x": "y" * 4_194_305}
        )
    too_many = {f"key_{index}": index for index in range(4097)}
    with pytest.raises(ValueError, match="4096-key"):
        secure.ValidateKeys.execute(too_many)
    with pytest.raises(ValueError, match="256-character"):
        secure.ValidateKeys.execute({"x" * 257: 1})


def test_real_isolated_guest_executes_all_current_paths_without_capabilities():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        session = await GuestSession(
            "string-constructor-pack", guest_runtime_root=V2,
        ).start()
        try:
            formatter = secure.StringFormatter
            plan = _sdk.ExecutionPlan(
                prompt_id="string-constructor-format",
                node_id="formatter",
                node_type=formatter.__name__,
                tier="sandbox",
                node_module=formatter.__module__,
                inputs={
                    "template": "{outer}",
                    "recursive_format": True,
                    "safe_format": True,
                    "show_status": True,
                    "dict": {"outer": "hello {name}", "name": "guest"},
                },
                permissions=(),
            )
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=(),
            )
            assert result.result == ("hello guest",)

            validator = secure.ValidateKeys
            validation = _sdk.ExecutionPlan(
                prompt_id="string-constructor-validate",
                node_id="validator",
                node_type=validator.__name__,
                tier="sandbox",
                node_module=validator.__module__,
                inputs={"dict": {"valid": "payload"}},
                permissions=(),
            )
            checked = await session.execute(
                validation, _runtime(validation, refs), capabilities=(),
            )
            assert checked.result == ({"valid": "payload"},)
            assert session.last_guest_pid not in (None, os.getpid())
        finally:
            await session.kill()

    asyncio.run(run())


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE.md").read_bytes() == (PACK / "LICENSE.md").read_bytes()
    source = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(V2.glob("*.py"))
    )
    assert "SDK_REFS = False" in source
    assert "SDK_PERMISSIONS = ()" in source
    validation_source = (V2 / "_validate_funcs.py").read_text()
    assert "import frozendict" not in validation_source
    assert "from frozendict" not in validation_source
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "import server", "from server", "folder_paths",
        "PromptServer", "open(", "eval(", "exec(", "sdk.ctx(",
        "from_value(", "_from_raw(", "torch", "numpy",
    ):
        assert forbidden not in source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "string-constructor" / "xce1c3aa"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_no_generated_caches_are_committed():
    assert not [
        path
        for path in PACK.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"} or path.suffix == ".pyc"
    ]
