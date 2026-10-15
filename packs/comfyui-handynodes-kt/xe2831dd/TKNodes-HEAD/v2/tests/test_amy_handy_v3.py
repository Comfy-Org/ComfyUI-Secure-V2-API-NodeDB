"""V3 behavior/outer/required guest evidence; dependency-stage scope explicit."""
import asyncio
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import pytest
import torch

V2 = Path(__file__).resolve().parents[1]
CORE = "/Users/ben/comfy/ComfyUI-secure-nodes"
BACKEND = "/Users/ben/comfy/ComfyUI_secure_nodes/backend"
HOST = "/Users/ben/comfy/ComfyUI/.venv"
sys.path[:0] = [CORE, BACKEND, str(Path(__file__).parent)]
os.environ.setdefault("COMFY_CORE_ROOT", CORE)
from comfy_api.latest import _sdk
from comfy_secure_nodes import packruntime
from comfy_secure_nodes.transport.host import GuestSession
from comfy_secure_nodes.transport import wire
import test_amy_handy_algorithms as controls

name = "amy_handy_v3_test"
spec = importlib.util.spec_from_file_location(name, V2 / "__init__.py", submodule_search_locations=[str(V2)])
pack = importlib.util.module_from_spec(spec)
sys.modules[name] = pack
spec.loader.exec_module(pack)
secure = sys.modules[name + "._secure_nodes"]
limits = sys.modules[name + "._limits"]
broker = sys.modules[name + "._broker"]

def expected(node_id, kwargs):
    with limits.scope():
        # Exact algorithm source control is covered separately. For approved
        # PCM backend adaptation the converted pure algorithm is the reference;
        # native current-loader RED and independent PCM oracle remain distinct.
        cls = secure.SOURCES[node_id]
        return getattr(cls(), cls.FUNCTION)(**controls.clone(kwargs))

@pytest.mark.parametrize("node_id", controls.IDS)
def test_registered_v3_values(node_id):
    kwargs = controls.inputs(node_id)
    expected_result = expected(node_id, kwargs)
    actual = asyncio.run(pack.NODE_CLASS_MAPPINGS[node_id].execute(**controls.clone(kwargs)))
    controls.equal(actual.result, expected_result)

def test_all29_export_count_and_per_node_permissions():
    assert len(pack.NODE_CLASS_MAPPINGS) == 29
    assert pack.WEB_DIRECTORY == "./web"
    for node_id, cls in pack.NODE_CLASS_MAPPINGS.items():
        assert cls.SDK_REFS is (node_id == 'TKPrintValueToLog')
        assert cls.SDK_PERMISSIONS == (("assets", "raw") if node_id in ("TKMultiImagePrompt", "TKMultiImageSelect")
                                      else () if node_id in secure.SCALARS else ("raw",))

def test_merge_returned_value_and_host_owned_input_unchanged():
    kwargs = controls.inputs("TKMergeAudioList")
    for audio in kwargs["audio_list"]:
        audio["waveform"].fill_(0.5)
    before = controls.clone(kwargs)
    reference = expected("TKMergeAudioList", kwargs)
    actual = asyncio.run(pack.NODE_CLASS_MAPPINGS["TKMergeAudioList"].execute(**kwargs))
    controls.equal(actual.result, reference)
    controls.equal(kwargs, before)

@pytest.mark.parametrize("node_id", ["TKSmartAudioChunker", "TKSmartVideoChunker"])
@pytest.mark.parametrize("duration,variation", [(0, 0), (1, 1), (1, 2), (-1, 0), (1000, 0)])
def test_chunk_nonprogressing_workload_refused_before_native(node_id, duration, variation, monkeypatch):
    kwargs = controls.inputs(node_id)
    kwargs.update(chunk_secs=duration, variation=variation)
    def forbidden(*args, **kwargs):
        raise AssertionError("native work must not start")
    monkeypatch.setattr(secure.SOURCES[node_id], secure.SOURCES[node_id].FUNCTION, forbidden)
    with pytest.raises(ValueError, match="workload"):
        asyncio.run(pack.NODE_CLASS_MAPPINGS[node_id].execute(**kwargs))

def test_projected_output_bytes_fail_before_allocation(monkeypatch):
    kwargs = controls.inputs("TKAudioToFPSMatcher")
    kwargs["video"] = torch.empty((1000, 1, 1, 3))
    kwargs["video_fps"] = 1
    def forbidden(*args, **kwargs):
        raise AssertionError("native padding must not start")
    monkeypatch.setattr(secure.SOURCES["TKAudioToFPSMatcher"], "match_audio_to_video", forbidden)
    with pytest.raises(ValueError, match="projected"):
        asyncio.run(pack.NODE_CLASS_MAPPINGS["TKAudioToFPSMatcher"].execute(**kwargs))

