from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import types

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
COMMIT = "450407917c79ea03c80e5ae030d2fcedfa87b501"
TREE = "14f07d08c8cb01123e203e7b4e7c4bd8191a6fa5"
COMFY_API_DTS_SHA256 = (
    "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
)
COMFY_API_PYI_SHA256 = (
    "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
)
NODE_IDS = {"ImagePreviewPause"}
PRISTINE_FILES = {
    "ImagePreviewPause.py", "LICENSE", "README.md", "__init__.py",
    "js/preview_pause.js", "manifest.json",
}

for path in (str(REPO), str(BACKEND), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("COMFY_CORE_ROOT", str(CORE))

from comfy_api.latest import _sdk  # noqa: E402
from comfy_secure_nodes import interactions, packdb, packpatch  # noqa: E402
from comfy_secure_nodes.packmanifest import FORMAT, encode_schema  # noqa: E402
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402
from comfy_secure_nodes.transport.host import GuestSession  # noqa: E402


def _import_v2(name="_secure_image_preview_pause_conversion_test"):
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)],
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
        "web_directory": "web",
    }


class _PreviewUI:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def preview_images(self, image, animated=False):
        self.calls.append((image, animated))
        return copy.deepcopy(self.result)


class _Execution:
    def __init__(self):
        self.calls = 0

    async def interrupt(self):
        self.calls += 1
        return True


def _plan(node_class, image, node_id="1"):
    return _sdk.ExecutionPlan(
        prompt_id=f"image-preview-pause-{node_id}",
        node_id=node_id,
        node_type="ImagePreviewPause",
        tier="sandbox",
        node_module=node_class.__module__,
        inputs={"images": image},
        permissions=tuple(node_class.SDK_PERMISSIONS),
        method="execute",
    )


def _runtime(plan, refs, ui, execution):
    context = _sdk.InProcessCtxProvider().build(plan)
    context.ui = ui
    context.execution = execution
    return _sdk.Runtime(refs=refs, ctx=context, ops=_sdk.InProcessOps())


def test_pinned_pristine_census_manifest_and_contract_are_exact():
    assert COMMIT in (V2 / "SECURE_CONVERSION.md").read_text()
    assert TREE == "14f07d08c8cb01123e203e7b4e7c4bd8191a6fa5"
    assert set(_tree(PACK, omit_v2=True)) == PRISTINE_FILES

    pristine_tree = ast.parse((PACK / "ImagePreviewPause.py").read_text())
    mapping = next(
        item for item in pristine_tree.body
        if isinstance(item, ast.ClassDef) and item.name == "ImagePreviewPause"
    )
    assert mapping.name == "ImagePreviewPause"
    root = (PACK / "__init__.py").read_text()
    assert root.count('"ImagePreviewPause": ImagePreviewPause') == 1
    backend = (PACK / "ImagePreviewPause.py").read_text()
    assert re.findall(r'@PromptServer\.instance\.routes\.post\("([^"]+)"\)', backend) == [
        "/image_preview_pause/continue/{node_id}",
        "/image_preview_pause/cancel",
    ]
    frontend = (PACK / "js" / "preview_pause.js").read_text()
    assert frontend.count("app.registerExtension({") == 1
    assert "api.interrupt = function" in frontend

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "./web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.image_preview_pause_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schema_preserves_wire_contract_and_declares_exact_authority():
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["ImagePreviewPause"]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "ImagePreviewPause"
    assert schema.display_name == "Preview Image with Pause"
    assert schema.category == "image"
    assert [item.id for item in schema.inputs] == ["images"]
    assert [item.io_type for item in schema.inputs] == ["IMAGE"]
    assert [item.id for item in schema.outputs] == ["images"]
    assert [item.io_type for item in schema.outputs] == ["IMAGE"]
    assert [item.value for item in schema.hidden] == [
        "UNIQUE_ID", "PROMPT", "EXTRA_PNGINFO",
    ]
    assert schema.is_output_node is True
    assert node_class.SDK_REFS is True
    assert node_class.SDK_PERMISSIONS == (
        "ui", "ui.interact", "execution.interrupt",
    )


