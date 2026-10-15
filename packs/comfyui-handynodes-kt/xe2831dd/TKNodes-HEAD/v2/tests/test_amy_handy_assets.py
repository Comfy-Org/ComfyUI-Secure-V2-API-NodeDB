"""Source pixels/fingerprints, explicit static-empty admission, actual guest tiers."""
import asyncio
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import numpy as np
import pytest
import torch
from PIL import Image
import test_amy_handy_v3 as proof
from comfy_secure_nodes import packdb
from comfy_secure_nodes.packmanifest import encode_schema

IDS = ("TKMultiImagePrompt", "TKMultiImageSelect")

@pytest.fixture
def assets(tmp_path, monkeypatch):
    import folder_paths
    monkeypatch.setattr(folder_paths, "get_input_directory", lambda: str(tmp_path))
    monkeypatch.setattr(folder_paths, "get_annotated_filepath", lambda value: str(tmp_path / value))
    (tmp_path / "managed").mkdir()
    Image.fromarray(np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)).save(tmp_path / "one.png")
    Image.new("RGBA", (3, 2), (17, 33, 77, 55)).save(tmp_path / "managed/two.png")
    spec = importlib.util.spec_from_file_location("amy_handy_native_multi", proof.V2.parent / "MultiImagePrompt.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return tmp_path, native

def kwargs(node_id):
    result = {"image_1": "one.png", "image_2": "", "image_3": "managed/two.png", "image_4": "missing.png"}
    if node_id == "TKMultiImagePrompt":
        result.update(prompt_1="first\nline", prompt_2="unused", prompt_3="third", prompt_4="missing")
        result["image_prompt_list"] = [{"image": torch.ones(1, 1, 1, 3), "filename": "upstream", "prompt": "chain", "slot": 3}]
    return result

def runtime():
    plan = proof._sdk.ExecutionPlan(prompt_id="handy-assets", node_id="assets", node_type="assets", tier="sandbox", node_module=proof.pack.__name__, inputs={})
    return proof._sdk.Runtime(proof._sdk.InProcessRefResolver(), proof._sdk.InProcessCtxProvider().build(plan), proof._sdk.InProcessOps())

@pytest.mark.parametrize("node_id", IDS)
def test_exact_managed_pixels_slot_order_chain_and_fingerprint(assets, node_id):
    _, native = assets
    value = kwargs(node_id)
    source = getattr(native, node_id)
    reference = source().collect(**value)
    fingerprint = source.IS_CHANGED(**value)
    rt = runtime()
    async def run():
        with proof._sdk.bind_runtime(rt.refs, rt.ctx, rt.ops):
            result = await proof.pack.NODE_CLASS_MAPPINGS[node_id].execute(**value)
            proof.controls.equal(result.result, reference)
            assert await proof.pack.NODE_CLASS_MAPPINGS[node_id].fingerprint_inputs(**value) == fingerprint
            empty = await proof.pack.NODE_CLASS_MAPPINGS[node_id].execute(**{"image_1": ""})
            assert empty.result == ([],)
    asyncio.run(run())

@pytest.mark.parametrize("node_id", IDS)
def test_successor_schema_remote_blank_proxy_and_exact_slots(assets, node_id):
    from comfy_secure_nodes.packmanifest import decode_schema
    root, native = assets
    cls = proof.pack.NODE_CLASS_MAPPINGS[node_id]
    declared = encode_schema(cls.GET_SCHEMA())
    source = getattr(native, node_id)
    restored = decode_schema(declared)
    assert [item.id for item in restored.inputs] == [key for rows in source.INPUT_TYPES().values() for key in rows]
    proxy = packdb._proxy_class(proof.pack.__name__ + "._secure_nodes", proof.V2 / "_secure_nodes.py", {"class": cls.__name__, "schema": declared})
    for item in proxy.define_schema().inputs:
        if item.id.startswith("image_") and item.id != "image_prompt_list":
            assert item.default == "" and item.options[0] == ""
            assert "one.png" in item.options
            assert item.remote.static_options == [""]
    (root / "one.png").unlink()
    for item in proxy.define_schema().inputs:
        if item.id.startswith("image_") and item.id != "image_prompt_list":
            assert "one.png" not in item.options and item.default == ""

@pytest.mark.parametrize("value", ["../escape.png", "/absolute.png", "C:\\path.png", "https://example/image", "a\0b", "x" * 1025])
def test_label_refusal_precedes_broker(value):
    with pytest.raises(ValueError):
        proof.broker.logical_name(value)

@pytest.mark.parametrize('registration',['owned','manifest'])
def test_required_two_guests_registered_multi_speaker_breather_and_denials(assets, monkeypatch, registration):
    import execution
    _, native = assets
    mappings = proof.pack.NODE_CLASS_MAPPINGS if registration=='owned' else packdb.load_pack(
        proof.V2.parent.parent,mount_name='custom_nodes.amy_handy_assets_manifest').node_mappings
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE", "required")
    async def run():
        previous = proof._sdk.providers.execution_backend
        original = proof.packruntime.resolve_for_tenant
        pids = []
        def selected(spec, tenant):
            resolved = original(spec, tenant)
            return replace(resolved, spec=replace(resolved.spec, pack_root=proof.V2))
        try:
            for repeat in range(2):
                with monkeypatch.context() as config:
                    config.setattr(proof.packruntime, "resolve_for_tenant", selected)
                    guest = await proof.GuestSession("amy-handy-assets-" + str(repeat), module_source_root=proof.V2, guest_runtime_root=proof.HOST).start()
                pids.append(guest.pid)
                assert guest.sandbox_kind == "seatbelt"
                caps = []
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        plan.inputs = await proof._sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                        return await guest.execute(plan, runtime, capabilities=caps, tenant="amy-handy-assets-" + str(repeat))
                proof._sdk.providers.register_execution_backend(Backend())
                async def call(node_id, value, method="execute"):
                    result = await execution._async_map_node_over_list("handy-assets", node_id, mappings[node_id], {key: [item] for key, item in value.items()}, method)
                    return (await execution.resolve_map_node_over_list_results(result))[0]
                try:
                    for node_id in IDS:
                        value = kwargs(node_id)
                        caps[:] = ("assets", "raw")
                        actual = await call(node_id, value)
                        proof.controls.equal(actual.result, getattr(native, node_id)().collect(**value))
                        assert await call(node_id, value, "fingerprint_inputs") == getattr(native, node_id).IS_CHANGED(**value)
                        empty = await call(node_id, {"image_1": ""})
                        assert empty.result == ([],)
                        for denied in ((), ("assets",), ("raw",)):
                            caps[:] = denied
                            with pytest.raises(proof.wire.WireError):
                                await call(node_id, value)
                        caps[:] = ("assets", "raw")
                        proof.controls.equal((await call(node_id, value)).result, getattr(native, node_id)().collect(**value))
                    caps[:] = ("raw",)
                    value = proof.controls.inputs("TKSpeakerAudioTrackExtractor")
                    value["addBreathNoise"] = True
                    proof.controls.equal((await call("TKSpeakerAudioTrackExtractor", value)).result, proof.expected("TKSpeakerAudioTrackExtractor", value))
                    for state in ("DataUnchanged", "DataChange"):
                        value = dict(silence_threshold=1.0, fullaudio=proof.controls.inputs("TKAudioUnwrap")["audio"], duration=0.0, speaker_times=json.dumps([{"start": 0, "end": .5, "speaker": 0}]), track_state=state)
                        for index in range(1,15):
                            value["track_start_" + str(index)] = 0
                            value["track_end_" + str(index)] = .1 if index == 1 else 0
                        reference = await proof.pack.NODE_CLASS_MAPPINGS["TKLocateSpeakersUsingSilenceBreaks"].execute(**value)
                        actual = await call("TKLocateSpeakersUsingSilenceBreaks", value)
                        proof.controls.equal(actual.result, reference.result)
                        assert actual.ui == reference.ui
                    print(json.dumps({"pid": guest.pid, "positive_ids": [*IDS,"TKSpeakerAudioTrackExtractor","TKLocateSpeakersUsingSilenceBreaks"], "tier": "required-seatbelt+production-outer", "qualification": "Managed assets+raw pixel algorithms; immutable breather oracle adaptation; unsealed local stage, no route/cloud."}))
                finally:
                    await guest.kill()
        finally:
            proof._sdk.providers.execution_backend = previous
        assert len(set(pids)) == 2
    asyncio.run(run())

@pytest.mark.parametrize('change',['same','grow','truncate'])
def test_public_range_cap_edge_and_changed_asset_detection(assets, change):
    root,_=assets
    target=root/'range.bin'
    size=16*1024*1024
    target.write_bytes(b'x'*size)
    rt=runtime()
    original=rt.ctx.assets.read_range
    calls=[]
    async def ranged(ref,*,offset,length):
        calls.append((offset,length))
        if len(calls)==1 and change=='grow':
            with target.open('ab') as stream:
                stream.write(b'x')
        elif len(calls)==1 and change=='truncate':
            target.write_bytes(b'x')
        return await original(ref,offset=offset,length=length)
    rt.ctx.assets.read_range=ranged
    async def run():
        with proof._sdk.bind_runtime(rt.refs,rt.ctx,rt.ops):
            if change=='same':
                assert len(await proof.broker.managed_bytes('range.bin',size))==size
                assert calls==[(0,size),(size,1)]
            else:
                with pytest.raises(ValueError,match='changed'):
                    await proof.broker.managed_bytes('range.bin',size)
    asyncio.run(run())