def test_silence_actual_cumulative_work_refusal_and_context_isolation():
    from pydub import AudioSegment
    segment = AudioSegment.silent(duration=1000, frame_rate=16000)
    with limits.scope():
        for _ in range(20):
            limits.detect_silence(segment, min_silence_len=100)
        with pytest.raises(ValueError, match="cumulative"):
            for _ in range(1000):
                limits.detect_silence(segment, min_silence_len=100)
    with limits.scope():
        assert limits.detect_silence(segment, min_silence_len=100) == [[0, 1000]]

@pytest.mark.parametrize("state", ["DataUnchanged", "DataChange"])
def test_source_speaker_order_full_carrier_manual_routing(state):
    rows = [{"start": i * .01, "end": i * .01 + .005, "speaker": i % 2} for i in range(20)]
    kwargs = dict(silence_threshold=1.0, fullaudio=controls.inputs("TKAudioUnwrap")["audio"],
                  duration=0.0, speaker_times=json.dumps(rows), track_state=state)
    for i in range(1, 15):
        kwargs["track_start_" + str(i)] = i / 10
        kwargs["track_end_" + str(i)] = i / 10 + .05
    result = asyncio.run(pack.NODE_CLASS_MAPPINGS["TKLocateSpeakersUsingSilenceBreaks"].execute(**kwargs))
    actual_rows = json.loads(result.result[0])
    assert len(actual_rows) == (20 if state == "DataUnchanged" else 14)
    if state == "DataUnchanged":
        assert actual_rows == rows
    else:
        assert [row["speaker"] for row in actual_rows] == [0] * 7 + [1] * 7
    assert result.ui["duration"] == [2.0]

@pytest.mark.parametrize("text", ["x", "[true]", '[{"start":0,"end":1,"speaker":2}]',
                                '[{"start":0,"end":NaN,"speaker":0}]', " " * 65537])
def test_corrupt_oversize_carrier_no_reset(text):
    with pytest.raises((ValueError, TypeError)):
        broker.carrier(text)

@pytest.mark.parametrize('registration',['owned','manifest'])
def test_required_guests_all26_outer_and_raw_denials(monkeypatch, registration):
    import execution
    from comfy_secure_nodes import packdb
    mappings = pack.NODE_CLASS_MAPPINGS if registration=='owned' else packdb.load_pack(
        V2.parent.parent,mount_name='custom_nodes.amy_handy_v3_manifest').node_mappings
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE", "required")
    async def run():
        prior = _sdk.providers.execution_backend
        real_resolve = packruntime.resolve_for_tenant
        pids = []
        def selected(spec, tenant):
            original = real_resolve(spec, tenant)
            assert original.python_executable == Path(sys.executable)
            return replace(original, spec=replace(original.spec, pack_root=V2))
        try:
            for repeat in range(2):
                with monkeypatch.context() as config:
                    config.setattr(packruntime, "resolve_for_tenant", selected)
                    guest = await GuestSession("amy-handy-algorithms-" + str(repeat),
                        module_source_root=V2, guest_runtime_root=HOST).start()
                assert guest.sandbox_kind == "seatbelt" and guest.python_executable == Path(sys.executable)
                pids.append(guest.pid)
                caps = []
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                        return await guest.execute(plan, runtime, capabilities=caps,
                            tenant="amy-handy-algorithms-" + str(repeat))
                _sdk.providers.register_execution_backend(Backend())
                try:
                    for node_id in controls.IDS:
                        cls = mappings[node_id]
                        caps[:] = cls.SDK_PERMISSIONS
                        kwargs = controls.inputs(node_id)
                        reference = expected(node_id, kwargs)
                        mapped = {key: [value] for key, value in kwargs.items()}
                        if node_id == "TKMergeAudioList":
                            mapped = {"audio_list": kwargs["audio_list"]}
                        result = await execution._async_map_node_over_list("handy-proof", node_id, cls, mapped, "execute")
                        actual = (await execution.resolve_map_node_over_list_results(result))[0]
                        controls.equal(actual.result, reference)
                        if "raw" in caps:
                            caps[:] = []
                            denied_inputs = mapped if node_id!='TKPrintValueToLog' else {
                                'value':[torch.ones(2,2)],'label':['tensor-denial']}
                            with pytest.raises(wire.WireError):
                                result = await execution._async_map_node_over_list("handy-deny", node_id, cls, denied_inputs, "execute")
                                await execution.resolve_map_node_over_list_results(result)
                            caps[:] = cls.SDK_PERMISSIONS
                    print(json.dumps({"pid": guest.pid, "registered_outer_positive_ids": controls.IDS,
                        "capabilities_per_node": True, "tier": "required-seatbelt+production-outer",
                        "qualification": "Unsealed staged PyDub profile, CPU finite fixtures; no whole29/route/frontend/cloud."}))
                finally:
                    await guest.kill()
        finally:
            _sdk.providers.execution_backend = prior
        assert len(set(pids)) == 2
    asyncio.run(run())