def test_preview_and_response_validation_is_bounded_and_path_safe():
    pack = _import_v2()
    module = sys.modules[f"{pack.__name__}.ImagePreviewPause"]
    assert module._preview_images({"images": [
        {"name": "one.png", "type": "temp", "subfolder": "reviews/one"},
        {"filename": "two.png", "type": "output", "subfolder": ""},
    ]}) == [
        {"filename": "one.png", "type": "temp", "subfolder": "reviews/one"},
        {"filename": "two.png", "type": "output", "subfolder": ""},
    ]
    assert module._action({"action": "continue"}) == "continue"
    assert module._action({"action": "cancel"}) == "cancel"
    for invalid in (
        {}, {"images": []}, {"images": [{}]},
        {"images": [{"filename": "../escape.png", "type": "temp"}]},
        {"images": [{"filename": "image.png", "type": "other"}]},
        {"images": [{"filename": "image.png", "type": "temp", "subfolder": "../x"}]},
        {"images": [{"filename": "image.png", "type": "temp"}] * 257},
    ):
        with pytest.raises((TypeError, ValueError)):
            module._preview_images(invalid)
    for invalid in (None, {}, {"action": "retry"}):
        with pytest.raises((TypeError, ValueError)):
            module._action(invalid)


def test_real_isolated_guest_previews_batch_passthrough_and_cancel(monkeypatch):
    import server

    monkeypatch.setattr(
        server.PromptServer,
        "instance",
        types.SimpleNamespace(client_id="image-preview-pause-test-client"),
        raising=False,
    )
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["ImagePreviewPause"]
    requests = []

    async def interact(**kwargs):
        requests.append(copy.deepcopy(kwargs))
        return responses[0]

    monkeypatch.setattr(interactions.BROKER, "request", interact)

    async def run():
        refs = _sdk.InProcessRefResolver()
        source = torch.rand((3, 8, 12, 3), generator=torch.Generator().manual_seed(5))
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", source))
        display = {"images": [
            {"filename": "batch-0.png", "type": "temp", "subfolder": "pause"},
            {"filename": "batch-1.png", "type": "temp", "subfolder": "pause"},
            {"filename": "batch-2.png", "type": "temp", "subfolder": "pause"},
        ]}
        ui = _PreviewUI(display)
        execution = _Execution()
        plan = _plan(node_class, image)
        session = await GuestSession("image-preview-pause-conversion").start()
        try:
            responses[:] = [{"action": "continue"}]
            result = await session.execute(
                plan, _runtime(plan, refs, ui, execution),
                capabilities=plan.permissions,
            )
            assert session.last_guest_pid not in (None, os.getpid())
            assert torch.equal(await refs.resolve(result.result[0]), source)
            assert result.ui == display
            assert len(ui.calls) == 1
            call = requests[-1]
            assert call["kind"] == "image-choice"
            assert call["timeout"] == 540.0
            assert call["reuse_last"] is False
            assert call["remember"] is False
            assert call["node_id"] == "1"
            assert call["payload"] == {
                "variant": "image-preview-pause.inline-v1",
                "images": display["images"],
                "count": 3,
            }
            assert execution.calls == 0

            responses[:] = [{"action": "cancel"}]
            with pytest.raises(Exception, match="user cancelled"):
                await session.execute(
                    plan, _runtime(plan, refs, ui, execution),
                    capabilities=plan.permissions,
                )
            assert execution.calls == 1

            responses[:] = [{"action": "retry"}]
            with pytest.raises(Exception, match="invalid action"):
                await session.execute(
                    plan, _runtime(plan, refs, ui, execution),
                    capabilities=plan.permissions,
                )
        finally:
            await session.kill()

    responses = []
    asyncio.run(run())


