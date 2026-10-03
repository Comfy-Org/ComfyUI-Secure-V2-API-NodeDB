from __future__ import annotations

import asyncio
import hashlib
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import torch

from comfy_api.latest import _sdk as secure_sdk
from comfy_secure_nodes import apistubs
from comfy_secure_nodes.transport.host import GuestSession


V2 = Path(__file__).resolve().parents[1]
DTS_SHA256 = "73837d21322bf597dc40a0c9b1b9b0a10ab46bf1849fb4a935380a226b9fc96d"
PYI_SHA256 = "aaac189f0c2d52d812d3d637d2a86caa1a2cb3c88f0dee040394cbe443ab210d"


def _load_package():
    name = "h3_secure_test_pack"
    for module_name in tuple(sys.modules):
        if module_name == name or module_name.startswith(name + "."):
            del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        name, V2 / "__init__.py", submodule_search_locations=[str(V2)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run(value):
    return asyncio.run(value)


def test_published_api_contracts_are_pinned_and_current():
    pyi = V2 / "comfy-api.pyi"
    dts = V2 / "comfy-api.d.ts"
    assert pyi.read_text() == apistubs.generate()
    assert hashlib.sha256(pyi.read_bytes()).hexdigest() == PYI_SHA256
    assert hashlib.sha256(dts.read_bytes()).hexdigest() == DTS_SHA256


class FakeImage:
    def __init__(self, count):
        self.indices = list(range(count))

    async def batch_size(self):
        return len(self.indices)

    async def select_batch(self, indices):
        result = FakeImage(0)
        result.indices = [self.indices[index] for index in indices]
        return result


class FakeLatent:
    def __init__(self, value):
        self._value = value

    async def value(self):
        return self._value


class FakeConditioning:
    def __init__(self):
        self.guides = None

    async def with_minimax_h3_guides(self, **guides):
        self.guides = guides
        return self


class Storage:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value


class Output:
    def __init__(self):
        self.state_calls = []
        self.video_calls = []

    async def save_state_dict(self, state, filename_prefix, metadata=None):
        self.state_calls.append((state, filename_prefix, metadata))
        return filename_prefix + "_00001_.safetensors"

    async def save_video(self, images, **options):
        self.video_calls.append((images, options))
        prefix = options["filename_prefix"]
        subfolder, stem = prefix.rsplit("/", 1)
        return {"images": [{
            "filename": stem + "_00001_.mp4",
            "subfolder": subfolder,
            "type": "output",
        }]}


def test_registration_and_schema_census():
    package = _load_package()
    assert set(package.NODE_CLASS_MAPPINGS) == {
        "H3Context", "H3ContextTrim", "H3ImportSource",
        "H3ContextSaveLatent", "H3ContextLoadLatent",
        "H3ProjectHub", "H3ProjectSave",
    }
    schemas = {key: value.define_schema() for key, value in package.NODE_CLASS_MAPPINGS.items()}
    expected_inputs = {
        "H3Context": [
            "conditioning", "latent", "context_length", "encode_mode",
            "anchor_mode", "crop", "audio_context_length", "audio_mode",
            "video_source", "seed_head", "head_hold", "hold_framing",
            "vae", "enabled", "context_frames", "context_latent",
            "audio_vae", "context_audio", "anchor_latent",
        ],
        "H3ImportSource": [
            "images", "source_fps", "width", "height", "crop", "keep",
            "vae", "audio", "audio_vae",
        ],
        "H3ContextTrim": [
            "images", "trim_frames", "audio", "fps", "match_tail",
        ],
        "H3ContextSaveLatent": ["latent", "filename_prefix", "clip_index"],
        "H3ContextLoadLatent": ["latent_path", "clip_index"],
        "H3ProjectHub": [
            "project_name", "create_if_missing", "vae", "audio_vae",
            "width", "height",
        ],
        "H3ProjectSave": ["project", "latent", "images", "fps", "audio"],
    }
    expected_outputs = {
        "H3Context": ["CONDITIONING", "INT", "LATENT"],
        "H3ImportSource": ["LATENT", "IMAGE", "AUDIO", "STRING"],
        "H3ContextTrim": ["IMAGE", "AUDIO"],
        "H3ContextSaveLatent": ["STRING"],
        "H3ContextLoadLatent": ["LATENT"],
        "H3ProjectHub": ["H3_PROJECT", "LATENT", "BOOLEAN", "STRING", "INT", "INT", "LATENT"],
        "H3ProjectSave": ["STRING"],
    }
    for node_id, schema in schemas.items():
        assert [value.id for value in schema.inputs] == expected_inputs[node_id]
        assert [value.io_type for value in schema.outputs] == expected_outputs[node_id]
    assert schemas["H3Context"].node_id == "H3Context"
    assert schemas["H3ContextLoadLatent"].inputs[0].default == "h3_context"
    assert len(schemas["H3Context"].inputs) == 19
    assert len(schemas["H3ProjectHub"].outputs) == 7


def test_cfr_mapping_and_trim_are_sample_locked(monkeypatch):
    package = _load_package()
    nodes = sys.modules[package.__name__ + ".nodes"]
    spec = importlib.util.spec_from_file_location(
        "h3_pristine_import_math", V2.parent / "import_source.py")
    pristine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pristine)
    for count, fps in ((300, 30.0), (1000, 29.97), (56, 24.0), (8, 60.0)):
        assert nodes._cfr_indices(count, fps) == pristine.cfr_index_map(count, fps)
    captured = {}

    async def audio_ref(waveform, sample_rate):
        captured["waveform"] = waveform
        captured["sample_rate"] = sample_rate
        return captured

    monkeypatch.setattr(nodes, "_audio_ref", audio_ref)
    image = FakeImage(56)
    waveform = torch.arange(2 * 1000, dtype=torch.float32).reshape(1, 2, 1000)
    audio = types.SimpleNamespace(value=lambda: _audio_value(waveform, 1000))
    result = _run(nodes.H3ContextTrim.execute(
        image, 5, audio=audio, fps=25.0, match_tail=True))
    assert result[0].indices == list(range(5, 56))
    assert captured["sample_rate"] == 1000
    assert captured["waveform"].shape[-1] == round(51 / 25 * 1000)
    assert torch.equal(captured["waveform"][..., 0], waveform[..., 200])


