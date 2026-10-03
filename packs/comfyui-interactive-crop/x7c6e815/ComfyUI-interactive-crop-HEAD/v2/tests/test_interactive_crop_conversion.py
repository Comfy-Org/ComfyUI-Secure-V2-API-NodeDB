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
import torch.nn.functional as functional


sys.dont_write_bytecode = True

V2 = pathlib.Path(__file__).resolve().parents[1]
PACK = V2.parent
SNAPSHOT = PACK.parent
REPO = pathlib.Path(__file__).resolve().parents[7]
BACKEND = REPO / "backend"
CORE = pathlib.Path(os.environ.get(
    "COMFY_CORE_ROOT", "~/comfy/ComfyUI-secure-nodes"
)).expanduser().resolve()
COMMIT = "7c6e815fdc66989573e4152a651c8d42d4ed384b"
TREE = "4682a32b76dcdb704e526aa4f0f384bba23fe196"
COMFY_API_DTS_SHA256 = (
    "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
)
COMFY_API_PYI_SHA256 = (
    "7deb60a3226572754969eab9777ad2c2b990285f3a3fb922ad610fdbf1040d38"
)
NODE_IDS = {"InteractiveCrop"}
PRISTINE_FILES = {
    ".gitattributes", ".gitignore", "LICENSE", "README.md", "__init__.py",
    "interactive_crop.py", "js/interactive_crop.js", "node.zip",
    "preview.png", "pyproject.toml",
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


def _import_v2(name="_secure_interactive_crop_conversion_test"):
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
    def __init__(self, refs):
        self.refs = refs
        self.calls = []

    async def preview_images(self, image, animated=False):
        value = await self.refs.resolve(image)
        self.calls.append((tuple(value.shape), animated))
        return {"images": [{
            "filename": "interactive-crop.png",
            "type": "temp",
            "subfolder": "interactive-crop",
        }]}


class _Execution:
    def __init__(self):
        self.calls = 0

    async def interrupt(self):
        self.calls += 1
        return True


def _plan(node_class, image, *, resize=False, node_id="1"):
    return _sdk.ExecutionPlan(
        prompt_id=f"interactive-crop-{node_id}",
        node_id=node_id,
        node_type="InteractiveCrop",
        tier="sandbox",
        node_module=node_class.__module__,
        inputs={
            "image": image,
            "force_original_ratio": False,
            "resize_to_original": resize,
        },
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
    assert TREE == "4682a32b76dcdb704e526aa4f0f384bba23fe196"
    assert set(_tree(PACK, omit_v2=True)) == PRISTINE_FILES
    assert hashlib.sha256((PACK / "node.zip").read_bytes()).hexdigest() == (
        "476b7d4f251e50792114a7eae5a88ab4981c32c1e1ad8e8fd9b4df59b55174e3"
    )
    assert not (V2 / "node.zip").exists()

    pristine_tree = ast.parse((PACK / "interactive_crop.py").read_text())
    mapping = next(
        item for item in pristine_tree.body
        if isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Name)
                and target.id == "NODE_CLASS_MAPPINGS" for target in item.targets)
    )
    assert isinstance(mapping.value, ast.Dict)
    assert {key.value for key in mapping.value.keys} == NODE_IDS
    pristine_backend = (PACK / "interactive_crop.py").read_text()
    assert re.findall(r'@routes\.post\("([^"]+)"\)', pristine_backend) == [
        "/interactive_crop/submit",
    ]
    pristine_frontend = (PACK / "js" / "interactive_crop.js").read_text()
    assert pristine_frontend.count("app.registerExtension({") == 1
    assert pristine_frontend.count('"interactive.crop.request"') == 1

    pack = _import_v2()
    assert set(pack.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert set(pack.NODE_DISPLAY_NAME_MAPPINGS) == NODE_IDS
    assert pack.WEB_DIRECTORY == "web"
    assert json.loads((V2 / "secure-nodes.json").read_text()) == _generated_manifest(pack)
    assert hashlib.sha256((V2 / "comfy-api.d.ts").read_bytes()).hexdigest() == COMFY_API_DTS_SHA256
    assert hashlib.sha256((V2 / "comfy-api.pyi").read_bytes()).hexdigest() == COMFY_API_PYI_SHA256

    loaded = packdb.load_pack(
        SNAPSHOT, mount_name="custom_nodes.interactive_crop_conversion_test",
    )
    assert set(loaded.node_mappings) == NODE_IDS
    assert loaded.web_directory == V2 / "web"
    assert loaded.frontend_permissions == frozenset()
    assert loaded.runtime.python_requires == ">=3.13,<3.14"


def test_schema_preserves_wire_contract_and_declares_exact_authority():
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["InteractiveCrop"]
    schema = node_class.GET_SCHEMA()
    schema.validate()
    assert schema.node_id == "InteractiveCrop"
    assert schema.display_name == "Interactive Crop"
    assert schema.category == "image"
    assert [item.id for item in schema.inputs] == [
        "image", "force_original_ratio", "resize_to_original",
    ]
    assert [item.io_type for item in schema.inputs] == ["IMAGE", "BOOLEAN", "BOOLEAN"]
    assert schema.inputs[1].default is False
    assert schema.inputs[2].default is False
    assert [item.id for item in schema.outputs] == ["image", "did_crop"]
    assert [item.io_type for item in schema.outputs] == ["IMAGE", "BOOLEAN"]
    assert [item.value for item in schema.hidden] == [
        "UNIQUE_ID", "PROMPT", "EXTRA_PNGINFO",
    ]
    assert node_class.SDK_REFS is True
    assert node_class.SDK_PERMISSIONS == (
        "raw", "ui", "ui.interact", "execution.interrupt",
    )


def test_selection_validation_clamping_order_and_bilinear_resize():
    pack = _import_v2()
    module = sys.modules[f"{pack.__name__}.interactive_crop"]
    assert module._selection(
        {"action": "continue", "x0": 99, "y0": -4, "x1": 2, "y1": 20},
        width=8,
        height=6,
    ) == ("continue", (2, 0, 8, 6))
    assert module._selection({"action": "passthrough"}, width=8, height=6) == (
        "passthrough", None,
    )
    for invalid in (
        {"action": "later"},
        {"action": "cancel", "x0": 1},
        {"action": "continue", "x0": True, "y0": 0, "x1": 1, "y1": 1},
        {"action": "continue", "x0": 0, "y0": 0, "x1": 1},
    ):
        with pytest.raises((TypeError, ValueError)):
            module._selection(invalid, width=8, height=6)

    value = torch.arange(1 * 2 * 3 * 1, dtype=torch.float32).reshape(1, 2, 3, 1)
    expected = functional.interpolate(
        value.permute(0, 3, 1, 2), size=(5, 7), mode="bilinear", align_corners=False,
    ).permute(0, 2, 3, 1).contiguous()
    assert torch.equal(module._resize_to(value, 5, 7), expected)


def test_real_isolated_guest_crops_full_batch_resizes_and_fails_closed(monkeypatch):
    import server

    monkeypatch.setattr(
        server.PromptServer,
        "instance",
        types.SimpleNamespace(client_id="interactive-crop-test-client"),
        raising=False,
    )
    pack = _import_v2()
    node_class = pack.NODE_CLASS_MAPPINGS["InteractiveCrop"]
    responses = []

    async def interact(**kwargs):
        responses.append(copy.deepcopy(kwargs))
        return current[0]

    monkeypatch.setattr(interactions.BROKER, "request", interact)

    async def run():
        refs = _sdk.InProcessRefResolver()
        source = torch.arange(2 * 6 * 8 * 3, dtype=torch.float32).reshape(2, 6, 8, 3) / 300
        image = _sdk.ImageRef._wrap(await refs.create("IMAGE", source))
        ui = _PreviewUI(refs)
        execution = _Execution()
        session = await GuestSession("interactive-crop-conversion").start()
        try:
            current[:] = [{
                "action": "continue", "x0": 7, "y0": 5,
                "x1": 2, "y1": -3,
            }]
            plan = _plan(node_class, image)
            result = await session.execute(
                plan, _runtime(plan, refs, ui, execution),
                capabilities=plan.permissions,
            )
            assert session.last_guest_pid not in (None, os.getpid())
            assert torch.equal(await refs.resolve(result.result[0]), source[:, 0:5, 2:7, :])
            assert result.result[1] is True
            assert ui.calls == [((2, 6, 8, 3), False)]
            call = responses[-1]
            assert call["kind"] == "image-choice"
            assert call["timeout"] == 240.0
            assert call["reuse_last"] is False
            assert call["remember"] is False
            assert call["node_id"] == "1"
            assert call["payload"] == {
                "variant": "interactive-crop.inline-v1",
                "image": {
                    "filename": "interactive-crop.png",
                    "type": "temp",
                    "subfolder": "interactive-crop",
                },
                "width": 8,
                "height": 6,
                "force_original_ratio": False,
            }

            current[:] = [{
                "action": "continue", "x0": 2, "y0": 1,
                "x1": 6, "y1": 5,
            }]
            resized_plan = _plan(node_class, image, resize=True, node_id="2")
            resized = await session.execute(
                resized_plan, _runtime(resized_plan, refs, ui, execution),
                capabilities=resized_plan.permissions,
            )
            expected = functional.interpolate(
                source[:, 1:5, 2:6, :].permute(0, 3, 1, 2),
                size=(6, 8), mode="bilinear", align_corners=False,
            ).permute(0, 2, 3, 1).contiguous()
            assert torch.equal(await refs.resolve(resized.result[0]), expected)
            assert resized.result[1] is True

            current[:] = [{"action": "passthrough"}]
            passthrough = await session.execute(
                plan, _runtime(plan, refs, ui, execution),
                capabilities=plan.permissions,
            )
            assert torch.equal(await refs.resolve(passthrough.result[0]), source)
            assert passthrough.result[1] is False

            current[:] = [{"action": "continue", "x0": 3, "y0": 2, "x1": 3, "y1": 5}]
            empty = await session.execute(
                plan, _runtime(plan, refs, ui, execution),
                capabilities=plan.permissions,
            )
            assert torch.equal(await refs.resolve(empty.result[0]), source)
            assert empty.result[1] is False

            current[:] = [{"action": "cancel"}]
            with pytest.raises(Exception, match="user cancelled"):
                await session.execute(
                    plan, _runtime(plan, refs, ui, execution),
                    capabilities=plan.permissions,
                )
            assert execution.calls == 1

            current[:] = [{"action": "later"}]
            with pytest.raises(Exception, match="action is invalid"):
                await session.execute(
                    plan, _runtime(plan, refs, ui, execution),
                    capabilities=plan.permissions,
                )
        finally:
            await session.kill()

    current = []
    asyncio.run(run())


def test_actual_broker_scopes_concurrent_tokens_and_ignores_late_responses(
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
        "variant": "interactive-crop.inline-v1",
        "image": {"filename": "preview.png", "type": "temp", "subfolder": "crop"},
        "width": 800,
        "height": 400,
        "force_original_ratio": False,
    }

    async def run():
        first = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="crop",
            node_id="1", sid="client", timeout=1,
        ))
        second = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="crop",
            node_id="2", sid="client", timeout=1,
        ))
        await asyncio.sleep(0)
        first_token = events[0][1]["request_id"]
        second_token = events[1][1]["request_id"]
        second_response = {"action": "passthrough"}
        first_response = {"action": "continue", "x0": 1, "y0": 2, "x1": 3, "y1": 4}
        assert broker.respond(second_token, second_response) is True
        assert broker.respond(first_token, first_response) is True
        assert await first == first_response
        assert await second == second_response
        assert broker.respond(first_token, {"action": "cancel"}) is False
        assert broker.respond(second_token, {"action": "cancel"}) is False

        timed = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="crop",
            node_id="3", sid="client", timeout=0.01,
        ))
        await asyncio.sleep(0)
        timed_token = events[-1][1]["request_id"]
        with pytest.raises(asyncio.TimeoutError):
            await timed
        assert broker.respond(timed_token, {"action": "passthrough"}) is False

        cancelled = asyncio.create_task(broker.request(
            kind="image-choice", payload=payload, tenant="tenant", pack="crop",
            node_id="4", sid="client", timeout=1,
        ))
        await asyncio.sleep(0)
        cancelled_token = events[-1][1]["request_id"]
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        assert broker.respond(cancelled_token, {"action": "passthrough"}) is False

    asyncio.run(run())