def test_actual_broker_scopes_tokens_and_rejects_duplicate_late_and_cancelled(
    monkeypatch,
):
    import server

    events = []
    monkeypatch.setattr(
        server.PromptServer,
        "instance",
        types.SimpleNamespace(send_sync=lambda event, data, sid=None: events.append((event, data, sid))),
        raising=False,
    )
    monkeypatch.setattr(interactions, "MIN_TIMEOUT_SECONDS", 0.001)
    broker = interactions.InteractionBroker()
    payload = {
        "variant": "image-preview-pause.inline-v1",
        "images": [{"filename": "preview.png", "type": "temp", "subfolder": "pause"}],
        "count": 1,
    }

    async def run():
        first = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="pause",
            node_id="1", sid="client", timeout=1,
        ))
        second = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="pause",
            node_id="2", sid="client", timeout=1,
        ))
        await asyncio.sleep(0)
        first_token = events[0][1]["request_id"]
        second_token = events[1][1]["request_id"]
        assert first_token != second_token
        assert broker.respond(second_token, {"action": "continue"}) is True
        assert broker.respond(first_token, {"action": "cancel"}) is True
        assert await first == {"action": "cancel"}
        assert await second == {"action": "continue"}
        assert broker.respond(first_token, {"action": "continue"}) is False
        assert broker.respond(second_token, {"action": "cancel"}) is False

        timed = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="pause",
            node_id="3", sid="client", timeout=0.01,
        ))
        await asyncio.sleep(0)
        timed_token = events[-1][1]["request_id"]
        with pytest.raises(asyncio.TimeoutError):
            await timed
        assert broker.respond(timed_token, {"action": "continue"}) is False

        cancelled = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="pause",
            node_id="4", sid="client", timeout=1,
        ))
        await asyncio.sleep(0)
        cancelled_token = events[-1][1]["request_id"]
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        assert broker.respond(cancelled_token, {"action": "cancel"}) is False

    asyncio.run(run())


def test_frontend_batch_ui_security_correlation_expiry_and_teardown():
    source = (V2 / "web" / "preview_pause.js").read_text()
    assert source.count("comfy.defs.extend(NODE_TYPE") == 1
    assert source.count('comfy.backend.on("secure-node-interaction"') == 1
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage",
        "MutationObserver", "app.registerExtension", "addDOMWidget",
        "app.graph", "._nodes", "setDirtyCanvas", "globalThis.fetch",
        "/image_preview_pause/continue", "/image_preview_pause/cancel",
        "api.interrupt =", "setInterval(",
    ):
        assert forbidden not in source
    for required in (
        "node.widgets.canvas", "comfy.backend.fetch(RESPONSE_ROUTE",
        "builder.onRemoved", "timeout * 1000 + 250", "finishRecord(record)",
        "createImageBitmap", "activateNext(state)", "closeImages(state.images)",
    ):
        assert required in source

    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "image_preview_pause_frontend_harness.mjs"),
            str(V2 / "web" / "preview_pause.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: ImagePreviewPause" in completed.stdout


def test_python_surface_has_no_ambient_host_authority():
    source = "\n".join(path.read_text(errors="replace") for path in sorted(V2.glob("*.py")))
    for forbidden in (
        "import folder_paths", "from folder_paths", "import server", "from server",
        "PromptServer", "aiohttp", "open(", "pathlib.Path(", "subprocess", "requests",
        "socket", "threading", "status_by_id", "send_sync", "time.sleep",
        "numpy", "PIL",
    ):
        assert forbidden not in source
    for required in (
        "sdk.ctx().interact.request", "sdk.ctx().ui.preview_images",
        "sdk.ctx().execution.interrupt", "sdk.ImageRef",
    ):
        assert required in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-imagepreviewpause"
        / "x4504079" / "comfyui-imagepreviewpause-x4504079"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    # Upstream's pristine Python/Markdown sources use CRLF. Preserve those
    # exact context bytes instead of pathlib's universal-newline translation.
    assert pair.with_suffix(".diff").read_bytes().decode("utf-8") == diff_text
    fresh = tmp_path / "comfyui-imagepreviewpause" / "x4504079"
    fresh.mkdir(parents=True)
    shutil.copytree(PACK, fresh / PACK.name, ignore=shutil.ignore_patterns("v2"))
    packpatch.apply(fresh, manifest, diff_text)
    rebuilt = fresh / PACK.name / "v2"
    packpatch.validate_tree(rebuilt, V2)
    assert _tree(rebuilt) == _tree(V2)


def test_tests_do_not_dirty_snapshot_with_cache_artifacts():
    assert not list(PACK.rglob("__pycache__"))
    assert not list(PACK.rglob("*.pyc"))
    assert not list(PACK.rglob(".pytest_cache"))