async def _audio_value(waveform, sample_rate):
    return {"waveform": waveform, "sample_rate": sample_rate}


def test_context_uses_native_h3_guides_without_core_patching(monkeypatch):
    package = _load_package()
    nodes = sys.modules[package.__name__ + ".nodes"]

    async def latent_ref(tensor, **fields):
        return {"tensor": tensor, **fields}

    monkeypatch.setattr(nodes, "_latent", latent_ref)
    target = torch.zeros((1, 24, 8, 4, 4))
    prior_video = torch.ones((1, 24, 8, 4, 4))
    prior_audio = torch.ones((1, 32, 2, 40))
    cond = FakeConditioning()
    result = _run(nodes.H3Context.execute(
        cond,
        FakeLatent({"samples": target}),
        22, "video", "head", "disabled",
        context_latent=FakeLatent({
            "samples": nodes.NestedTensor([prior_video, prior_audio]),
        }),
        seed_head=False,
    ))
    assert result[0] is cond
    assert result[1] == 9
    assert result[2]._value["samples"] is target
    assert [position for position, _ in cond.guides["video_guides"]] == [0.0, 1.0, 5.0]
    assert len(cond.guides["audio_guides"]) == 1
    start, audio = cond.guides["audio_guides"][0]
    assert abs(start - (-13.2)) < 1e-6
    assert audio["tensor"].shape[-1] == 37