def test_required_guest_print_tensor_passthrough(monkeypatch):
    import execution
    monkeypatch.setenv("COMFY_SECURE_SANDBOX_MODE", "required")
    async def run():
        prior = _sdk.providers.execution_backend
        real_resolve = packruntime.resolve_for_tenant
        def selected(spec, tenant):
            original = real_resolve(spec, tenant)
            return replace(original, spec=replace(original.spec, pack_root=V2))
        with monkeypatch.context() as config:
            config.setattr(packruntime, "resolve_for_tenant", selected)
            guest = await GuestSession("amy-handy-print-tensor", module_source_root=V2,
                guest_runtime_root=HOST).start()
        cls = pack.NODE_CLASS_MAPPINGS["TKPrintValueToLog"]
        caps = list(cls.SDK_PERMISSIONS)
        class Backend:
            async def dispatch(self, plan, local_call, runtime):
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs, plan.input_types)
                return await guest.execute(plan, runtime, capabilities=caps,
                    tenant="amy-handy-print-tensor")
        _sdk.providers.register_execution_backend(Backend())
        try:
            value = torch.tensor([[1., 2.], [3., 4.]])
            result = await execution._async_map_node_over_list("print", "TKPrintValueToLog", cls,
                {"value": [value], "label": ["tensor"]}, "execute")
            actual = (await execution.resolve_map_node_over_list_results(result))[0]
            assert torch.equal(actual.result[0], value)
            assert actual.result[0] is value
            caps[:] = []
            with pytest.raises(wire.WireError, match="raw"):
                result = await execution._async_map_node_over_list("deny", "TKPrintValueToLog", cls,
                    {"value": [value], "label": ["tensor"]}, "execute")
                await execution.resolve_map_node_over_list_results(result)
            caps[:] = cls.SDK_PERMISSIONS
            # Unknown host values are opaque public handles, not raw objects.
            opaque = object()
            result = await execution._async_map_node_over_list("recover", "TKPrintValueToLog", cls,
                {"value": [opaque], "label": ["opaque"]}, "execute")
            actual = (await execution.resolve_map_node_over_list_results(result))[0]
            assert actual.result[0] is opaque
            from comfy.model_patcher import ModelPatcher
            import comfy.sd
            model = ModelPatcher(torch.nn.Linear(2, 2), torch.device('cpu'), torch.device('cpu'))
            # Exact canonical CLIP class is an opaque host-identity fixture;
            # no tokenizer/weights/method is invoked or inference claimed.
            clip = comfy.sd.CLIP.__new__(comfy.sd.CLIP)
            mixed = {'model': model, 'clip': clip, 'nested': (value, ['text', 2])}
            result = await execution._async_map_node_over_list('mixed', 'TKPrintValueToLog', cls,
                {'value':[mixed],'label':['mixed']}, 'execute')
            actual = (await execution.resolve_map_node_over_list_results(result))[0]
            returned=actual.result[0]
            assert returned['model'] is model and returned['clip'] is clip
            assert returned['nested'][0] is value
            assert returned['nested'][1]==['text',2]
        finally:
            _sdk.providers.execution_backend = prior
            await guest.kill()
    asyncio.run(run())

@pytest.mark.parametrize("value", [["x" * 40000, "y" * 40000],
    {"z" * 65537: 1}, [[0] * 1024 for _ in range(5)]])
def test_print_cumulative_work_refused_before_formatting(value, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("formatting must not begin")
    source=secure.SOURCES['TKPrintValueToLog']
    monkeypatch.setattr(source,source.FUNCTION,forbidden)
    with pytest.raises(ValueError, match="budget"):
        asyncio.run(pack.NODE_CLASS_MAPPINGS['TKPrintValueToLog'].execute(value=value,label='bounded'))
