from __future__ import annotations

import ast
import asyncio
import base64
import copy
import hashlib
import importlib.util
import io
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
PACK_DB = SNAPSHOT.parents[2]
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = pathlib.Path("/Users/ben/comfy/ComfyUI_secure_nodes/backend")
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "/Users/ben/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "ff59e58b335866ebc203ad4c506633531f091709"
COMFY_API_SHA256 = (
    "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
)
PAIR = PACK_DB / "patches" / "comfyui-workflow-snapshot-manager" / "xff59e58" / (
    "comfyui-workflow-snapshot-manager-xff59e58"
)

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_secure_nodes import packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402
from comfy_api.latest import _sdk  # noqa: E402


def _import_v2():
    name = "_secure_workflow_snapshot_conversion_test"
    sys.modules.pop(name, None)
    sys.modules.pop(f"{name}.snapshot_node", None)
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
    for node_id, node_class in sorted(pack.NODE_CLASS_MAPPINGS.items()):
        nodes[node_id] = {
            "module": "snapshot_node",
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
        "frontend_permissions": [],
        "nodes": nodes,
        "runtime": manifest_declaration(V2),
        "web_directory": "js",
    }


def test_pinned_pristine_and_secure_census_are_exact():
    conversion = (V2 / "SECURE_CONVERSION.md").read_text()
    assert COMMIT in conversion
    assert (PACK / "snapshot_routes.py").read_text().count("@routes.") == 15

    tree = ast.parse((PACK / "snapshot_node.py").read_text())
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "SaveSnapshot" in classes
    assert (PACK / "js" / "snapshot_manager.js").read_text().count(
        "app.registerExtension({"
    ) == 2

    pack = _import_v2()
    assert pack.NODE_CLASS_MAPPINGS == {"SaveSnapshot": pack.SaveSnapshot}
    assert pack.NODE_DISPLAY_NAME_MAPPINGS == {"SaveSnapshot": "Save Snapshot"}
    assert pack.WEB_DIRECTORY == "./js"

    loaded = packdb.load_pack(
        SNAPSHOT,
        mount_name="custom_nodes.workflow_snapshot_conversion_test",
    )
    assert set(loaded.node_mappings) == {"SaveSnapshot"}
    assert loaded.web_directory == V2 / "js"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_save_snapshot_schema_validation_passthrough_and_capture_request():
    pack = _import_v2()
    node = pack.SaveSnapshot
    schema = node.GET_SCHEMA()
    assert schema.node_id == "SaveSnapshot"
    assert schema.display_name == "Save Snapshot"
    assert schema.category == "Snapshot Manager"
    assert schema.is_output_node is True
    assert [(item.id, item.io_type) for item in schema.inputs] == [
        ("value", "*"), ("label", "STRING"),
    ]
    assert schema.inputs[1].default == "Node Trigger"
    assert [(item.id, item.io_type) for item in schema.outputs] == [("value", "*")]
    assert node.SDK_REFS is True
    assert node.SDK_PERMISSIONS == ("raw", "ui")
    assert node.validate_inputs(label="okay") is True
    assert "string" in node.validate_inputs(label=10)
    assert "500" in node.validate_inputs(label="x" * 501)

    marker = object()
    output = asyncio.run(node.execute(marker, label="  Named capture  "))
    assert output.result == (marker,)
    assert output.ui == {
        "snapshot_manager_capture": [{"label": "Named capture"}],
    }

    import torch
    from PIL import Image

    snapshot_node = sys.modules[node.__module__]

    class TestImageRef(snapshot_node.sdk.ImageRef):
        async def raw(self):
            return torch.full((1, 300, 400, 3), 0.5)

    image_ref = TestImageRef(kind="IMAGE", id="test-image")
    with_thumbnail = asyncio.run(node.execute(image_ref, label="Image"))
    assert with_thumbnail.result == (image_ref,)
    encoded = with_thumbnail.ui["snapshot_manager_capture"][0]["thumbnail"]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as thumbnail:
        assert thumbnail.format == "JPEG"
        assert thumbnail.size == (200, 150)


def test_save_snapshot_runs_in_an_isolated_guest_with_raw_and_ui_capabilities():
    import torch

    pack = _import_v2()
    node = pack.SaveSnapshot

    async def run():
        refs = _sdk.InProcessRefResolver()
        image = torch.rand(1, 48, 64, 3)
        image_ref = _sdk.ImageRef._wrap(await refs.create("IMAGE", image))
        plan = _sdk.ExecutionPlan(
            prompt_id="workflow-snapshot-test",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={"value": image_ref, "label": "Guest image"},
            permissions=node.SDK_PERMISSIONS,
        )
        runtime = _sdk.Runtime(
            refs=refs,
            ctx=_sdk.InProcessCtxProvider().build(plan),
            ops=_sdk.InProcessOps(),
        )
        session = await GuestSession(
            "workflow-snapshot-pack",
            guest_runtime_root=V2,
        ).start()
        try:
            output = await session.execute(
                plan, runtime, capabilities=node.SDK_PERMISSIONS,
            )
            returned = await refs.resolve(output.result[0])
            return output, returned, image, session.last_guest_pid
        finally:
            await session.kill()

    output, returned, original, guest_pid = asyncio.run(run())
    assert guest_pid not in (None, os.getpid())
    assert returned is original
    payload = output.ui["snapshot_manager_capture"][0]
    assert payload["label"] == "Guest image"
    assert base64.b64decode(payload["thumbnail"]).startswith(b"\xff\xd8")


def test_manifest_contract_and_sources_are_secure_and_fresh():
    pack = _import_v2()
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == (
        COMFY_API_SHA256
    )

    python_source = "\n".join(path.read_text(errors="replace") for path in V2.glob("*.py"))
    for forbidden in (
        "import server", "from server", "PromptServer", "aiohttp",
        "snapshot_routes", "snapshot_storage", "subprocess",
    ):
        assert forbidden not in python_source

    frontend = "\n".join(path.read_text(errors="replace") for path in (V2 / "js").glob("*.js"))
    for forbidden in (
        "api.fetchApi", "comfy.backend", "fetch(", "localStorage",
        "indexedDB", "window.", "document.", "innerHTML",
    ):
        assert forbidden not in frontend
    assert 'from "/comfy/api/v2.js"' in frontend
    assert 'scope: "canvas"' in frontend
    assert 'mode: "replace"' in frontend
    assert 'mode: "new"' in frontend


def test_frontend_behavior_limits_security_and_profile_tabs():
    completed = subprocess.run(
        ["npm", "test", "--", "--test-reporter=spec"],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "tests 17" in completed.stdout
    assert "fail 0" in completed.stdout


def test_pristine_to_v2_patch_roundtrip_is_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    assert json.loads(PAIR.with_suffix(".json").read_text()) == manifest
    assert PAIR.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-workflow-snapshot-manager" / "xff59e58"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_do_not_dirty_pristine_or_v2_with_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