def test_project_routes_are_tenant_storage_state_machine(monkeypatch):
    package = _load_package()
    project = sys.modules[package.__name__ + ".project_nodes"]
    routes = importlib.import_module(package.__name__ + "._secure_routes")
    storage = Storage()
    context = types.SimpleNamespace(storage=storage)
    monkeypatch.setattr(project.sdk, "ctx", lambda: context)

    def call(handler, *, query=None, body=None):
        response = _run(handler({
            "query": query or {},
            "body": json.dumps(body or {}),
        }))
        return response["status"], json.loads(response["body"])

    status, created = call(routes.create, body={"name": "Film One"})
    assert status == 200 and created["approved"] == []
    manifest = json.loads(storage.values["h3-project:Film One"])
    manifest["takes"] = [
        {"index": 1, "take": 1, "basename": "clip_001_take1", "latent": "a", "video": "v"},
        {"index": 1, "take": 2, "basename": "clip_001_take2", "latent": "b", "video": "w"},
    ]
    manifest["pending"] = manifest["takes"][0]
    storage.values["h3-project:Film One"] = json.dumps(manifest)
    status, accepted = call(routes.approve, body={"name": "Film One"})
    assert status == 200 and accepted["state"]["approved"][0]["take"] == 1
    status, selected = call(routes.select_take, body={
        "name": "Film One", "index": 2, "take": 2,
    })
    assert status == 404 and selected["ok"] is False
    status, reopened = call(routes.reopen, body={"name": "Film One"})
    assert status == 200 and reopened["state"]["pending"]["take"] == 1
    manifest = json.loads(storage.values["h3-project:Film One"])
    manifest["pending"] = None
    manifest["approved"] = [manifest["takes"][0]]
    storage.values["h3-project:Film One"] = json.dumps(manifest)
    status, branched = call(routes.branch, body={
        "name": "Film One", "new_name": "Alternate", "index": 1,
        "take": 2,
    })
    assert status == 200
    assert branched["state"]["approved"][0]["take"] == 2
    assert branched["state"]["branched_from"] == {
        "project": "Film One", "index": 1, "take": 2,
    }


def test_frontend_uses_only_sandbox_entrypoints():
    source = (V2 / "web" / "h3_project_panel.js").read_text()
    assert 'from "/comfy/api/v2.js"' in source
    assert "comfy.backend.ownFetch" in source
    assert "comfy.ui.addSidebarTab" in source
    for forbidden in (
        "window.", "document.", "localStorage", "indexedDB",
        'from "../../scripts/', "api.fetchApi", "doc.addEventListener",
    ):
        assert forbidden not in source
    assert source.count('addEventListener("keydown"') == 2  # scoped inputs


def test_trim_executes_across_the_real_guest_boundary():
    package = _load_package()
    node = package.NODE_CLASS_MAPPINGS["H3ContextTrim"]

    async def run():
        refs = secure_sdk.InProcessRefResolver()
        image_value = torch.arange(
            8 * 3 * 4 * 3, dtype=torch.float32).reshape(8, 3, 4, 3)
        waveform = torch.arange(1600, dtype=torch.float32).reshape(1, 2, 800)
        images = secure_sdk.ImageRef._wrap(await refs.create("IMAGE", image_value))
        audio = secure_sdk.AudioRef._wrap(await refs.create("AUDIO", {
            "waveform": waveform,
            "sample_rate": 800,
        }))
        plan = secure_sdk.ExecutionPlan(
            prompt_id="h3-secure-trim",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={
                "images": images,
                "trim_frames": 2,
                "audio": audio,
                "fps": 20.0,
                "match_tail": True,
            },
            permissions=tuple(node.SDK_PERMISSIONS),
        )
        runtime = secure_sdk.Runtime(
            refs=refs,
            ctx=secure_sdk.InProcessCtxProvider().build(plan),
            ops=secure_sdk.InProcessOps(),
        )
        session = await GuestSession("h3-secure-trim").start()
        try:
            result = await session.execute(
                plan, runtime, capabilities=plan.permissions)
            return (
                await refs.resolve(result.result[0]),
                await refs.resolve(result.result[1]),
                session.last_guest_pid,
            )
        finally:
            await session.kill()

    images, audio, guest_pid = _run(run())
    assert guest_pid is not None
    assert torch.equal(images, torch.arange(
        8 * 3 * 4 * 3, dtype=torch.float32).reshape(8, 3, 4, 3)[2:])
    assert audio["sample_rate"] == 800
    assert audio["waveform"].shape[-1] == round(6 / 20 * 800)


