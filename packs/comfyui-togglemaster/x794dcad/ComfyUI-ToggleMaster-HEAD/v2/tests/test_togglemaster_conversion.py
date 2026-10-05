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


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "794dcadf8c33c19a8242c4f8ff7edcf8b0883f7c"
COMFY_API_DTS_SHA256 = (
    "bb40d8a1b50dc1c8cdf7db8f042f9e79de80b1d88ff2ddc56c41fde04a7ec09f"
)
COMFY_API_PYI_SHA256 = (
    "5c85bd4742059f3206d98c22aa79f44e445330a405cad1d7056bf33728ffca1b"
)
NODE_IDS = {"DynamicTextConcatenate"}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_v2(name="_secure_togglemaster_conversion_test"):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name,
        V2 / "__init__.py",
        submodule_search_locations=[str(V2)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def _import_pristine_from_copy(tmp_path: pathlib.Path):
    copy_root = tmp_path / "pristine"
    shutil.copytree(PACK, copy_root, ignore=shutil.ignore_patterns("v2"))
    name = "_pristine_togglemaster_census"
    spec = importlib.util.spec_from_file_location(
        name,
        copy_root / "__init__.py",
        submodule_search_locations=[str(copy_root)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
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
            "permissions": list(
                getattr(node_class, "SDK_PERMISSIONS", ()) or ()),
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
        "web_directory": "web",
    }


def _runtime(plan):
    return _sdk.Runtime(
        refs=_sdk.InProcessRefResolver(),
        ctx=_sdk.InProcessCtxProvider().build(plan),
        ops=_sdk.InProcessOps(),
    )


def test_pinned_census_manifest_and_authoritative_contract_are_exact(tmp_path):
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    pristine = _import_pristine_from_copy(tmp_path)
    assert set(pristine.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert pristine.WEB_DIRECTORY == "./js"
    assert sum(
        path.read_text(errors="replace").count("app.registerExtension({")
        for path in (PACK / "js").glob("*.js")
    ) == 2

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == (
        _generated_manifest(pack))
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_DTS_SHA256)
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == (
        COMFY_API_PYI_SHA256)

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.togglemaster_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"
    assert not loaded.routes


def test_schema_preserves_all_inputs_and_outputs_exactly():
    node_class = _import_v2().NODE_CLASS_MAPPINGS["DynamicTextConcatenate"]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "DynamicTextConcatenate"
    assert schema.display_name == "Dynamic Text Concatenate"
    assert schema.category == "utils"
    assert [item.id for item in schema.inputs] == [
        *[f"text_{index}" for index in range(1, 11)],
        "delimiter",
        "custom_delimiter",
    ]
    for item in schema.inputs[:10]:
        assert item.io_type == "STRING"
        assert item.optional is True
        assert item.force_input is True
    delimiter = schema.inputs[10]
    assert delimiter.io_type == "COMBO"
    assert delimiter.options == [
        "space", "none", "comma", "newline", "pipe", "custom",
    ]
    assert delimiter.default == "space"
    assert delimiter.optional is True
    custom = schema.inputs[11]
    assert custom.io_type == "STRING"
    assert custom.default == ""
    assert custom.optional is True
    assert [(item.id, item.io_type) for item in schema.outputs] == [
        ("text", "STRING"),
    ]
    assert getattr(node_class, "SDK_REFS", False) is False
    assert getattr(node_class, "SDK_PERMISSIONS", ()) == ()


def test_delimiters_numeric_order_empty_handling_and_real_guest_execution():
    node_class = _import_v2().NODE_CLASS_MAPPINGS["DynamicTextConcatenate"]
    direct_cases = [
        ("space", "", {"text_2": "B", "text_1": "A"}, "A B"),
        ("none", "", {"text_1": "A", "text_3": "C"}, "AC"),
        ("comma", "", {"text_1": "A", "text_2": "B"}, "A, B"),
        ("newline", "", {"text_1": "A", "text_2": "B"}, "A\nB"),
        ("pipe", "", {"text_1": "A", "text_2": "B"}, "A | B"),
        ("custom", "::", {"text_1": "A", "text_10": "Z"}, "A::Z"),
        ("unknown", "!", {"text_1": "A", "text_2": "B"}, "A B"),
        ("space", "", {"text_1": "", "text_2": None, "text_3": 7}, "7"),
    ]
    for delimiter, custom, values, expected in direct_cases:
        result = node_class.execute(
            delimiter=delimiter, custom_delimiter=custom, **values,
        )
        assert result.result == (expected,)

    async def run():
        session = await GuestSession("togglemaster-conversion").start()
        try:
            plan = _sdk.ExecutionPlan(
                prompt_id="togglemaster-conversion",
                node_id="1",
                node_type="DynamicTextConcatenate",
                tier="sandbox",
                node_module=node_class.__module__,
                inputs={
                    "delimiter": "custom",
                    "custom_delimiter": " / ",
                    "text_1": "one",
                    "text_4": "four",
                    "text_10": "ten",
                },
                permissions=(),
                method="execute",
            )
            result = await session.execute(plan, _runtime(plan), capabilities=())
            assert session.last_guest_pid not in (None, os.getpid())
            assert result.result == ("one / four / ten",)
        finally:
            await session.kill()

    asyncio.run(run())


def test_frontend_behavior_security_and_lifecycle():
    sources = [
        (V2 / "web" / "dynamic_text_concatenate.js").read_text(),
        (V2 / "web" / "wireless_master_toggle.js").read_text(),
    ]
    source = "\n".join(sources)
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage", "fetch(",
        "app.registerExtension", "LiteGraph", "app.graph", "._nodes",
        "MutationObserver", "WebSocket", "XMLHttpRequest",
    ):
        assert forbidden not in source
    for required in (
        'comfy.defs.extend(NODE_TYPE', 'comfy.defs.define({',
        'queryNodes({ scope })', 'scope: "document"', "comfy.sameEntity",
        "comfy.graph.batch", "node.widgets.mount", "stopNodeChanges?.()",
        "clearTimeout(state.timer)", "node.inputs.add", "node.inputs.remove",
    ):
        assert required in source

    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "togglemaster_frontend_harness.mjs"),
            str(V2 / "web" / "dynamic_text_concatenate.js"),
            str(V2 / "web" / "wireless_master_toggle.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: ToggleMaster" in completed.stdout


def test_python_surface_has_no_ambient_authority():
    source = "\n".join(
        path.read_text(errors="replace") for path in sorted(V2.glob("*.py"))
    )
    for forbidden in (
        "import os", "import pathlib", "import subprocess", "import requests",
        "import socket", "import server", "from server", "folder_paths",
        "PromptServer", "open(", "eval(", "exec(", "sdk.ctx(",
        "SDK_PERMISSIONS",
    ):
        assert forbidden not in source
    assert "from comfy_api.latest import io" in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-togglemaster"
        / "x794dcad" / "comfyui-togglemaster-x794dcad"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-togglemaster" / "x794dcad"
    fresh.mkdir(parents=True)
    shutil.copytree(
        PACK,
        fresh / PACK.name,
        ignore=shutil.ignore_patterns("v2"),
    )
    packpatch.apply(fresh, manifest, diff_text)
    assert _tree(fresh / PACK.name) == _tree(PACK)
    assert _tree(PACK, omit_v2=True) == _tree(fresh / PACK.name, omit_v2=True)


def test_no_cache_artifacts_in_pristine_or_v2():
    for root in (PACK, V2):
        assert not list(root.rglob("__pycache__"))
        assert not list(root.rglob("*.pyc"))
