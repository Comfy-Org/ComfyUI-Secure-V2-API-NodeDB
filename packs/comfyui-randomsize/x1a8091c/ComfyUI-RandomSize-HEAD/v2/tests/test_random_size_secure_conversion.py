from __future__ import annotations

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
COMMIT = "1a8091c831abea905bfe060c9b501bf87fd4ad00"
DTS_SHA = "4a49be64d7396d115ebda49eecf05898b59aa3e98dfa398ec4f472ae139de5f3"
PYI_SHA = "f2d067f03a2f80f942ba0d5c777daa1148562e44e836b72cb27129b36ba3855f"
PAIR = (
    PACK_DB
    / "patches"
    / "comfyui-randomsize"
    / "x1a8091c"
    / "comfyui-randomsize-x1a8091c"
)
FRONTEND_HARNESS = V2 / "tests" / "random_size_frontend_harness.mjs"

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


class _Routes:
    def __init__(self):
        self.registered = []

    def post(self, route):
        def register(function):
            self.registered.append(("POST", route, function))
            return function
        return register


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
    return _import_package("_secure_random_size_test", V2)


def _pristine(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "pristine"
    shutil.copytree(PACK, root, ignore=shutil.ignore_patterns("v2"))
    routes = _Routes()
    messages = []
    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(
            routes=routes,
            send_sync=lambda event, payload: messages.append((event, payload)),
        )
    )
    monkeypatch.setitem(sys.modules, "server", server)
    package = _import_package("_pristine_random_size_test", root)
    return package, routes, messages


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
                    "validate_inputs",
                    "fingerprint_inputs",
                    "check_lazy_status",
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


def _runtime(plan, refs):
    return _sdk.Runtime(
        refs=refs,
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_pinned_actual_loader_census_entrypoint_schema_and_routes_are_exact(
    tmp_path,
    monkeypatch,
):
    pristine, routes, _messages = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    report = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in report
    assert "1 supported, 0 rejected, 0 pending" in report
    assert set(pristine.NODE_CLASS_MAPPINGS) == {"JOJR_RandomSize"}
    assert set(secure.NODE_CLASS_MAPPINGS) == set(pristine.NODE_CLASS_MAPPINGS)
    assert secure.NODE_DISPLAY_NAME_MAPPINGS == pristine.NODE_DISPLAY_NAME_MAPPINGS
    assert pristine.WEB_DIRECTORY == "js"
    assert secure.WEB_DIRECTORY == "web"
    assert [(method, path) for method, path, _ in routes.registered] == [
        ("POST", "/JOJR_RandomSize/get_sizes")
    ]
    pristine_js = list((PACK / "js").glob("*.js"))
    assert len(pristine_js) == 1
    assert pristine_js[0].read_text().count("app.registerExtension(") == 1

    legacy = pristine.NODE_CLASS_MAPPINGS["JOJR_RandomSize"]
    node = secure.NODE_CLASS_MAPPINGS["JOJR_RandomSize"]
    schema = node.GET_SCHEMA()
    schema.validate()
    legacy_inputs = legacy.INPUT_TYPES()
    assert [item.id for item in schema.inputs] == ["seed", "preset"]
    assert [item.io_type for item in schema.inputs] == ["INT", "COMBO"]
    assert schema.inputs[0].default == 0
    assert schema.inputs[0].min == 0
    assert schema.inputs[0].max == 0xFFFFFFFFFFFFFFFF
    assert schema.inputs[1].options == legacy_inputs["required"]["preset"][0]
    assert [item.io_type for item in schema.outputs] == ["INT", "INT"]
    assert [item.display_name for item in schema.outputs] == ["width", "height"]
    assert [item.value for item in schema.hidden] == ["UNIQUE_ID"]
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ()

    extension = asyncio.run(secure.comfy_entrypoint())
    assert asyncio.run(extension.get_node_list()) == [secure.RandomSize]
    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.random_size_census_test",
    )
    assert set(loaded.node_mappings) == {"JOJR_RandomSize"}
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert not loaded.routes


def test_all_embedded_preset_tables_match_pinned_yaml(tmp_path, monkeypatch):
    pristine, _routes, _messages = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    expected_options = pristine.RandomSize.INPUT_TYPES()["required"]["preset"][0]
    assert list(secure.nodes.PRESETS) == expected_options
    for preset in expected_options:
        assert list(secure.nodes.PRESETS[preset]) == pristine.random_size.get_sizes_from_preset_file(
            preset
        )