def test_h3_nested_av_guides_cross_the_real_guest_boundary():
    from comfy.nested_tensor import NestedTensor as CoreNestedTensor

    package = _load_package()
    node = package.NODE_CLASS_MAPPINGS["H3Context"]

    async def run():
        refs = secure_sdk.InProcessRefResolver()
        conditioning_value = [[torch.zeros((1, 3, 4)), {}]]
        conditioning = secure_sdk.CondRef._wrap(
            await refs.create("CONDITIONING", conditioning_value))
        latent = secure_sdk.LatentRef._wrap(await refs.create("LATENT", {
            "samples": torch.zeros((1, 24, 8, 4, 4)),
        }))
        prior = secure_sdk.LatentRef._wrap(await refs.create("LATENT", {
            "samples": CoreNestedTensor([
                torch.ones((1, 24, 8, 4, 4)),
                torch.ones((1, 32, 2, 40)),
            ]),
        }))
        plan = secure_sdk.ExecutionPlan(
            prompt_id="h3-secure-context",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={
                "conditioning": conditioning,
                "latent": latent,
                "context_length": 22,
                "encode_mode": "video",
                "anchor_mode": "head",
                "crop": "disabled",
                "audio_context_length": 22,
                "audio_mode": "timeline",
                "video_source": "latent",
                "seed_head": False,
                "head_hold": 1.0,
                "hold_framing": False,
                "context_latent": prior,
            },
            permissions=tuple(node.SDK_PERMISSIONS),
        )
        runtime = secure_sdk.Runtime(
            refs=refs,
            ctx=secure_sdk.InProcessCtxProvider().build(plan),
            ops=secure_sdk.InProcessOps(),
        )
        session = await GuestSession("h3-secure-context").start()
        try:
            result = await session.execute(
                plan, runtime, capabilities=plan.permissions)
            return (
                await refs.resolve(result.result[0]),
                result.result[1],
                await refs.resolve(result.result[2]),
            )
        finally:
            await session.kill()

    conditioning, trim, latent = _run(run())
    assert trim == 9
    metadata = conditioning[0][1]
    assert metadata["minimax_frame_count"] == 26
    assert [item["resolved_frame_index"]
            for item in metadata["minimax_keyframes"]] == [0.0, 1.0, 5.0, -13.2]
    assert latent["samples"].shape == (1, 24, 8, 4, 4)


def test_project_save_records_managed_outputs_in_a_real_guest(monkeypatch, tmp_path):
    from comfy.nested_tensor import NestedTensor as CoreNestedTensor
    from comfy_secure_nodes import storage as secure_storage

    package = _load_package()
    node = package.NODE_CLASS_MAPPINGS["H3ProjectSave"]
    host_storage = secure_storage.PackStorage(tmp_path)
    monkeypatch.setattr(secure_storage, "_STORAGE", host_storage)

    async def run():
        refs = secure_sdk.InProcessRefResolver()
        latent = secure_sdk.LatentRef._wrap(await refs.create("LATENT", {
            "samples": CoreNestedTensor([
                torch.ones((1, 24, 2, 4, 6)),
                torch.ones((1, 32, 2, 4)),
            ]),
        }))
        images = secure_sdk.ImageRef._wrap(await refs.create(
            "IMAGE", torch.zeros((5, 64, 96, 3))))
        manifest = {
            "version": 2, "name": "Film", "width": 0, "height": 0,
            "approved": [], "pending": None, "takes": [],
            "auto_approve": False,
        }
        host_storage.set(
            "default", "development/h3-secure-save", "h3-project:Film",
            json.dumps(manifest),
        )
        output = Output()
        plan = secure_sdk.ExecutionPlan(
            prompt_id="h3-secure-save",
            node_id="1",
            node_type=node.__name__,
            tier="sandbox",
            node_module=node.__module__,
            inputs={
                "project": {"name": "Film"}, "latent": latent,
                "images": images, "fps": 24,
            },
            permissions=tuple(node.SDK_PERMISSIONS),
        )
        runtime = secure_sdk.Runtime(
            refs=refs,
            ctx=types.SimpleNamespace(output=output),
            ops=secure_sdk.InProcessOps(),
        )
        session = await GuestSession("h3-secure-save").start()
        try:
            result = await session.execute(
                plan, runtime, capabilities=plan.permissions)
            stored = host_storage.get(
                "default", "development/h3-secure-save", "h3-project:Film")
            return result.result[0], json.loads(stored), output
        finally:
            await session.kill()

    basename, manifest, output = _run(run())
    assert basename == "clip_001_take1"
    assert manifest["pending"]["basename"] == basename
    assert manifest["pending"]["meta"] == {
        "frames": 5, "fps": 24, "width": 96, "height": 64,
    }
    assert manifest["pending"]["video"] == (
        "h3_projects/Film/clips/clip_001_take1_00001_.mp4")
    assert output.state_calls[0][1] == "h3_projects/Film/clips/clip_001_take1"
    assert output.video_calls[0][1]["format"] == "mp4"