def test_frontend_behavior_security_concurrency_scaling_and_teardown():
    source = (V2 / "web" / "interactive_crop.js").read_text()
    assert source.count("comfy.defs.extend(NODE_TYPE") == 1
    assert source.count("comfy.backend.on('secure-node-interaction'") == 1
    for forbidden in (
        "window.", "document.", "localStorage", "sessionStorage",
        "MutationObserver", "app.registerExtension", "addDOMWidget",
        "app.graph", "._nodes", "setDirtyCanvas", "globalThis.fetch",
        "/interactive_crop/submit", "interactive.crop.request",
    ):
        assert forbidden not in source
    for required in (
        "node.widgets.canvas", "comfy.backend.fetch(RESPONSE_ROUTE",
        "onPointerDown", "onPointerMove", "onPointerUp", "builder.onRemoved",
        "timeout * 1000 + 250", "finishRecord(record)",
    ):
        assert required in source

    completed = subprocess.run(
        [
            "node", "--experimental-vm-modules",
            str(V2 / "tests" / "interactive_crop_frontend_harness.mjs"),
            str(V2 / "web" / "interactive_crop.js"),
        ],
        cwd=V2,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: Interactive Crop" in completed.stdout


def test_python_surface_has_no_ambient_host_authority():
    source = "\n".join(path.read_text(errors="replace") for path in sorted(V2.glob("*.py")))
    for forbidden in (
        "import folder_paths", "from folder_paths", "import server", "from server",
        "PromptServer", "aiohttp", "open(", "Path(", "subprocess", "requests",
        "socket", "threading", "_WAITERS", "send_sync",
    ):
        assert forbidden not in source
    for required in (
        "sdk.ctx().interact.request", "sdk.ctx().ui.preview_images",
        "sdk.ctx().execution.interrupt", "await image.raw()",
        "sdk.ImageRef._from_raw",
    ):
        assert required in source


def test_pristine_snapshot_and_patch_roundtrip_are_byte_exact(tmp_path):
    manifest, diff_text = packpatch.generate(SNAPSHOT)
    pair = (
        REPO / "pack-db" / "patches" / "comfyui-interactive-crop"
        / "x7c6e815" / "comfyui-interactive-crop-x7c6e815"
    )
    assert json.loads(pair.with_suffix(".json").read_text()) == manifest
    assert pair.with_suffix(".diff").read_text() == diff_text
    fresh = tmp_path / "comfyui-interactive-crop" / "x7c6e815"
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