@pytest.mark.parametrize("preset", (
    "Preset", "FLUX.yaml", "640.yaml", "1024.yaml", "768.yaml",
    "512.yaml", "SD1.5.yaml", "SDXL.yaml", "896.yaml",
))
def test_selection_outputs_and_marked_ui_are_differential(
    tmp_path,
    monkeypatch,
    preset,
):
    pristine, _routes, messages = _pristine(tmp_path, monkeypatch)
    secure = _secure()
    size_count = len(secure.nodes.PRESETS[preset])
    for seed in (0, size_count - 1, size_count, 1777, 0xFFFFFFFFFFFFFFFF):
        messages.clear()
        expected = pristine.RandomSize().func(seed, preset, "node-7")
        result = secure.RandomSize.execute(seed, preset, "node-7")
        assert result.result == expected
        assert len(messages) == 1
        event, payload = messages[0]
        assert event == "jojr.random-sizes.sendmessage"
        assert payload["id"] == "node-7"
        assert result.ui["sizes"] == payload["message"]
        selected = [item.strip("*") for item in payload["message"] if item.startswith("*")]
        assert result.ui["selected"] == selected
        assert result.ui["preset"] == [preset]
        assert result.result == tuple(int(value) for value in selected[0].split("x"))


def test_selection_is_deterministic_independent_and_fail_closed():
    secure = _secure()
    first = secure.RandomSize.execute(999_999, "1024.yaml", "a")
    second = secure.RandomSize.execute(999_999, "1024.yaml", "b")
    assert first.result == second.result
    assert first.ui == second.ui
    assert secure.RandomSize.execute(0, "Preset", "x").result == (320, 768)
    assert secure.RandomSize.execute(8, "Preset", "x").result == (768, 320)
    for seed in (-1, 0x10000000000000000, True, 1.5):
        with pytest.raises((TypeError, ValueError)):
            secure.RandomSize.execute(seed, "Preset", "x")
    for preset in ("../../secret.yaml", "", None):
        with pytest.raises(ValueError, match="unknown preset"):
            secure.RandomSize.execute(0, preset, "x")


def test_real_isolated_guest_executes_without_any_capabilities():
    secure = _secure()

    async def run():
        refs = _sdk.InProcessRefResolver()
        plan = _sdk.ExecutionPlan(
            prompt_id="random-size-test",
            node_id="random-size",
            node_type=secure.RandomSize.__name__,
            tier="sandbox",
            node_module=secure.RandomSize.__module__,
            inputs={"seed": 1777, "preset": "FLUX.yaml", "id": "guest"},
            permissions=(),
        )
        session = await GuestSession(
            "random-size-pack", guest_runtime_root=V2,
        ).start()
        try:
            result = await session.execute(
                plan, _runtime(plan, refs), capabilities=(),
            )
            return result.result, session.last_guest_pid
        finally:
            await session.kill()

    result, guest_pid = asyncio.run(run())
    assert result == _secure().RandomSize.execute(
        1777, "FLUX.yaml", "guest"
    ).result
    assert guest_pid not in (None, os.getpid())


def test_frontend_mounted_state_safety_and_teardown():
    process = subprocess.run(
        ["node", "--experimental-vm-modules", FRONTEND_HARNESS, V2 / "web" / "main.js"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert "PASS: secure Random Size" in process.stdout


def test_manifest_stubs_license_and_authority_boundary_are_exact():
    secure = _secure()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _manifest(secure)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == DTS_SHA
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == PYI_SHA
    assert (V2 / "LICENSE").read_bytes() == (PACK / "LICENSE").read_bytes()
    python_source = "\n".join(
        path.read_text() for path in sorted(V2.glob("*.py"))
    )
    frontend_source = "\n".join(
        path.read_text() for path in sorted((V2 / "web").glob("*.js"))
    )
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "import server", "from server", "folder_paths",
        "PromptServer", "open(", "eval(", "exec(", "sdk.ctx(",
        "from_value(", "_from_raw(", "torch", "numpy",
    ):
        assert forbidden not in python_source
    for forbidden in (
        "/scripts/app.js", "/scripts/api.js", "/scripts/widgets.js",
        "app.graph", "app.canvas", "window.", "document.", "localStorage",
        "indexedDB", "fetch(", "comfy.backend", "innerHTML",
        "addEventListener", "removeEventListener",
    ):
        assert forbidden not in frontend_source


def test_pristine_to_v2_patch_pair_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-randomsize" / "x1a8091c"
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
